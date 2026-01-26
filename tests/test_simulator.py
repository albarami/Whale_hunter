#!/usr/bin/env python3
"""
Tests for the Transaction Simulator module.
"""

import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.simulator import (
    TransactionSimulator, 
    SimulationResult, 
    SimulatorAccuracyStats,
    LossMagnitude
)


class TestSimulatorAccuracyStats(unittest.TestCase):
    """Tests for SimulatorAccuracyStats."""
    
    def test_blocker_accuracy_no_losers(self):
        """Test blocker accuracy with no losers."""
        stats = SimulatorAccuracyStats()
        self.assertEqual(stats.blocker_accuracy, 0.0)
    
    def test_blocker_accuracy_all_blocked(self):
        """Test blocker accuracy when all losers blocked."""
        stats = SimulatorAccuracyStats(
            passed_that_lost=0,
            blocked_that_would_have_lost=10
        )
        self.assertEqual(stats.blocker_accuracy, 1.0)
    
    def test_blocker_accuracy_half_blocked(self):
        """Test blocker accuracy when half losers blocked."""
        stats = SimulatorAccuracyStats(
            passed_that_lost=5,
            blocked_that_would_have_lost=5
        )
        self.assertEqual(stats.blocker_accuracy, 0.5)
    
    def test_assassin_not_ready_insufficient_signals(self):
        """Test assassin not ready with insufficient signals."""
        stats = SimulatorAccuracyStats(
            total_signals=30,
            blocked_that_would_have_lost=30
        )
        self.assertFalse(stats.assassin_ready)
    
    def test_assassin_ready_when_criteria_met(self):
        """Test assassin ready when all criteria met."""
        stats = SimulatorAccuracyStats(
            total_signals=60,
            passed_that_lost=1,
            blocked_that_would_have_lost=20
        )
        # 20/21 = 95.2% > 95%
        self.assertTrue(stats.assassin_ready)
    
    def test_weighted_accuracy(self):
        """Test weighted accuracy calculation."""
        stats = SimulatorAccuracyStats(
            rug_blocked=5,
            rug_missed=0,
            modest_loss_blocked=3,
            modest_loss_missed=1,
            marginal_loss_blocked=2,
            marginal_loss_missed=2
        )
        # Rugs: 5 blocked * 3.0 = 15, total = 15
        # Modest: 3 blocked * 1.5 = 4.5, total = 6
        # Marginal: 2 blocked * 1.0 = 2, total = 4
        # Total weighted blocked: 15 + 4.5 + 2 = 21.5
        # Total weighted losers: 15 + 6 + 4 = 25
        expected = 21.5 / 25
        self.assertAlmostEqual(stats.weighted_accuracy, expected, places=2)


class TestSimulationResult(unittest.TestCase):
    """Tests for SimulationResult."""
    
    def test_honeypot_detection(self):
        """Test that honeypot is correctly detected."""
        result = SimulationResult(
            success=True,
            is_honeypot=True,
            can_buy=True,
            can_sell=False,
            buy_tax_pct=0,
            sell_tax_pct=100,
            effective_tax_pct=100,
            max_slippage_pct=0,
            reason="Cannot sell"
        )
        
        self.assertTrue(result.is_honeypot)
        self.assertTrue(result.can_buy)
        self.assertFalse(result.can_sell)
    
    def test_high_tax_detection(self):
        """Test that high tax is detected as honeypot."""
        result = SimulationResult(
            success=True,
            is_honeypot=True,
            can_buy=True,
            can_sell=True,
            buy_tax_pct=15,
            sell_tax_pct=10,
            effective_tax_pct=25,
            max_slippage_pct=5,
            reason="High tax: 25%"
        )
        
        self.assertTrue(result.is_honeypot)
        self.assertEqual(result.effective_tax_pct, 25)


class TestTransactionSimulator(unittest.TestCase):
    """Tests for TransactionSimulator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TransactionSimulator(
            rpc_url="https://api.mainnet-beta.solana.com",
            test_amount_sol=0.01
        )
    
    def test_initialization(self):
        """Test simulator initialization."""
        self.assertEqual(self.simulator.test_amount_sol, 0.01)
        self.assertIsInstance(self.simulator.stats, SimulatorAccuracyStats)
    
    def test_record_outcome_win(self):
        """Test recording a winning outcome."""
        # Simulate a passed signal
        self.simulator.pending_outcomes["token1"] = SimulationResult(
            success=True, is_honeypot=False, can_buy=True, can_sell=True,
            buy_tax_pct=1, sell_tax_pct=1, effective_tax_pct=2,
            max_slippage_pct=1, reason="OK"
        )
        
        # Record win
        self.simulator.record_outcome("token1", pnl=50.0, loss_pct=0)
        
        self.assertEqual(self.simulator.stats.passed_that_won, 1)
        self.assertEqual(self.simulator.stats.passed_that_lost, 0)
    
    def test_record_outcome_rug_loss(self):
        """Test recording a rug pull loss."""
        # Simulate a passed signal that turned out to be a rug
        self.simulator.pending_outcomes["token2"] = SimulationResult(
            success=True, is_honeypot=False, can_buy=True, can_sell=True,
            buy_tax_pct=1, sell_tax_pct=1, effective_tax_pct=2,
            max_slippage_pct=1, reason="OK"
        )
        
        # Record rug loss
        self.simulator.record_outcome("token2", pnl=-100.0, loss_pct=95)
        
        self.assertEqual(self.simulator.stats.passed_that_lost, 1)
        self.assertEqual(self.simulator.stats.rug_missed, 1)
    
    def test_assassin_status_not_ready(self):
        """Test assassin status when not ready."""
        ready, message = self.simulator.get_assassin_status()
        
        self.assertFalse(ready)
        self.assertIn("Need 50+ signals", message)
    
    def test_accuracy_report(self):
        """Test accuracy report generation."""
        report = self.simulator.get_accuracy_report()
        
        self.assertIn("total_signals", report)
        self.assertIn("blocked", report)
        self.assertIn("passed", report)
        self.assertIn("assassin_ready", report)
        self.assertIn("loss_breakdown", report)


class TestLossMagnitude(unittest.TestCase):
    """Tests for LossMagnitude enum."""
    
    def test_loss_magnitude_values(self):
        """Test loss magnitude enum values."""
        self.assertEqual(LossMagnitude.RUG.value, "RUG")
        self.assertEqual(LossMagnitude.MODEST.value, "MODEST")
        self.assertEqual(LossMagnitude.MARGINAL.value, "MARGINAL")
        self.assertEqual(LossMagnitude.NONE.value, "NONE")


class TestAsyncSimulator(unittest.IsolatedAsyncioTestCase):
    """Async tests for TransactionSimulator."""
    
    async def test_start_stop(self):
        """Test starting and stopping the simulator."""
        simulator = TransactionSimulator(
            rpc_url="https://api.mainnet-beta.solana.com"
        )
        
        await simulator.start()
        self.assertIsNotNone(simulator._session)
        
        await simulator.stop()
        self.assertIsNone(simulator._session)


if __name__ == "__main__":
    unittest.main()
