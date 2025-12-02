"""Migration operations and utilities"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text


class MigrationOperations:
    """Handle migration operations like dry-run, confirmation, etc."""

    @staticmethod
    def generate_timestamped_message(message: str) -> str:
        """Add timestamp prefix to migration message"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{message}"

    @staticmethod
    def get_pending_migrations_details(alembic_cfg: Config) -> List[dict]:
        """Get detailed list of pending migrations"""
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        
        from sqlalchemy import create_engine
        from alembic.runtime.migration import MigrationContext
        
        db_url = alembic_cfg.get_main_option("sqlalchemy.url")
        engine = create_engine(db_url)
        
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
        
        pending = []
        for revision in script_dir.walk_revisions():
            if current_rev is None or revision.revision != current_rev:
                pending.append({
                    "revision": revision.revision,
                    "message": revision.doc or "No message",
                })
            else:
                break
        
        return list(reversed(pending))

    @staticmethod
    def show_migration_sql(alembic_cfg: Config, revision: str = "head") -> str:
        """Generate SQL for migration without applying"""
        import io
        from contextlib import redirect_stdout
        
        output = io.StringIO()
        
        # Configure for SQL output
        alembic_cfg.set_main_option("sqlalchemy.url", alembic_cfg.get_main_option("sqlalchemy.url"))
        
        with redirect_stdout(output):
            command.upgrade(alembic_cfg, revision, sql=True)
        
        return output.getvalue()

    @staticmethod
    def confirm_migration(pending_migrations: List[dict]) -> bool:
        """Ask user to confirm migration"""
        import typer
        
        if not pending_migrations:
            return True
        
        print(f"\n➜ About to apply {len(pending_migrations)} migration(s):")
        for mig in pending_migrations:
            print(f"  • {mig['revision'][:12]} - {mig['message']}")
        
        return typer.confirm("\nContinue?", default=True)
