"""
MySQL integration tests.

Requires a running MySQL instance. Start with:
    docker compose up -d

Tests are skipped automatically if MySQL is not reachable.
"""
import os
from pathlib import Path

import pytest

MYSQL_URL = os.getenv(
    "MYSQL_DATABASE_URL",
    "mysql+pymysql://migrator:migrator@localhost:3306/migrator_test",
)


def _mysql_available() -> bool:
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(MYSQL_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


mysql_only = pytest.mark.skipif(
    not _mysql_available(),
    reason="MySQL not reachable — run: docker compose up -d",
)


@pytest.fixture
def mysql_config(tmp_path):
    from migrator.core.config import MigratorConfig

    return MigratorConfig(
        database_url=MYSQL_URL,
        migrations_dir=tmp_path / "migrations",
        base_import_path="models.Base",
    )


@mysql_only
def test_mysql_check_existing_tables_empty(mysql_config):
    """check_existing_tables works against MySQL"""
    from migrator.core.alembic_backend import AlembicBackend

    backend = AlembicBackend(mysql_config)
    tables = backend.check_existing_tables()
    assert isinstance(tables, list)


@mysql_only
def test_mysql_current_returns_none_before_migrations(mysql_config, tmp_path):
    """current() returns None on a fresh MySQL database"""
    from migrator.core.alembic_backend import AlembicBackend

    backend = AlembicBackend(mysql_config)
    backend.init(mysql_config.migrations_dir)
    assert backend.current() is None


@mysql_only
def test_mysql_full_migration_workflow(mysql_config, tmp_path, monkeypatch):
    """init -> makemigrations -> migrate -> downgrade against MySQL"""
    import os
    from sqlalchemy import create_engine, inspect as sa_inspect

    # Write a simple model
    (tmp_path / "models.py").write_text(
        "from sqlalchemy.orm import declarative_base\n"
        "from sqlalchemy import Column, Integer, String\n"
        "Base = declarative_base()\n"
        "class Product(Base):\n"
        "    __tablename__ = 'products'\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    name = Column(String(100))\n"
    )

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        monkeypatch.setenv("DATABASE_URL", MYSQL_URL)

        from migrator.core.alembic_backend import AlembicBackend

        backend = AlembicBackend(mysql_config)
        backend.init(mysql_config.migrations_dir)
        backend.create_migration("create products", autogenerate=True, use_timestamp=False)
        backend.apply_migrations("head")

        engine = create_engine(MYSQL_URL)
        try:
            tables = sa_inspect(engine).get_table_names()
            assert "products" in tables
        finally:
            engine.dispose()

        backend.downgrade("-1")

        engine = create_engine(MYSQL_URL)
        try:
            tables = sa_inspect(engine).get_table_names()
            assert "products" not in tables
        finally:
            engine.dispose()

    finally:
        os.chdir(original_cwd)
        # Clean up alembic_version if left behind
        try:
            engine = create_engine(MYSQL_URL)
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
                conn.commit()
            engine.dispose()
        except Exception:
            pass


@mysql_only
def test_mysql_stamp(mysql_config, tmp_path):
    """stamp marks database without running migrations"""
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        from migrator.core.alembic_backend import AlembicBackend

        backend = AlembicBackend(mysql_config)
        backend.init(mysql_config.migrations_dir)
        backend.stamp("head")
        # After stamp head with no migrations, current should be None
        assert backend.current() is None
    finally:
        os.chdir(original_cwd)
