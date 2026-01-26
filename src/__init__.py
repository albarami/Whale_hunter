"""
V3.1 "Dark Forest" Autonomous Crypto Trading System
====================================================

A production-ready whale tracking and signal execution system.

Modules:
- database: SQLite operations with V3.1 schema
- wallet_tracker: Wallet reputation & decay
- signal_processor: Signal validation & veto system
- simulator: Honeypot simulation (simulateTransaction)
- risk_manager: Position sizing, drawdown, kill switches
- entropy: Signal entropy injection (Ghost mode)
- metrics: False positive tracking, accuracy
- api_clients: Helius, BirdEye, Solscan clients
"""

__version__ = "3.1.0"
__author__ = "Whale Hunter"
