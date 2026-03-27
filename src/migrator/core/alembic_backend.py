from pathlib import Path
from typing import Any, List, Optional

from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from migrator.core.alembic_setup import create_alembic_config, scaffold
from migrator.core.base import MigrationBackend
from migrator.core.config import MigratorConfig


class AlembicBackend(MigrationBackend):
    """Alembic implementation of migration backend"""

    def __init__(self, config: MigratorConfig):
        self.config = config
        self.alembic_cfg = create_alembic_config(config)

    def init(self, directory: Path, base: Any = None) -> None:
        scaffold(directory, self.config, base=base)

    def create_migration(self, message: str, autogenerate: bool = True, use_timestamp: bool = True) -> Path:
        if use_timestamp:
            from migrator.core.migration_operations import MigrationOperations
            message = MigrationOperations.generate_timestamped_message(message)
        command.revision(self.alembic_cfg, message=message, autogenerate=autogenerate)
        return self._get_latest_migration()

    def show_migration_sql(self, revision: str = "head") -> str:
        from migrator.core.migration_operations import MigrationOperations
        return MigrationOperations.show_migration_sql(self.alembic_cfg, revision)

    def _get_latest_migration(self) -> Path:
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        revisions = list(script_dir.walk_revisions())
        return Path(revisions[0].path) if revisions else Path()

    def apply_migrations(self, revision: str = "head") -> None:
        command.upgrade(self.alembic_cfg, revision)

    def downgrade(self, revision: str = "-1") -> None:
        command.downgrade(self.alembic_cfg, revision)

    def history(self) -> List[dict]:
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        engine = create_engine(self.config.database_url)
        try:
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                applied_revisions = set(context.get_current_heads())
        finally:
            engine.dispose()

        visited: set = set()
        queue = list(applied_revisions)
        while queue:
            head = queue.pop()
            if head in visited:
                continue
            visited.add(head)
            rev = script_dir.get_revision(head)
            if not rev or not rev.down_revision:
                continue
            downs = rev.down_revision if isinstance(rev.down_revision, tuple) else (rev.down_revision,)
            for d in downs:
                applied_revisions.add(d)
                queue.append(d)

        return [
            {
                "revision": r.revision,
                "message": r.doc or "No message",
                "down_revision": r.down_revision,
                "status": "applied" if r.revision in applied_revisions else "pending",
            }
            for r in reversed(list(script_dir.walk_revisions()))
        ]

    def get_pending_migrations(self) -> List[dict]:
        from migrator.core.migration_operations import MigrationOperations
        return MigrationOperations.get_pending_migrations_details(self.alembic_cfg)

    def current(self) -> Optional[str]:
        engine = create_engine(self.config.database_url)
        try:
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return context.get_current_revision()
        finally:
            engine.dispose()

    def stamp(self, revision: str = "head") -> None:
        command.stamp(self.alembic_cfg, revision)

    def check_existing_tables(self) -> List[str]:
        engine = create_engine(self.config.database_url)
        try:
            return inspect(engine).get_table_names()
        finally:
            engine.dispose()
