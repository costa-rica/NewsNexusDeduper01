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
from metrics.text_hash import ContentHashProcessor
from metrics.embeddings import EmbeddingProcessor
from db import DatabaseManager
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

    # Content Hash command
    contenthash_parser = subparsers.add_parser('contenthash', help='Compute content hash similarity scores')
    contenthash_parser.add_argument('--force', action='store_true', help='Recompute all content hash scores, even existing ones')

    # Embedding Search command
    embeddingsearch_parser = subparsers.add_parser('embeddingsearch', help='Compute semantic embedding similarity scores')
    embeddingsearch_parser.add_argument('--force', action='store_true', help='Recompute all embedding scores, even existing ones')
    embeddingsearch_parser.add_argument('--model', type=str, default='all-MiniLM-L6-v2', help='Sentence transformer model name (default: all-MiniLM-L6-v2)')
    embeddingsearch_parser.add_argument('--batch-size', type=int, default=500, help='Batch size for processing (default: 500)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        config = Config()
        pair_indexer = PairIndexer(config)
        db_manager = DatabaseManager(config)

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

            # Add content hash status
            content_processor = ContentHashProcessor(db_manager)
            content_stats = content_processor.get_content_hash_stats()
            completion_pct = (content_stats['content_hash_completed'] * 100) // content_stats['total_pairs'] if content_stats['total_pairs'] > 0 else 0
            match_pct = (content_stats['matching_content'] * 100) // content_stats['content_hash_completed'] if content_stats['content_hash_completed'] > 0 else 0
            print(f"Content hash completed: {content_stats['content_hash_completed']} ({completion_pct}%)")
            print(f"Content matches found: {content_stats['matching_content']} ({match_pct}%)")

            # Add embedding search status
            try:
                embedding_processor = EmbeddingProcessor(db_manager)
                embedding_stats = embedding_processor.get_embedding_search_stats()
                embedding_completion_pct = (embedding_stats['embedding_search_completed'] * 100) // embedding_stats['total_pairs'] if embedding_stats['total_pairs'] > 0 else 0
                avg_score = embedding_stats['avg_similarity_score']
                print(f"Embedding search completed: {embedding_stats['embedding_search_completed']} ({embedding_completion_pct}%)")
                print(f"High similarity pairs (>0.8): {embedding_stats['high_similarity_pairs']}")
                print(f"Average similarity score: {avg_score:.3f}")
            except ImportError:
                print("Embedding search: Not available (sentence-transformers not installed)")

        elif args.command == 'urlcheck':
            url_service = URLCheckService(config)

            with timer("Computing URL similarity scores"):
                result = url_service.compute_url_check_scores(
                    batch_size=args.batch_size,
                    force=args.force
                )
                print(f"Processed {result['processed_pairs']} pairs")
                print(f"Found {result['url_matches_found']} URL matches ({result['match_rate']}% match rate)")

        elif args.command == 'contenthash':
            content_processor = ContentHashProcessor(db_manager)

            if args.force:
                # Reset all contentHash values to NULL for recomputation
                with timer("Resetting content hash values"):
                    reset_query = "UPDATE ArticleDuplicateRatings SET contentHash = NULL WHERE contentHash IS NOT NULL"
                    reset_count = db_manager.execute_update(reset_query)
                    print(f"Reset {reset_count} existing content hash values for recomputation")

            # Process all pending content hash computations
            total_processed = 0
            total_matches = 0

            with timer("Computing content hash similarity scores"):
                while True:
                    batch_result = content_processor.process_content_hash_batch(batch_size=1000)

                    if batch_result['processed'] == 0:
                        break

                    total_processed += batch_result['processed']
                    total_matches += batch_result['matches']

                    print(f"Batch: {batch_result['processed']} processed, {batch_result['matches']} matches, {batch_result['errors']} errors")

                print(f"Total processed: {total_processed} pairs")
                print(f"Total matches found: {total_matches} ({(total_matches * 100) // total_processed if total_processed > 0 else 0}% match rate)")

        elif args.command == 'embeddingsearch':
            try:
                embedding_processor = EmbeddingProcessor(db_manager, model_name=args.model)
            except ImportError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

            if args.force:
                # Reset all embeddingSearch values to NULL for recomputation
                with timer("Resetting embedding search values"):
                    reset_query = "UPDATE ArticleDuplicateRatings SET embeddingSearch = NULL WHERE embeddingSearch IS NOT NULL"
                    reset_count = db_manager.execute_update(reset_query)
                    print(f"Reset {reset_count} existing embedding search values for recomputation")

            # Process all pending embedding search computations with progress bars
            with timer("Computing embedding similarity scores"):
                result = embedding_processor.process_all_embedding_search(batch_size=args.batch_size)

                if result['total_processed'] == 0:
                    print("No pending embedding computations found")
                else:
                    print(f"Total processed: {result['total_processed']} pairs")
                    print(f"High similarity pairs (>0.8): {result['total_high_similarity']} ({(result['total_high_similarity'] * 100) // result['total_processed'] if result['total_processed'] > 0 else 0}%)")
                    print(f"Average similarity score: {result['overall_avg_similarity']:.3f}")
                    print(f"Batches completed: {result['batches_completed']}")
                    print(f"Final embedding cache size: {result['final_cache_size']} unique articles")
                    if result['total_errors'] > 0:
                        print(f"Errors encountered: {result['total_errors']}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())