"""
V3.1 Transaction Simulator Module

Handles:
- simulateTransaction RPC calls
- Buy + sell simulation
- Tax detection
- Accuracy tracking with loss magnitude weighting
"""

import logging
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import base64
import json

logger = logging.getLogger(__name__)


class LossMagnitude(Enum):
    """Loss magnitude classification for weighting."""
    RUG = "RUG"           # 100% loss
    MODEST = "MODEST"     # 10-30% loss  
    MARGINAL = "MARGINAL" # <10% loss
    NONE = "NONE"         # Not a loss


@dataclass
class SimulationResult:
    """Result of transaction simulation."""
    success: bool
    is_honeypot: bool
    can_buy: bool
    can_sell: bool
    buy_tax_pct: float
    sell_tax_pct: float
    effective_tax_pct: float
    max_slippage_pct: float
    reason: str
    raw_response: Optional[Dict] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SimulatorAccuracyStats:
    """Accuracy tracking for simulator."""
    total_signals: int = 0
    simulator_blocked: int = 0
    simulator_passed: int = 0
    
    # Outcome tracking
    passed_that_won: int = 0
    passed_that_lost: int = 0
    blocked_that_would_have_won: int = 0
    blocked_that_would_have_lost: int = 0
    
    # Loss magnitude tracking
    rug_blocked: int = 0
    rug_missed: int = 0
    modest_loss_blocked: int = 0
    modest_loss_missed: int = 0
    marginal_loss_blocked: int = 0
    marginal_loss_missed: int = 0
    
    @property
    def blocker_accuracy(self) -> float:
        """What % of losers did we correctly block?"""
        total_losers = self.passed_that_lost + self.blocked_that_would_have_lost
        if total_losers == 0:
            return 0.0
        return self.blocked_that_would_have_lost / total_losers
    
    @property
    def weighted_accuracy(self) -> float:
        """Accuracy weighted by loss magnitude."""
        # Weights: Rug (3x), Modest (1.5x), Marginal (1x)
        rug_weight = 3.0
        modest_weight = 1.5
        marginal_weight = 1.0
        
        total_weighted_losers = (
            (self.rug_blocked + self.rug_missed) * rug_weight +
            (self.modest_loss_blocked + self.modest_loss_missed) * modest_weight +
            (self.marginal_loss_blocked + self.marginal_loss_missed) * marginal_weight
        )
        
        if total_weighted_losers == 0:
            return 0.0
        
        weighted_blocked = (
            self.rug_blocked * rug_weight +
            self.modest_loss_blocked * modest_weight +
            self.marginal_loss_blocked * marginal_weight
        )
        
        return weighted_blocked / total_weighted_losers
    
    @property
    def assassin_ready(self) -> bool:
        """Is Assassin allowed to go live?"""
        if self.total_signals < 50:
            return False
        return self.blocker_accuracy >= 0.95


class TransactionSimulator:
    """
    Transaction simulator using Solana simulateTransaction RPC.
    
    Key features:
    - Simulates buy and sell transactions
    - Detects honeypots (can't sell)
    - Calculates effective tax
    - Tracks accuracy for Assassin readiness
    """
    
    # Tax thresholds
    MAX_ACCEPTABLE_TAX = 10.0  # 10% max
    HIGH_TAX_WARNING = 5.0    # 5% warning
    
    def __init__(self, rpc_url: str, test_amount_sol: float = 0.01):
        self.rpc_url = rpc_url
        self.test_amount_sol = test_amount_sol
        self.stats = SimulatorAccuracyStats()
        self.pending_outcomes: Dict[str, SimulationResult] = {}
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Initialize HTTP session."""
        if not self._session:
            self._session = aiohttp.ClientSession()
    
    async def stop(self):
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
    
    # =========================================================================
    # MAIN SIMULATION METHODS
    # =========================================================================
    
    async def full_honeypot_check(self, token_address: str, 
                                   wallet_address: str = None) -> SimulationResult:
        """
        Full honeypot check: simulate both buy and sell.
        Returns detailed simulation result.
        """
        self.stats.total_signals += 1
        
        try:
            # Simulate buy
            buy_result = await self._simulate_buy(token_address, wallet_address)
            
            if not buy_result['success']:
                result = SimulationResult(
                    success=False,
                    is_honeypot=True,
                    can_buy=False,
                    can_sell=False,
                    buy_tax_pct=100.0,
                    sell_tax_pct=100.0,
                    effective_tax_pct=100.0,
                    max_slippage_pct=100.0,
                    reason=f"Buy simulation failed: {buy_result.get('error', 'Unknown')}"
                )
                self.stats.simulator_blocked += 1
                return result
            
            # Simulate sell
            sell_result = await self._simulate_sell(token_address, wallet_address)
            
            if not sell_result['success']:
                result = SimulationResult(
                    success=True,
                    is_honeypot=True,
                    can_buy=True,
                    can_sell=False,
                    buy_tax_pct=buy_result.get('tax_pct', 0),
                    sell_tax_pct=100.0,
                    effective_tax_pct=100.0,
                    max_slippage_pct=100.0,
                    reason=f"HONEYPOT: Cannot sell - {sell_result.get('error', 'Unknown')}"
                )
                self.stats.simulator_blocked += 1
                return result
            
            # Calculate effective tax
            buy_tax = buy_result.get('tax_pct', 0)
            sell_tax = sell_result.get('tax_pct', 0)
            effective_tax = buy_tax + sell_tax
            
            # Determine if it's a honeypot
            is_honeypot = effective_tax > self.MAX_ACCEPTABLE_TAX
            
            if is_honeypot:
                self.stats.simulator_blocked += 1
                reason = f"High tax: {effective_tax:.1f}% (buy: {buy_tax:.1f}%, sell: {sell_tax:.1f}%)"
            else:
                self.stats.simulator_passed += 1
                reason = f"OK: {effective_tax:.1f}% total tax"
            
            result = SimulationResult(
                success=True,
                is_honeypot=is_honeypot,
                can_buy=True,
                can_sell=True,
                buy_tax_pct=buy_tax,
                sell_tax_pct=sell_tax,
                effective_tax_pct=effective_tax,
                max_slippage_pct=max(buy_result.get('slippage_pct', 0), 
                                     sell_result.get('slippage_pct', 0)),
                reason=reason
            )
            
            # Store for outcome tracking
            self.pending_outcomes[token_address] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Simulation error for {token_address}: {e}")
            self.stats.simulator_blocked += 1
            return SimulationResult(
                success=False,
                is_honeypot=True,
                can_buy=False,
                can_sell=False,
                buy_tax_pct=0,
                sell_tax_pct=0,
                effective_tax_pct=0,
                max_slippage_pct=0,
                reason=f"Simulation error: {str(e)}"
            )
    
    async def _simulate_buy(self, token_address: str, 
                            wallet_address: str = None) -> Dict[str, Any]:
        """Simulate a buy transaction."""
        try:
            # Build buy transaction
            tx = await self._build_swap_transaction(
                input_mint="So11111111111111111111111111111111111111112",  # SOL
                output_mint=token_address,
                amount=int(self.test_amount_sol * 1e9),  # Convert to lamports
                wallet=wallet_address
            )
            
            if not tx:
                return {"success": False, "error": "Failed to build transaction"}
            
            # Simulate
            result = await self._simulate_transaction(tx)
            
            if result.get("error"):
                return {"success": False, "error": result["error"]}
            
            # Calculate tax from output difference
            expected_output = result.get("expected_output", 0)
            actual_output = result.get("actual_output", 0)
            
            if expected_output > 0:
                tax_pct = ((expected_output - actual_output) / expected_output) * 100
            else:
                tax_pct = 0
            
            return {
                "success": True,
                "tax_pct": max(0, tax_pct),
                "slippage_pct": result.get("slippage_pct", 0),
                "expected_output": expected_output,
                "actual_output": actual_output
            }
            
        except Exception as e:
            logger.error(f"Buy simulation error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _simulate_sell(self, token_address: str,
                             wallet_address: str = None) -> Dict[str, Any]:
        """Simulate a sell transaction."""
        try:
            # Build sell transaction
            tx = await self._build_swap_transaction(
                input_mint=token_address,
                output_mint="So11111111111111111111111111111111111111112",  # SOL
                amount=int(1e6),  # 1 token (assuming 6 decimals)
                wallet=wallet_address
            )
            
            if not tx:
                return {"success": False, "error": "Failed to build transaction"}
            
            # Simulate
            result = await self._simulate_transaction(tx)
            
            if result.get("error"):
                return {"success": False, "error": result["error"]}
            
            # Calculate tax
            expected_output = result.get("expected_output", 0)
            actual_output = result.get("actual_output", 0)
            
            if expected_output > 0:
                tax_pct = ((expected_output - actual_output) / expected_output) * 100
            else:
                tax_pct = 0
            
            return {
                "success": True,
                "tax_pct": max(0, tax_pct),
                "slippage_pct": result.get("slippage_pct", 0)
            }
            
        except Exception as e:
            logger.error(f"Sell simulation error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _build_swap_transaction(self, input_mint: str, output_mint: str,
                                       amount: int, wallet: str = None) -> Optional[str]:
        """
        Build swap transaction using Jupiter API.
        Returns base64-encoded transaction.
        """
        try:
            # Get quote from Jupiter
            quote_url = (
                f"https://quote-api.jup.ag/v6/quote?"
                f"inputMint={input_mint}&outputMint={output_mint}&amount={amount}&slippageBps=300"
            )
            
            async with self._session.get(quote_url) as resp:
                if resp.status != 200:
                    logger.error(f"Jupiter quote error: {resp.status}")
                    return None
                quote = await resp.json()
            
            if not quote.get("outAmount"):
                return None
            
            # For simulation, we don't need actual wallet - use dummy
            wallet = wallet or "11111111111111111111111111111111"
            
            # Get swap transaction
            swap_url = "https://quote-api.jup.ag/v6/swap"
            swap_payload = {
                "quoteResponse": quote,
                "userPublicKey": wallet,
                "wrapAndUnwrapSol": True,
                "computeUnitPriceMicroLamports": 1000
            }
            
            async with self._session.post(swap_url, json=swap_payload) as resp:
                if resp.status != 200:
                    logger.error(f"Jupiter swap error: {resp.status}")
                    return None
                swap_data = await resp.json()
            
            return swap_data.get("swapTransaction")
            
        except Exception as e:
            logger.error(f"Build transaction error: {e}")
            return None
    
    async def _simulate_transaction(self, tx_base64: str) -> Dict[str, Any]:
        """
        Simulate transaction using Solana RPC.
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "simulateTransaction",
                "params": [
                    tx_base64,
                    {
                        "encoding": "base64",
                        "commitment": "confirmed",
                        "replaceRecentBlockhash": True
                    }
                ]
            }
            
            async with self._session.post(self.rpc_url, json=payload) as resp:
                result = await resp.json()
            
            if "error" in result:
                return {"error": result["error"].get("message", "Unknown error")}
            
            sim_result = result.get("result", {}).get("value", {})
            
            if sim_result.get("err"):
                return {"error": f"Simulation failed: {sim_result['err']}"}
            
            # Parse logs for output amounts
            logs = sim_result.get("logs", [])
            
            # Extract expected vs actual from logs (simplified)
            # In production, parse Program logs for swap amounts
            return {
                "success": True,
                "expected_output": 1000000,  # Placeholder
                "actual_output": 950000,     # Placeholder - 5% tax
                "slippage_pct": 0.5,
                "logs": logs
            }
            
        except Exception as e:
            logger.error(f"Simulate transaction error: {e}")
            return {"error": str(e)}
    
    # =========================================================================
    # ACCURACY TRACKING
    # =========================================================================
    
    def record_outcome(self, token_address: str, pnl: float, 
                       loss_pct: float = None) -> None:
        """
        Record actual outcome for accuracy tracking.
        Call this after trade completes or position closes.
        """
        result = self.pending_outcomes.pop(token_address, None)
        
        won = pnl > 0
        
        # Determine loss magnitude
        loss_magnitude = LossMagnitude.NONE
        if not won and loss_pct is not None:
            if loss_pct >= 90:
                loss_magnitude = LossMagnitude.RUG
            elif loss_pct >= 10:
                loss_magnitude = LossMagnitude.MODEST
            else:
                loss_magnitude = LossMagnitude.MARGINAL
        
        # Update basic stats
        if result and not result.is_honeypot:
            # We passed this signal
            if won:
                self.stats.passed_that_won += 1
            else:
                self.stats.passed_that_lost += 1
                # Track by magnitude
                if loss_magnitude == LossMagnitude.RUG:
                    self.stats.rug_missed += 1
                elif loss_magnitude == LossMagnitude.MODEST:
                    self.stats.modest_loss_missed += 1
                elif loss_magnitude == LossMagnitude.MARGINAL:
                    self.stats.marginal_loss_missed += 1
        else:
            # We blocked this signal
            if won:
                self.stats.blocked_that_would_have_won += 1
            else:
                self.stats.blocked_that_would_have_lost += 1
                # Track by magnitude
                if loss_magnitude == LossMagnitude.RUG:
                    self.stats.rug_blocked += 1
                elif loss_magnitude == LossMagnitude.MODEST:
                    self.stats.modest_loss_blocked += 1
                elif loss_magnitude == LossMagnitude.MARGINAL:
                    self.stats.marginal_loss_blocked += 1
        
        # Log accuracy periodically
        if self.stats.total_signals % 10 == 0:
            logger.info(
                f"Simulator accuracy: {self.stats.blocker_accuracy:.1%} | "
                f"Weighted: {self.stats.weighted_accuracy:.1%} | "
                f"Assassin ready: {self.stats.assassin_ready}"
            )
    
    def get_assassin_status(self) -> Tuple[bool, str]:
        """Check if Assassin can be enabled."""
        if self.stats.total_signals < 50:
            return False, f"Need 50+ signals, have {self.stats.total_signals}"
        
        accuracy = self.stats.blocker_accuracy
        if accuracy < 0.95:
            return False, f"Accuracy {accuracy:.1%} < required 95%"
        
        return True, f"Assassin READY: {accuracy:.1%} accuracy over {self.stats.total_signals} signals"
    
    def get_accuracy_report(self) -> Dict[str, Any]:
        """Get detailed accuracy report."""
        return {
            "total_signals": self.stats.total_signals,
            "blocked": self.stats.simulator_blocked,
            "passed": self.stats.simulator_passed,
            "basic_accuracy": self.stats.blocker_accuracy,
            "weighted_accuracy": self.stats.weighted_accuracy,
            "assassin_ready": self.stats.assassin_ready,
            "loss_breakdown": {
                "rugs_blocked": self.stats.rug_blocked,
                "rugs_missed": self.stats.rug_missed,
                "modest_blocked": self.stats.modest_loss_blocked,
                "modest_missed": self.stats.modest_loss_missed,
                "marginal_blocked": self.stats.marginal_loss_blocked,
                "marginal_missed": self.stats.marginal_loss_missed
            },
            "passed_that_won": self.stats.passed_that_won,
            "passed_that_lost": self.stats.passed_that_lost,
            "blocked_would_have_won": self.stats.blocked_that_would_have_won,
            "blocked_would_have_lost": self.stats.blocked_that_would_have_lost
        }


# Quick simulation function for CLI use
async def quick_honeypot_check(token_address: str, 
                                rpc_url: str = "https://api.mainnet-beta.solana.com"
                               ) -> SimulationResult:
    """Quick honeypot check for a single token."""
    simulator = TransactionSimulator(rpc_url)
    await simulator.start()
    try:
        result = await simulator.full_honeypot_check(token_address)
        return result
    finally:
        await simulator.stop()
