"""
Pair Indexer Service for NewsNexus Deduper

Creates pairwise combinations of new articles from CSV with approved articles
and populates the ArticleDuplicateRatings table.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Any

from config import Config
from db import DatabaseManager
from csv_utils.load_csv import CSVLoader


class PairIndexer:
    """Service for creating article pairs and populating ArticleDuplicateRatings table"""

    def __init__(self, config: Config):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.csv_loader = CSVLoader(self.db_manager)

    def create_pairs_from_csv(self, csv_path: Path | str, force: bool = False) -> Dict[str, int]:
        """
        Load article IDs from CSV and create pairwise combinations with approved articles.

        Args:
            csv_path: Path to CSV file containing article IDs
            force: If True, recreate pairs even if they already exist

        Returns:
            Dictionary with counts: new_pairs, existing_pairs, total_pairs
        """
        if isinstance(csv_path, str):
            csv_path = Path(csv_path)

        print(f"Loading article IDs from: {csv_path}")

        # Load article IDs from CSV
        new_article_ids, invalid_ids = self.csv_loader.load_article_ids_from_csv(csv_path)

        if not new_article_ids:
            print("No valid article IDs found in CSV")
            return {"new_pairs": 0, "existing_pairs": 0, "total_pairs": 0}

        print(f"Processing {len(new_article_ids)} new article IDs")

        # Get approved article IDs
        approved_article_ids = self.db_manager.get_approved_article_ids()
        print(f"Found {len(approved_article_ids)} approved articles")

        if not approved_article_ids:
            print("No approved articles found in ArticleApproveds table")
            return {"new_pairs": 0, "existing_pairs": 0, "total_pairs": 0}

        # Check for existing pairs if not forcing
        existing_pairs_count = 0
        if not force:
            existing_pairs_count = self.db_manager.get_existing_pairs_count(new_article_ids)
            print(f"Found {existing_pairs_count} existing pairs")

        # Create pairs (cartesian product)
        pairs_to_insert = []
        total_possible_pairs = len(new_article_ids) * len(approved_article_ids)

        print(f"Creating {total_possible_pairs} article pairs...")

        for new_article_id in new_article_ids:
            for approved_article_id in approved_article_ids:
                pairs_to_insert.append((new_article_id, approved_article_id))

        # Insert pairs in batches for efficiency
        new_pairs_count = 0
        if pairs_to_insert:
            batch_size = 1000
            batches = [pairs_to_insert[i:i + batch_size] for i in range(0, len(pairs_to_insert), batch_size)]

            print(f"Inserting pairs in {len(batches)} batches of {batch_size}...")

            for i, batch in enumerate(batches, 1):
                inserted_count = self.db_manager.insert_duplicate_ratings_batch(batch)
                new_pairs_count += inserted_count

                if i % 10 == 0 or i == len(batches):  # Progress update every 10 batches
                    print(f"Processed batch {i}/{len(batches)} - inserted {new_pairs_count} new pairs so far")

        # Get final statistics
        total_pairs = self.db_manager.get_duplicate_ratings_count()
        skipped_pairs = total_possible_pairs - new_pairs_count

        result = {
            "new_pairs": new_pairs_count,
            "existing_pairs": skipped_pairs,
            "total_pairs": total_pairs,
            "csv_articles_loaded": len(new_article_ids),
            "approved_articles": len(approved_article_ids)
        }

        return result

    def reset_ratings_table(self) -> int:
        """
        Clear all data from ArticleDuplicateRatings table.

        Returns:
            Number of rows deleted
        """
        print("Clearing ArticleDuplicateRatings table...")
        deleted_count = self.db_manager.clear_duplicate_ratings()
        print(f"Deleted {deleted_count} rows")
        return deleted_count

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status and statistics.

        Returns:
            Dictionary with various counts and statistics
        """
        stats = self.db_manager.get_duplicate_ratings_stats()

        # Get approved articles count
        approved_count = len(self.db_manager.get_approved_article_ids())
        stats['approved_articles'] = approved_count

        # Estimate CSV articles loaded (unique new articles)
        stats['csv_articles_loaded'] = stats['unique_new_articles']

        return stats

    def validate_setup(self) -> bool:
        """
        Validate that the database and tables are properly set up.

        Returns:
            True if setup is valid
        """
        try:
            # Test database connection
            with self.db_manager.get_connection() as conn:
                # Check if required tables exist
                tables_query = """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('Articles', 'ArticleApproveds', 'ArticleDuplicateRatings')
                """
                cursor = conn.cursor()
                cursor.execute(tables_query)
                tables = [row[0] for row in cursor.fetchall()]

                required_tables = ['Articles', 'ArticleApproveds', 'ArticleDuplicateRatings']
                missing_tables = [table for table in required_tables if table not in tables]

                if missing_tables:
                    print(f"Missing required tables: {missing_tables}")
                    return False

                print("Database validation successful")
                return True

        except Exception as e:
            print(f"Database validation failed: {e}")
            return False