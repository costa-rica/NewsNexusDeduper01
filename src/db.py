"""
Database connection and helper utilities for NewsNexus Deduper

Provides SQLite connection management and common database operations.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

from config import Config


class DatabaseManager:
    """Manages SQLite database connections and operations"""

    def __init__(self, config: Config):
        self.config = config
        self.db_path = config.database_path

        # Enable WAL mode for better concurrency
        self._setup_database()

    def _setup_database(self):
        """Set up database with optimal settings"""
        with self.get_connection() as conn:
            # Enable WAL mode for better performance
            conn.execute("PRAGMA journal_mode=WAL")
            # Increase cache size
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys=ON")

    @contextmanager
    def get_connection(self):
        """Get database connection with proper cleanup"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()

    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """Execute an UPDATE/INSERT/DELETE query and return affected rows"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.rowcount

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Execute query with multiple parameter sets"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            return cursor.rowcount

    def get_approved_article_ids(self) -> List[int]:
        """Get all approved article IDs from ArticleApproveds table"""
        query = """
        SELECT DISTINCT articleId
        FROM ArticleApproveds
        ORDER BY articleId
        """
        rows = self.execute_query(query)
        return [row['articleId'] for row in rows]

    def get_duplicate_ratings_count(self) -> int:
        """Get count of rows in ArticleDuplicateRatings table"""
        query = "SELECT COUNT(*) as count FROM ArticleDuplicateRatings"
        result = self.execute_query(query)
        return result[0]['count']

    def get_duplicate_ratings_stats(self) -> Dict[str, int]:
        """Get statistics about ArticleDuplicateRatings table"""
        stats = {}

        # Total pairs
        query = "SELECT COUNT(*) as count FROM ArticleDuplicateRatings"
        result = self.execute_query(query)
        stats['total_pairs'] = result[0]['count']

        # Unique new articles
        query = "SELECT COUNT(DISTINCT articleIdNew) as count FROM ArticleDuplicateRatings"
        result = self.execute_query(query)
        stats['unique_new_articles'] = result[0]['count']

        # Unique approved articles
        query = "SELECT COUNT(DISTINCT articleIdApproved) as count FROM ArticleDuplicateRatings"
        result = self.execute_query(query)
        stats['unique_approved_articles'] = result[0]['count']

        return stats

    def clear_duplicate_ratings(self) -> int:
        """Clear all data from ArticleDuplicateRatings table"""
        query = "DELETE FROM ArticleDuplicateRatings"
        return self.execute_update(query)

    def insert_duplicate_ratings_batch(self, pairs: List[Tuple[int, int]]) -> int:
        """Insert multiple article pairs into ArticleDuplicateRatings table"""
        if not pairs:
            return 0

        query = """
        INSERT OR IGNORE INTO ArticleDuplicateRatings
        (articleIdNew, articleIdApproved, createdAt, updatedAt)
        VALUES (?, ?, datetime('now'), datetime('now'))
        """

        return self.execute_many(query, pairs)

    def check_article_exists(self, article_id: int) -> bool:
        """Check if article exists in Articles table"""
        query = "SELECT 1 FROM Articles WHERE id = ? LIMIT 1"
        result = self.execute_query(query, (article_id,))
        return len(result) > 0

    def get_existing_pairs_count(self, new_article_ids: List[int]) -> int:
        """Get count of existing pairs for the given new article IDs"""
        if not new_article_ids:
            return 0

        placeholders = ','.join('?' * len(new_article_ids))
        query = f"""
        SELECT COUNT(*) as count
        FROM ArticleDuplicateRatings
        WHERE articleIdNew IN ({placeholders})
        """
        result = self.execute_query(query, new_article_ids)
        return result[0]['count']