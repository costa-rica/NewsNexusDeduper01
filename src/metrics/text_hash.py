"""
Text-based content hashing for article deduplication.

This module provides functionality to compute content hashes for articles
based on their headline and text content, enabling detection of exact or
near-duplicate textual content.
"""

import hashlib
import re
from typing import Optional, List, Tuple
import logging

from db import DatabaseManager

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent hashing by:
    - Converting to lowercase
    - Removing extra whitespace
    - Removing non-alphanumeric characters except spaces
    - Stripping leading/trailing whitespace
    """
    if not text:
        return ""

    # Convert to lowercase and remove non-alphanumeric except spaces
    normalized = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    # Collapse multiple whitespace to single space
    normalized = re.sub(r'\s+', ' ', normalized)
    # Strip leading/trailing whitespace
    return normalized.strip()


def compute_content_hash(headline: Optional[str], text: Optional[str]) -> str:
    """
    Compute a hash of the article content based on headline and text.

    Args:
        headline: Article headline
        text: Article text content

    Returns:
        SHA-256 hex digest of normalized content
    """
    # Normalize both headline and text
    norm_headline = normalize_text(headline) if headline else ""
    norm_text = normalize_text(text) if text else ""

    # Combine headline and text with separator
    combined_content = f"{norm_headline}|||{norm_text}"

    # Compute SHA-256 hash
    return hashlib.sha256(combined_content.encode('utf-8')).hexdigest()


def compute_content_hash_similarity(hash1: str, hash2: str) -> float:
    """
    Compute similarity between two content hashes.

    Args:
        hash1: First content hash
        hash2: Second content hash

    Returns:
        1.0 if hashes match exactly, 0.0 otherwise
    """
    return 1.0 if hash1 == hash2 else 0.0


class ContentHashProcessor:
    """Processes content hash metrics for article pairs"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_articles_for_content_hash(self, batch_size: int = 1000) -> List:
        """Get article pairs that need content hash checking (contentHash is NULL)"""
        query = """
        SELECT
            adr.id,
            adr.articleIdNew,
            adr.articleIdApproved,
            aa1.headlineForPdfReport as headlineNew,
            aa1.textForPdfReport as textNew,
            aa2.headlineForPdfReport as headlineApproved,
            aa2.textForPdfReport as textApproved
        FROM ArticleDuplicateRatings adr
        JOIN ArticleApproveds aa1 ON aa1.articleId = adr.articleIdNew
        JOIN ArticleApproveds aa2 ON aa2.articleId = adr.articleIdApproved
        WHERE adr.contentHash IS NULL
        LIMIT ?
        """
        return self.db.execute_query(query, (batch_size,))

    def update_content_hash_batch(self, content_hash_updates: List[Tuple[float, int]]) -> int:
        """Update contentHash values for multiple rating IDs"""
        if not content_hash_updates:
            return 0

        query = """
        UPDATE ArticleDuplicateRatings
        SET contentHash = ?, updatedAt = datetime('now')
        WHERE id = ?
        """
        return self.db.execute_many(query, content_hash_updates)

    def process_content_hash_batch(self, batch_size: int = 1000) -> dict:
        """
        Process a batch of article pairs for content hash computation.

        Args:
            batch_size: Number of pairs to process in this batch

        Returns:
            Dictionary with processing statistics
        """
        # Get articles that need content hash processing
        articles = self.get_articles_for_content_hash(batch_size)

        if not articles:
            return {
                'processed': 0,
                'matches': 0,
                'non_matches': 0,
                'errors': 0
            }

        logger.info(f"Processing content hash for {len(articles)} article pairs")

        content_hash_updates = []
        matches = 0
        errors = 0

        for article in articles:
            try:
                # Compute content hashes for both articles
                hash_new = compute_content_hash(
                    article['headlineNew'],
                    article['textNew']
                )
                hash_approved = compute_content_hash(
                    article['headlineApproved'],
                    article['textApproved']
                )

                # Compute similarity score
                similarity = compute_content_hash_similarity(hash_new, hash_approved)

                if similarity == 1.0:
                    matches += 1

                content_hash_updates.append((similarity, article['id']))

            except Exception as e:
                logger.error(f"Error processing content hash for pair {article['id']}: {e}")
                errors += 1
                # Set contentHash to 0.0 for failed comparisons
                content_hash_updates.append((0.0, article['id']))

        # Update database with results
        updated_count = self.update_content_hash_batch(content_hash_updates)

        stats = {
            'processed': len(articles),
            'matches': matches,
            'non_matches': len(articles) - matches - errors,
            'errors': errors,
            'updated_db_rows': updated_count
        }

        logger.info(f"Content hash batch completed: {stats}")
        return stats

    def get_content_hash_stats(self) -> dict:
        """Get statistics about content hash progress"""
        stats = {}

        # Total pairs
        query = "SELECT COUNT(*) as count FROM ArticleDuplicateRatings"
        result = self.db.execute_query(query)
        stats['total_pairs'] = result[0]['count']

        # Pairs with content hash completed
        query = "SELECT COUNT(*) as count FROM ArticleDuplicateRatings WHERE contentHash IS NOT NULL"
        result = self.db.execute_query(query)
        stats['content_hash_completed'] = result[0]['count']

        # Pairs pending content hash
        stats['content_hash_pending'] = stats['total_pairs'] - stats['content_hash_completed']

        # Matching content (contentHash = 1)
        query = "SELECT COUNT(*) as count FROM ArticleDuplicateRatings WHERE contentHash = 1"
        result = self.db.execute_query(query)
        stats['matching_content'] = result[0]['count']

        return stats