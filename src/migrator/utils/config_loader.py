import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv


class ConfigLoader:
    """Load database URL from multiple sources"""

    @staticmethod
    def _find_env_file() -> Optional[Path]:
        """Search for .env file in current and parent directories"""
        current = Path.cwd()
        for _ in range(5):
            env_file = current / ".env"
            if env_file.exists():
                return env_file
            if current.parent == current:
                break
            current = current.parent
        return None

    _async_warning_shown = False

    @staticmethod
    def _normalize_database_url(url: str) -> str:
        """Convert async database URLs to sync for Alembic compatibility"""
        async_drivers = {
            "+asyncpg": "",
            "+aiomysql": "+pymysql",
            "+aiosqlite": "",
        }
        
        for async_driver, sync_driver in async_drivers.items():
            if async_driver in url:
                # Only show warning once per session
                if not ConfigLoader._async_warning_shown:
                    from migrator.core.logger import warning
                    warning(f"Detected async driver: {async_driver}")
                    warning(f"Converting to sync for Alembic: {sync_driver or 'default'}")
                    ConfigLoader._async_warning_shown = True
                url = url.replace(async_driver, sync_driver)
                break
        
        return url

    @staticmethod
    def _try_explicit_config(config_path: Path) -> Optional[str]:
        """Load from explicitly specified config file"""
        if not config_path.exists():
            return None
        
        if config_path.suffix == ".py":
            spec = importlib.util.spec_from_file_location("config", config_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return getattr(module, "DATABASE_URL", None) or getattr(module, "SQLALCHEMY_DATABASE_URI", None)
        elif config_path.suffix in [".yaml", ".yml"]:
            with open(config_path) as f:
                config = yaml.safe_load(f)
                return config.get("database", {}).get("url") or config.get("database_url")
        elif config_path.suffix == ".toml":
            import tomllib
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
                return config.get("database", {}).get("url") or config.get("database_url")
        
        return None

    @staticmethod
    def load_database_url(config_path: Optional[Path] = None) -> str:
        """Auto-detect database URL from multiple sources"""
        # Try explicit config path first
        if config_path:
            db_url = ConfigLoader._try_explicit_config(config_path)
            if db_url:
                return ConfigLoader._normalize_database_url(db_url)
        
        # Find and load .env file
        env_file = ConfigLoader._find_env_file()
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        sources = [
            ("DATABASE_URL environment variable", ConfigLoader._try_env),
            ("SQLALCHEMY_DATABASE_URI environment variable", ConfigLoader._try_sqlalchemy_env),
            ("settings.py", ConfigLoader._try_settings_py),
            ("config.py", ConfigLoader._try_config_py),
            ("config.yaml", ConfigLoader._try_config_yaml),
            ("config.toml", ConfigLoader._try_config_toml),
        ]

        for source_name, source_func in sources:
            db_url = source_func()
            if db_url:
                return ConfigLoader._normalize_database_url(db_url)

        raise ValueError(
            "DATABASE_URL not found. Please set it in:\n"
            "  - .env file (DATABASE_URL=...)\n"
            "  - Environment variable\n"
            "  - settings.py or config.py\n"
            "  - config.yaml or config.toml"
        )

    @staticmethod
    def _try_env() -> Optional[str]:
        return os.getenv("DATABASE_URL")

    @staticmethod
    def _try_sqlalchemy_env() -> Optional[str]:
        return os.getenv("SQLALCHEMY_DATABASE_URI")

    @staticmethod
    def _try_settings_py() -> Optional[str]:
        try:
            sys.path.insert(0, str(Path.cwd()))
            from settings import DATABASE_URL

            return DATABASE_URL
        except (ImportError, AttributeError):
            try:
                from settings import SQLALCHEMY_DATABASE_URI

                return SQLALCHEMY_DATABASE_URI
            except (ImportError, AttributeError):
                return None

    @staticmethod
    def _try_config_py() -> Optional[str]:
        try:
            sys.path.insert(0, str(Path.cwd()))
            from config import DATABASE_URL

            return DATABASE_URL
        except (ImportError, AttributeError):
            try:
                from config import SQLALCHEMY_DATABASE_URI

                return SQLALCHEMY_DATABASE_URI
            except (ImportError, AttributeError):
                return None

    @staticmethod
    def _try_config_yaml() -> Optional[str]:
        try:
            with open("config.yaml") as f:
                config = yaml.safe_load(f)
                return config.get("database", {}).get("url") or config.get("database_url")
        except (FileNotFoundError, yaml.YAMLError, AttributeError):
            return None

    @staticmethod
    def _try_config_toml() -> Optional[str]:
        try:
            import tomllib

            with open("config.toml", "rb") as f:
                config = tomllib.load(f)
                return config.get("database", {}).get("url") or config.get("database_url")
        except (ImportError, FileNotFoundError, Exception):
            return None
