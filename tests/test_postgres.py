"""
PostgreSQL integration tests.

Requires a running PostgreSQL instance. Start with:
    docker compose up -d postgres

Tests are skipped automatically if PostgreSQL is not reachable.
"""
import os
import sys
from pathlib import Path

import pytest

PG_URL = os.getenv(
    "PG_DATABASE_URL",
    "postgresql+psycopg2://migrator:migrator@localhost:5433/migrator_test",
)

MODELS_SRC = """\
from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = relationship("Note", back_populates="author", cascade="all, delete-orphan")

class Note(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    body = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    author = relationship("User", back_populates="notes")
"""


def _pg_available() -> bool:
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(PG_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


pg_only = pytest.mark.skipif(
    not _pg_available(),
    reason="PostgreSQL not reachable — run: docker compose up -d postgres",
)


def _cleanup(engine):
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS notes CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS tags CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        conn.commit()
    engine.dispose()


@pg_only
def test_pg_init_creates_migration_structure(tmp_path):
    """init creates correct directory structure against Postgres"""
    from migrator.core.alembic_backend import AlembicBackend
    from migrator.core.config import MigratorConfig

    config = MigratorConfig(
        database_url=PG_URL,
        migrations_dir=tmp_path / "migrations",
        base_import_path="pg_models.Base",
    )
    AlembicBackend(config).init(config.migrations_dir)

    assert (tmp_path / "migrations" / "env.py").exists()
    assert (tmp_path / "migrations" / "alembic.ini").exists()
    assert (tmp_path / "migrations" / "versions").exists()
    env_content = (tmp_path / "migrations" / "env.py").read_text()
    assert "from pg_models import Base" in env_content
    assert "DATABASE_URL" in env_content


@pg_only
def test_pg_autogenerate_detects_models(tmp_path):
    """makemigrations autogenerates correct SQL for User and Note models"""
    (tmp_path / "pg_models.py").write_text(MODELS_SRC)

    original_cwd, original_sys_path = os.getcwd(), sys.path[:]
    try:
        os.chdir(tmp_path)
        from migrator.core.alembic_backend import AlembicBackend
        from migrator.core.config import MigratorConfig

        config = MigratorConfig(
            database_url=PG_URL,
            migrations_dir=tmp_path / "migrations",
            base_import_path="pg_models:Base",
        )
        backend = AlembicBackend(config)
        backend.init(config.migrations_dir)
        migration_path = backend.create_migration("create users and notes", autogenerate=True, use_timestamp=False)

        content = Path(migration_path).read_text()
        assert "users" in content
        assert "notes" in content
        assert "op.create_table" in content
    finally:
        os.chdir(original_cwd)
        sys.path[:] = original_sys_path


@pg_only
def test_pg_full_migration_workflow(tmp_path):
    """init -> makemigrations -> migrate -> verify tables -> downgrade"""
    (tmp_path / "pg_models.py").write_text(MODELS_SRC)

    from sqlalchemy import create_engine, inspect as sa_inspect

    original_cwd, original_sys_path = os.getcwd(), sys.path[:]
    engine = create_engine(PG_URL)
    try:
        _cleanup(engine)
        os.chdir(tmp_path)

        from migrator.core.alembic_backend import AlembicBackend
        from migrator.core.config import MigratorConfig

        config = MigratorConfig(
            database_url=PG_URL,
            migrations_dir=tmp_path / "migrations",
            base_import_path="pg_models:Base",
        )
        backend = AlembicBackend(config)
        backend.init(config.migrations_dir)
        backend.create_migration("create users and notes", autogenerate=True, use_timestamp=False)
        backend.apply_migrations("head")

        engine2 = create_engine(PG_URL)
        try:
            tables = sa_inspect(engine2).get_table_names()
            assert "users" in tables
            assert "notes" in tables
        finally:
            engine2.dispose()

        backend.downgrade("-1")

        engine3 = create_engine(PG_URL)
        try:
            tables = sa_inspect(engine3).get_table_names()
            assert "users" not in tables
            assert "notes" not in tables
        finally:
            engine3.dispose()

    finally:
        os.chdir(original_cwd)
        sys.path[:] = original_sys_path
        _cleanup(engine)


@pg_only
def test_pg_history_shows_applied_after_migrate(tmp_path):
    """history() correctly marks revision as applied after migrate"""
    (tmp_path / "pg_models.py").write_text(MODELS_SRC)

    from sqlalchemy import create_engine

    original_cwd, original_sys_path = os.getcwd(), sys.path[:]
    engine = create_engine(PG_URL)
    try:
        _cleanup(engine)
        os.chdir(tmp_path)

        from migrator.core.alembic_backend import AlembicBackend
        from migrator.core.config import MigratorConfig

        config = MigratorConfig(
            database_url=PG_URL,
            migrations_dir=tmp_path / "migrations",
            base_import_path="pg_models:Base",
        )
        backend = AlembicBackend(config)
        backend.init(config.migrations_dir)
        backend.create_migration("create users and notes", autogenerate=True, use_timestamp=False)
        backend.apply_migrations("head")

        history = backend.history()
        assert len(history) == 1
        assert history[0]["status"] == "applied"

    finally:
        os.chdir(original_cwd)
        sys.path[:] = original_sys_path
        _cleanup(engine)


@pg_only
def test_pg_check_existing_tables(tmp_path):
    """check_existing_tables detects tables created outside migrations"""
    from sqlalchemy import Column, Integer, String, create_engine
    from sqlalchemy.orm import declarative_base

    pg_base = declarative_base()

    class Tag(pg_base):  # noqa: N806
        __tablename__ = "tags"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    engine = create_engine(PG_URL)
    try:
        pg_base.metadata.create_all(engine)
        engine.dispose()

        from migrator.core.alembic_backend import AlembicBackend
        from migrator.core.config import MigratorConfig

        config = MigratorConfig(
            database_url=PG_URL,
            migrations_dir=tmp_path / "migrations",
            base_import_path="pg_models.Base",
        )
        tables = AlembicBackend(config).check_existing_tables()
        assert "tags" in tables
    finally:
        engine2 = create_engine(PG_URL)
        _cleanup(engine2)
