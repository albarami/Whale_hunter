#!/usr/bin/env python3
"""
V3.1 Bootstrap Script - System Initialization

This script:
1. Creates necessary directories
2. Initializes the SQLite database
3. Loads CEX blacklist
4. Validates API configuration
5. Sets up initial system state

Usage:
    python scripts/bootstrap.py [--config CONFIG_PATH]
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import yaml

from src.database import WalletGraphDB
from src.wallet_tracker import WalletTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_directories():
    """Create necessary directories."""
    directories = [
        "data",
        "logs",
        "config",
    ]
    
    for dir_name in directories:
        path = Path(dir_name)
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"✓ Directory: {path}")
    
    # Create .gitkeep files
    for dir_name in ["data", "logs"]:
        gitkeep = Path(dir_name) / ".gitkeep"
        gitkeep.touch(exist_ok=True)


def load_environment():
    """Load environment variables."""
    env_file = Path("config/.env")
    
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f"✓ Loaded environment from {env_file}")
    else:
        # Try .env in root
        if Path(".env").exists():
            load_dotenv()
            logger.info("✓ Loaded environment from .env")
        else:
            logger.warning("⚠ No .env file found. Copy config/.env.example to config/.env")


def validate_api_keys():
    """Validate required API keys."""
    required_keys = {
        "HELIUS_API_KEY": "Helius (https://www.helius.dev/)",
        "BIRDEYE_API_KEY": "BirdEye (https://birdeye.so/api)",
    }
    
    optional_keys = {
        "SOLSCAN_API_KEY": "Solscan (https://solscan.io/apis)",
    }
    
    all_valid = True
    
    logger.info("\nValidating API keys...")
    
    for key, description in required_keys.items():
        value = os.getenv(key)
        if value and len(value) > 10:
            logger.info(f"✓ {key}: configured")
        else:
            logger.error(f"✗ {key}: MISSING - Get from {description}")
            all_valid = False
    
    for key, description in optional_keys.items():
        value = os.getenv(key)
        if value and len(value) > 10:
            logger.info(f"✓ {key}: configured (optional)")
        else:
            logger.info(f"○ {key}: not configured (optional)")
    
    return all_valid


def initialize_database(db_path: str = "data/wallet_graph.db"):
    """Initialize SQLite database."""
    logger.info(f"\nInitializing database at {db_path}...")
    
    db = WalletGraphDB(db_path)
    
    # Set initial system state
    initial_capital = float(os.getenv("INITIAL_CAPITAL_USD", "500"))
    db.set_state("current_capital", initial_capital)
    db.set_state("peak_capital", initial_capital)
    db.set_state("risk_mode", "NORMAL")
    db.set_state("system_phase", 0)
    db.set_state("initialized_at", datetime.utcnow().isoformat())
    
    stats = db.get_stats()
    logger.info(f"✓ Database initialized")
    logger.info(f"  - Wallets: {stats['total_wallets']}")
    logger.info(f"  - Signals: {stats['total_signals']}")
    logger.info(f"  - Trades: {stats['total_trades']}")
    logger.info(f"  - Initial capital: ${initial_capital}")
    
    db.close()
    return True


def load_cex_blacklist():
    """Load and validate CEX blacklist."""
    blacklist_path = Path("config/cex_blacklist.yaml")
    
    if not blacklist_path.exists():
        logger.warning(f"⚠ CEX blacklist not found at {blacklist_path}")
        return False
    
    try:
        with open(blacklist_path, 'r') as f:
            data = yaml.safe_load(f)
        
        total_wallets = 0
        for chain, exchanges in data.items():
            if isinstance(exchanges, dict):
                for exchange, wallets in exchanges.items():
                    if isinstance(wallets, list):
                        total_wallets += len(wallets)
        
        logger.info(f"✓ CEX blacklist loaded: {total_wallets} known CEX wallets")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error loading CEX blacklist: {e}")
        return False


def validate_config():
    """Validate main configuration file."""
    config_path = Path("config/settings.yaml")
    
    if not config_path.exists():
        logger.warning(f"⚠ Config not found at {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate required sections
        required_sections = [
            "system",
            "signal_freshness",
            "risk",
            "confidence",
            "first_50_trades",
            "kill_switch"
        ]
        
        missing = [s for s in required_sections if s not in config]
        
        if missing:
            logger.warning(f"⚠ Missing config sections: {missing}")
            return False
        
        logger.info(f"✓ Configuration validated")
        logger.info(f"  - System phase: {config.get('system', {}).get('current_phase', 0)}")
        logger.info(f"  - Mode: {config.get('system', {}).get('mode', 'shadow')}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error validating config: {e}")
        return False


def print_status_summary():
    """Print system status summary."""
    print("\n" + "="*60)
    print("V3.1 'DARK FOREST' SYSTEM STATUS")
    print("="*60)
    
    # Load current state
    db = WalletGraphDB("data/wallet_graph.db")
    stats = db.get_stats()
    
    current_capital = db.get_state("current_capital", 500)
    system_phase = db.get_state("system_phase", 0)
    risk_mode = db.get_state("risk_mode", "NORMAL")
    
    print(f"""
System Phase: {system_phase} ({'Paper Trading' if system_phase == 0 else 'Live'})
Risk Mode: {risk_mode}
Current Capital: ${current_capital:.2f}

Database Stats:
  - Tracked Wallets: {stats['total_wallets']}
  - Logged Signals: {stats['total_signals']}
  - Total Trades: {stats['total_trades']}
  - Total PnL: ${stats['total_pnl']:.2f}
  - Mother Wallets: {stats['mother_wallet_count']}

Next Steps:
  1. Run 'python scripts/phase0_logger.py' to start logging signals
  2. Run 'python scripts/harvester.py' to harvest winner wallets
  3. Run 'python scripts/god_view.py' to generate Black Book
""")
    
    db.close()


def main():
    parser = argparse.ArgumentParser(description="Initialize V3.1 Whale Hunter system")
    parser.add_argument("--config", default="config/settings.yaml", help="Config file path")
    parser.add_argument("--db", default="data/wallet_graph.db", help="Database path")
    parser.add_argument("--skip-api-check", action="store_true", help="Skip API key validation")
    args = parser.parse_args()
    
    print("="*60)
    print("V3.1 'DARK FOREST' BOOTSTRAP")
    print("="*60)
    
    # Step 1: Create directories
    logger.info("\n[1/5] Creating directories...")
    create_directories()
    
    # Step 2: Load environment
    logger.info("\n[2/5] Loading environment...")
    load_environment()
    
    # Step 3: Validate API keys
    if not args.skip_api_check:
        logger.info("\n[3/5] Validating API keys...")
        api_valid = validate_api_keys()
        if not api_valid:
            logger.warning("\n⚠ Some API keys are missing. The system will have limited functionality.")
    else:
        logger.info("\n[3/5] Skipping API key validation...")
    
    # Step 4: Initialize database
    logger.info("\n[4/5] Initializing database...")
    initialize_database(args.db)
    
    # Step 5: Validate configuration
    logger.info("\n[5/5] Validating configuration...")
    config_valid = validate_config()
    cex_valid = load_cex_blacklist()
    
    # Print summary
    print_status_summary()
    
    print("="*60)
    print("BOOTSTRAP COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
