from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from migrator.utils.config_loader import ConfigLoader


class MigratorConfig(BaseModel):
    database_url: str
    migrations_dir: Path = Path("migrations")
    base_import_path: Optional[str] = None

    @classmethod
    def load(
        cls,
        migrations_dir: Optional[Path] = None,
        config_path: Optional[Path] = None
    ) -> "MigratorConfig":
        """Auto-detect config from multiple sources"""
        db_url = ConfigLoader.load_database_url(config_path)

        return cls(database_url=db_url, migrations_dir=migrations_dir or Path("migrations"))
