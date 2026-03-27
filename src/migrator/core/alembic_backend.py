from pathlib import Path
from typing import Any, List, Optional

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

    def init(self, directory: Path, base: Any = None) -> None:
        """Initialize migration environment"""
        directory.mkdir(parents=True, exist_ok=True)
        versions_dir = directory / "versions"
        versions_dir.mkdir(exist_ok=True)

        self._create_env_py(directory, base=base)
        self._create_script_mako(directory)
        self._create_alembic_ini(directory)

    def _create_env_py(self, directory: Path, base: Any = None) -> None:
        """Create customized env.py"""
        template_content = read_template("env.py.mako")
        template = Template(template_content)

        if self.config.base_import_path:
            if ":" in self.config.base_import_path:
                module_path, base_name = self.config.base_import_path.split(":", 1)
            else:
                parts = self.config.base_import_path.rsplit(".", 1)
                module_path = parts[0]
                base_name = parts[1]
            imports = f"from {module_path} import {base_name}"
            target_metadata = f"{base_name}.metadata"
        else:
            imports = "# Import your Base here"
            target_metadata = "None"

        model_imports = ""
        if base is not None:
            from migrator.core.detector import ModelDetector
            modules = ModelDetector.find_model_modules(base)
            if modules:
                model_imports = "\n".join(f"import {m}  # noqa: F401" for m in modules)

        content = template.render(imports=imports, target_metadata=target_metadata, model_imports=model_imports)
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
# URL is loaded from DATABASE_URL environment variable at runtime (see env.py)
sqlalchemy.url = placeholder

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
        """Get migration history with correct applied status"""
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        engine = create_engine(self.config.database_url)

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            applied_revisions = set(context.get_current_heads())
            # Walk back through down_revisions to find all applied
            heads = list(applied_revisions)
            for head in heads:
                rev = script_dir.get_revision(head)
                while rev and rev.down_revision:
                    down = rev.down_revision
                    if isinstance(down, tuple):
                        for d in down:
                            applied_revisions.add(d)
                            heads.append(d)
                    else:
                        applied_revisions.add(down)
                        heads.append(down)
                    rev = script_dir.get_revision(down if not isinstance(down, tuple) else down[0])

        all_revisions = list(reversed(list(script_dir.walk_revisions())))
        return [
            {
                "revision": r.revision,
                "message": r.doc or "No message",
                "down_revision": r.down_revision,
                "status": "applied" if r.revision in applied_revisions else "pending",
            }
            for r in all_revisions
        ]

    def get_pending_migrations(self) -> List[dict]:
        """Get list of pending migrations"""
        from migrator.core.migration_operations import MigrationOperations
        return MigrationOperations.get_pending_migrations_details(self.alembic_cfg)

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


