#!/usr/bin/env python3
"""
V3.1 God View Script - Mother Wallet Discovery

This script:
1. Runs the "God View" query to find mother wallets
2. Generates the Black Book (top wallets to monitor)
3. Ranks wallets by winning children count
4. Outputs actionable intelligence

Usage:
    python scripts/god_view.py [--min-winners MIN] [--output OUTPUT]
    
    --min-winners: Minimum winning children to qualify (default: 3)
    --output: Output file path (default: data/black_book.json)
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import WalletGraphDB
from src.wallet_tracker import WalletTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_god_view_query(db: WalletGraphDB, min_winners: int = 3) -> List[Dict]:
    """
    Run the "God View" query to find mother wallets.
    
    This is the core Sybil Hunter intelligence gathering.
    """
    logger.info(f"Running God View query (min_winners={min_winners})...")
    
    mothers = db.find_mother_wallets(min_funded_winners=min_winners)
    
    logger.info(f"Found {len(mothers)} mother wallets")
    
    return mothers


def generate_black_book(tracker: WalletTracker, min_winners: int = 3) -> List[Dict]:
    """
    Generate the Black Book - prioritized list of wallets to monitor.
    """
    logger.info("Generating Black Book...")
    
    black_book = tracker.get_black_book(min_winners=min_winners)
    
    logger.info(f"Black Book contains {len(black_book)} entries")
    
    return black_book


def print_black_book(black_book: List[Dict], limit: int = 20):
    """Print Black Book in formatted output."""
    print("\n" + "="*80)
    print("BLACK BOOK - TOP MOTHER WALLETS TO MONITOR")
    print("="*80)
    print(f"\nGenerated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Total entries: {len(black_book)}")
    print("\n" + "-"*80)
    print(f"{'Rank':<6}{'Address':<16}{'Children':<10}{'Trust':<10}{'PnL':<12}{'Last Win'}")
    print("-"*80)
    
    for entry in black_book[:limit]:
        addr = entry['address'][:14] + '..' if len(entry['address']) > 14 else entry['address']
        last_win = entry['last_win_date'][:10] if entry['last_win_date'] else 'Never'
        
        print(
            f"{entry['rank']:<6}"
            f"{addr:<16}"
            f"{entry['funded_winner_count']:<10}"
            f"{entry['trust_score']:.2f}      "
            f"${entry['total_children_pnl']:>10.2f}  "
            f"{last_win}"
        )
    
    if len(black_book) > limit:
        print(f"\n... and {len(black_book) - limit} more")
    
    print("\n" + "="*80)


def export_black_book(black_book: List[Dict], output_path: str):
    """Export Black Book to JSON file."""
    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_entries": len(black_book),
        "wallets": black_book
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Black Book exported to {output_path}")


def analyze_cluster_patterns(db: WalletGraphDB, mothers: List):
    """Analyze patterns across mother wallets."""
    print("\n" + "="*60)
    print("CLUSTER PATTERN ANALYSIS")
    print("="*60)
    
    if not mothers:
        print("\nNo mother wallets to analyze.")
        return
    
    # Collect child wallets
    all_children = set()
    children_per_mother = []
    
    for mother in mothers:
        children = set(mother.child_wallets)
        all_children.update(children)
        children_per_mother.append(len(children))
    
    print(f"\nTotal unique child wallets: {len(all_children)}")
    print(f"Average children per mother: {sum(children_per_mother)/len(children_per_mother):.1f}")
    print(f"Max children from single mother: {max(children_per_mother)}")
    
    # Check for overlapping children (shared across mothers)
    child_counts = {}
    for mother in mothers:
        for child in mother.child_wallets:
            child_counts[child] = child_counts.get(child, 0) + 1
    
    shared_children = [c for c, count in child_counts.items() if count > 1]
    print(f"\nChildren shared across mothers: {len(shared_children)}")
    
    if shared_children:
        print("\n⚠ WARNING: Shared children may indicate cluster overlap or coordination")


def main():
    parser = argparse.ArgumentParser(description="God View - Mother Wallet Discovery")
    parser.add_argument("--min-winners", type=int, default=3, 
                        help="Minimum winning children to qualify")
    parser.add_argument("--output", default="data/black_book.json",
                        help="Output file path")
    parser.add_argument("--db", default="data/wallet_graph.db",
                        help="Database path")
    parser.add_argument("--limit", type=int, default=20,
                        help="Number of entries to display")
    parser.add_argument("--no-export", action="store_true",
                        help="Don't export to file")
    args = parser.parse_args()
    
    # Initialize
    db = WalletGraphDB(args.db)
    tracker = WalletTracker(db)
    
    try:
        # Run God View query
        mothers = run_god_view_query(db, args.min_winners)
        
        # Generate Black Book
        black_book = generate_black_book(tracker, args.min_winners)
        
        # Print results
        print_black_book(black_book, limit=args.limit)
        
        # Analyze patterns
        analyze_cluster_patterns(db, mothers)
        
        # Export if requested
        if not args.no_export and black_book:
            export_black_book(black_book, args.output)
            print(f"\n✓ Black Book exported to {args.output}")
        
        # Show database stats
        stats = db.get_stats()
        print(f"\n" + "-"*40)
        print("DATABASE SUMMARY")
        print(f"-"*40)
        print(f"Total wallets tracked: {stats['total_wallets']}")
        print(f"Wallets by tier: {stats['wallets_by_tier']}")
        print(f"Total signals: {stats['total_signals']}")
        print(f"Total PnL: ${stats['total_pnl']:.2f}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
