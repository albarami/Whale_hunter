"""
V3.1 Signal Processor Module

Handles:
- Veto system (not linear weighting)
- Signal saturation control (cooldowns)
- Asset-class-specific freshness checks
- Cluster validation
- Go/No-Go checklist validation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import yaml

from .database import WalletGraphDB, Signal
from .wallet_tracker import WalletTracker, WalletSignal

logger = logging.getLogger(__name__)


class SignalAction(Enum):
    """Possible actions for a signal."""
    EXECUTE = "EXECUTE"
    REJECT = "REJECT"
    HOLD = "HOLD"  # Wait for more confirmation


class VetoReason(Enum):
    """Reasons for signal veto."""
    TOKEN_TOO_YOUNG = "TOKEN_TOO_YOUNG"
    TOKEN_TOO_OLD = "TOKEN_TOO_OLD"
    INSUFFICIENT_CONFIDENCE = "INSUFFICIENT_CONFIDENCE"
    CEX_FUNDED_NO_CLUSTER = "CEX_FUNDED_NO_CLUSTER"
    SIMULATION_FAILED = "SIMULATION_FAILED"
    HIGH_TAX = "HIGH_TAX"
    SIGNAL_SATURATION = "SIGNAL_SATURATION"
    WALLET_COOLDOWN = "WALLET_COOLDOWN"
    DRAWDOWN_PROTECTION = "DRAWDOWN_PROTECTION"
    FIRST_50_RULES = "FIRST_50_RULES"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    CLUSTER_SUSPICIOUS = "CLUSTER_SUSPICIOUS"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    LIQUIDITY_TOO_LOW = "LIQUIDITY_TOO_LOW"


@dataclass
class TokenInfo:
    """Token information for freshness checks."""
    address: str
    creation_time: datetime
    market_cap_usd: float
    liquidity_usd: float
    holder_count: int
    price_usd: float
    volume_24h: float


@dataclass
class SignalDecision:
    """Decision output from signal processor."""
    action: SignalAction
    confidence: float
    position_usd: float
    veto_reasons: List[VetoReason] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    components_used: List[str] = field(default_factory=list)
    graph_boosted: bool = False
    requires_simulation: bool = True


@dataclass
class ProcessedSignal:
    """Fully processed signal ready for execution."""
    original_signal: Signal
    wallet_signal: Optional[WalletSignal]
    token_info: Optional[TokenInfo]
    decision: SignalDecision
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SignalProcessor:
    """
    Signal validation and processing engine.
    
    Key principles:
    - VETO system, not linear weighting (any veto = reject)
    - Asset-class-specific freshness requirements
    - Signal saturation control (cooldowns)
    - Fail-closed design
    """
    
    def __init__(self, db: WalletGraphDB, wallet_tracker: WalletTracker,
                 config_path: str = "config/settings.yaml"):
        self.db = db
        self.wallet_tracker = wallet_tracker
        self.config = self._load_config(config_path)
        
        # Cooldown tracking
        self.wallet_cooldowns: Dict[str, datetime] = {}
        self.token_cooldowns: Dict[str, datetime] = {}
        self.recent_signals: List[ProcessedSignal] = []
        
        # System state
        self.kill_switch_active = False
        self.capital_preservation_mode = False
    
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
            "signal_freshness": {
                "meme_coin": {"min_age_seconds": 3600, "max_age_hours": 48},
                "mid_cap": {"min_age_seconds": 1800, "max_age_hours": 72},
                "large_cap": {"min_age_seconds": 0, "max_age_hours": 168}
            },
            "market_cap_thresholds": {
                "large_cap_min": 100000000,
                "mid_cap_min": 10000000
            },
            "confidence": {
                "min_trade_confidence": 0.60
            },
            "cooldowns": {
                "wallet_cooldown_minutes": 60,
                "token_cooldown_minutes": 30,
                "max_signals_per_hour": 10
            }
        }
    
    # =========================================================================
    # MAIN PROCESSING PIPELINE
    # =========================================================================
    
    async def process_signal(self, signal: Signal, token_info: TokenInfo,
                            simulation_result: Optional[Dict] = None) -> ProcessedSignal:
        """
        Main signal processing pipeline.
        Runs all veto checks and returns final decision.
        """
        veto_reasons = []
        warnings = []
        components_used = ["V2.0"]
        
        # Get wallet signal if available
        wallet_signal = None
        if signal.wallet:
            wallet_signal = self.wallet_tracker.get_wallet_signal(signal.wallet)
        
        # =====================================================================
        # VETO CHECK 1: System State
        # =====================================================================
        if self.kill_switch_active:
            veto_reasons.append(VetoReason.KILL_SWITCH_ACTIVE)
        
        # =====================================================================
        # VETO CHECK 2: Token Age (Asset-Class Specific)
        # =====================================================================
        age_check = self._check_token_age(token_info)
        if not age_check[0]:
            veto_reasons.append(age_check[1])
            warnings.append(age_check[2])
        
        # =====================================================================
        # VETO CHECK 3: Confidence Threshold
        # =====================================================================
        base_confidence = signal.confidence
        min_confidence = self.config.get("confidence", {}).get("min_trade_confidence", 0.60)
        
        if self.capital_preservation_mode:
            min_confidence += 0.15  # Higher threshold in preservation mode
        
        if base_confidence < min_confidence:
            veto_reasons.append(VetoReason.INSUFFICIENT_CONFIDENCE)
        
        # =====================================================================
        # VETO CHECK 4: CEX Funding
        # =====================================================================
        if wallet_signal and wallet_signal.is_cex_funded and not wallet_signal.mother_wallet:
            veto_reasons.append(VetoReason.CEX_FUNDED_NO_CLUSTER)
        
        # =====================================================================
        # VETO CHECK 5: Simulation Results
        # =====================================================================
        if simulation_result:
            if simulation_result.get("is_honeypot", False):
                veto_reasons.append(VetoReason.SIMULATION_FAILED)
            
            tax_pct = simulation_result.get("effective_tax_pct", 0)
            if tax_pct > 10:
                veto_reasons.append(VetoReason.HIGH_TAX)
                warnings.append(f"Tax {tax_pct:.1f}% exceeds 10% threshold")
        
        # =====================================================================
        # VETO CHECK 6: Signal Saturation (Cooldowns)
        # =====================================================================
        saturation_check = self._check_signal_saturation(signal.wallet, signal.token)
        if not saturation_check[0]:
            veto_reasons.append(saturation_check[1])
        
        # =====================================================================
        # VETO CHECK 7: Liquidity
        # =====================================================================
        if token_info.liquidity_usd < 10000:  # $10k minimum liquidity
            veto_reasons.append(VetoReason.LIQUIDITY_TOO_LOW)
            warnings.append(f"Liquidity ${token_info.liquidity_usd:.0f} below $10k threshold")
        
        # =====================================================================
        # VETO CHECK 8: First 50 Trades Rules
        # =====================================================================
        first_50_check = self._check_first_50_rules(wallet_signal)
        if not first_50_check[0]:
            veto_reasons.append(VetoReason.FIRST_50_RULES)
            warnings.append(first_50_check[1])
        
        # =====================================================================
        # CALCULATE FINAL CONFIDENCE (Graph Boost)
        # =====================================================================
        graph_boost = 0.0
        graph_boosted = False
        
        if wallet_signal and not veto_reasons and not self.capital_preservation_mode:
            boost_config = self.config.get("confidence", {}).get("graph_boost", {})
            
            if wallet_signal.signal_strength == "SCREAMING_BUY":
                graph_boost = boost_config.get("s_tier_boost", 0.25)
            elif wallet_signal.signal_strength == "STRONG_BUY":
                graph_boost = boost_config.get("a_tier_boost", 0.15)
            elif wallet_signal.signal_strength == "MODERATE":
                graph_boost = boost_config.get("b_tier_boost", 0.05)
            
            if graph_boost > 0:
                graph_boosted = True
                components_used.append("Graph")
        
        final_confidence = min(base_confidence + graph_boost, 1.0)
        
        # Apply decay
        if wallet_signal:
            final_confidence *= wallet_signal.decay_factor
        
        # =====================================================================
        # DETERMINE ACTION
        # =====================================================================
        if veto_reasons:
            action = SignalAction.REJECT
            position_usd = 0.0
        else:
            action = SignalAction.EXECUTE
            position_usd = self._calculate_position_size(
                final_confidence, token_info, graph_boosted
            )
        
        decision = SignalDecision(
            action=action,
            confidence=final_confidence,
            position_usd=position_usd,
            veto_reasons=veto_reasons,
            warnings=warnings,
            components_used=components_used,
            graph_boosted=graph_boosted,
            requires_simulation=(simulation_result is None)
        )
        
        processed = ProcessedSignal(
            original_signal=signal,
            wallet_signal=wallet_signal,
            token_info=token_info,
            decision=decision
        )
        
        # Track signal
        self.recent_signals.append(processed)
        self._cleanup_old_signals()
        
        # Update cooldowns if executing
        if action == SignalAction.EXECUTE:
            self._update_cooldowns(signal.wallet, signal.token)
        
        logger.info(
            f"Signal processed: {action.value} | "
            f"Token: {signal.token[:8]}... | "
            f"Confidence: {final_confidence:.2f} | "
            f"Vetoes: {len(veto_reasons)}"
        )
        
        return processed
    
    # =========================================================================
    # VETO CHECK HELPERS
    # =========================================================================
    
    def _check_token_age(self, token_info: TokenInfo) -> Tuple[bool, Optional[VetoReason], str]:
        """Check if token meets age requirements for its class."""
        token_class = self._classify_token(token_info)
        freshness_config = self.config.get("signal_freshness", {}).get(token_class, {})
        
        min_age_seconds = freshness_config.get("min_age_seconds", 3600)
        max_age_hours = freshness_config.get("max_age_hours", 48)
        
        token_age_seconds = (datetime.utcnow() - token_info.creation_time).total_seconds()
        token_age_hours = token_age_seconds / 3600
        
        if token_age_seconds < min_age_seconds:
            return (
                False, 
                VetoReason.TOKEN_TOO_YOUNG,
                f"{token_class} token age {token_age_seconds/60:.1f}min < required {min_age_seconds/60:.0f}min"
            )
        
        if token_age_hours > max_age_hours:
            return (
                False,
                VetoReason.TOKEN_TOO_OLD,
                f"Token age {token_age_hours:.1f}h > max {max_age_hours}h"
            )
        
        return (True, None, "")
    
    def _classify_token(self, token_info: TokenInfo) -> str:
        """Classify token by market cap/liquidity."""
        thresholds = self.config.get("market_cap_thresholds", {})
        
        large_cap_min = thresholds.get("large_cap_min", 100000000)
        mid_cap_min = thresholds.get("mid_cap_min", 10000000)
        
        if token_info.market_cap_usd >= large_cap_min:
            return "large_cap"
        elif token_info.market_cap_usd >= mid_cap_min:
            return "mid_cap"
        else:
            return "meme_coin"
    
    def _check_signal_saturation(self, wallet: str, token: str) -> Tuple[bool, Optional[VetoReason]]:
        """Check for signal saturation (cooldowns)."""
        now = datetime.utcnow()
        cooldowns = self.config.get("cooldowns", {})
        
        # Check wallet cooldown
        wallet_cooldown_minutes = cooldowns.get("wallet_cooldown_minutes", 60)
        if wallet and wallet in self.wallet_cooldowns:
            cooldown_end = self.wallet_cooldowns[wallet] + timedelta(minutes=wallet_cooldown_minutes)
            if now < cooldown_end:
                return (False, VetoReason.WALLET_COOLDOWN)
        
        # Check token cooldown
        token_cooldown_minutes = cooldowns.get("token_cooldown_minutes", 30)
        if token in self.token_cooldowns:
            cooldown_end = self.token_cooldowns[token] + timedelta(minutes=token_cooldown_minutes)
            if now < cooldown_end:
                return (False, VetoReason.SIGNAL_SATURATION)
        
        # Check hourly signal limit
        max_per_hour = cooldowns.get("max_signals_per_hour", 10)
        one_hour_ago = now - timedelta(hours=1)
        recent_count = sum(1 for s in self.recent_signals if s.timestamp > one_hour_ago)
        if recent_count >= max_per_hour:
            return (False, VetoReason.SIGNAL_SATURATION)
        
        return (True, None)
    
    def _check_first_50_rules(self, wallet_signal: Optional[WalletSignal]) -> Tuple[bool, str]:
        """Check first 50 trades special rules."""
        first_50_config = self.config.get("first_50_trades", {})
        if not first_50_config.get("enabled", True):
            return (True, "")
        
        trade_count = self.db.get_trade_count()
        if trade_count >= 50:
            return (True, "")  # Past first 50
        
        # Check: No graph-boosted trades in first 50
        if first_50_config.get("no_graph_boost", True):
            if wallet_signal and wallet_signal.signal_strength in ["SCREAMING_BUY", "STRONG_BUY"]:
                return (False, "First 50 trades: No graph-boosted trades allowed")
        
        # Check: Max 5 trades in first week
        if trade_count < 5:
            max_first_week = first_50_config.get("max_trades_first_week", 5)
            recent_trades = self.db.get_trades_in_timeframe(hours=168)  # 7 days
            if len(recent_trades) >= max_first_week:
                return (False, f"First week: Max {max_first_week} trades reached")
        
        return (True, "")
    
    def _update_cooldowns(self, wallet: str, token: str) -> None:
        """Update cooldowns after signal execution."""
        now = datetime.utcnow()
        if wallet:
            self.wallet_cooldowns[wallet] = now
        self.token_cooldowns[token] = now
    
    def _cleanup_old_signals(self) -> None:
        """Remove old signals from tracking."""
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.recent_signals = [s for s in self.recent_signals if s.timestamp > cutoff]
    
    # =========================================================================
    # POSITION SIZING
    # =========================================================================
    
    def _calculate_position_size(self, confidence: float, token_info: TokenInfo,
                                  graph_boosted: bool) -> float:
        """Calculate position size based on confidence and rules."""
        risk_config = self.config.get("risk", {})
        current_capital = float(self.db.get_state("current_capital", 500))
        
        # Get position sizing rules for capital tier
        if current_capital < 500:
            sizing = risk_config.get("position_sizing", {}).get("capital_under_500", {})
        elif current_capital < 2000:
            sizing = risk_config.get("position_sizing", {}).get("capital_500_2000", {})
        elif current_capital < 5000:
            sizing = risk_config.get("position_sizing", {}).get("capital_2000_5000", {})
        else:
            sizing = risk_config.get("position_sizing", {}).get("capital_above_5000", {})
        
        max_pct = sizing.get("max_position_pct", 0.10)
        default_pct = sizing.get("default_position_pct", 0.05)
        
        # First 50 trades: Max 3%
        trade_count = self.db.get_trade_count()
        if trade_count < 50:
            max_pct = min(max_pct, 0.03)
        
        # Capital preservation mode: 25% of normal
        if self.capital_preservation_mode:
            max_pct *= 0.25
        
        # Calculate base position
        position_pct = default_pct * confidence
        position_pct = min(position_pct, max_pct)
        
        position_usd = current_capital * position_pct
        
        # Graph boost: +20% if graph-confirmed
        if graph_boosted and not self.capital_preservation_mode:
            position_usd *= 1.20
        
        # Apply absolute limits
        absolute_limits = risk_config.get("absolute_limits", {})
        min_position = absolute_limits.get("min_position_usd", 5)
        max_position = absolute_limits.get("max_position_usd", 500)
        
        position_usd = max(min_position, min(position_usd, max_position))
        
        return round(position_usd, 2)
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    def set_kill_switch(self, active: bool, reason: str = None) -> None:
        """Activate or deactivate kill switch."""
        self.kill_switch_active = active
        if active:
            logger.critical(f"KILL SWITCH ACTIVATED: {reason}")
        else:
            logger.info("Kill switch deactivated")
    
    def set_capital_preservation_mode(self, active: bool) -> None:
        """Activate or deactivate capital preservation mode."""
        self.capital_preservation_mode = active
        if active:
            logger.warning("CAPITAL PRESERVATION MODE ACTIVATED")
        else:
            logger.info("Capital preservation mode deactivated")
    
    # =========================================================================
    # GO/NO-GO CHECKLIST
    # =========================================================================
    
    def validate_go_nogo_checklist(self) -> Tuple[bool, List[str]]:
        """
        Validate Go/No-Go checklist for V2.5 → V3.0 transition.
        Returns (ready, issues_list).
        """
        checklist = self.config.get("go_nogo_checklist", {})
        issues = []
        
        # Check 1: Minimum signals tracked
        min_signals = checklist.get("min_signals_tracked", 50)
        stats = self.db.get_stats()
        if stats.get("total_signals", 0) < min_signals:
            issues.append(f"Need {min_signals}+ signals tracked, have {stats.get('total_signals', 0)}")
        
        # Check 2: Simulator accuracy (would need metrics module)
        # This is a placeholder - actual implementation in metrics.py
        min_accuracy = checklist.get("min_simulator_accuracy", 0.95)
        # accuracy = self.metrics.get_simulator_accuracy()
        # if accuracy < min_accuracy:
        #     issues.append(f"Simulator accuracy {accuracy:.1%} < required {min_accuracy:.0%}")
        
        # Check 3: Capital threshold
        min_capital = checklist.get("min_capital_usd", 5000)
        current_capital = float(self.db.get_state("current_capital", 500))
        if current_capital < min_capital:
            issues.append(f"Capital ${current_capital:.0f} < required ${min_capital:.0f}")
        
        # Check 4: Win rate
        min_win_rate = checklist.get("min_win_rate_3_months", 0.55)
        outcomes = stats.get("signals_by_outcome", {})
        wins = outcomes.get("WIN", 0)
        losses = outcomes.get("LOSS", 0)
        if (wins + losses) > 0:
            win_rate = wins / (wins + losses)
            if win_rate < min_win_rate:
                issues.append(f"Win rate {win_rate:.1%} < required {min_win_rate:.0%}")
        else:
            issues.append("No completed trades to calculate win rate")
        
        # Check 5: Positive ROI
        if checklist.get("require_positive_roi", True):
            total_pnl = stats.get("total_pnl", 0)
            if total_pnl <= 0:
                issues.append(f"Total PnL ${total_pnl:.2f} must be positive")
        
        return (len(issues) == 0, issues)
