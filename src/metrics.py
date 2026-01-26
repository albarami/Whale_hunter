"""
V3.1 Metrics Module

Handles:
- False positive tracking
- False positive cost tracking
- Simulator accuracy by loss magnitude
- Win rate tracking
- ROI calculations
- Performance reporting
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import json

from .database import WalletGraphDB

logger = logging.getLogger(__name__)


@dataclass
class TradeOutcome:
    """Record of a trade outcome."""
    trade_id: int
    token: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    win: bool
    timestamp: datetime
    was_graph_boosted: bool
    simulation_passed: bool
    loss_magnitude: Optional[str] = None  # RUG, MODEST, MARGINAL


@dataclass
class FalsePositiveMetrics:
    """Metrics for false positive tracking."""
    # Total counts
    total_signals: int = 0
    executed_signals: int = 0
    
    # Outcome tracking
    wins: int = 0
    losses: int = 0
    
    # False positive tracking
    false_positives: int = 0  # Executed but lost
    false_negatives: int = 0  # Rejected but would have won
    
    # Loss magnitude breakdown
    rug_losses: int = 0
    modest_losses: int = 0
    marginal_losses: int = 0
    
    # Cost tracking (USD)
    total_loss_usd: float = 0.0
    rug_loss_usd: float = 0.0
    modest_loss_usd: float = 0.0
    marginal_loss_usd: float = 0.0
    
    # Gain tracking
    total_gain_usd: float = 0.0

    @property
    def win_rate(self) -> float:
        """Overall win rate."""
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0.0
    
    @property
    def false_positive_rate(self) -> float:
        """Rate of false positives (traded but lost)."""
        if self.executed_signals == 0:
            return 0.0
        return self.false_positives / self.executed_signals
    
    @property
    def net_pnl(self) -> float:
        """Net PnL in USD."""
        return self.total_gain_usd - self.total_loss_usd
    
    @property
    def weighted_false_positive_cost(self) -> float:
        """Weighted cost of false positives by severity."""
        # Rugs weighted 3x, modest 1.5x, marginal 1x
        return (self.rug_loss_usd * 3.0 + 
                self.modest_loss_usd * 1.5 + 
                self.marginal_loss_usd * 1.0)


@dataclass
class ClusterMetrics:
    """Metrics for a wallet cluster."""
    cluster_id: str
    total_signals: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    last_signal_date: Optional[datetime] = None
    
    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0.0


class MetricsTracker:
    """
    Comprehensive metrics tracking for the trading system.
    
    Tracks:
    - False positive rates and costs
    - Simulator accuracy
    - Win rates by signal type
    - Cluster-level performance
    - ROI calculations
    """
    
    # Loss magnitude thresholds
    RUG_THRESHOLD = 0.90     # >90% loss = rug
    MODEST_THRESHOLD = 0.10  # 10-90% loss = modest
    # <10% loss = marginal
    
    # FP rate thresholds for allocation adjustment
    FP_RATE_WARNING = 0.20   # 20% = warning
    FP_RATE_REDUCE = 0.30    # 30% = reduce allocation
    FP_RATE_DISABLE = 0.40   # 40% = disable V3
    
    def __init__(self, db: WalletGraphDB):
        self.db = db
        self.fp_metrics = FalsePositiveMetrics()
        self.cluster_metrics: Dict[str, ClusterMetrics] = defaultdict(ClusterMetrics)
        self.trade_outcomes: List[TradeOutcome] = []
        self.v3_allocation_multiplier = 1.0
        
        # Period tracking
        self.daily_outcomes: Dict[str, List[TradeOutcome]] = defaultdict(list)
        self.weekly_outcomes: Dict[str, List[TradeOutcome]] = defaultdict(list)
        
        # Load historical data
        self._load_historical_metrics()
    
    def _load_historical_metrics(self) -> None:
        """Load historical metrics from database."""
        # This would load from database in production
        # For now, start fresh
        pass
    
    # =========================================================================
    # OUTCOME RECORDING
    # =========================================================================
    
    def record_trade_outcome(self, trade_id: int, token: str,
                              entry_price: float, exit_price: float,
                              pnl: float, was_graph_boosted: bool = False,
                              simulation_passed: bool = True,
                              cluster_id: str = None) -> TradeOutcome:
        """
        Record a completed trade outcome.
        """
        # Calculate PnL percentage
        pnl_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0
        win = pnl > 0
        
        # Determine loss magnitude
        loss_magnitude = None
        if not win:
            loss_pct = abs(pnl_pct)
            if loss_pct >= self.RUG_THRESHOLD:
                loss_magnitude = "RUG"
            elif loss_pct >= self.MODEST_THRESHOLD:
                loss_magnitude = "MODEST"
            else:
                loss_magnitude = "MARGINAL"
        
        outcome = TradeOutcome(
            trade_id=trade_id,
            token=token,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            win=win,
            timestamp=datetime.utcnow(),
            was_graph_boosted=was_graph_boosted,
            simulation_passed=simulation_passed,
            loss_magnitude=loss_magnitude
        )
        
        self.trade_outcomes.append(outcome)
        
        # Update FP metrics
        self._update_fp_metrics(outcome)
        
        # Update cluster metrics
        if cluster_id:
            self._update_cluster_metrics(cluster_id, outcome)
        
        # Update period tracking
        date_key = outcome.timestamp.strftime("%Y-%m-%d")
        week_key = outcome.timestamp.strftime("%Y-W%W")
        self.daily_outcomes[date_key].append(outcome)
        self.weekly_outcomes[week_key].append(outcome)
        
        # Check allocation adjustment
        self._check_allocation_adjustment()
        
        logger.info(
            f"Trade outcome recorded: {'WIN' if win else 'LOSS'} "
            f"${pnl:.2f} ({pnl_pct*100:+.1f}%) "
            f"{'[GRAPH]' if was_graph_boosted else ''} "
            f"{'[' + loss_magnitude + ']' if loss_magnitude else ''}"
        )
        
        return outcome
    
    def _update_fp_metrics(self, outcome: TradeOutcome) -> None:
        """Update false positive metrics."""
        self.fp_metrics.total_signals += 1
        self.fp_metrics.executed_signals += 1
        
        if outcome.win:
            self.fp_metrics.wins += 1
            self.fp_metrics.total_gain_usd += outcome.pnl
        else:
            self.fp_metrics.losses += 1
            self.fp_metrics.false_positives += 1
            self.fp_metrics.total_loss_usd += abs(outcome.pnl)
            
            # Track by magnitude
            if outcome.loss_magnitude == "RUG":
                self.fp_metrics.rug_losses += 1
                self.fp_metrics.rug_loss_usd += abs(outcome.pnl)
            elif outcome.loss_magnitude == "MODEST":
                self.fp_metrics.modest_losses += 1
                self.fp_metrics.modest_loss_usd += abs(outcome.pnl)
            elif outcome.loss_magnitude == "MARGINAL":
                self.fp_metrics.marginal_losses += 1
                self.fp_metrics.marginal_loss_usd += abs(outcome.pnl)
    
    def _update_cluster_metrics(self, cluster_id: str, outcome: TradeOutcome) -> None:
        """Update cluster-level metrics."""
        if cluster_id not in self.cluster_metrics:
            self.cluster_metrics[cluster_id] = ClusterMetrics(cluster_id=cluster_id)
        
        metrics = self.cluster_metrics[cluster_id]
        metrics.total_signals += 1
        metrics.total_pnl += outcome.pnl
        metrics.last_signal_date = outcome.timestamp
        
        if outcome.win:
            metrics.wins += 1
        else:
            metrics.losses += 1
    
    def record_rejected_outcome(self, token: str, would_have_won: bool) -> None:
        """
        Record outcome of a rejected signal (for FN tracking).
        Call this when you track what happened to a signal you rejected.
        """
        self.fp_metrics.total_signals += 1
        
        if would_have_won:
            self.fp_metrics.false_negatives += 1
    
    # =========================================================================
    # ALLOCATION ADJUSTMENT
    # =========================================================================
    
    def _check_allocation_adjustment(self) -> None:
        """Check if V3 allocation should be adjusted based on FP rate."""
        fp_rate = self.fp_metrics.false_positive_rate
        
        old_multiplier = self.v3_allocation_multiplier
        
        if fp_rate >= self.FP_RATE_DISABLE:
            self.v3_allocation_multiplier = 0.0
            logger.warning(f"V3 DISABLED: FP rate {fp_rate:.1%} >= {self.FP_RATE_DISABLE:.0%}")
        elif fp_rate >= self.FP_RATE_REDUCE:
            # Reduce proportionally
            reduction = (fp_rate - self.FP_RATE_WARNING) / (self.FP_RATE_DISABLE - self.FP_RATE_WARNING)
            self.v3_allocation_multiplier = max(0.5, 1.0 - reduction)
            logger.warning(
                f"V3 REDUCED to {self.v3_allocation_multiplier:.0%}: "
                f"FP rate {fp_rate:.1%}"
            )
        elif fp_rate >= self.FP_RATE_WARNING:
            logger.warning(f"V3 WARNING: FP rate {fp_rate:.1%} approaching threshold")
            self.v3_allocation_multiplier = 1.0
        else:
            self.v3_allocation_multiplier = 1.0
        
        if old_multiplier != self.v3_allocation_multiplier:
            logger.info(
                f"V3 allocation adjusted: {old_multiplier:.0%} -> "
                f"{self.v3_allocation_multiplier:.0%}"
            )
    
    def get_adjusted_position(self, base_position: float) -> float:
        """Apply allocation adjustment to position size."""
        return base_position * self.v3_allocation_multiplier
    
    # =========================================================================
    # WIN RATE CALCULATIONS
    # =========================================================================
    
    def get_win_rate(self, period_days: int = None) -> float:
        """Get win rate, optionally for a specific period."""
        if period_days is None:
            return self.fp_metrics.win_rate
        
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        recent = [o for o in self.trade_outcomes if o.timestamp >= cutoff]
        
        if not recent:
            return 0.0
        
        wins = sum(1 for o in recent if o.win)
        return wins / len(recent)
    
    def get_win_rate_by_type(self) -> Dict[str, float]:
        """Get win rate broken down by signal type."""
        graph_outcomes = [o for o in self.trade_outcomes if o.was_graph_boosted]
        v2_outcomes = [o for o in self.trade_outcomes if not o.was_graph_boosted]
        
        return {
            "overall": self.fp_metrics.win_rate,
            "graph_boosted": (
                sum(1 for o in graph_outcomes if o.win) / len(graph_outcomes)
                if graph_outcomes else 0.0
            ),
            "v2_only": (
                sum(1 for o in v2_outcomes if o.win) / len(v2_outcomes)
                if v2_outcomes else 0.0
            )
        }
    
    # =========================================================================
    # CLUSTER ANALYSIS
    # =========================================================================
    
    def get_cluster_win_rates(self) -> Dict[str, float]:
        """Get win rates for all tracked clusters."""
        return {
            cluster_id: metrics.win_rate
            for cluster_id, metrics in self.cluster_metrics.items()
        }
    
    def get_collapsing_clusters(self, threshold: float = 0.30) -> List[str]:
        """Get clusters with win rate below threshold."""
        return [
            cluster_id
            for cluster_id, metrics in self.cluster_metrics.items()
            if metrics.total_signals >= 5 and metrics.win_rate < threshold
        ]
    
    # =========================================================================
    # ROI CALCULATIONS
    # =========================================================================
    
    def calculate_roi(self, initial_capital: float,
                       period_days: int = None) -> Dict[str, float]:
        """Calculate ROI metrics."""
        if period_days:
            cutoff = datetime.utcnow() - timedelta(days=period_days)
            outcomes = [o for o in self.trade_outcomes if o.timestamp >= cutoff]
        else:
            outcomes = self.trade_outcomes
        
        if not outcomes:
            return {
                "roi_pct": 0.0,
                "total_pnl": 0.0,
                "total_trades": 0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0
            }
        
        total_pnl = sum(o.pnl for o in outcomes)
        roi_pct = (total_pnl / initial_capital) * 100
        
        wins = [o.pnl for o in outcomes if o.win]
        losses = [abs(o.pnl) for o in outcomes if not o.win]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        total_gains = sum(wins)
        total_losses = sum(losses)
        profit_factor = total_gains / total_losses if total_losses > 0 else float('inf')
        
        return {
            "roi_pct": roi_pct,
            "total_pnl": total_pnl,
            "total_trades": len(outcomes),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor
        }
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    def get_performance_report(self, initial_capital: float = 500) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        roi = self.calculate_roi(initial_capital)
        win_rates = self.get_win_rate_by_type()
        
        return {
            "summary": {
                "total_trades": self.fp_metrics.executed_signals,
                "win_rate": self.fp_metrics.win_rate,
                "total_pnl": self.fp_metrics.net_pnl,
                "roi_pct": roi["roi_pct"]
            },
            "false_positives": {
                "rate": self.fp_metrics.false_positive_rate,
                "count": self.fp_metrics.false_positives,
                "cost_usd": self.fp_metrics.total_loss_usd,
                "weighted_cost": self.fp_metrics.weighted_false_positive_cost
            },
            "loss_breakdown": {
                "rugs": {
                    "count": self.fp_metrics.rug_losses,
                    "cost": self.fp_metrics.rug_loss_usd
                },
                "modest": {
                    "count": self.fp_metrics.modest_losses,
                    "cost": self.fp_metrics.modest_loss_usd
                },
                "marginal": {
                    "count": self.fp_metrics.marginal_losses,
                    "cost": self.fp_metrics.marginal_loss_usd
                }
            },
            "win_rates_by_type": win_rates,
            "v3_allocation_multiplier": self.v3_allocation_multiplier,
            "cluster_count": len(self.cluster_metrics),
            "collapsing_clusters": len(self.get_collapsing_clusters())
        }
    
    def get_daily_summary(self, date: str = None) -> Dict[str, Any]:
        """Get summary for a specific day."""
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        outcomes = self.daily_outcomes.get(date, [])
        
        if not outcomes:
            return {
                "date": date,
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "pnl": 0.0,
                "win_rate": 0.0
            }
        
        wins = sum(1 for o in outcomes if o.win)
        losses = len(outcomes) - wins
        pnl = sum(o.pnl for o in outcomes)
        
        return {
            "date": date,
            "trades": len(outcomes),
            "wins": wins,
            "losses": losses,
            "pnl": pnl,
            "win_rate": wins / len(outcomes)
        }
