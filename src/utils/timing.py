"""
Timing and logging utilities for NewsNexus Deduper
"""

import time
from contextlib import contextmanager
from typing import Generator


@contextmanager
def timer(description: str) -> Generator[None, None, None]:
    """
    Context manager for timing operations and printing duration.

    Args:
        description: Description of the operation being timed

    Usage:
        with timer("Loading data"):
            load_data()
    """
    start_time = time.time()
    print(f"{description}...")

    try:
        yield
    finally:
        end_time = time.time()
        duration = end_time - start_time

        if duration < 60:
            print(f"{description} completed in {duration:.2f} seconds")
        else:
            minutes = int(duration // 60)
            seconds = duration % 60
            print(f"{description} completed in {minutes}m {seconds:.2f}s")


def format_number(num: int) -> str:
    """
    Format large numbers with commas for readability.

    Args:
        num: Number to format

    Returns:
        Formatted number string
    """
    return f"{num:,}"