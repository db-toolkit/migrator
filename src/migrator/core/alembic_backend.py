from pathlib import Path
from typing import List, Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from mako.template import Template
from sqlalchemy import create_engine, inspect

from migrator.core.base import MigrationBackend
from migrator.core.config import MigratorConfig
from migrator.utils.file_utils import read_template, write_file


class AlembicBackend(MigrationBackend):
    """Alembic implementation of migration backend"""

    def __init__(self, config: MigratorConfig):
        self.config = config
        self.alembic_cfg = self._create_alembic_config()

    def _create_alembic_config(self) -> Config:
        """Create Alembic configuration"""
        cfg = Config()
        cfg.set_main_option("script_location", str(self.config.migrations_dir))
        cfg.set_main_option("sqlalchemy.url", self.config.database_url)
        return cfg

    def init(self, directory: Path) -> None:
        """Initialize migration environment"""
        directory.mkdir(parents=True, exist_ok=True)
        versions_dir = directory / "versions"
        versions_dir.mkdir(exist_ok=True)

        self._create_env_py(directory)
        self._create_script_mako(directory)
        self._create_alembic_ini(directory)

    def _create_env_py(self, directory: Path) -> None:
        """Create customized env.py"""
        template_content = read_template("env.py.mako")
        template = Template(template_content)

        if self.config.base_import_path:
            parts = self.config.base_import_path.rsplit(".", 1)
            module_path = parts[0]
            base_name = parts[1]
            imports = f"from {module_path} import {base_name}"
            target_metadata = f"{base_name}.metadata"
        else:
            imports = "# Import your Base here"
            target_metadata = "None"

        content = template.render(imports=imports, target_metadata=target_metadata)
        write_file(directory / "env.py", content)

    def _create_script_mako(self, directory: Path) -> None:
        """Copy script.py.mako template"""
        content = read_template("script.py.mako")
        write_file(directory / "script.py.mako", content)

    def _create_alembic_ini(self, directory: Path) -> None:
        """Create alembic.ini file"""
        ini_content = f"""[alembic]
script_location = {directory}
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = {self.config.database_url}

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
        ini_path = directory / "alembic.ini"
        with open(ini_path, "w") as f:
            f.write(ini_content)

    def create_migration(self, message: str, autogenerate: bool = True, use_timestamp: bool = True) -> Path:
        """Create new migration"""
        if use_timestamp:
            from migrator.core.migration_operations import MigrationOperations
            message = MigrationOperations.generate_timestamped_message(message)
        
        command.revision(self.alembic_cfg, message=message, autogenerate=autogenerate)
        return self._get_latest_migration()
    
    def show_migration_sql(self, revision: str = "head") -> str:
        """Show SQL for migration without applying"""
        from migrator.core.migration_operations import MigrationOperations
        return MigrationOperations.show_migration_sql(self.alembic_cfg, revision)

    def _get_latest_migration(self) -> Path:
        """Get path to latest migration file"""
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        revisions = list(script_dir.walk_revisions())
        if revisions:
            latest = revisions[0]
            return Path(latest.path)
        return Path()

    def apply_migrations(self, revision: str = "head") -> None:
        """Apply migrations"""
        command.upgrade(self.alembic_cfg, revision)

    def downgrade(self, revision: str = "-1") -> None:
        """Rollback migrations"""
        command.downgrade(self.alembic_cfg, revision)

    def history(self) -> List[dict]:
        """Get migration history with correct status"""
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        current_rev = self.current()
        revisions = []
        
        # Get all revisions in chronological order
        all_revisions = list(reversed(list(script_dir.walk_revisions())))
        
        # Determine which revisions are applied
        applied_revisions = set()
        if current_rev:
            # Find current revision and mark all up to it as applied
            for i, revision in enumerate(all_revisions):
                applied_revisions.add(revision.revision)
                if revision.revision == current_rev:
                    break
        
        for revision in all_revisions:
            status = "applied" if revision.revision in applied_revisions else "pending"
            revisions.append(
                {
                    "revision": revision.revision,
                    "message": revision.doc or "No message",
                    "down_revision": revision.down_revision,
                    "status": status,
                }
            )

        return revisions

    def current(self) -> Optional[str]:
        """Get current revision"""
        engine = create_engine(self.config.database_url)

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()

        return current_rev

    def stamp(self, revision: str = "head") -> None:
        """Mark database as migrated without running migrations"""
        command.stamp(self.alembic_cfg, revision)

    def check_existing_tables(self) -> List[str]:
        """Check for existing tables in database"""
        engine = create_engine(self.config.database_url)
        inspector = inspect(engine)
        return inspector.get_table_names()

    def get_pending_migrations(self) -> List[dict]:
        """Get list of pending migrations"""
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        current = self.current()
        pending = []

        for revision in script_dir.walk_revisions():
            if current is None or revision.revision != current:
                pending.append(
                    {
                        "revision": revision.revision,
                        "message": revision.doc or "No message",
                    }
                )
            else:
                break

        return list(reversed(pending))
