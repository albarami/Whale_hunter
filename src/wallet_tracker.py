"""
V3.1 Wallet Tracker Module

Handles:
- Insider decay half-life (30-day confidence halving)
- Tier assignment (S/A/B/C)
- CEX filtering
- Graph poisoning protection (trust earned slowly, lost quickly)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import yaml

from .database import WalletGraphDB, Wallet

logger = logging.getLogger(__name__)


@dataclass
class TierCriteria:
    """Criteria for wallet tier assignment."""
    min_wins: int
    min_win_rate: float
    min_net_pnl: float
    min_confidence: float


@dataclass 
class WalletSignal:
    """Signal derived from wallet activity."""
    wallet: str
    tier: str
    confidence: float
    signal_strength: str  # SCREAMING_BUY, STRONG_BUY, MODERATE, WEAK
    mother_wallet: Optional[str]
    hops: int
    is_cex_funded: bool
    decay_factor: float


class WalletTracker:
    """
    Wallet tracking and reputation management.
    
    Key principles:
    - Trust is earned slowly (multiple wins required)
    - Trust is lost quickly (single loss = significant penalty)
    - Confidence decays over time (30-day half-life)
    - CEX-funded wallets have reduced signal value
    """
    
    # Default tier criteria
    TIER_CRITERIA = {
        "S_TIER": TierCriteria(min_wins=5, min_win_rate=0.70, min_net_pnl=5000, min_confidence=0.8),
        "A_TIER": TierCriteria(min_wins=3, min_win_rate=0.60, min_net_pnl=1000, min_confidence=0.6),
        "B_TIER": TierCriteria(min_wins=2, min_win_rate=0.50, min_net_pnl=100, min_confidence=0.4),
        "C_TIER": TierCriteria(min_wins=0, min_win_rate=0.0, min_net_pnl=-float('inf'), min_confidence=0.0),
    }
    
    # Trust parameters
    MIN_WINS_FOR_TRUST = 3  # Need 3+ wins before considered trustworthy
    CONFIDENCE_HALF_LIFE_DAYS = 30  # 30-day half-life
    WIN_CONFIDENCE_BOOST = 1.1  # +10% on win
    LOSS_CONFIDENCE_PENALTY = 0.7  # -30% on loss
    
    # Poisoning protection
    MIN_CYCLES_FOR_MOTHER = 2  # Mother wallet needs 2+ funding cycles
    NET_PNL_WEIGHT = 0.7  # 70% weight on PnL, 30% on hit rate
    
    def __init__(self, db: WalletGraphDB, config_path: str = "config/settings.yaml"):
        self.db = db
        self.config = self._load_config(config_path)
        self._load_cex_blacklist()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Could not load config from {config_path}: {e}")
            return {}
    
    def _load_cex_blacklist(self) -> None:
        """Load CEX blacklist from config."""
        try:
            with open("config/cex_blacklist.yaml", 'r') as f:
                data = yaml.safe_load(f)
                self.cex_blacklist = {}
                for chain, exchanges in data.items():
                    if isinstance(exchanges, dict):
                        for exchange, wallets in exchanges.items():
                            if isinstance(wallets, list):
                                for wallet in wallets:
                                    self.cex_blacklist[wallet] = exchange
        except Exception as e:
            logger.warning(f"Could not load CEX blacklist: {e}")
            self.cex_blacklist = {}
    
    # =========================================================================
    # CEX FILTERING
    # =========================================================================
    
    def is_cex_wallet(self, address: str) -> Tuple[bool, Optional[str]]:
        """
        Check if address is a known CEX hot wallet.
        Returns (is_cex, exchange_name).
        """
        if address in self.cex_blacklist:
            return True, self.cex_blacklist[address]
        return False, None
    
    def check_cex_funding(self, wallet_address: str) -> Tuple[bool, Optional[str]]:
        """
        Check if wallet was funded by a CEX.
        Returns (is_cex_funded, cex_source).
        """
        funders = self.db.get_wallet_funders(wallet_address, max_hops=1)
        
        for funder in funders:
            is_cex, exchange = self.is_cex_wallet(funder.funder_address)
            if is_cex:
                # Mark wallet as CEX-funded
                self.db.mark_cex_funded(wallet_address, exchange)
                return True, exchange
        
        return False, None
    
    # =========================================================================
    # TIER ASSIGNMENT
    # =========================================================================
    
    def calculate_tier(self, wallet: Wallet) -> str:
        """
        Calculate wallet tier based on performance metrics.
        """
        total_trades = wallet.win_count + wallet.loss_count
        if total_trades == 0:
            return "C_TIER"
        
        win_rate = wallet.win_count / total_trades
        
        # Check each tier from highest to lowest
        for tier_name in ["S_TIER", "A_TIER", "B_TIER"]:
            criteria = self.TIER_CRITERIA[tier_name]
            if (wallet.win_count >= criteria.min_wins and
                win_rate >= criteria.min_win_rate and
                wallet.total_pnl >= criteria.min_net_pnl and
                wallet.confidence >= criteria.min_confidence):
                return tier_name
        
        return "C_TIER"
    
    def update_tier(self, wallet_address: str) -> str:
        """Update wallet tier and return new tier."""
        wallet = self.db.get_wallet(wallet_address)
        if not wallet:
            return "UNKNOWN"
        
        new_tier = self.calculate_tier(wallet)
        
        if new_tier != wallet.tier:
            logger.info(f"Wallet {wallet_address[:8]}... tier changed: {wallet.tier} -> {new_tier}")
        
        return new_tier
    
    # =========================================================================
    # TRUST SCORE CALCULATION (Anti-Poisoning)
    # =========================================================================
    
    def calculate_trust_score(self, wallet: Wallet) -> float:
        """
        Calculate trust score with anti-poison measures.
        Trust = (net_pnl_normalized * 0.7) + (win_rate * 0.3)
        Only applies after MIN_WINS_FOR_TRUST
        """
        # Not enough history - no trust yet
        if wallet.win_count < self.MIN_WINS_FOR_TRUST:
            return 0.0
        
        total_trades = wallet.win_count + wallet.loss_count
        if total_trades == 0:
            return 0.0
        
        # Win rate component
        win_rate = wallet.win_count / total_trades
        
        # Normalize PnL (cap at 10x for normalization)
        pnl_normalized = min(max(wallet.total_pnl / 1000, -1), 1)  # -1 to 1 range
        
        # Weighted trust score
        trust = (pnl_normalized * self.NET_PNL_WEIGHT) + (win_rate * (1 - self.NET_PNL_WEIGHT))
        
        # Apply base confidence decay
        trust *= wallet.confidence
        
        # CEX-funded penalty
        if wallet.is_cex_funded:
            trust *= 0.5  # 50% penalty
        
        return max(trust, 0)
    
    # =========================================================================
    # CONFIDENCE DECAY
    # =========================================================================
    
    def calculate_decay_factor(self, wallet: Wallet) -> float:
        """
        Calculate confidence decay factor based on time since last win.
        Uses 30-day half-life.
        """
        if not wallet.last_win_date:
            reference_date = wallet.first_seen
        else:
            reference_date = wallet.last_win_date
        
        days_since = (datetime.utcnow() - reference_date).total_seconds() / 86400
        decay_factor = 0.5 ** (days_since / self.CONFIDENCE_HALF_LIFE_DAYS)
        
        return decay_factor
    
    def apply_decay_to_wallet(self, wallet_address: str) -> float:
        """Apply decay to a specific wallet and return new confidence."""
        wallet = self.db.get_wallet(wallet_address)
        if not wallet:
            return 0.0
        
        decay_factor = self.calculate_decay_factor(wallet)
        new_confidence = wallet.confidence * decay_factor
        
        return new_confidence
    
    def run_daily_decay(self) -> Dict[str, int]:
        """
        Run daily decay process for all wallets.
        Returns stats about changes made.
        """
        logger.info("Starting daily confidence decay...")
        
        # Apply decay via database
        stats = self.db.apply_confidence_decay()
        
        # Also decay edges
        edges_removed = self.db.apply_edge_decay()
        stats['edges_removed'] = edges_removed
        
        logger.info(f"Daily decay complete: {stats}")
        return stats
    
    # =========================================================================
    # WALLET SIGNAL GENERATION
    # =========================================================================
    
    def get_wallet_signal(self, wallet_address: str) -> Optional[WalletSignal]:
        """
        Generate a trading signal based on wallet analysis.
        Returns None if wallet doesn't meet signal criteria.
        """
        wallet = self.db.get_wallet(wallet_address)
        if not wallet:
            return None
        
        # Check CEX funding
        is_cex_funded, cex_source = self.check_cex_funding(wallet_address)
        
        # Get insider connection if any
        insider_signal = self.db.check_insider_signal(wallet_address)
        
        # Calculate decay factor
        decay_factor = self.calculate_decay_factor(wallet)
        
        # Calculate trust score
        trust_score = self.calculate_trust_score(wallet)
        
        # Determine signal strength
        signal_strength = self._determine_signal_strength(
            wallet, insider_signal, is_cex_funded, trust_score
        )
        
        if signal_strength == "NONE":
            return None
        
        return WalletSignal(
            wallet=wallet_address,
            tier=wallet.tier,
            confidence=wallet.confidence * decay_factor,
            signal_strength=signal_strength,
            mother_wallet=insider_signal['mother_wallet'] if insider_signal else None,
            hops=insider_signal['hops'] if insider_signal else 0,
            is_cex_funded=is_cex_funded,
            decay_factor=decay_factor
        )
    
    def _determine_signal_strength(self, wallet: Wallet, insider_signal: Optional[Dict],
                                    is_cex_funded: bool, trust_score: float) -> str:
        """Determine signal strength based on all factors."""
        
        # CEX-funded with no insider connection = weak signal
        if is_cex_funded and not insider_signal:
            if trust_score > 0.5:
                return "WEAK"
            return "NONE"
        
        # S-Tier with insider connection = screaming buy
        if insider_signal and insider_signal.get('signal_strength') == "SCREAMING_BUY":
            return "SCREAMING_BUY"
        
        # A-Tier or strong insider connection
        if insider_signal and insider_signal.get('signal_strength') == "STRONG_BUY":
            return "STRONG_BUY"
        
        # Based on tier alone
        if wallet.tier == "S_TIER" and trust_score > 0.7:
            return "STRONG_BUY"
        elif wallet.tier == "A_TIER" and trust_score > 0.5:
            return "MODERATE"
        elif wallet.tier == "B_TIER" and trust_score > 0.3:
            return "WEAK"
        
        return "NONE"
    
    # =========================================================================
    # MOTHER WALLET OPERATIONS
    # =========================================================================
    
    def can_promote_to_mother(self, address: str) -> Tuple[bool, str]:
        """
        Check if wallet can be promoted to Mother status.
        Requires multiple funding cycles with winning children.
        """
        wallet = self.db.get_wallet(address)
        if not wallet:
            return False, "Wallet not found"
        
        # Get funding relationships
        mothers = self.db.find_mother_wallets(min_funded_winners=self.MIN_CYCLES_FOR_MOTHER)
        
        for mother in mothers:
            if mother.address == address:
                if mother.total_children_pnl <= 0:
                    return False, f"Children net PnL is ${mother.total_children_pnl:.2f}, must be positive"
                return True, f"Qualifies: {mother.funded_winner_count} winning children, ${mother.total_children_pnl:.2f} children PnL"
        
        return False, f"Not enough winning children (need {self.MIN_CYCLES_FOR_MOTHER}+)"
    
    def get_black_book(self, min_winners: int = 3) -> List[Dict[str, Any]]:
        """
        Generate the "Black Book" - list of top mother wallets to monitor.
        """
        mothers = self.db.find_mother_wallets(min_funded_winners=min_winners)
        
        black_book = []
        for mother in mothers:
            trust_score = mother.confidence * (1.0 if mother.total_children_pnl > 0 else 0.5)
            
            black_book.append({
                "address": mother.address,
                "funded_winner_count": mother.funded_winner_count,
                "child_wallets": mother.child_wallets,
                "last_win_date": mother.last_win_date.isoformat() if mother.last_win_date else None,
                "confidence": mother.confidence,
                "total_children_pnl": mother.total_children_pnl,
                "trust_score": trust_score,
                "rank": len(black_book) + 1
            })
        
        # Sort by trust score
        black_book.sort(key=lambda x: x['trust_score'], reverse=True)
        
        # Update ranks
        for i, entry in enumerate(black_book):
            entry['rank'] = i + 1
        
        return black_book
    
    # =========================================================================
    # OUTCOME RECORDING
    # =========================================================================
    
    def record_trade_outcome(self, wallet_address: str, pnl: float) -> Dict[str, Any]:
        """
        Record trade outcome and update wallet stats.
        Returns summary of changes made.
        """
        wallet = self.db.get_wallet(wallet_address)
        if not wallet:
            self.db.add_wallet(wallet_address)
            wallet = self.db.get_wallet(wallet_address)
        
        old_tier = wallet.tier
        old_confidence = wallet.confidence
        
        # Update wallet in database
        self.db.update_wallet_outcome(wallet_address, pnl)
        
        # Recalculate tier
        new_tier = self.update_tier(wallet_address)
        
        # Get updated wallet
        updated_wallet = self.db.get_wallet(wallet_address)
        
        return {
            "wallet": wallet_address,
            "pnl": pnl,
            "outcome": "WIN" if pnl > 0 else "LOSS",
            "old_tier": old_tier,
            "new_tier": new_tier,
            "tier_changed": old_tier != new_tier,
            "old_confidence": old_confidence,
            "new_confidence": updated_wallet.confidence,
            "confidence_change": updated_wallet.confidence - old_confidence
        }
    
    # =========================================================================
    # TEMPORAL CLUSTERING DETECTION
    # =========================================================================
    
    def detect_temporal_clustering(self, wallets: List[str], 
                                   time_window_seconds: int = 30) -> List[List[str]]:
        """
        Detect wallets that were funded in temporal clusters.
        Returns list of clustered wallet groups.
        """
        from collections import defaultdict
        
        # Group wallets by funding timestamp (within window)
        funding_times = defaultdict(list)
        
        for wallet in wallets:
            funders = self.db.get_wallet_funders(wallet, max_hops=1)
            for funder in funders:
                # Round to window
                window_key = int(funder.timestamp.timestamp() / time_window_seconds)
                funding_times[window_key].append({
                    "wallet": wallet,
                    "funder": funder.funder_address,
                    "amount": funder.amount,
                    "timestamp": funder.timestamp
                })
        
        # Find clusters of 5+ wallets
        clusters = []
        for window_key, entries in funding_times.items():
            if len(entries) >= 5:
                # Check if from same funder or CEX
                by_funder = defaultdict(list)
                for entry in entries:
                    by_funder[entry['funder']].append(entry['wallet'])
                
                for funder, cluster_wallets in by_funder.items():
                    if len(cluster_wallets) >= 5:
                        clusters.append(cluster_wallets)
                        logger.warning(
                            f"Temporal cluster detected: {len(cluster_wallets)} wallets "
                            f"funded by {funder[:8]}... in {time_window_seconds}s window"
                        )
        
        return clusters
