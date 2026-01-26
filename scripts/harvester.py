#!/usr/bin/env python3
"""
V3.1 Harvester Script - Winner Reverse Search (Sybil Hunter)

This script:
1. Finds tokens that 10x'd in the past 24-48 hours
2. Extracts first 50 buyers of each winning token
3. Traces funding sources for each buyer
4. Filters out CEX-funded wallets
5. Builds wallet graph with funding relationships

Usage:
    python scripts/harvester.py [--days DAYS] [--min-gain MIN_GAIN]
    
    --days: Look back period (default: 2)
    --min-gain: Minimum gain multiplier (default: 10.0)
    
Example:
    python scripts/harvester.py --days 7 --min-gain 5.0
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv("config/.env")

from src.database import WalletGraphDB
from src.wallet_tracker import WalletTracker
from src.api_clients import HeliusClient, BirdEyeClient, SolscanClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WinnerHarvester:
    """
    Harvests winning tokens and traces early buyers.
    Core component of the Sybil Hunter (HEAD 1).
    """
    
    def __init__(self, db: WalletGraphDB, tracker: WalletTracker):
        self.db = db
        self.tracker = tracker
        
        # Initialize API clients
        self.helius = HeliusClient()
        self.birdeye = BirdEyeClient()
        self.solscan = SolscanClient()
        
        # Stats
        self.tokens_processed = 0
        self.wallets_harvested = 0
        self.funding_relations_found = 0
        self.cex_funded_skipped = 0
    
    async def start(self):
        """Initialize API clients."""
        await self.helius.start()
        await self.birdeye.start()
        await self.solscan.start()
        logger.info("API clients initialized")
    
    async def stop(self):
        """Clean up API clients."""
        await self.helius.stop()
        await self.birdeye.stop()
        await self.solscan.stop()
    
    async def find_winning_tokens(self, days: int = 2, 
                                   min_gain: float = 10.0) -> List[Dict]:
        """
        Find tokens that gained significantly in the past N days.
        
        Returns list of token info dicts.
        """
        logger.info(f"Searching for {min_gain}x+ tokens in past {days} days...")
        
        # In production, this would query BirdEye or similar API
        # For now, we'll return empty - user can manually add tokens
        
        # Placeholder: In real implementation, use BirdEye trending API
        # or scan DEXScreener/similar for big movers
        
        winners = []
        
        # Example: Get trending tokens from BirdEye
        # This is a placeholder - actual implementation depends on API availability
        
        logger.info(f"Found {len(winners)} winning tokens")
        return winners
    
    async def harvest_token_buyers(self, token_address: str, 
                                    min_gain: float = 10.0,
                                    max_buyers: int = 50) -> Dict:
        """
        Harvest early buyers for a specific token.
        
        Args:
            token_address: Token mint address
            min_gain: Minimum gain to qualify as "winner"
            max_buyers: Maximum number of early buyers to trace
            
        Returns:
            Harvest results dict
        """
        logger.info(f"Harvesting buyers for token {token_address[:8]}...")
        
        results = {
            "token": token_address,
            "buyers_found": 0,
            "wallets_added": 0,
            "funding_traced": 0,
            "cex_skipped": 0
        }
        
        try:
            # Get early trades for this token
            trades = await self.birdeye.get_recent_trades(token_address, limit=200)
            
            if not trades:
                logger.warning(f"No trades found for {token_address[:8]}")
                return results
            
            # Sort by timestamp to get earliest buyers
            trades.sort(key=lambda x: x.get("blockUnixTime", 0))
            
            # Get unique buyers
            seen_wallets = set()
            early_buyers = []
            
            for trade in trades:
                wallet = trade.get("owner") or trade.get("source")
                if not wallet or wallet in seen_wallets:
                    continue
                
                seen_wallets.add(wallet)
                early_buyers.append({
                    "wallet": wallet,
                    "timestamp": datetime.fromtimestamp(trade.get("blockUnixTime", 0)),
                    "amount": trade.get("tokenAmount", 0),
                    "tx": trade.get("txHash", "")
                })
                
                if len(early_buyers) >= max_buyers:
                    break
            
            results["buyers_found"] = len(early_buyers)
            logger.info(f"Found {len(early_buyers)} early buyers")
            
            # Process each buyer
            for buyer in early_buyers:
                wallet = buyer["wallet"]
                
                # Add wallet to database
                self.db.add_wallet(wallet)
                results["wallets_added"] += 1
                
                # Record the buy
                self.db.add_buy(
                    wallet=wallet,
                    token=token_address,
                    amount=buyer["amount"],
                    price=0,  # Would need price at time of buy
                    timestamp=buyer["timestamp"]
                )
                
                # Trace funding source
                funding = await self._trace_funding_source(wallet)
                
                if funding:
                    # Check if CEX-funded
                    is_cex, cex_name = self.tracker.is_cex_wallet(funding["funder"])
                    
                    if is_cex:
                        logger.debug(f"  {wallet[:8]}: CEX-funded ({cex_name}), skipping")
                        self.db.mark_cex_funded(wallet, cex_name)
                        results["cex_skipped"] += 1
                        self.cex_funded_skipped += 1
                    else:
                        # Add funding relationship
                        self.db.add_funding_relationship(
                            funder=funding["funder"],
                            funded=wallet,
                            amount=funding["amount"],
                            timestamp=funding["timestamp"],
                            tx_hash=funding["tx_hash"]
                        )
                        results["funding_traced"] += 1
                        self.funding_relations_found += 1
                        logger.debug(f"  {wallet[:8]}: Funded by {funding['funder'][:8]}")
            
            self.tokens_processed += 1
            self.wallets_harvested += results["wallets_added"]
            
            return results
            
        except Exception as e:
            logger.error(f"Error harvesting {token_address[:8]}: {e}")
            return results
    
    async def _trace_funding_source(self, wallet: str) -> Optional[Dict]:
        """
        Trace the funding source for a wallet.
        Returns the primary SOL transfer that funded this wallet.
        """
        try:
            # Get SOL transfers to this wallet
            transfers = await self.solscan.get_account_sol_transfers(wallet, limit=20)
            
            if not transfers:
                return None
            
            # Find significant incoming transfer (likely initial funding)
            for transfer in transfers:
                # Check if this is an incoming transfer
                if transfer.get("dst") == wallet:
                    amount = transfer.get("lamport", 0) / 1e9  # Convert to SOL
                    
                    # Only consider significant funding (>0.05 SOL)
                    if amount >= 0.05:
                        return {
                            "funder": transfer.get("src"),
                            "amount": amount,
                            "timestamp": datetime.fromtimestamp(transfer.get("blockTime", 0)),
                            "tx_hash": transfer.get("txHash", "")
                        }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error tracing funding for {wallet[:8]}: {e}")
            return None
    
    async def run_harvest(self, days: int = 2, min_gain: float = 10.0,
                          tokens: List[str] = None) -> Dict:
        """
        Run full harvest operation.
        
        Args:
            days: Look back period
            min_gain: Minimum gain multiplier
            tokens: Optional list of specific tokens to harvest
        """
        logger.info("="*60)
        logger.info("STARTING HARVEST OPERATION")
        logger.info("="*60)
        
        start_time = datetime.utcnow()
        
        # Reset stats
        self.tokens_processed = 0
        self.wallets_harvested = 0
        self.funding_relations_found = 0
        self.cex_funded_skipped = 0
        
        if tokens:
            # Harvest specific tokens
            for token in tokens:
                await self.harvest_token_buyers(token, min_gain)
                await asyncio.sleep(1)  # Rate limiting
        else:
            # Find and harvest winning tokens
            winners = await self.find_winning_tokens(days, min_gain)
            
            for winner in winners:
                await self.harvest_token_buyers(winner["address"], min_gain)
                await asyncio.sleep(1)  # Rate limiting
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        results = {
            "tokens_processed": self.tokens_processed,
            "wallets_harvested": self.wallets_harvested,
            "funding_relations": self.funding_relations_found,
            "cex_skipped": self.cex_funded_skipped,
            "duration_seconds": duration
        }
        
        logger.info("="*60)
        logger.info("HARVEST COMPLETE")
        logger.info(f"  Tokens processed: {results['tokens_processed']}")
        logger.info(f"  Wallets harvested: {results['wallets_harvested']}")
        logger.info(f"  Funding relations: {results['funding_relations']}")
        logger.info(f"  CEX-funded skipped: {results['cex_skipped']}")
        logger.info(f"  Duration: {duration:.1f}s")
        logger.info("="*60)
        
        return results


async def main():
    parser = argparse.ArgumentParser(description="Harvest winning tokens and trace buyers")
    parser.add_argument("--days", type=int, default=2, help="Look back period in days")
    parser.add_argument("--min-gain", type=float, default=10.0, help="Minimum gain multiplier")
    parser.add_argument("--tokens", nargs="+", help="Specific tokens to harvest")
    parser.add_argument("--db", default="data/wallet_graph.db", help="Database path")
    args = parser.parse_args()
    
    # Initialize
    db = WalletGraphDB(args.db)
    tracker = WalletTracker(db)
    harvester = WinnerHarvester(db, tracker)
    
    try:
        await harvester.start()
        
        if args.tokens:
            logger.info(f"Harvesting {len(args.tokens)} specific tokens...")
            await harvester.run_harvest(
                days=args.days,
                min_gain=args.min_gain,
                tokens=args.tokens
            )
        else:
            # Interactive mode
            print("\n" + "="*60)
            print("WINNER HARVESTER - Interactive Mode")
            print("="*60)
            print("\nEnter token addresses to harvest (one per line).")
            print("Type 'done' when finished, or 'quit' to exit.\n")
            
            tokens = []
            while True:
                user_input = input("> ").strip()
                
                if user_input.lower() == 'quit':
                    break
                elif user_input.lower() == 'done':
                    if tokens:
                        await harvester.run_harvest(
                            days=args.days,
                            min_gain=args.min_gain,
                            tokens=tokens
                        )
                    tokens = []
                    print("\nEnter more tokens or 'quit' to exit:\n")
                elif len(user_input) > 30:  # Looks like a token address
                    tokens.append(user_input)
                    print(f"  Added: {user_input[:16]}... ({len(tokens)} queued)")
        
        # Show final stats
        stats = db.get_stats()
        print(f"\nDatabase Stats:")
        print(f"  Total wallets: {stats['total_wallets']}")
        print(f"  Mother wallets: {stats['mother_wallet_count']}")
        
    finally:
        await harvester.stop()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
