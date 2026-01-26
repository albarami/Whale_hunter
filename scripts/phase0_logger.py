#!/usr/bin/env python3
"""
V3.1 Phase 0 Logger - Manual Signal Logging

This script provides an interactive interface for logging whale signals
during the paper trading phase. All signals are stored for later analysis
and backtesting.

Usage:
    python scripts/phase0_logger.py

Commands:
    - Paste token address: Log a new signal
    - 'stats': Show current statistics
    - 'recent': Show recent signals
    - 'export': Export data to CSV
    - 'update': Update signal outcomes
    - 'quit': Exit
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
import csv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv("config/.env")

from src.database import WalletGraphDB, Signal
from src.api_clients import BirdEyeClient, HeliusClient

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase0Logger:
    """
    Interactive signal logger for Phase 0 paper trading.
    """
    
    def __init__(self, db_path: str = "data/wallet_graph.db"):
        self.db = WalletGraphDB(db_path)
        self.birdeye = BirdEyeClient()
        self.helius = HeliusClient()
        self._session_start = datetime.utcnow()
        self._signals_logged = 0
    
    async def start(self):
        """Initialize API clients."""
        await self.birdeye.start()
        await self.helius.start()
    
    async def stop(self):
        """Clean up."""
        await self.birdeye.stop()
        await self.helius.stop()
        self.db.close()
    
    async def log_signal(self, token: str, wallet: str = None,
                         amount_usd: float = 0.0, latency: float = 5.0,
                         notes: str = None) -> int:
        """
        Log a new whale signal.
        
        Returns signal ID.
        """
        # Fetch current price
        price = await self.birdeye.get_token_price(token)
        if price is None:
            price = 0.0
            print("  ⚠ Could not fetch price")
        
        # Estimate confidence based on available info
        confidence = 0.5  # Base confidence
        
        # Log to database
        signal_id = self.db.log_signal(
            wallet=wallet or "UNKNOWN",
            token=token,
            price=price,
            amount_usd=amount_usd,
            signal_type="MANUAL_LOG",
            confidence=confidence
        )
        
        self._signals_logged += 1
        
        return signal_id
    
    async def update_signal_prices(self, signal_id: int) -> None:
        """
        Update signal with 1h and 24h prices.
        """
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT token, price, timestamp FROM signals WHERE id = ?", (signal_id,))
        row = cursor.fetchone()
        
        if not row:
            print(f"Signal {signal_id} not found")
            return
        
        token, entry_price, timestamp = row
        
        # Get current price
        current_price = await self.birdeye.get_token_price(token)
        
        if current_price is None:
            print("Could not fetch current price")
            return
        
        # Calculate outcome
        if entry_price > 0:
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            
            if pnl_pct > 10:
                outcome = "WIN"
            elif pnl_pct < -10:
                outcome = "LOSS"
            else:
                outcome = "NEUTRAL"
        else:
            pnl_pct = 0
            outcome = "UNKNOWN"
        
        # Determine loss magnitude
        loss_magnitude = None
        if outcome == "LOSS":
            if pnl_pct <= -90:
                loss_magnitude = "RUG"
            elif pnl_pct <= -30:
                loss_magnitude = "MODEST"
            else:
                loss_magnitude = "MARGINAL"
        
        # Update in database
        cursor.execute("""
            UPDATE signals 
            SET price_24h = ?, outcome = ?, pnl = ?, loss_magnitude = ?
            WHERE id = ?
        """, (current_price, outcome, pnl_pct, loss_magnitude, signal_id))
        self.db.conn.commit()
        
        print(f"\n  Updated signal {signal_id}:")
        print(f"    Entry: ${entry_price:.8f}")
        print(f"    Current: ${current_price:.8f}")
        print(f"    PnL: {pnl_pct:+.1f}%")
        print(f"    Outcome: {outcome}")
        if loss_magnitude:
            print(f"    Loss Type: {loss_magnitude}")
    
    def get_stats(self) -> dict:
        """Get logging statistics."""
        cursor = self.db.conn.cursor()
        
        # Total signals
        cursor.execute("SELECT COUNT(*) FROM signals")
        total = cursor.fetchone()[0]
        
        # By outcome
        cursor.execute("""
            SELECT outcome, COUNT(*) 
            FROM signals 
            WHERE outcome IS NOT NULL 
            GROUP BY outcome
        """)
        outcomes = dict(cursor.fetchall())
        
        # Pending
        cursor.execute("SELECT COUNT(*) FROM signals WHERE outcome IS NULL")
        pending = cursor.fetchone()[0]
        
        # Today's signals
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT COUNT(*) FROM signals 
            WHERE date(timestamp) = ?
        """, (today,))
        today_count = cursor.fetchone()[0]
        
        # Calculate win rate
        wins = outcomes.get("WIN", 0)
        losses = outcomes.get("LOSS", 0)
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        
        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "neutral": outcomes.get("NEUTRAL", 0),
            "pending": pending,
            "today": today_count,
            "win_rate": win_rate,
            "session_logged": self._signals_logged
        }
    
    def get_recent_signals(self, limit: int = 10) -> List[dict]:
        """Get recent signals."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, token, price, outcome, pnl
            FROM signals
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        signals = []
        for row in cursor.fetchall():
            signals.append({
                "id": row[0],
                "timestamp": row[1],
                "token": row[2],
                "price": row[3],
                "outcome": row[4],
                "pnl": row[5]
            })
        
        return signals
    
    def export_to_csv(self, filepath: str = "data/signals_export.csv") -> str:
        """Export all signals to CSV."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, wallet, token, price, amount_usd,
                   confidence, simulation_passed, price_1h, price_24h,
                   outcome, pnl, loss_magnitude, notes
            FROM signals
            ORDER BY timestamp DESC
        """)
        
        rows = cursor.fetchall()
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'id', 'timestamp', 'wallet', 'token', 'price', 'amount_usd',
                'confidence', 'simulation_passed', 'price_1h', 'price_24h',
                'outcome', 'pnl', 'loss_magnitude', 'notes'
            ])
            writer.writerows(rows)
        
        return filepath


async def main():
    logger = Phase0Logger()
    await logger.start()
    
    print("\n" + "="*60)
    print("PHASE 0 SIGNAL LOGGER - V3.1")
    print("="*60)
    print("\nCommands:")
    print("  - Paste token address to log a signal")
    print("  - 'stats' - Show statistics")
    print("  - 'recent' - Show recent signals")
    print("  - 'update <id>' - Update signal outcome")
    print("  - 'export' - Export to CSV")
    print("  - 'quit' - Exit\n")
    
    try:
        while True:
            user_input = input("\n> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                break
            
            elif user_input.lower() == 'stats':
                stats = logger.get_stats()
                print(f"""
───────────────────────────
STATISTICS
───────────────────────────
Total signals:    {stats['total']}
Today's signals:  {stats['today']}
Session logged:   {stats['session_logged']}

Wins:             {stats['wins']}
Losses:           {stats['losses']}
Neutral:          {stats['neutral']}
Pending:          {stats['pending']}

Win Rate:         {stats['win_rate']:.1%}
""")
            
            elif user_input.lower() == 'recent':
                signals = logger.get_recent_signals(10)
                print("\nRECENT SIGNALS:")
                print("-" * 70)
                for s in signals:
                    outcome = s['outcome'] or 'PENDING'
                    pnl = f"{s['pnl']:+.1f}%" if s['pnl'] else '-'
                    print(f"  [{s['id']:4d}] {s['timestamp'][:16]} | {s['token'][:12]}... | {outcome:8} | {pnl}")
            
            elif user_input.lower().startswith('update '):
                try:
                    signal_id = int(user_input.split()[1])
                    await logger.update_signal_prices(signal_id)
                except (ValueError, IndexError):
                    print("Usage: update <signal_id>")
            
            elif user_input.lower() == 'export':
                filepath = logger.export_to_csv()
                print(f"\n✓ Exported to {filepath}")
            
            elif len(user_input) > 30:  # Looks like token address
                token = user_input
                
                # Get optional details
                wallet = input("  Wallet (Enter to skip): ").strip() or None
                amount_str = input("  USD amount (Enter to skip): ").strip()
                amount = float(amount_str) if amount_str else 0.0
                notes = input("  Notes (Enter to skip): ").strip() or None
                
                print("\n  Fetching price...")
                signal_id = await logger.log_signal(
                    token=token,
                    wallet=wallet,
                    amount_usd=amount,
                    notes=notes
                )
                
                print(f"\n  ✓ LOGGED: Signal #{signal_id}")
                print(f"    Token: {token[:20]}...")
                if wallet:
                    print(f"    Wallet: {wallet[:20]}...")
            
            else:
                print("Unknown command. Type 'quit' to exit.")
    
    finally:
        await logger.stop()
        print("\nGoodbye!")


if __name__ == "__main__":
    asyncio.run(main())
