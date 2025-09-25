"""
Configuration management for NewsNexus Deduper

Loads environment variables from .env file and provides configuration values.
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Configuration class that loads settings from environment variables"""

    def __init__(self):
        # Load .env file if it exists
        self._load_dotenv()

        # Database configuration
        self.PATH_TO_DATABASE = self._get_required_env('PATH_TO_DATABASE')
        self.NAME_DB = self._get_required_env('NAME_DB')

        # CSV configuration
        self.PATH_TO_CSV = self._get_required_env('PATH_TO_CSV')

        # Python virtual environment (for reference)
        self.PATH_TO_PYTHON_VENV = os.getenv('PATH_TO_PYTHON_VENV')

        # Validate paths
        self._validate_config()

    def _load_dotenv(self):
        """Load environment variables from .env file"""
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()

    def _get_required_env(self, key: str) -> str:
        """Get required environment variable or raise error"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable '{key}' not found")
        return value

    def _validate_config(self):
        """Validate configuration values"""
        # Check database directory exists
        db_dir = Path(self.PATH_TO_DATABASE)
        if not db_dir.exists():
            raise ValueError(f"Database directory does not exist: {self.PATH_TO_DATABASE}")

        # Check database file exists
        db_path = db_dir / self.NAME_DB
        if not db_path.exists():
            raise ValueError(f"Database file does not exist: {db_path}")

    @property
    def database_path(self) -> Path:
        """Get full path to database file"""
        return Path(self.PATH_TO_DATABASE) / self.NAME_DB

    @property
    def csv_path(self) -> Optional[Path]:
        """Get path to CSV file"""
        if self.PATH_TO_CSV:
            return Path(self.PATH_TO_CSV)
        return None