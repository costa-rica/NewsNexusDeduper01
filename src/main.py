#!/usr/bin/env python3
"""
NewsNexus Deduper - Main CLI Entry Point

This script provides a command-line interface for the NewsNexus deduplication system.
It handles loading new article IDs from CSV and creating pairwise comparisons.
"""

import argparse
import sys
from pathlib import Path

from config import Config
from services.pair_indexer import PairIndexer
from services.urlcheck import URLCheckService
from utils.timing import timer


def main():
    parser = argparse.ArgumentParser(
        description="NewsNexus Deduper - Identify potential duplicate news articles"
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Load command
    load_parser = subparsers.add_parser('load', help='Load article IDs from CSV and create pairs')
    load_parser.add_argument('--csv-path', type=str, help='Path to CSV file (overrides config)')
    load_parser.add_argument('--force', action='store_true', help='Force reload even if pairs exist')

    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Clear ArticleDuplicateRatings table')
    reset_parser.add_argument('--confirm', action='store_true', help='Confirm the reset operation')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show current status and counts')

    # URL Check command
    urlcheck_parser = subparsers.add_parser('urlcheck', help='Compute URL similarity scores')
    urlcheck_parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for processing (default: 1000)')
    urlcheck_parser.add_argument('--force', action='store_true', help='Recompute all URL scores, even existing ones')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        config = Config()
        pair_indexer = PairIndexer(config)

        if args.command == 'load':
            csv_path = args.csv_path or config.PATH_TO_CSV
            if not csv_path or not Path(csv_path).exists():
                print(f"Error: CSV file not found: {csv_path}")
                return 1

            with timer("Loading article pairs"):
                result = pair_indexer.create_pairs_from_csv(csv_path, force=args.force)
                print(f"Created {result['new_pairs']} new pairs")
                print(f"Skipped {result['existing_pairs']} existing pairs")
                print(f"Total pairs in database: {result['total_pairs']}")

        elif args.command == 'reset':
            if not args.confirm:
                print("Warning: This will delete all data in ArticleDuplicateRatings table")
                print("Use --confirm flag to proceed")
                return 1

            with timer("Resetting ArticleDuplicateRatings table"):
                deleted_count = pair_indexer.reset_ratings_table()
                print(f"Deleted {deleted_count} rows from ArticleDuplicateRatings")

        elif args.command == 'status':
            status = pair_indexer.get_status()
            print(f"ArticleDuplicateRatings rows: {status['total_pairs']}")
            print(f"Unique new articles: {status['unique_new_articles']}")
            print(f"Unique approved articles: {status['unique_approved_articles']}")
            print(f"Articles from CSV loaded: {status['csv_articles_loaded']}")

            # Add URL check status
            url_service = URLCheckService(config)
            url_status = url_service.get_url_check_status()
            print(f"URL check completed: {url_status['url_check_completed']} ({url_status['completion_percentage']}%)")
            print(f"URL matches found: {url_status['matching_urls']} ({url_status['match_percentage']}%)")

        elif args.command == 'urlcheck':
            url_service = URLCheckService(config)

            with timer("Computing URL similarity scores"):
                result = url_service.compute_url_check_scores(
                    batch_size=args.batch_size,
                    force=args.force
                )
                print(f"Processed {result['processed_pairs']} pairs")
                print(f"Found {result['url_matches_found']} URL matches ({result['match_rate']}% match rate)")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())