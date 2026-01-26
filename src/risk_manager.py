"""
V3.1 Risk Manager Module

Handles:
- Position sizing by capital tier
- Drawdown monitoring
- Capital Preservation Mode (15% trigger)
- First 50 Trades special rules
- Kill switch logic
- Go/No-Go checklist validation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import yaml

from .database import WalletGraphDB

logger = logging.getLogger(__name__)


class RiskMode(Enum):
    """System risk modes."""
    NORMAL = "NORMAL"
    CAPITAL_PRESERVATION = "CAPITAL_PRESERVATION"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    OBSERVATION = "OBSERVATION"


class KillSwitchTrigger(Enum):
    """Kill switch trigger types."""
    MOTHER_EXPLOSION = "MOTHER_EXPLOSION"
    WIN_RATE_COLLAPSE = "WIN_RATE_COLLAPSE"
    CLUSTER_CORRELATION = "CLUSTER_CORRELATION"
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"
    HOURLY_LOSS = "HOURLY_LOSS"
    MANUAL = "MANUAL"


@dataclass
class RiskState:
    """Current risk management state."""
    mode: RiskMode = RiskMode.NORMAL
    current_capital: float = 500.0
    peak_capital: float = 500.0
    drawdown_pct: float = 0.0
    trade_count: int = 0
    consecutive_losses: int = 0
    daily_loss: float = 0.0
    weekly_loss: float = 0.0
    kill_switch_active: bool = False
    kill_switch_reason: Optional[str] = None
    observation_end: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None


@dataclass
class PositionSizeResult:
    """Result of position size calculation."""
    position_usd: float
    position_pct: float
    max_allowed: float
    adjustments: List[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: Optional[str] = None


@dataclass
class GoNoGoResult:
    """Result of Go/No-Go checklist."""
    ready: bool
    checks: Dict[str, bool]
    issues: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RiskManager:
    """
    Risk management and capital protection system.
    
    Key principles:
    - Fail-closed design (block when uncertain)
    - Capital preservation priority
    - Progressive risk reduction on losses
    - Strict first 50 trades rules
    """
    
    def __init__(self, db: WalletGraphDB, config_path: str = "config/settings.yaml"):
        self.db = db
        self.config = self._load_config(config_path)
        self.state = RiskState()
        self._initialize_state()
        
        # Callbacks for state changes
        self.on_mode_change: Optional[Callable] = None
        self.on_kill_switch: Optional[Callable] = None
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Could not load config: {e}, using defaults")
            return self._default_config()
    
    def _default_config(self) -> Dict:
        """Default configuration values."""
        return {
            "risk": {
                "position_sizing": {
                    "capital_under_500": {"max_position_pct": 0.05, "default_position_pct": 0.03},
                    "capital_500_2000": {"max_position_pct": 0.08, "default_position_pct": 0.05},
                    "capital_2000_5000": {"max_position_pct": 0.10, "default_position_pct": 0.07},
                    "capital_above_5000": {"max_position_pct": 0.10, "default_position_pct": 0.08}
                },
                "absolute_limits": {
                    "min_position_usd": 5,
                    "max_position_usd": 500,
                    "max_daily_loss_usd": 100,
                    "max_weekly_loss_usd": 250
                },
                "drawdown": {
                    "warning_threshold": 0.10,
                    "capital_preservation": 0.15,
                    "emergency_stop": 0.25
                },
                "daily_limits": {
                    "max_trades": 10,
                    "max_concurrent_positions": 5
                }
            },
            "capital_preservation": {
                "position_size_multiplier": 0.25,
                "confidence_increase": 0.15,
                "disable_graph_signals": True,
                "require_manual_review": True,
                "cooldown_hours": 24
            },
            "first_50_trades": {
                "enabled": True,
                "max_position_pct": 0.03,
                "no_graph_boost": True,
                "mandatory_review_hours": 24,
                "max_trades_first_week": 5
            },
            "kill_switch": {
                "graph": {
                    "max_new_mothers_24h": 10,
                    "win_rate_collapse_threshold": 0.30,
                    "min_clusters_for_collapse": 3,
                    "observation_period_hours": 72
                },
                "emergency": {
                    "max_consecutive_losses": 5,
                    "max_hourly_loss_pct": 0.05,
                    "require_manual_restart": True
                }
            }
        }
    
    def _initialize_state(self) -> None:
        """Initialize state from database."""
        # Load current capital
        self.state.current_capital = float(self.db.get_state("current_capital", 500))
        self.state.peak_capital = float(self.db.get_state("peak_capital", 500))
        self.state.trade_count = self.db.get_trade_count()
        
        # Calculate drawdown
        if self.state.peak_capital > 0:
            self.state.drawdown_pct = (
                (self.state.peak_capital - self.state.current_capital) / 
                self.state.peak_capital
            )
        
        # Check for existing mode
        saved_mode = self.db.get_state("risk_mode", "NORMAL")
        self.state.mode = RiskMode(saved_mode)
        
        logger.info(
            f"Risk manager initialized: Capital=${self.state.current_capital:.2f}, "
            f"Drawdown={self.state.drawdown_pct:.1%}, Mode={self.state.mode.value}"
        )
    
    # =========================================================================
    # POSITION SIZING
    # =========================================================================
    
    def calculate_position_size(self, confidence: float, 
                                 graph_boosted: bool = False) -> PositionSizeResult:
        """
        Calculate position size based on all risk factors.
        """
        adjustments = []
        risk_config = self.config.get("risk", {})
        
        # Check for blocks first
        if self.state.mode == RiskMode.EMERGENCY_STOP:
            return PositionSizeResult(
                position_usd=0, position_pct=0, max_allowed=0,
                blocked=True, block_reason="Emergency stop active"
            )
        
        if self.state.kill_switch_active:
            return PositionSizeResult(
                position_usd=0, position_pct=0, max_allowed=0,
                blocked=True, block_reason=f"Kill switch: {self.state.kill_switch_reason}"
            )
        
        # Get base sizing for capital tier
        capital = self.state.current_capital
        if capital < 500:
            sizing = risk_config.get("position_sizing", {}).get("capital_under_500", {})
        elif capital < 2000:
            sizing = risk_config.get("position_sizing", {}).get("capital_500_2000", {})
        elif capital < 5000:
            sizing = risk_config.get("position_sizing", {}).get("capital_2000_5000", {})
        else:
            sizing = risk_config.get("position_sizing", {}).get("capital_above_5000", {})
        
        max_pct = sizing.get("max_position_pct", 0.10)
        default_pct = sizing.get("default_position_pct", 0.05)
        
        # First 50 trades: Max 3%
        first_50_config = self.config.get("first_50_trades", {})
        if first_50_config.get("enabled", True) and self.state.trade_count < 50:
            first_50_max = first_50_config.get("max_position_pct", 0.03)
            if max_pct > first_50_max:
                max_pct = first_50_max
                adjustments.append(f"First 50 trades: Max {first_50_max*100:.0f}%")
        
        # Capital preservation mode: 25% of normal
        if self.state.mode == RiskMode.CAPITAL_PRESERVATION:
            preservation_config = self.config.get("capital_preservation", {})
            multiplier = preservation_config.get("position_size_multiplier", 0.25)
            max_pct *= multiplier
            default_pct *= multiplier
            adjustments.append(f"Capital preservation: {multiplier*100:.0f}% of normal")
        
        # Calculate position based on confidence
        position_pct = default_pct * confidence
        position_pct = min(position_pct, max_pct)
        
        # Graph boost: +20% if allowed
        if graph_boosted and self.state.mode == RiskMode.NORMAL:
            if self.state.trade_count >= 50:  # No boost in first 50
                position_pct *= 1.20
                adjustments.append("Graph boost: +20%")
        
        # Calculate USD amount
        position_usd = capital * position_pct
        
        # Apply absolute limits
        absolute_limits = risk_config.get("absolute_limits", {})
        min_position = absolute_limits.get("min_position_usd", 5)
        max_position = absolute_limits.get("max_position_usd", 500)
        
        if position_usd < min_position:
            position_usd = min_position
            adjustments.append(f"Minimum position: ${min_position}")
        elif position_usd > max_position:
            position_usd = max_position
            adjustments.append(f"Maximum position: ${max_position}")
        
        return PositionSizeResult(
            position_usd=round(position_usd, 2),
            position_pct=position_pct,
            max_allowed=max_pct * capital,
            adjustments=adjustments
        )
    
    # =========================================================================
    # DRAWDOWN MONITORING
    # =========================================================================
    
    def update_capital(self, new_capital: float) -> None:
        """Update capital and check drawdown triggers."""
        old_capital = self.state.current_capital
        self.state.current_capital = new_capital
        
        # Update peak if new high
        if new_capital > self.state.peak_capital:
            self.state.peak_capital = new_capital
            self.db.set_state("peak_capital", new_capital)
        
        # Calculate drawdown
        if self.state.peak_capital > 0:
            self.state.drawdown_pct = (
                (self.state.peak_capital - new_capital) / 
                self.state.peak_capital
            )
        
        # Save state
        self.db.set_state("current_capital", new_capital)
        
        # Check triggers
        self._check_drawdown_triggers()
        
        logger.info(
            f"Capital updated: ${old_capital:.2f} -> ${new_capital:.2f} | "
            f"Drawdown: {self.state.drawdown_pct:.1%}"
        )
    
    def _check_drawdown_triggers(self) -> None:
        """Check and trigger drawdown-based modes."""
        drawdown_config = self.config.get("risk", {}).get("drawdown", {})
        
        emergency_threshold = drawdown_config.get("emergency_stop", 0.25)
        preservation_threshold = drawdown_config.get("capital_preservation", 0.15)
        warning_threshold = drawdown_config.get("warning_threshold", 0.10)
        
        if self.state.drawdown_pct >= emergency_threshold:
            self._enter_emergency_stop("Drawdown exceeded emergency threshold")
        elif self.state.drawdown_pct >= preservation_threshold:
            self._enter_capital_preservation()
        elif self.state.drawdown_pct >= warning_threshold:
            logger.warning(
                f"DRAWDOWN WARNING: {self.state.drawdown_pct:.1%} "
                f"(preservation at {preservation_threshold:.0%})"
            )
    
    def _enter_capital_preservation(self) -> None:
        """Enter capital preservation mode."""
        if self.state.mode == RiskMode.CAPITAL_PRESERVATION:
            return
        
        logger.warning(
            f"ENTERING CAPITAL PRESERVATION MODE | "
            f"Drawdown: {self.state.drawdown_pct:.1%}"
        )
        
        self.state.mode = RiskMode.CAPITAL_PRESERVATION
        self.db.set_state("risk_mode", self.state.mode.value)
        
        if self.on_mode_change:
            self.on_mode_change(self.state.mode)
    
    def _enter_emergency_stop(self, reason: str) -> None:
        """Enter emergency stop mode."""
        logger.critical(f"EMERGENCY STOP: {reason}")
        
        self.state.mode = RiskMode.EMERGENCY_STOP
        self.state.kill_switch_active = True
        self.state.kill_switch_reason = reason
        self.db.set_state("risk_mode", self.state.mode.value)
        
        # Log kill switch event
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO kill_switch_events (trigger_type, trigger_reason, mode)
            VALUES (?, ?, ?)
        """, (KillSwitchTrigger.CONSECUTIVE_LOSSES.value, reason, self.state.mode.value))
        self.db.conn.commit()
        
        if self.on_kill_switch:
            self.on_kill_switch(reason)
    
    def exit_capital_preservation(self, manual_approval: bool = True) -> bool:
        """
        Exit capital preservation mode.
        Requires manual approval by default.
        """
        if self.state.mode != RiskMode.CAPITAL_PRESERVATION:
            return False
        
        preservation_config = self.config.get("capital_preservation", {})
        
        if preservation_config.get("require_manual_review", True) and not manual_approval:
            logger.warning("Manual approval required to exit capital preservation")
            return False
        
        logger.info("Exiting capital preservation mode")
        self.state.mode = RiskMode.NORMAL
        self.db.set_state("risk_mode", self.state.mode.value)
        
        if self.on_mode_change:
            self.on_mode_change(self.state.mode)
        
        return True
    
    # =========================================================================
    # KILL SWITCH LOGIC
    # =========================================================================
    
    def check_graph_kill_switch(self, mother_discoveries_24h: int,
                                 cluster_win_rates: Dict[str, float]) -> Optional[str]:
        """
        Check graph kill switch triggers.
        Returns trigger reason if triggered, None otherwise.
        """
        kill_config = self.config.get("kill_switch", {}).get("graph", {})
        
        # Check mother wallet explosion
        max_mothers = kill_config.get("max_new_mothers_24h", 10)
        if mother_discoveries_24h > max_mothers:
            reason = (
                f"MOTHER EXPLOSION: {mother_discoveries_24h} new mothers in 24h "
                f"(threshold: {max_mothers})"
            )
            self.trigger_kill_switch(KillSwitchTrigger.MOTHER_EXPLOSION, reason)
            return reason
        
        # Check win rate collapse
        collapse_threshold = kill_config.get("win_rate_collapse_threshold", 0.30)
        min_clusters = kill_config.get("min_clusters_for_collapse", 3)
        
        collapsing_clusters = sum(
            1 for rate in cluster_win_rates.values() 
            if rate < collapse_threshold
        )
        
        if collapsing_clusters >= min_clusters:
            reason = (
                f"WIN RATE COLLAPSE: {collapsing_clusters} clusters below "
                f"{collapse_threshold*100:.0f}% threshold"
            )
            self.trigger_kill_switch(KillSwitchTrigger.WIN_RATE_COLLAPSE, reason)
            return reason
        
        return None
    
    def trigger_kill_switch(self, trigger: KillSwitchTrigger, reason: str) -> None:
        """Trigger the kill switch."""
        logger.critical(f"🚨 KILL SWITCH TRIGGERED: {trigger.value} - {reason}")
        
        kill_config = self.config.get("kill_switch", {}).get("graph", {})
        observation_hours = kill_config.get("observation_period_hours", 72)
        
        self.state.kill_switch_active = True
        self.state.kill_switch_reason = reason
        self.state.mode = RiskMode.OBSERVATION
        self.state.observation_end = datetime.utcnow() + timedelta(hours=observation_hours)
        
        self.db.set_state("risk_mode", self.state.mode.value)
        
        # Log event
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO kill_switch_events (trigger_type, trigger_reason, mode, observation_end)
            VALUES (?, ?, ?, ?)
        """, (trigger.value, reason, self.state.mode.value, 
              self.state.observation_end.isoformat()))
        self.db.conn.commit()
        
        if self.on_kill_switch:
            self.on_kill_switch(reason)
    
    def check_emergency_triggers(self, consecutive_losses: int,
                                  hourly_loss_pct: float) -> Optional[str]:
        """Check emergency kill switch triggers."""
        emergency_config = self.config.get("kill_switch", {}).get("emergency", {})
        
        max_losses = emergency_config.get("max_consecutive_losses", 5)
        max_hourly_loss = emergency_config.get("max_hourly_loss_pct", 0.05)
        
        if consecutive_losses >= max_losses:
            reason = f"Consecutive losses: {consecutive_losses} >= {max_losses}"
            self._enter_emergency_stop(reason)
            return reason
        
        if hourly_loss_pct >= max_hourly_loss:
            reason = f"Hourly loss: {hourly_loss_pct:.1%} >= {max_hourly_loss:.0%}"
            self._enter_emergency_stop(reason)
            return reason
        
        return None
    
    def reset_kill_switch(self, manual_approval: bool = True) -> bool:
        """Reset kill switch (requires manual approval)."""
        emergency_config = self.config.get("kill_switch", {}).get("emergency", {})
        
        if emergency_config.get("require_manual_restart", True) and not manual_approval:
            logger.warning("Manual approval required to reset kill switch")
            return False
        
        logger.info("Resetting kill switch")
        self.state.kill_switch_active = False
        self.state.kill_switch_reason = None
        self.state.mode = RiskMode.NORMAL
        self.state.observation_end = None
        
        self.db.set_state("risk_mode", self.state.mode.value)
        
        # Mark event as resolved
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE kill_switch_events 
            SET resolved = TRUE, resolution_notes = 'Manual reset'
            WHERE resolved = FALSE
        """)
        self.db.conn.commit()
        
        return True
    
    # =========================================================================
    # FIRST 50 TRADES RULES
    # =========================================================================
    
    def check_first_50_rules(self, graph_boosted: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Check first 50 trades special rules.
        Returns (allowed, rejection_reason).
        """
        first_50_config = self.config.get("first_50_trades", {})
        
        if not first_50_config.get("enabled", True):
            return (True, None)
        
        if self.state.trade_count >= 50:
            return (True, None)  # Past first 50
        
        # No graph-boosted trades
        if first_50_config.get("no_graph_boost", True) and graph_boosted:
            return (False, "First 50 trades: No graph-boosted trades allowed")
        
        # Max 5 trades in first week
        if self.state.trade_count < 5:
            max_first_week = first_50_config.get("max_trades_first_week", 5)
            trades_this_week = len(self.db.get_trades_in_timeframe(hours=168))
            if trades_this_week >= max_first_week:
                return (False, f"First week limit: {trades_this_week}/{max_first_week} trades")
        
        # 24h review before second trade each day
        review_hours = first_50_config.get("mandatory_review_hours", 24)
        if self.state.last_trade_time:
            hours_since_last = (datetime.utcnow() - self.state.last_trade_time).total_seconds() / 3600
            trades_today = len([
                t for t in self.db.get_trades_in_timeframe(hours=24)
                if t.timestamp.date() == datetime.utcnow().date()
            ])
            if trades_today > 0 and hours_since_last < review_hours:
                return (False, f"First 50: {review_hours}h review required between daily trades")
        
        return (True, None)
    
    def record_trade(self, pnl: float) -> None:
        """Record a trade and update risk state."""
        self.state.trade_count += 1
        self.state.last_trade_time = datetime.utcnow()
        
        # Track consecutive losses
        if pnl < 0:
            self.state.consecutive_losses += 1
            self.state.daily_loss += abs(pnl)
        else:
            self.state.consecutive_losses = 0
        
        # Update capital
        self.update_capital(self.state.current_capital + pnl)
        
        # Check emergency triggers
        self.check_emergency_triggers(
            self.state.consecutive_losses,
            self.state.daily_loss / self.state.peak_capital if self.state.peak_capital > 0 else 0
        )
    
    # =========================================================================
    # GO/NO-GO CHECKLIST
    # =========================================================================
    
    def validate_go_nogo(self, simulator_accuracy: float = 0.0) -> GoNoGoResult:
        """
        Validate Go/No-Go checklist for V2.5 → V3.0 transition.
        """
        checklist_config = self.config.get("go_nogo_checklist", {})
        
        checks = {}
        issues = []
        
        # Check 1: Minimum signals tracked
        min_signals = checklist_config.get("min_signals_tracked", 50)
        stats = self.db.get_stats()
        signal_count = stats.get("total_signals", 0)
        checks["min_signals"] = signal_count >= min_signals
        if not checks["min_signals"]:
            issues.append(f"Signals: {signal_count}/{min_signals}")
        
        # Check 2: Simulator accuracy
        min_accuracy = checklist_config.get("min_simulator_accuracy", 0.95)
        checks["simulator_accuracy"] = simulator_accuracy >= min_accuracy
        if not checks["simulator_accuracy"]:
            issues.append(f"Simulator accuracy: {simulator_accuracy:.1%} < {min_accuracy:.0%}")
        
        # Check 3: Capital threshold
        min_capital = checklist_config.get("min_capital_usd", 5000)
        checks["capital"] = self.state.current_capital >= min_capital
        if not checks["capital"]:
            issues.append(f"Capital: ${self.state.current_capital:.0f} < ${min_capital:.0f}")
        
        # Check 4: Win rate over 3 months
        min_win_rate = checklist_config.get("min_win_rate_3_months", 0.55)
        outcomes = stats.get("signals_by_outcome", {})
        wins = outcomes.get("WIN", 0)
        losses = outcomes.get("LOSS", 0)
        total = wins + losses
        win_rate = wins / total if total > 0 else 0
        checks["win_rate"] = win_rate >= min_win_rate
        if not checks["win_rate"]:
            if total == 0:
                issues.append("No completed trades for win rate")
            else:
                issues.append(f"Win rate: {win_rate:.1%} < {min_win_rate:.0%}")
        
        # Check 5: Positive ROI
        if checklist_config.get("require_positive_roi", True):
            total_pnl = stats.get("total_pnl", 0)
            checks["positive_roi"] = total_pnl > 0
            if not checks["positive_roi"]:
                issues.append(f"ROI: ${total_pnl:.2f} (must be positive)")
        else:
            checks["positive_roi"] = True
        
        # Check 6: Graph kill switch tested
        if checklist_config.get("graph_kill_switch_tested", True):
            # Check if there's been a kill switch event
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM kill_switch_events")
            kill_switch_tests = cursor.fetchone()[0]
            checks["kill_switch_tested"] = kill_switch_tests > 0
            if not checks["kill_switch_tested"]:
                issues.append("Graph kill switch not tested")
        else:
            checks["kill_switch_tested"] = True
        
        ready = all(checks.values())
        
        return GoNoGoResult(
            ready=ready,
            checks=checks,
            issues=issues
        )
    
    # =========================================================================
    # STATE REPORTING
    # =========================================================================
    
    def get_risk_report(self) -> Dict[str, Any]:
        """Get comprehensive risk report."""
        return {
            "mode": self.state.mode.value,
            "capital": {
                "current": self.state.current_capital,
                "peak": self.state.peak_capital,
                "drawdown_pct": self.state.drawdown_pct
            },
            "trades": {
                "total": self.state.trade_count,
                "consecutive_losses": self.state.consecutive_losses,
                "in_first_50": self.state.trade_count < 50
            },
            "kill_switch": {
                "active": self.state.kill_switch_active,
                "reason": self.state.kill_switch_reason,
                "observation_end": self.state.observation_end.isoformat() if self.state.observation_end else None
            },
            "daily_loss": self.state.daily_loss,
            "weekly_loss": self.state.weekly_loss
        }
