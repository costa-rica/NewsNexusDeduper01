"""
URL Check Service for NewsNexus Deduper

Computes URL similarity scores by canonicalizing URLs and checking for exact matches.
Populates the urlCheck column in ArticleDuplicateRatings table.
"""

from typing import Dict, List, Tuple, Any

from config import Config
from db import DatabaseManager
from utils.canonical_url import URLCanonicalizer
from utils.timing import timer


class URLCheckService:
    """Service for computing URL similarity scores"""

    def __init__(self, config: Config):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.canonicalizer = URLCanonicalizer()

    def compute_url_check_scores(self, batch_size: int = 1000, force: bool = False) -> Dict[str, int]:
        """
        Compute URL check scores for all article pairs.

        Args:
            batch_size: Number of pairs to process at once
            force: If True, recompute even if urlCheck already exists

        Returns:
            Dictionary with processing statistics
        """
        print("Computing URL check scores...")

        if force:
            print("Force mode: clearing existing URL check scores")
            self._clear_url_check_scores()

        total_processed = 0
        total_matches = 0
        batch_count = 0

        while True:
            # Get batch of article pairs that need URL checking
            if force:
                pairs = self._get_all_pairs_batch(batch_size, batch_count * batch_size)
            else:
                pairs = self.db_manager.get_articles_for_url_check(batch_size)

            if not pairs:
                break

            batch_count += 1
            print(f"Processing batch #{batch_count} ({len(pairs)} pairs)")

            # Compute URL check scores for this batch
            url_check_updates = []
            batch_matches = 0

            for pair in pairs:
                url_check_score = self._compute_url_similarity(pair['urlNew'], pair['urlApproved'])
                url_check_updates.append((url_check_score, pair['id']))

                if url_check_score == 1.0:
                    batch_matches += 1

            # Update database with batch results
            if url_check_updates:
                updated_count = self.db_manager.update_url_check_batch(url_check_updates)
                total_processed += updated_count
                total_matches += batch_matches

                print(f"Updated {updated_count} pairs, found {batch_matches} URL matches in this batch")

            # Progress report every 10 batches
            if batch_count % 10 == 0:
                print(f"Progress: {total_processed} pairs processed, {total_matches} total matches found")

        # Final statistics
        stats = {
            "processed_pairs": total_processed,
            "url_matches_found": total_matches,
            "match_rate": round(total_matches / total_processed * 100, 2) if total_processed > 0 else 0
        }

        print(f"URL check completed: {total_processed} pairs processed, {total_matches} matches ({stats['match_rate']}%)")

        return stats

    def _compute_url_similarity(self, url1: str, url2: str) -> float:
        """
        Compute URL similarity score (0.0 or 1.0 for exact match after canonicalization).

        Args:
            url1: First URL
            url2: Second URL

        Returns:
            1.0 if URLs match after canonicalization, 0.0 otherwise
        """
        try:
            # Handle None/null URLs
            if not url1 or not url2:
                return 0.0

            # Use canonicalizer to check if URLs match
            if self.canonicalizer.urls_match(url1, url2):
                return 1.0
            else:
                return 0.0

        except Exception as e:
            # Log error but don't fail the batch
            print(f"Warning: Error comparing URLs '{url1}' and '{url2}': {e}")
            return 0.0

    def _get_all_pairs_batch(self, batch_size: int, offset: int) -> List:
        """Get all article pairs for force mode (ignoring existing urlCheck values)"""
        query = """
        SELECT
            adr.id,
            adr.articleIdNew,
            adr.articleIdApproved,
            a1.url as urlNew,
            a2.url as urlApproved
        FROM ArticleDuplicateRatings adr
        JOIN Articles a1 ON a1.id = adr.articleIdNew
        JOIN Articles a2 ON a2.id = adr.articleIdApproved
        LIMIT ? OFFSET ?
        """
        return self.db_manager.execute_query(query, (batch_size, offset))

    def _clear_url_check_scores(self) -> int:
        """Clear all existing URL check scores"""
        query = "UPDATE ArticleDuplicateRatings SET urlCheck = NULL, updatedAt = datetime('now')"
        return self.db_manager.execute_update(query)

    def get_url_check_status(self) -> Dict[str, Any]:
        """
        Get current URL check processing status and statistics.

        Returns:
            Dictionary with status information
        """
        stats = self.db_manager.get_url_check_stats()

        # Add percentage calculations
        if stats['total_pairs'] > 0:
            stats['completion_percentage'] = round(stats['url_check_completed'] / stats['total_pairs'] * 100, 1)
            if stats['url_check_completed'] > 0:
                stats['match_percentage'] = round(stats['matching_urls'] / stats['url_check_completed'] * 100, 1)
            else:
                stats['match_percentage'] = 0.0
        else:
            stats['completion_percentage'] = 0.0
            stats['match_percentage'] = 0.0

        return stats

    def sample_url_comparisons(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get a sample of URL comparisons for debugging/validation.

        Args:
            limit: Number of samples to return

        Returns:
            List of dictionaries with URL comparison details
        """
        query = """
        SELECT
            adr.articleIdNew,
            adr.articleIdApproved,
            adr.urlCheck,
            a1.url as urlNew,
            a2.url as urlApproved
        FROM ArticleDuplicateRatings adr
        JOIN Articles a1 ON a1.id = adr.articleIdNew
        JOIN Articles a2 ON a2.id = adr.articleIdApproved
        WHERE adr.urlCheck IS NOT NULL
        ORDER BY adr.urlCheck DESC, adr.id
        LIMIT ?
        """
        rows = self.db_manager.execute_query(query, (limit,))

        samples = []
        for row in rows:
            sample = {
                'articleIdNew': row['articleIdNew'],
                'articleIdApproved': row['articleIdApproved'],
                'urlCheck': row['urlCheck'],
                'urlNew': row['urlNew'],
                'urlApproved': row['urlApproved'],
                'canonicalNew': self.canonicalizer.canonicalize_url(row['urlNew']),
                'canonicalApproved': self.canonicalizer.canonicalize_url(row['urlApproved'])
            }
            samples.append(sample)

        return samples

    def validate_url_processing(self) -> bool:
        """
        Validate that URL processing is working correctly.

        Returns:
            True if validation passes
        """
        try:
            # Test URL canonicalization
            test_cases = [
                ("https://example.com", "http://www.example.com/", True),
                ("https://example.com/article", "https://example.com/different", False),
                ("https://news.com?utm_source=google", "https://news.com", True)
            ]

            for url1, url2, expected_match in test_cases:
                actual_match = self.canonicalizer.urls_match(url1, url2)
                if actual_match != expected_match:
                    print(f"URL validation failed: {url1} vs {url2} - expected {expected_match}, got {actual_match}")
                    return False

            print("URL processing validation successful")
            return True

        except Exception as e:
            print(f"URL processing validation failed: {e}")
            return False