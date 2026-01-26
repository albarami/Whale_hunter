"""
V3.1 Entropy Injection Module (Ghost Mode)

Handles:
- Random delay injection (5-30ms)
- Probabilistic execution skipping (10%)
- Wallet rotation logic
- Position size randomization

Purpose: Prevent pattern detection by adversaries
"""

import random
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import yaml

logger = logging.getLogger(__name__)


@dataclass
class EntropyConfig:
    """Configuration for entropy injection."""
    enabled: bool = True
    
    # Delay settings
    delay_min_ms: int = 5
    delay_max_ms: int = 30
    
    # Skip probability
    skip_probability: float = 0.10  # Skip 10% of valid signals
    
    # Wallet rotation
    wallet_rotation_enabled: bool = True
    num_wallets: int = 5
    
    # Position randomization
    position_min_multiplier: float = 0.95
    position_max_multiplier: float = 1.05


@dataclass
class EntropyDecision:
    """Result of entropy processing."""
    should_execute: bool
    delay_ms: float
    wallet_index: int
    position_multiplier: float
    skip_reason: Optional[str] = None
    entropy_applied: List[str] = field(default_factory=list)


@dataclass
class SkippedSignal:
    """Record of an entropy-skipped signal."""
    token: str
    timestamp: datetime
    reason: str
    original_confidence: float


class EntropyInjector:
    """
    Inject randomness to avoid being trackable.
    
    Adversaries can detect consistent patterns in:
    - Timing (always executing X ms after signal)
    - Position sizing (always using exact amounts)
    - Wallet usage (always same wallet)
    
    Solution: Be unpredictable while maintaining edge.
    """
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config = self._load_config(config_path)
        
        # Wallet management
        self.execution_wallets: List[str] = []
        self.current_wallet_index: int = 0
        
        # Tracking
        self.skipped_signals: List[SkippedSignal] = []
        self.total_signals: int = 0
        self.total_skipped: int = 0
        self.total_delays_ms: float = 0
    
    def _load_config(self, config_path: str) -> EntropyConfig:
        """Load entropy configuration from YAML."""
        try:
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
                entropy_data = data.get("entropy", {})
                
                return EntropyConfig(
                    enabled=entropy_data.get("enabled", True),
                    delay_min_ms=entropy_data.get("delay", {}).get("min_ms", 5),
                    delay_max_ms=entropy_data.get("delay", {}).get("max_ms", 30),
                    skip_probability=entropy_data.get("skip_probability", 0.10),
                    wallet_rotation_enabled=entropy_data.get("wallet_rotation", {}).get("enabled", True),
                    num_wallets=entropy_data.get("wallet_rotation", {}).get("num_wallets", 5),
                    position_min_multiplier=entropy_data.get("position_randomization", {}).get("min_multiplier", 0.95),
                    position_max_multiplier=entropy_data.get("position_randomization", {}).get("max_multiplier", 1.05)
                )
        except Exception as e:
            logger.warning(f"Could not load entropy config: {e}, using defaults")
            return EntropyConfig()
    
    def set_execution_wallets(self, wallets: List[str]) -> None:
        """Set the list of execution wallets for rotation."""
        self.execution_wallets = wallets
        logger.info(f"Entropy: Set {len(wallets)} execution wallets for rotation")
    
    # =========================================================================
    # CORE ENTROPY METHODS
    # =========================================================================
    
    def generate_jitter_delay(self) -> float:
        """
        Generate random delay before execution.
        Prevents timing pattern detection.
        Returns delay in milliseconds.
        """
        if not self.config.enabled:
            return 0.0
        
        delay_ms = random.uniform(
            self.config.delay_min_ms,
            self.config.delay_max_ms
        )
        
        self.total_delays_ms += delay_ms
        return delay_ms
    
    def should_skip_signal(self) -> bool:
        """
        Probabilistically skip some valid signals.
        This prevents adversaries from correlating ALL your entries.
        
        Counter-intuitive but crucial:
        Missing 10% of opportunities is worth it to stay invisible.
        """
        if not self.config.enabled:
            return False
        
        return random.random() < self.config.skip_probability
    
    def get_next_wallet(self) -> Optional[str]:
        """
        Rotate through execution wallets.
        Each trade uses different wallet, harder to track.
        """
        if not self.config.wallet_rotation_enabled:
            return self.execution_wallets[0] if self.execution_wallets else None
        
        if not self.execution_wallets:
            return None
        
        wallet = self.execution_wallets[self.current_wallet_index]
        
        # Rotate to next wallet
        self.current_wallet_index = (
            self.current_wallet_index + 1
        ) % len(self.execution_wallets)
        
        return wallet
    
    def randomize_position_size(self, base_size: float) -> float:
        """
        Slightly randomize position size.
        Prevents exact-amount pattern matching.
        """
        if not self.config.enabled:
            return base_size
        
        multiplier = random.uniform(
            self.config.position_min_multiplier,
            self.config.position_max_multiplier
        )
        
        return round(base_size * multiplier, 2)
    
    # =========================================================================
    # MAIN PROCESSING METHOD
    # =========================================================================
    
    def process_signal(self, token: str, confidence: float) -> EntropyDecision:
        """
        Apply all entropy measures to a signal.
        Returns decision with all entropy parameters.
        """
        self.total_signals += 1
        entropy_applied = []
        
        # Check if we should skip
        if self.should_skip_signal():
            self.total_skipped += 1
            self.skipped_signals.append(SkippedSignal(
                token=token,
                timestamp=datetime.utcnow(),
                reason="ENTROPY_SKIP",
                original_confidence=confidence
            ))
            
            logger.info(
                f"ENTROPY SKIP: Randomly skipping signal for {token[:8]}... "
                f"(skip rate: {self.total_skipped}/{self.total_signals})"
            )
            
            return EntropyDecision(
                should_execute=False,
                delay_ms=0,
                wallet_index=0,
                position_multiplier=1.0,
                skip_reason="ENTROPY_SKIP",
                entropy_applied=["probabilistic_skip"]
            )
        
        # Generate delay
        delay_ms = self.generate_jitter_delay()
        if delay_ms > 0:
            entropy_applied.append(f"delay_{delay_ms:.1f}ms")
        
        # Get wallet rotation
        wallet_index = self.current_wallet_index
        _ = self.get_next_wallet()  # Advance rotation
        if self.config.wallet_rotation_enabled:
            entropy_applied.append(f"wallet_rotation_{wallet_index}")
        
        # Position randomization
        position_multiplier = random.uniform(
            self.config.position_min_multiplier,
            self.config.position_max_multiplier
        )
        entropy_applied.append(f"position_jitter_{position_multiplier:.3f}")
        
        return EntropyDecision(
            should_execute=True,
            delay_ms=delay_ms,
            wallet_index=wallet_index,
            position_multiplier=position_multiplier,
            entropy_applied=entropy_applied
        )
    
    async def apply_delay(self, delay_ms: float) -> None:
        """Apply the calculated delay."""
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)  # Convert to seconds
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get entropy statistics."""
        return {
            "enabled": self.config.enabled,
            "total_signals": self.total_signals,
            "total_skipped": self.total_skipped,
            "skip_rate": self.total_skipped / self.total_signals if self.total_signals > 0 else 0,
            "configured_skip_probability": self.config.skip_probability,
            "average_delay_ms": self.total_delays_ms / max(1, self.total_signals - self.total_skipped),
            "execution_wallets": len(self.execution_wallets),
            "recent_skips": [
                {
                    "token": s.token[:8] + "...",
                    "timestamp": s.timestamp.isoformat(),
                    "confidence": s.original_confidence
                }
                for s in self.skipped_signals[-10:]  # Last 10
            ]
        }
    
    def reset_stats(self) -> None:
        """Reset statistics."""
        self.skipped_signals = []
        self.total_signals = 0
        self.total_skipped = 0
        self.total_delays_ms = 0


class AntiPatternExecutor:
    """
    Executor that wraps standard execution with entropy injection.
    Use this instead of direct execution for production.
    """
    
    def __init__(self, executor, entropy: EntropyInjector):
        """
        Args:
            executor: The actual execution engine
            entropy: EntropyInjector instance
        """
        self.executor = executor
        self.entropy = entropy
    
    async def execute_with_entropy(self, token: str, amount_usd: float,
                                    confidence: float, **kwargs) -> Optional[Any]:
        """
        Execute trade with anti-pattern measures.
        """
        # Get entropy decision
        decision = self.entropy.process_signal(token, confidence)
        
        if not decision.should_execute:
            logger.info(f"Trade skipped by entropy: {decision.skip_reason}")
            return None
        
        # Apply delay
        await self.entropy.apply_delay(decision.delay_ms)
        
        # Get wallet
        wallet = self.entropy.execution_wallets[decision.wallet_index] \
            if self.entropy.execution_wallets else None
        
        # Randomize position
        adjusted_amount = amount_usd * decision.position_multiplier
        
        logger.debug(
            f"Executing with entropy: delay={decision.delay_ms:.1f}ms, "
            f"wallet_idx={decision.wallet_index}, "
            f"amount=${adjusted_amount:.2f} (was ${amount_usd:.2f})"
        )
        
        # Execute
        return await self.executor.execute(
            token=token,
            amount_usd=adjusted_amount,
            wallet=wallet,
            **kwargs
        )
