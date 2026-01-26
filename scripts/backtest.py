#!/usr/bin/env python3
"""
V3.1 Backtest Script - Historical Signal Replay

This script:
1. Loads historical signals from database or CSV
2. Replays them through the current strategy
3. Compares "would have traded" vs actual outcomes
4. Validates strategy before going live

Usage:
    python scripts/backtest.py [--days DAYS] [--strategy STRATEGY]
    
    --days: Number of days to backtest (default: 90)
    --strategy: Strategy version to test (v2, v25, v3)
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import csv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import WalletGraphDB, Signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BacktestSignal:
    """Historical signal for replay."""
    id: int
    timestamp: datetime
    wallet: str
    token: str
    price: float
    confidence: float
    simulation_passed: Optional[bool]
    outcome: str
    pnl: float


@dataclass
class BacktestResult:
    """Results of backtesting a strategy."""
    total_signals: int
    would_have_traded: int
    simulated_wins: int
    simulated_losses: int
    simulated_win_rate: float
    simulated_pnl: float
    actual_win_rate: float
    false_positive_rate: float
    false_negative_rate: float
    edge_vs_actual: float


class BacktestFramework:
    """
    Historical simulation framework.
    Replay past signals through current strategy and compare outcomes.
    """
    
    # Default parameters
    DEFAULT_WIN_GAIN = 0.50   # Assume 50% gain on winners
    DEFAULT_LOSS = -0.30      # Assume 30% loss on losers (with stops)
    DEFAULT_POSITION = 25.0   # Default position size for PnL calc
    
    def __init__(self, db: WalletGraphDB):
        self.db = db
        self.signals: List[BacktestSignal] = []
    
    def load_signals_from_db(self, start_date: datetime, end_date: datetime):
        """Load historical signals from database."""
        cursor = self.db.conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, wallet, token, price, confidence,
                   simulation_passed, outcome, pnl
            FROM signals
            WHERE timestamp BETWEEN ? AND ?
              AND outcome IS NOT NULL
            ORDER BY timestamp
        """, (start_date.isoformat(), end_date.isoformat()))
        
        self.signals = []
        for row in cursor.fetchall():
            self.signals.append(BacktestSignal(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                wallet=row[2] or "UNKNOWN",
                token=row[3],
                price=row[4] or 0,
                confidence=row[5] or 0.5,
                simulation_passed=row[6],
                outcome=row[7],
                pnl=row[8] or 0
            ))
        
        logger.info(f"Loaded {len(self.signals)} signals for backtest")
    
    def load_signals_from_csv(self, filepath: str, start_date: datetime, end_date: datetime):
        """Load historical signals from CSV file."""
        self.signals = []
        
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    timestamp = datetime.fromisoformat(row['timestamp'])
                    
                    if start_date <= timestamp <= end_date:
                        self.signals.append(BacktestSignal(
                            id=int(row.get('id', 0)),
                            timestamp=timestamp,
                            wallet=row.get('wallet', 'UNKNOWN'),
                            token=row['token'],
                            price=float(row.get('price', 0)),
                            confidence=float(row.get('confidence', 0.5)),
                            simulation_passed=row.get('simulation_passed') == 'True',
                            outcome=row.get('outcome', 'UNKNOWN'),
                            pnl=float(row.get('pnl', 0))
                        ))
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error parsing row: {e}")
        
        logger.info(f"Loaded {len(self.signals)} signals from CSV")
    
    def run_backtest(self, strategy_version: str = "v25",
                      min_confidence: float = 0.6) -> BacktestResult:
        """
        Run backtest with specified strategy.
        
        Args:
            strategy_version: v2, v25, or v3
            min_confidence: Minimum confidence to trade
        """
        logger.info(f"Running backtest with strategy={strategy_version}, min_conf={min_confidence}")
        
        results = {
            "total": 0,
            "would_trade": 0,
            "would_win": 0,
            "would_lose": 0,
            "actual_wins": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "simulated_pnl": 0.0
        }
        
        for signal in self.signals:
            results["total"] += 1
            
            # Determine if we would trade
            would_trade = self._evaluate_signal(signal, strategy_version, min_confidence)
            actually_won = signal.outcome == "WIN"
            
            if would_trade:
                results["would_trade"] += 1
                
                if actually_won:
                    results["would_win"] += 1
                    gain = self.DEFAULT_POSITION * self.DEFAULT_WIN_GAIN
                    results["simulated_pnl"] += gain
                else:
                    results["would_lose"] += 1
                    results["false_positives"] += 1
                    loss = self.DEFAULT_POSITION * self.DEFAULT_LOSS
                    results["simulated_pnl"] += loss
            else:
                if actually_won:
                    results["false_negatives"] += 1
            
            if actually_won:
                results["actual_wins"] += 1
        
        # Calculate metrics
        would_trade = max(results["would_trade"], 1)
        total = max(results["total"], 1)
        non_traded = total - would_trade
        
        return BacktestResult(
            total_signals=results["total"],
            would_have_traded=results["would_trade"],
            simulated_wins=results["would_win"],
            simulated_losses=results["would_lose"],
            simulated_win_rate=results["would_win"] / would_trade,
            simulated_pnl=results["simulated_pnl"],
            actual_win_rate=results["actual_wins"] / total,
            false_positive_rate=results["false_positives"] / would_trade,
            false_negative_rate=results["false_negatives"] / non_traded if non_traded > 0 else 0,
            edge_vs_actual=(results["would_win"] / would_trade) - (results["actual_wins"] / total)
        )
    
    def _evaluate_signal(self, signal: BacktestSignal, 
                         strategy: str, min_confidence: float) -> bool:
        """
        Evaluate if we would have traded this signal.
        """
        # V2.0: Basic confidence threshold
        if strategy == "v2":
            return signal.confidence >= min_confidence
        
        # V2.5: Confidence + simulation
        elif strategy == "v25":
            if signal.confidence < min_confidence:
                return False
            if signal.simulation_passed is False:
                return False
            return True
        
        # V3.0: Full evaluation (would need graph data)
        elif strategy == "v3":
            if signal.confidence < min_confidence:
                return False
            if signal.simulation_passed is False:
                return False
            # Would also check graph signals here
            return True
        
        return False
    
    def validate_for_live(self, result: BacktestResult) -> Tuple[bool, List[str]]:
        """
        Check if backtest results meet live trading requirements.
        """
        issues = []
        
        if result.simulated_win_rate < 0.55:
            issues.append(f"Win rate {result.simulated_win_rate:.1%} < required 55%")
        
        if result.simulated_pnl < 0:
            issues.append(f"Simulated PnL negative: ${result.simulated_pnl:.2f}")
        
        if result.false_positive_rate > 0.30:
            issues.append(f"False positive rate {result.false_positive_rate:.1%} > 30% threshold")
        
        if result.would_have_traded < 30:
            issues.append(f"Sample size too small: {result.would_have_traded} trades")
        
        passed = len(issues) == 0
        return passed, issues


def print_backtest_results(result: BacktestResult, passed: bool, issues: List[str]):
    """Print formatted backtest results."""
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)
    
    print(f"""
Signal Analysis:
  Total signals:      {result.total_signals}
  Would have traded:  {result.would_have_traded}
  Simulated wins:     {result.simulated_wins}
  Simulated losses:   {result.simulated_losses}

Performance Metrics:
  Simulated win rate: {result.simulated_win_rate:.1%}
  Actual win rate:    {result.actual_win_rate:.1%}
  Edge vs random:     {result.edge_vs_actual:+.1%}
  Simulated PnL:      ${result.simulated_pnl:.2f}

Error Rates:
  False positive:     {result.false_positive_rate:.1%}
  False negative:     {result.false_negative_rate:.1%}
""")
    
    print("-"*60)
    if passed:
        print("✓ BACKTEST PASSED - Strategy validated for live trading")
    else:
        print("✗ BACKTEST FAILED - Issues found:")
        for issue in issues:
            print(f"  - {issue}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description="Backtest trading strategies")
    parser.add_argument("--days", type=int, default=90, help="Days to backtest")
    parser.add_argument("--strategy", choices=["v2", "v25", "v3"], default="v25",
                        help="Strategy version")
    parser.add_argument("--min-confidence", type=float, default=0.6,
                        help="Minimum confidence threshold")
    parser.add_argument("--csv", help="CSV file to load signals from")
    parser.add_argument("--db", default="data/wallet_graph.db", help="Database path")
    args = parser.parse_args()
    
    # Initialize
    db = WalletGraphDB(args.db)
    backtester = BacktestFramework(db)
    
    # Date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=args.days)
    
    try:
        # Load signals
        if args.csv:
            backtester.load_signals_from_csv(args.csv, start_date, end_date)
        else:
            backtester.load_signals_from_db(start_date, end_date)
        
        if not backtester.signals:
            print("\n⚠ No signals found for backtest.")
            print("  Log some signals using 'python scripts/phase0_logger.py'")
            print("  and update their outcomes before running backtest.")
            return
        
        # Run backtest
        result = backtester.run_backtest(
            strategy_version=args.strategy,
            min_confidence=args.min_confidence
        )
        
        # Validate
        passed, issues = backtester.validate_for_live(result)
        
        # Print results
        print_backtest_results(result, passed, issues)
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
