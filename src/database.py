"""
V3.1 Database Module - SQLite Operations with Graph Support

This module provides:
- SQLite database schema for V3.1 architecture
- Wallet tracking with tier system
- Funding relationship graph (SQLite-based, Neo4j-ready)
- Mother wallet discovery queries
- Confidence decay operations
- Trade and signal logging

Migration Path: SQLite → Neo4j when wallet count exceeds 5,000
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class Wallet:
    """Wallet entity with tracking data."""
    address: str
    tier: str
    first_seen: datetime
    total_pnl: float
    win_count: int
    loss_count: int
    last_win_date: Optional[datetime]
    confidence: float
    is_cex_funded: bool
    trust_score: float = 0.0


@dataclass
class FundingRelation:
    """Funding relationship between wallets."""
    funder_address: str
    funded_address: str
    amount: float
    timestamp: datetime
    tx_hash: str
    edge_confidence: float


@dataclass
class MotherWallet:
    """Mother wallet with cluster information."""
    address: str
    funded_winner_count: int
    child_wallets: List[str]
    last_win_date: Optional[datetime]
    confidence: float
    total_children_pnl: float


@dataclass
class Signal:
    """Trading signal entity."""
    id: int
    timestamp: datetime
    wallet: str
    token: str
    price: float
    amount_usd: float
    signal_type: str
    confidence: float
    simulation_passed: Optional[bool]
    simulation_tax: Optional[float]
    outcome: Optional[str]
    pnl: Optional[float]
    notes: Optional[str]


@dataclass
class Trade:
    """Executed trade entity."""
    id: int
    timestamp: datetime
    signal_id: Optional[int]
    token: str
    direction: str
    amount_usd: float
    entry_price: float
    exit_price: Optional[float]
    pnl: Optional[float]
    status: str
    wallet_used: str
    trade_number: int  # For first 50 tracking


class WalletGraphDB:
    """
    SQLite-based graph database for wallet provenance tracking.
    
    Handles up to ~5,000 wallets efficiently before Neo4j migration.
    Implements V3.1 schema with:
    - Trust decay (30-day half-life)
    - CEX filtering
    - Graph poisoning protection
    - Mother wallet discovery
    """
    
    def __init__(self, db_path: str = "data/wallet_graph.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        logger.info(f"Database initialized at {self.db_path}")
    
    def _init_schema(self):
        """Initialize V3.1 database schema."""
        cursor = self.conn.cursor()
        
        # =========================================================================
        # WALLETS TABLE
        # =========================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY,
                tier TEXT DEFAULT 'C_TIER',
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_pnl REAL DEFAULT 0,
                win_count INTEGER DEFAULT 0,
                loss_count INTEGER DEFAULT 0,
                last_win_date TIMESTAMP,
                confidence REAL DEFAULT 1.0,
                trust_score REAL DEFAULT 0.0,
                is_cex_funded BOOLEAN DEFAULT FALSE,
                cex_source TEXT,
                metadata TEXT  -- JSON for additional data
            )
        """)
        
        # =========================================================================
        # FUNDING TABLE - Wallet funding relationships
        # =========================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS funding (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                funder_address TEXT NOT NULL,
                funded_address TEXT NOT NULL,
                amount REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tx_hash TEXT,
                edge_confidence REAL DEFAULT 1.0,
                temporal_cluster_id TEXT,  -- For detecting coordinated funding
                FOREIGN KEY (funder_address) REFERENCES wallets(address),
                FOREIGN KEY (funded_address) REFERENCES wallets(address),
                UNIQUE(funder_address, funded_address, tx_hash)
            )
        """)
        
        # =========================================================================
        # SIGNALS TABLE - Trading signals with simulation results
        # =========================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                wallet TEXT,
                token TEXT NOT NULL,
                price REAL,
                amount_usd REAL,
                signal_type TEXT DEFAULT 'WHALE_BUY',
                confidence REAL DEFAULT 0.5,
                -- Simulation results
                simulation_passed BOOLEAN,
                simulation_tax REAL,
                simulation_reason TEXT,
                -- Outcome tracking
                price_1h REAL,
                price_24h REAL,
                outcome TEXT,  -- WIN, LOSS, NEUTRAL, PENDING
                pnl REAL,
                loss_magnitude TEXT,  -- RUG, MODEST, MARGINAL for weighting
                notes TEXT,
                FOREIGN KEY (wallet) REFERENCES wallets(address)
            )
        """)
        
        # =========================================================================
        # TRADES TABLE - Executed trades (for first 50 tracking)
        # =========================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                signal_id INTEGER,
                token TEXT NOT NULL,
                direction TEXT NOT NULL,  -- BUY, SELL
                amount_usd REAL NOT NULL,
                entry_price REAL,
                exit_price REAL,
                pnl REAL,
                status TEXT DEFAULT 'OPEN',  -- OPEN, CLOSED, CANCELLED
                wallet_used TEXT,
                trade_number INTEGER,  -- Sequential trade number for first 50
                was_graph_boosted BOOLEAN DEFAULT FALSE,
                entropy_applied BOOLEAN DEFAULT FALSE,
                notes TEXT,
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            )
        """)
        
        # =========================================================================
        # BUYS TABLE - Token buy records
        # =========================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS buys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                token_address TEXT NOT NULL,
                amount REAL,
                price REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pnl REAL,
                is_winner BOOLEAN,
                FOREIGN KEY (wallet_address) REFERENCES wallets(address)
            )
        """)
        
        # =========================================================================
        # KILL_SWITCH_EVENTS TABLE - Track kill switch triggers
        # =========================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kill_switch_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trigger_type TEXT NOT NULL,
                trigger_reason TEXT,
                mode TEXT,
                observation_end TIMESTAMP,
                resolved BOOLEAN DEFAULT FALSE,
                resolution_notes TEXT
            )
        """)
        
        # =========================================================================
        # SYSTEM_STATE TABLE - Track system state and metrics
        # =========================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # =========================================================================
        # INDEXES for performance
        # =========================================================================
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_tier ON wallets(tier)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_confidence ON wallets(confidence)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_funding_funder ON funding(funder_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_funding_funded ON funding(funded_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_funding_timestamp ON funding(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_token ON signals(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_wallet ON signals(wallet)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_outcome ON signals(outcome)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buys_wallet ON buys(wallet_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buys_token ON buys(token_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
        
        self.conn.commit()
    
    # =========================================================================
    # WALLET OPERATIONS
    # =========================================================================
    
    def add_wallet(self, address: str, tier: str = "C_TIER", 
                   is_cex_funded: bool = False, cex_source: str = None) -> bool:
        """Add or update a wallet."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO wallets (address, tier, is_cex_funded, cex_source)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    tier = CASE WHEN excluded.tier > wallets.tier THEN excluded.tier ELSE wallets.tier END,
                    is_cex_funded = excluded.is_cex_funded,
                    cex_source = excluded.cex_source
            """, (address, tier, is_cex_funded, cex_source))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding wallet {address}: {e}")
            return False
    
    def get_wallet(self, address: str) -> Optional[Wallet]:
        """Get wallet by address."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM wallets WHERE address = ?", (address,))
        row = cursor.fetchone()
        
        if row:
            return Wallet(
                address=row['address'],
                tier=row['tier'],
                first_seen=datetime.fromisoformat(row['first_seen']) if row['first_seen'] else datetime.utcnow(),
                total_pnl=row['total_pnl'] or 0,
                win_count=row['win_count'] or 0,
                loss_count=row['loss_count'] or 0,
                last_win_date=datetime.fromisoformat(row['last_win_date']) if row['last_win_date'] else None,
                confidence=row['confidence'] or 1.0,
                is_cex_funded=bool(row['is_cex_funded']),
                trust_score=row['trust_score'] or 0.0
            )
        return None
    
    def update_wallet_outcome(self, address: str, pnl: float) -> None:
        """
        Update wallet after trade outcome.
        Trust earned slowly, lost quickly (anti-poison principle).
        """
        cursor = self.conn.cursor()
        
        if pnl > 0:
            # Win: Boost confidence slowly (capped at 1.0)
            cursor.execute("""
                UPDATE wallets 
                SET confidence = MIN(confidence * 1.1, 1.0),
                    last_win_date = CURRENT_TIMESTAMP,
                    win_count = win_count + 1,
                    total_pnl = total_pnl + ?
                WHERE address = ?
            """, (pnl, address))
        else:
            # Loss: Reduce confidence quickly
            cursor.execute("""
                UPDATE wallets 
                SET confidence = confidence * 0.7,
                    loss_count = loss_count + 1,
                    total_pnl = total_pnl + ?
                WHERE address = ?
            """, (pnl, address))
        
        self.conn.commit()
        self._update_wallet_tier(address)
    
    def _update_wallet_tier(self, address: str) -> None:
        """Update wallet tier based on current stats."""
        wallet = self.get_wallet(address)
        if not wallet:
            return
        
        total_trades = wallet.win_count + wallet.loss_count
        if total_trades == 0:
            return
        
        win_rate = wallet.win_count / total_trades
        
        # Tier assignment logic
        new_tier = "C_TIER"
        if wallet.win_count >= 5 and win_rate >= 0.70 and wallet.total_pnl >= 5000 and wallet.confidence >= 0.8:
            new_tier = "S_TIER"
        elif wallet.win_count >= 3 and win_rate >= 0.60 and wallet.total_pnl >= 1000 and wallet.confidence >= 0.6:
            new_tier = "A_TIER"
        elif wallet.win_count >= 2 and win_rate >= 0.50 and wallet.total_pnl >= 100 and wallet.confidence >= 0.4:
            new_tier = "B_TIER"
        
        cursor = self.conn.cursor()
        cursor.execute("UPDATE wallets SET tier = ? WHERE address = ?", (new_tier, address))
        self.conn.commit()
    
    def mark_cex_funded(self, address: str, cex_source: str) -> None:
        """Mark wallet as CEX-funded."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE wallets SET is_cex_funded = TRUE, cex_source = ?
            WHERE address = ?
        """, (cex_source, address))
        self.conn.commit()
    
    # =========================================================================
    # FUNDING RELATIONSHIP OPERATIONS
    # =========================================================================
    
    def add_funding_relationship(self, funder: str, funded: str, 
                                  amount: float, timestamp: datetime = None,
                                  tx_hash: str = None) -> bool:
        """Add funding relationship between wallets."""
        # Ensure both wallets exist
        self.add_wallet(funder)
        self.add_wallet(funded)
        
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO funding (funder_address, funded_address, amount, timestamp, tx_hash)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
            """, (funder, funded, amount, timestamp or datetime.utcnow(), tx_hash))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding funding relationship: {e}")
            return False
    
    def get_wallet_funders(self, address: str, max_hops: int = 2) -> List[FundingRelation]:
        """Get funding sources for a wallet (up to max_hops)."""
        cursor = self.conn.cursor()
        
        funders = []
        current_addresses = [address]
        
        for hop in range(max_hops):
            if not current_addresses:
                break
            
            placeholders = ','.join(['?' for _ in current_addresses])
            cursor.execute(f"""
                SELECT * FROM funding 
                WHERE funded_address IN ({placeholders})
                ORDER BY timestamp DESC
            """, current_addresses)
            
            rows = cursor.fetchall()
            next_addresses = []
            
            for row in rows:
                funders.append(FundingRelation(
                    funder_address=row['funder_address'],
                    funded_address=row['funded_address'],
                    amount=row['amount'],
                    timestamp=datetime.fromisoformat(row['timestamp']) if row['timestamp'] else datetime.utcnow(),
                    tx_hash=row['tx_hash'] or '',
                    edge_confidence=row['edge_confidence']
                ))
                next_addresses.append(row['funder_address'])
            
            current_addresses = list(set(next_addresses))
        
        return funders
    
    # =========================================================================
    # MOTHER WALLET DISCOVERY (THE "GOD VIEW" QUERY)
    # =========================================================================
    
    def find_mother_wallets(self, min_funded_winners: int = 3) -> List[MotherWallet]:
        """
        Find wallets that funded multiple addresses who bought winning tokens.
        This is the core "Sybil Hunter" query.
        """
        cursor = self.conn.cursor()
        
        query = """
            SELECT 
                f.funder_address as mother,
                COUNT(DISTINCT f.funded_address) as funded_count,
                GROUP_CONCAT(DISTINCT f.funded_address) as children,
                MAX(w.last_win_date) as last_win,
                AVG(w.confidence) as avg_confidence,
                SUM(w.total_pnl) as total_children_pnl
            FROM funding f
            JOIN wallets w ON f.funded_address = w.address
            WHERE w.win_count > 0
              AND w.is_cex_funded = FALSE
              AND f.edge_confidence > 0.3
            GROUP BY f.funder_address
            HAVING funded_count >= ?
            ORDER BY funded_count DESC, avg_confidence DESC
        """
        
        cursor.execute(query, (min_funded_winners,))
        
        mothers = []
        for row in cursor.fetchall():
            mothers.append(MotherWallet(
                address=row['mother'],
                funded_winner_count=row['funded_count'],
                child_wallets=row['children'].split(',') if row['children'] else [],
                last_win_date=datetime.fromisoformat(row['last_win']) if row['last_win'] else None,
                confidence=row['avg_confidence'] or 1.0,
                total_children_pnl=row['total_children_pnl'] or 0
            ))
        
        logger.info(f"Found {len(mothers)} mother wallets with {min_funded_winners}+ winning children")
        return mothers
    
    def check_insider_signal(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """
        Check if wallet is connected to known insider cluster.
        Returns signal info if yes, None if no connection.
        """
        cursor = self.conn.cursor()
        
        # Check direct funding (1 hop)
        cursor.execute("""
            SELECT 
                f.funder_address,
                w.tier,
                w.win_count,
                w.confidence,
                w.total_pnl
            FROM funding f
            JOIN wallets w ON f.funder_address = w.address
            WHERE f.funded_address = ?
              AND w.tier IN ('S_TIER', 'A_TIER')
              AND w.confidence > 0.5
              AND w.is_cex_funded = FALSE
        """, (wallet_address,))
        
        result = cursor.fetchone()
        
        if result:
            signal_strength = "SCREAMING_BUY" if result['tier'] == "S_TIER" else "STRONG_BUY"
            return {
                "wallet": wallet_address,
                "mother_wallet": result['funder_address'],
                "mother_tier": result['tier'],
                "mother_wins": result['win_count'],
                "confidence": result['confidence'],
                "signal_strength": signal_strength,
                "hops": 1
            }
        
        # Check 2 hops
        cursor.execute("""
            SELECT 
                f2.funder_address,
                w.tier,
                w.win_count,
                w.confidence,
                w.total_pnl
            FROM funding f1
            JOIN funding f2 ON f1.funder_address = f2.funded_address
            JOIN wallets w ON f2.funder_address = w.address
            WHERE f1.funded_address = ?
              AND w.tier IN ('S_TIER', 'A_TIER')
              AND w.confidence > 0.5
              AND w.is_cex_funded = FALSE
        """, (wallet_address,))
        
        result = cursor.fetchone()
        
        if result:
            signal_strength = "STRONG_BUY" if result['tier'] == "S_TIER" else "MODERATE"
            return {
                "wallet": wallet_address,
                "mother_wallet": result['funder_address'],
                "mother_tier": result['tier'],
                "mother_wins": result['win_count'],
                "confidence": result['confidence'] * 0.8,  # Decay for 2 hops
                "signal_strength": signal_strength,
                "hops": 2
            }
        
        return None
    
    # =========================================================================
    # CONFIDENCE DECAY (30-day half-life)
    # =========================================================================
    
    def apply_confidence_decay(self) -> Dict[str, int]:
        """
        Apply 30-day half-life decay to all wallets.
        No wallet stays S-Tier indefinitely. Run daily.
        """
        cursor = self.conn.cursor()
        
        # Calculate decay based on days since last win
        cursor.execute("""
            UPDATE wallets
            SET confidence = MAX(confidence * POWER(0.5, 
                CAST((julianday('now') - julianday(COALESCE(last_win_date, first_seen))) / 30.0 AS REAL)
            ), 0.01)
            WHERE confidence > 0.01
        """)
        
        # Downgrade tiers based on decayed confidence
        cursor.execute("UPDATE wallets SET tier = 'A_TIER' WHERE tier = 'S_TIER' AND confidence < 0.7")
        cursor.execute("UPDATE wallets SET tier = 'B_TIER' WHERE tier = 'A_TIER' AND confidence < 0.5")
        cursor.execute("UPDATE wallets SET tier = 'C_TIER' WHERE tier = 'B_TIER' AND confidence < 0.3")
        
        self.conn.commit()
        
        # Get stats
        cursor.execute("SELECT COUNT(*) FROM wallets WHERE confidence < 0.1")
        low_confidence = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM wallets WHERE tier = 'S_TIER'")
        s_tier = cursor.fetchone()[0]
        
        logger.info(f"Decay applied: {low_confidence} low confidence wallets, {s_tier} S-tier remaining")
        
        return {"low_confidence_wallets": low_confidence, "s_tier_count": s_tier}
    
    def apply_edge_decay(self) -> int:
        """
        Apply decay to funding relationship edges.
        60-day half-life for edges.
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE funding
            SET edge_confidence = MAX(edge_confidence * POWER(0.5,
                CAST((julianday('now') - julianday(timestamp)) / 60.0 AS REAL)
            ), 0.01)
            WHERE edge_confidence > 0.01
        """)
        
        # Remove very weak edges
        cursor.execute("DELETE FROM funding WHERE edge_confidence < 0.05")
        deleted = cursor.rowcount
        
        self.conn.commit()
        
        logger.info(f"Edge decay applied, {deleted} weak edges removed")
        return deleted
    
    # =========================================================================
    # SIGNAL OPERATIONS
    # =========================================================================
    
    def log_signal(self, wallet: str, token: str, price: float, 
                   amount_usd: float, signal_type: str = "WHALE_BUY",
                   confidence: float = 0.5) -> int:
        """Log a new trading signal."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO signals (wallet, token, price, amount_usd, signal_type, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (wallet, token, price, amount_usd, signal_type, confidence))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_signal_simulation(self, signal_id: int, passed: bool, 
                                  tax: float, reason: str) -> None:
        """Update signal with simulation results."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE signals 
            SET simulation_passed = ?, simulation_tax = ?, simulation_reason = ?
            WHERE id = ?
        """, (passed, tax, reason, signal_id))
        self.conn.commit()
    
    def update_signal_outcome(self, signal_id: int, price_1h: float, 
                               price_24h: float, outcome: str, pnl: float,
                               loss_magnitude: str = None) -> None:
        """Update signal with outcome data."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE signals 
            SET price_1h = ?, price_24h = ?, outcome = ?, pnl = ?, loss_magnitude = ?
            WHERE id = ?
        """, (price_1h, price_24h, outcome, pnl, loss_magnitude, signal_id))
        self.conn.commit()
    
    def get_pending_signals(self, hours: int = 24) -> List[Signal]:
        """Get signals pending outcome tracking."""
        cursor = self.conn.cursor()
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        cursor.execute("""
            SELECT * FROM signals 
            WHERE outcome IS NULL 
              AND timestamp > ?
            ORDER BY timestamp DESC
        """, (cutoff.isoformat(),))
        
        signals = []
        for row in cursor.fetchall():
            signals.append(Signal(
                id=row['id'],
                timestamp=datetime.fromisoformat(row['timestamp']),
                wallet=row['wallet'],
                token=row['token'],
                price=row['price'],
                amount_usd=row['amount_usd'],
                signal_type=row['signal_type'],
                confidence=row['confidence'],
                simulation_passed=row['simulation_passed'],
                simulation_tax=row['simulation_tax'],
                outcome=row['outcome'],
                pnl=row['pnl'],
                notes=row['notes']
            ))
        
        return signals
    
    # =========================================================================
    # TRADE OPERATIONS
    # =========================================================================
    
    def log_trade(self, token: str, direction: str, amount_usd: float,
                  entry_price: float, wallet_used: str, signal_id: int = None,
                  was_graph_boosted: bool = False) -> int:
        """Log an executed trade."""
        cursor = self.conn.cursor()
        
        # Get current trade count for first 50 tracking
        cursor.execute("SELECT MAX(trade_number) FROM trades")
        result = cursor.fetchone()
        trade_number = (result[0] or 0) + 1
        
        cursor.execute("""
            INSERT INTO trades (signal_id, token, direction, amount_usd, 
                               entry_price, wallet_used, trade_number, 
                               was_graph_boosted, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
        """, (signal_id, token, direction, amount_usd, entry_price, 
              wallet_used, trade_number, was_graph_boosted))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def close_trade(self, trade_id: int, exit_price: float, pnl: float) -> None:
        """Close a trade with exit price and PnL."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE trades 
            SET exit_price = ?, pnl = ?, status = 'CLOSED'
            WHERE id = ?
        """, (exit_price, pnl, trade_id))
        self.conn.commit()
    
    def get_trade_count(self) -> int:
        """Get total trade count (for first 50 rules)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status != 'CANCELLED'")
        return cursor.fetchone()[0]
    
    def get_trades_in_timeframe(self, hours: int = 24) -> List[Trade]:
        """Get trades in the last N hours."""
        cursor = self.conn.cursor()
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        cursor.execute("""
            SELECT * FROM trades 
            WHERE timestamp > ?
            ORDER BY timestamp DESC
        """, (cutoff.isoformat(),))
        
        trades = []
        for row in cursor.fetchall():
            trades.append(Trade(
                id=row['id'],
                timestamp=datetime.fromisoformat(row['timestamp']),
                signal_id=row['signal_id'],
                token=row['token'],
                direction=row['direction'],
                amount_usd=row['amount_usd'],
                entry_price=row['entry_price'],
                exit_price=row['exit_price'],
                pnl=row['pnl'],
                status=row['status'],
                wallet_used=row['wallet_used'],
                trade_number=row['trade_number']
            ))
        
        return trades
    
    # =========================================================================
    # BUYS OPERATIONS
    # =========================================================================
    
    def add_buy(self, wallet: str, token: str, amount: float, 
                price: float, timestamp: datetime = None) -> int:
        """Record a token buy."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO buys (wallet_address, token_address, amount, price, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (wallet, token, amount, price, timestamp or datetime.utcnow()))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_early_buyers(self, token: str, limit: int = 50) -> List[Dict]:
        """Get early buyers of a token."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT b.*, w.tier, w.confidence, w.is_cex_funded
            FROM buys b
            LEFT JOIN wallets w ON b.wallet_address = w.address
            WHERE b.token_address = ?
            ORDER BY b.timestamp ASC
            LIMIT ?
        """, (token, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # =========================================================================
    # SYSTEM STATE
    # =========================================================================
    
    def set_state(self, key: str, value: Any) -> None:
        """Set a system state value."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO system_state (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET 
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, json.dumps(value) if not isinstance(value, str) else value))
        self.conn.commit()
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a system state value."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row['value'])
            except:
                return row['value']
        return default
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Wallet stats
        cursor.execute("SELECT COUNT(*) FROM wallets")
        stats['total_wallets'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT tier, COUNT(*) FROM wallets GROUP BY tier")
        stats['wallets_by_tier'] = dict(cursor.fetchall())
        
        # Signal stats
        cursor.execute("SELECT COUNT(*) FROM signals")
        stats['total_signals'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT outcome, COUNT(*) FROM signals WHERE outcome IS NOT NULL GROUP BY outcome")
        stats['signals_by_outcome'] = dict(cursor.fetchall())
        
        # Trade stats
        cursor.execute("SELECT COUNT(*) FROM trades")
        stats['total_trades'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(pnl) FROM trades WHERE pnl IS NOT NULL")
        stats['total_pnl'] = cursor.fetchone()[0] or 0
        
        # Mother wallet count
        cursor.execute("""
            SELECT COUNT(DISTINCT funder_address) FROM funding f
            JOIN wallets w ON f.funded_address = w.address
            WHERE w.win_count > 0
            GROUP BY funder_address HAVING COUNT(*) >= 3
        """)
        stats['mother_wallet_count'] = len(cursor.fetchall())
        
        return stats
    
    def should_migrate_to_neo4j(self) -> bool:
        """Check if wallet count exceeds SQLite threshold."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM wallets")
        count = cursor.fetchone()[0]
        return count > 5000
    
    def close(self) -> None:
        """Close database connection."""
        self.conn.close()


# Convenience function for quick database access
def get_db(db_path: str = "data/wallet_graph.db") -> WalletGraphDB:
    """Get database instance."""
    return WalletGraphDB(db_path)
