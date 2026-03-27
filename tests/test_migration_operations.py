"""Tests for MigrationOperations"""
import os

from migrator.core.migration_operations import MigrationOperations


def test_generate_timestamped_message_format():
    msg = MigrationOperations.generate_timestamped_message("add users")
    # format: YYYYMMDD_HHMMSS_add users
    parts = msg.split("_", 2)
    assert len(parts) == 3
    assert parts[0].isdigit() and len(parts[0]) == 8
    assert parts[1].isdigit() and len(parts[1]) == 6
    assert parts[2] == "add users"


def test_confirm_migration_empty_list_returns_true():
    """confirm_migration returns True immediately for empty list"""
    assert MigrationOperations.confirm_migration([]) is True


def test_confirm_migration_non_interactive_proceeds(capsys):
    """confirm_migration defaults to True in non-interactive mode (typer.Abort)"""
    pending = [{"revision": "abc123def456", "message": "create users"}]
    # CliRunner / non-interactive raises Abort — should return True
    result = MigrationOperations.confirm_migration(pending)
    assert result is True


def test_show_migration_sql_returns_string(temp_dir):
    """show_migration_sql returns a string (may be empty if no migrations)"""
    from migrator.core.alembic_backend import AlembicBackend
    from migrator.core.config import MigratorConfig

    db_path = temp_dir / "test.db"
    config = MigratorConfig(
        database_url=f"sqlite:///{db_path}",
        migrations_dir=temp_dir / "migrations",
        base_import_path="models.Base",
    )

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
        backend = AlembicBackend(config)
        backend.init(config.migrations_dir)
        backend.create_migration("create items", autogenerate=True, use_timestamp=False)
        sql = MigrationOperations.show_migration_sql(backend.alembic_cfg, "head")
        assert isinstance(sql, str)
        assert "CREATE TABLE" in sql.upper()
    finally:
        os.chdir(original_cwd)


def test_get_pending_migrations_details_empty(temp_dir):
    """Returns empty list when no migration files exist"""
    from migrator.core.alembic_backend import AlembicBackend
    from migrator.core.config import MigratorConfig

    db_path = temp_dir / "test.db"
    config = MigratorConfig(
        database_url=f"sqlite:///{db_path}",
        migrations_dir=temp_dir / "migrations",
        base_import_path="models.Base",
    )
    backend = AlembicBackend(config)
    backend.init(config.migrations_dir)

    pending = MigrationOperations.get_pending_migrations_details(backend.alembic_cfg)
    assert pending == []
