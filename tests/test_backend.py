from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base

from migrator.core.alembic_backend import AlembicBackend
from migrator.core.config import MigratorConfig


@pytest.fixture
def test_config():
    return MigratorConfig(
        database_url="sqlite:///test.db",
        migrations_dir=Path("migrations"),
        base_import_path="models.Base",
    )


@pytest.fixture
def sqlite_config(temp_dir):
    db_path = temp_dir / "test.db"
    return MigratorConfig(
        database_url=f"sqlite:///{db_path}",
        migrations_dir=temp_dir / "migrations",
        base_import_path="models.Base",
    )


def test_alembic_backend_init(test_config, temp_dir):
    backend = AlembicBackend(test_config)
    assert backend.config == test_config
    assert backend.alembic_cfg is not None


def test_init_creates_migration_directory(test_config, temp_dir):
    backend = AlembicBackend(test_config)
    migrations_dir = temp_dir / "migrations"
    backend.init(migrations_dir)
    assert migrations_dir.exists()
    assert (migrations_dir / "versions").exists()
    assert (migrations_dir / "env.py").exists()
    assert (migrations_dir / "script.py.mako").exists()
    assert (migrations_dir / "alembic.ini").exists()


def test_env_py_contains_base_import(test_config, temp_dir):
    backend = AlembicBackend(test_config)
    migrations_dir = temp_dir / "migrations"
    backend.init(migrations_dir)
    env_content = (migrations_dir / "env.py").read_text()
    assert "from models import Base" in env_content
    assert "Base.metadata" in env_content


def test_env_py_colon_notation_base_import(temp_dir):
    """base_import_path with colon notation (app.core.db:Base) generates correct import"""
    config = MigratorConfig(
        database_url="sqlite:///test.db",
        migrations_dir=temp_dir / "migrations",
        base_import_path="app.core.db:Base",
    )
    backend = AlembicBackend(config)
    backend.init(temp_dir / "migrations")
    env_content = (temp_dir / "migrations" / "env.py").read_text()
    assert "from app.core.db import Base" in env_content
    assert "Base.metadata" in env_content


def test_current_returns_none_before_migrations(sqlite_config, temp_dir):
    """current() returns None when no migrations have been applied"""
    backend = AlembicBackend(sqlite_config)
    backend.init(sqlite_config.migrations_dir)
    assert backend.current() is None


def test_check_existing_tables_empty(sqlite_config):
    """check_existing_tables returns empty list for fresh database"""
    backend = AlembicBackend(sqlite_config)
    tables = backend.check_existing_tables()
    assert isinstance(tables, list)
    assert tables == []


def test_check_existing_tables_after_create(sqlite_config, temp_dir):
    """check_existing_tables detects tables created outside migrations"""
    base = declarative_base()  # noqa: N806

    class User(base):  # noqa: N806
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
        name = Column(String)

    engine = create_engine(sqlite_config.database_url)
    base.metadata.create_all(engine)
    engine.dispose()

    backend = AlembicBackend(sqlite_config)
    tables = backend.check_existing_tables()
    assert "users" in tables


def test_history_applied_status_after_migrate(sqlite_config, temp_dir):
    """history() marks revision as applied after migrate"""
    import os
    (temp_dir / "models.py").write_text(
        "from sqlalchemy.orm import declarative_base\n"
        "from sqlalchemy import Column, Integer\n"
        "Base = declarative_base()\n"
        "class Item(Base):\n"
        "    __tablename__ = 'items'\n"
        "    id = Column(Integer, primary_key=True)\n"
    )
    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        backend = AlembicBackend(sqlite_config)
        backend.init(sqlite_config.migrations_dir)
        backend.create_migration("create items", autogenerate=True, use_timestamp=False)
        backend.apply_migrations("head")
        history = backend.history()
        assert len(history) == 1
        assert history[0]["status"] == "applied"
    finally:
        os.chdir(original_cwd)


def test_history_pending_status_before_migrate(sqlite_config, temp_dir):
    """history() marks revision as pending before migrate"""
    import os
    (temp_dir / "models.py").write_text(
        "from sqlalchemy.orm import declarative_base\n"
        "from sqlalchemy import Column, Integer\n"
        "Base = declarative_base()\n"
        "class Item(Base):\n"
        "    __tablename__ = 'items'\n"
        "    id = Column(Integer, primary_key=True)\n"
    )
    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        backend = AlembicBackend(sqlite_config)
        backend.init(sqlite_config.migrations_dir)
        backend.create_migration("create items", autogenerate=True, use_timestamp=False)
        history = backend.history()
        assert len(history) == 1
        assert history[0]["status"] == "pending"
    finally:
        os.chdir(original_cwd)


def test_get_pending_migrations(test_config, temp_dir):
    backend = AlembicBackend(test_config)
    migrations_dir = temp_dir / "migrations"
    backend.init(migrations_dir)
    pending = backend.get_pending_migrations()
    assert isinstance(pending, list)
