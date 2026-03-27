"""Alembic environment scaffolding — creates migrations directory, env.py, alembic.ini, script.py.mako"""
from pathlib import Path
from typing import Any, Optional

from alembic.config import Config
from mako.template import Template

from migrator.core.config import MigratorConfig
from migrator.utils.file_utils import read_template, write_file


def create_alembic_config(config: MigratorConfig) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(config.migrations_dir))
    cfg.set_main_option("sqlalchemy.url", config.database_url)
    return cfg


def scaffold(directory: Path, config: MigratorConfig, base: Any = None) -> None:
    """Create the full migrations directory structure."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "versions").mkdir(exist_ok=True)
    _create_env_py(directory, config, base)
    _create_script_mako(directory)
    _create_alembic_ini(directory)


def _create_env_py(directory: Path, config: MigratorConfig, base: Any = None) -> None:
    template = Template(read_template("env.py.mako"))

    if config.base_import_path:
        if ":" in config.base_import_path:
            module_path, base_name = config.base_import_path.split(":", 1)
        else:
            parts = config.base_import_path.rsplit(".", 1)
            module_path, base_name = parts[0], parts[1]
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

    write_file(directory / "env.py", template.render(
        imports=imports,
        target_metadata=target_metadata,
        model_imports=model_imports,
    ))


def _create_script_mako(directory: Path) -> None:
    write_file(directory / "script.py.mako", read_template("script.py.mako"))


def _create_alembic_ini(directory: Path) -> None:
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
    write_file(directory / "alembic.ini", ini_content)
