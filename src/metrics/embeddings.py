"""
Embedding-based similarity for article deduplication.

This module provides functionality to compute semantic similarity between articles
using sentence embeddings, enabling detection of articles with similar meaning
even when using different words.
"""

import numpy as np
from typing import Optional, List, Tuple, Dict
import logging
from tqdm import tqdm

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from db import DatabaseManager

logger = logging.getLogger(__name__)


def combine_article_text(headline: Optional[str], text: Optional[str]) -> str:
    """
    Combine headline and text into a single string for embedding.

    Args:
        headline: Article headline
        text: Article text content

    Returns:
        Combined text string, or empty string if both are None/empty
    """
    headline = headline.strip() if headline else ""
    text = text.strip() if text else ""

    if headline and text:
        return f"{headline}. {text}"
    elif headline:
        return headline
    elif text:
        return text
    else:
        return ""


def compute_cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Compute cosine similarity between two embeddings.

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector

    Returns:
        Cosine similarity score between 0 and 1
    """
    # Normalize vectors
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    # Compute cosine similarity
    similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)

    # Clamp to [0, 1] range (cosine similarity is [-1, 1], but we want [0, 1])
    return max(0.0, float(similarity))


class EmbeddingProcessor:
    """Processes embedding-based similarity metrics for article pairs"""

    def __init__(self, db_manager: DatabaseManager, model_name: str = "all-MiniLM-L6-v2"):
        self.db = db_manager
        self.model_name = model_name
        self.model = None
        self.embedding_cache = {}  # Cache embeddings by articleId

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required for embedding similarity. "
                "Install with: pip install sentence-transformers"
            )

    def _load_model(self):
        """Lazy load the embedding model"""
        if self.model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully")

    def get_articles_for_embedding_search(self, batch_size: int = 1000) -> List:
        """Get article pairs that need embedding search (embeddingSearch is NULL)"""
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
        WHERE adr.embeddingSearch IS NULL
        LIMIT ?
        """
        return self.db.execute_query(query, (batch_size,))

    def get_embedding_search_stats(self) -> dict:
        """Get statistics about embedding search progress"""
        stats = {}

        # Total pairs
        query = "SELECT COUNT(*) as count FROM ArticleDuplicateRatings"
        result = self.db.execute_query(query)
        stats['total_pairs'] = result[0]['count']

        # Pairs with embedding search completed
        query = "SELECT COUNT(*) as count FROM ArticleDuplicateRatings WHERE embeddingSearch IS NOT NULL"
        result = self.db.execute_query(query)
        stats['embedding_search_completed'] = result[0]['count']

        # Pairs pending embedding search
        stats['embedding_search_pending'] = stats['total_pairs'] - stats['embedding_search_completed']

        # High similarity pairs (embeddingSearch > 0.8)
        query = "SELECT COUNT(*) as count FROM ArticleDuplicateRatings WHERE embeddingSearch > 0.8"
        result = self.db.execute_query(query)
        stats['high_similarity_pairs'] = result[0]['count']

        # Average similarity score
        query = "SELECT AVG(embeddingSearch) as avg_score FROM ArticleDuplicateRatings WHERE embeddingSearch IS NOT NULL"
        result = self.db.execute_query(query)
        stats['avg_similarity_score'] = float(result[0]['avg_score']) if result[0]['avg_score'] else 0.0

        return stats

    def update_embedding_search_batch(self, embedding_updates: List[Tuple[float, int]]) -> int:
        """Update embeddingSearch values for multiple rating IDs"""
        if not embedding_updates:
            return 0

        query = """
        UPDATE ArticleDuplicateRatings
        SET embeddingSearch = ?, updatedAt = datetime('now')
        WHERE id = ?
        """
        return self.db.execute_many(query, embedding_updates)

    def get_or_compute_embedding(self, article_id: int, headline: str, text: str) -> np.ndarray:
        """Get embedding from cache or compute it"""
        if article_id in self.embedding_cache:
            return self.embedding_cache[article_id]

        # Combine text and compute embedding
        combined_text = combine_article_text(headline, text)
        if not combined_text:
            # Empty text gets zero embedding
            embedding = np.zeros(self.model.get_sentence_embedding_dimension())
        else:
            embedding = self.model.encode([combined_text])[0]

        # Cache the result
        self.embedding_cache[article_id] = embedding
        return embedding

    def process_embedding_search_batch(self, batch_size: int = 500) -> dict:
        """
        Process a batch of article pairs for embedding search computation.
        Uses smaller default batch size due to computational intensity.

        Args:
            batch_size: Number of pairs to process in this batch

        Returns:
            Dictionary with processing statistics
        """
        self._load_model()

        # Get articles that need embedding processing
        articles = self.get_articles_for_embedding_search(batch_size)

        if not articles:
            return {
                'processed': 0,
                'high_similarity': 0,
                'avg_similarity': 0.0,
                'errors': 0
            }

        logger.info(f"Processing embeddings for {len(articles)} article pairs")

        embedding_updates = []
        similarities = []
        errors = 0

        # Use tqdm for progress bar - updates in place without new lines
        with tqdm(articles, desc="Computing embeddings", unit="pairs", leave=False) as pbar:
            for article in pbar:
                try:
                    # Get or compute embeddings for both articles
                    embedding_new = self.get_or_compute_embedding(
                        article['articleIdNew'],
                        article['headlineNew'],
                        article['textNew']
                    )
                    embedding_approved = self.get_or_compute_embedding(
                        article['articleIdApproved'],
                        article['headlineApproved'],
                        article['textApproved']
                    )

                    # Compute similarity score
                    similarity = compute_cosine_similarity(embedding_new, embedding_approved)
                    similarities.append(similarity)

                    embedding_updates.append((similarity, article['id']))

                    # Update progress bar with current similarity
                    pbar.set_postfix({
                        'similarity': f'{similarity:.3f}',
                        'cached': len(self.embedding_cache)
                    })

                except Exception as e:
                    logger.error(f"Error processing embeddings for pair {article['id']}: {e}")
                    errors += 1
                    # Set embeddingSearch to 0.0 for failed comparisons
                    embedding_updates.append((0.0, article['id']))

        # Update database with results
        updated_count = self.update_embedding_search_batch(embedding_updates)

        # Calculate statistics
        high_similarity_count = sum(1 for s in similarities if s > 0.8)
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

        stats = {
            'processed': len(articles),
            'high_similarity': high_similarity_count,
            'avg_similarity': avg_similarity,
            'errors': errors,
            'updated_db_rows': updated_count,
            'cached_embeddings': len(self.embedding_cache)
        }

        logger.info(f"Embedding batch completed: {stats}")
        return stats

    def process_all_embedding_search(self, batch_size: int = 500) -> dict:
        """
        Process all pending embedding search computations with overall progress bar.

        Args:
            batch_size: Number of pairs to process per batch

        Returns:
            Dictionary with overall processing statistics
        """
        # Get total count first
        stats = self.get_embedding_search_stats()
        total_pending = stats['embedding_search_pending']

        if total_pending == 0:
            return {
                'total_processed': 0,
                'total_high_similarity': 0,
                'overall_avg_similarity': 0.0,
                'total_errors': 0,
                'batches_completed': 0
            }

        total_processed = 0
        total_high_similarity = 0
        all_similarities = []
        total_errors = 0
        batches_completed = 0

        # Overall progress bar
        with tqdm(total=total_pending, desc="Overall embedding progress", unit="pairs") as overall_pbar:
            while True:
                batch_result = self.process_embedding_search_batch(batch_size)

                if batch_result['processed'] == 0:
                    break

                total_processed += batch_result['processed']
                total_high_similarity += batch_result['high_similarity']
                total_errors += batch_result['errors']
                batches_completed += 1

                # Update overall progress
                overall_pbar.update(batch_result['processed'])
                overall_pbar.set_postfix({
                    'batch_avg': f"{batch_result['avg_similarity']:.3f}",
                    'high_sim': total_high_similarity,
                    'cached': batch_result.get('cached_embeddings', 0)
                })

                # Collect similarities for overall average
                if batch_result['avg_similarity'] > 0:
                    # Approximate individual similarities based on batch average
                    batch_similarities = [batch_result['avg_similarity']] * batch_result['processed']
                    all_similarities.extend(batch_similarities)

        overall_avg_similarity = sum(all_similarities) / len(all_similarities) if all_similarities else 0.0

        return {
            'total_processed': total_processed,
            'total_high_similarity': total_high_similarity,
            'overall_avg_similarity': overall_avg_similarity,
            'total_errors': total_errors,
            'batches_completed': batches_completed,
            'final_cache_size': len(self.embedding_cache)
        }