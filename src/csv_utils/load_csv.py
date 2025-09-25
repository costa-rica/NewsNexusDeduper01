"""
CSV loading utilities for NewsNexus Deduper

Handles loading and validation of article IDs from CSV files.
"""

import csv
from pathlib import Path
from typing import List, Set, Tuple

from db import DatabaseManager


class CSVLoader:
    """Handles loading article IDs from CSV files"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def load_article_ids_from_csv(self, csv_path: Path, validate_articles: bool = True) -> Tuple[List[int], Set[int]]:
        """
        Load article IDs from CSV file.

        Args:
            csv_path: Path to CSV file with 'articleId' header
            validate_articles: Whether to validate that articles exist in database

        Returns:
            Tuple of (valid_article_ids, invalid_article_ids)
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        article_ids = []
        invalid_ids = set()

        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as file:  # utf-8-sig handles BOM
                reader = csv.DictReader(file)

                # Clean fieldnames to remove any BOM or whitespace
                if reader.fieldnames:
                    reader.fieldnames = [field.strip() for field in reader.fieldnames]

                # Validate header
                if 'articleId' not in reader.fieldnames:
                    print(f"Available columns: {reader.fieldnames}")
                    raise ValueError("CSV file must have 'articleId' column")

                # Load article IDs
                for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                    article_id_str = row.get('articleId', '').strip()

                    if not article_id_str:
                        continue  # Skip empty rows

                    try:
                        article_id = int(article_id_str)
                        article_ids.append(article_id)
                    except ValueError:
                        print(f"Warning: Invalid article ID '{article_id_str}' at row {row_num}")
                        continue

        except Exception as e:
            raise ValueError(f"Error reading CSV file: {e}")

        # Remove duplicates while preserving order
        seen = set()
        unique_article_ids = []
        for article_id in article_ids:
            if article_id not in seen:
                seen.add(article_id)
                unique_article_ids.append(article_id)

        print(f"Loaded {len(unique_article_ids)} unique article IDs from CSV")

        # Validate that articles exist in database
        if validate_articles and unique_article_ids:
            valid_ids = []
            for article_id in unique_article_ids:
                if self.db_manager.check_article_exists(article_id):
                    valid_ids.append(article_id)
                else:
                    invalid_ids.add(article_id)
                    print(f"Warning: Article ID {article_id} not found in Articles table")

            print(f"Found {len(valid_ids)} valid articles, {len(invalid_ids)} invalid articles")
            return valid_ids, invalid_ids

        return unique_article_ids, set()

    def validate_csv_format(self, csv_path: Path) -> bool:
        """
        Validate that CSV file has correct format.

        Args:
            csv_path: Path to CSV file

        Returns:
            True if format is valid
        """
        if not csv_path.exists():
            return False

        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as file:  # Handle BOM
                reader = csv.DictReader(file)

                # Clean fieldnames to remove any BOM or whitespace
                if reader.fieldnames:
                    reader.fieldnames = [field.strip() for field in reader.fieldnames]

                # Check header
                if 'articleId' not in reader.fieldnames:
                    return False

                # Check first few rows have valid data
                for i, row in enumerate(reader):
                    if i >= 5:  # Check first 5 rows
                        break

                    article_id_str = row.get('articleId', '').strip()
                    if article_id_str:
                        try:
                            int(article_id_str)
                        except ValueError:
                            return False

            return True

        except Exception:
            return False