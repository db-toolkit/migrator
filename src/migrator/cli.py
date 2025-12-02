from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from migrator.core.alembic_backend import AlembicBackend
from migrator.core.config import MigratorConfig
from migrator.core.detector import ModelDetector
from migrator.core.logger import error, info, success
from migrator.utils.validators import sanitize_message, validate_database_url
from migrator.version import __version__

app = typer.Typer(help="🧩 Migrator - Universal Migration CLI")
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"Migrator CLI v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    )
):
    """Migrator - Universal Migration CLI for Python apps"""
    pass


@app.command()
def init(
    directory: Path = typer.Option(Path("migrations"), "--dir", "-d", help="Migration directory"),
    base_path: str = typer.Option(None, "--base", "-b", help="Base class path (e.g. app.core.database:Base)"),
    config_path: Path = typer.Option(None, "--config", "-c", help="Config file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed detection process"),
):
    """Initialize migration environment"""
    try:
        if verbose:
            info("Verbose mode enabled")
        
        info("Detecting project configuration...")
        
        if verbose:
            from migrator.utils.config_loader import ConfigLoader
            env_file = ConfigLoader._find_env_file()
            if env_file:
                info(f"Found .env at: {env_file}")
            else:
                info("No .env file found")
        
        config = MigratorConfig.load(migrations_dir=directory, config_path=config_path)
        
        if verbose:
            info(f"Database URL: {config.database_url[:30]}...")

        info("Finding SQLAlchemy Base...")
        base = ModelDetector.find_base(explicit_path=base_path)
        
        # Get the detected import path
        detected_path = ModelDetector.get_detected_import_path()
        if detected_path:
            config.base_import_path = detected_path
        
        if not base:
            error("Could not find SQLAlchemy Base class")
            
            searched = ModelDetector.get_searched_paths()
            if searched:
                info(f"Searched in: {', '.join(searched[:5])}")
                if len(searched) > 5:
                    info(f"... and {len(searched) - 5} more locations")
            
            console.print("\n💡 Troubleshooting Tips:")
            console.print("  1. Ensure your models inherit from Base")
            console.print("  2. Check if Base = declarative_base() exists")
            console.print("  3. Verify models are imported in __init__.py")
            console.print("  4. Use --base flag: migrator init --base app.core.database:Base")
            console.print("  5. Check that DATABASE_URL is correctly set")
            
            raise typer.Exit(1)
        
        if verbose:
            info(f"Found Base in: {base.__module__}")
            if config.base_import_path:
                info(f"Using import path: {config.base_import_path}")

        info(f"Initializing migrations in {directory}...")
        backend = AlembicBackend(config)
        backend.init(directory)

        success(f"Migration environment created at {directory}")
        console.print("\n📁 Structure:")
        console.print(f"  {directory}/")
        console.print("  ├── versions/")
        console.print("  ├── env.py")
        console.print("  ├── script.py.mako")
        console.print("  └── alembic.ini")

    except Exception as e:
        error(f"Initialization failed: {e}")
        raise typer.Exit(1)


@app.command()
def makemigrations(
    message: str = typer.Argument(None, help="Migration description"),
    autogenerate: bool = typer.Option(True, "--auto/--manual", help="Auto-generate migration"),
    base_path: str = typer.Option(None, "--base", "-b", help="Base class path"),
    show_sql: bool = typer.Option(False, "--show-sql", help="Show SQL that will be generated"),
):
    """Create new migration"""
    try:
        config = MigratorConfig.load()
        
        if autogenerate and not config.base_import_path:
            base = ModelDetector.find_base(explicit_path=base_path)
            
            # Get the detected import path
            detected_path = ModelDetector.get_detected_import_path()
            if detected_path:
                config.base_import_path = detected_path
            
            if not base:
                error("Could not find SQLAlchemy Base class")
                console.print("\n💡 Troubleshooting Tips:")
                console.print("  1. Ensure your models inherit from Base")
                console.print("  2. Check if Base = declarative_base() exists")
                console.print("  3. Verify models are imported in __init__.py")
                console.print("  4. Use --base flag: migrator makemigrations --base app.db:Base")
                raise typer.Exit(1)

        if not validate_database_url(config.database_url):
            error("Invalid database URL format")
            console.print("\n💡 Troubleshooting Tips:")
            console.print("  1. Check DATABASE_URL in .env file")
            console.print("  2. Format: postgresql://user:pass@host:port/dbname")
            console.print("  3. Ensure database credentials are correct")
            raise typer.Exit(1)

        # Auto-generate message if not provided
        if not message:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            message = f"auto_migration_{timestamp}"
            info(f"No message provided, using: {message}")
        else:
            message = sanitize_message(message)

        backend = AlembicBackend(config)

        info(f"Creating migration: {message}")
        migration_path = backend.create_migration(message, autogenerate, use_timestamp=True)

        success(f"Migration created: {migration_path}")
        
        if show_sql:
            console.print("\n📄 Generated SQL:")
            sql = backend.show_migration_sql()
            console.print(sql)

    except Exception as e:
        error(f"Migration creation failed: {e}")
        raise typer.Exit(1)


@app.command()
def migrate(
    revision: str = typer.Option("head", "--revision", "-r", help="Target revision"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show SQL without executing"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Apply migrations"""
    try:
        config = MigratorConfig.load()
        backend = AlembicBackend(config)

        # Check for existing tables (excluding migration tracking table)
        existing_tables = backend.check_existing_tables()
        # Filter out alembic_version table
        user_tables = [t for t in existing_tables if t != "alembic_version"]
        current = backend.current()

        if user_tables and not current:
            console.print(f"\n⚠️  Found {len(user_tables)} existing tables in database")
            console.print("\nOptions:")
            console.print("  1. Mark database as migrated (stamp) - Recommended")
            console.print("  2. Continue anyway (may cause conflicts)")
            console.print("  3. Cancel")

            choice = typer.prompt("\nChoice", type=int, default=3)

            if choice == 1:
                backend.stamp(revision)
                success(f"Database marked as migrated to {revision}")
                return
            elif choice == 3:
                info("Migration cancelled")
                return

        if dry_run:
            info("Dry-run mode: showing SQL only")
            console.print("\n📄 SQL Preview:")
            sql = backend.show_migration_sql(revision)
            console.print(sql)
            return

        # Get pending migrations for confirmation
        from migrator.core.migration_operations import MigrationOperations
        pending = MigrationOperations.get_pending_migrations_details(backend.alembic_cfg)
        
        # Show confirmation prompt unless --yes flag is used
        if pending and not yes:
            if not MigrationOperations.confirm_migration(pending):
                info("Migration cancelled")
                return

        info(f"Current revision: {current or 'None'}")
        info(f"Upgrading to: {revision}")

        backend.apply_migrations(revision)

        success("Database up-to-date")

    except Exception as e:
        error(f"Migration failed: {e}")
        error_msg = str(e).lower()
        
        console.print("\n💡 Troubleshooting Tips:")
        if "foreign key constraint" in error_msg:
            console.print("  1. Use 'migrator stamp head' to mark existing database as migrated")
            console.print("  2. Check if tables already exist in the database")
        elif "no module named" in error_msg:
            console.print("  1. Ensure all model files are importable")
            console.print("  2. Check if __init__.py exists in model directories")
            console.print("  3. Verify PYTHONPATH includes your project root")
        elif "connection" in error_msg or "refused" in error_msg:
            console.print("  1. Check if database server is running")
            console.print("  2. Verify DATABASE_URL credentials are correct")
            console.print("  3. Ensure database exists and is accessible")
        else:
            console.print("  1. Check migration files for syntax errors")
            console.print("  2. Verify database connection is working")
            console.print("  3. Run 'migrator status' to check current state")
        
        raise typer.Exit(1)


@app.command()
def downgrade(revision: str = typer.Option("-1", "--revision", "-r", help="Target revision")):
    """Rollback migrations"""
    try:
        config = MigratorConfig.load()
        backend = AlembicBackend(config)

        current = backend.current()
        info(f"Current revision: {current}")
        info(f"Downgrading to: {revision}")

        backend.downgrade(revision)

        success("Rollback complete")

    except Exception as e:
        error(f"Downgrade failed: {e}")
        raise typer.Exit(1)


@app.command()
def history():
    """Show migration history"""
    try:
        config = MigratorConfig.load()
        backend = AlembicBackend(config)

        migrations = backend.history()
        current = backend.current()

        if not migrations:
            info("No migrations found")
            return

        table = Table(title="Migration History")
        table.add_column("Revision", style="cyan")
        table.add_column("Message", style="white")
        table.add_column("Status", style="green")

        for migration in migrations:
            status_icon = "✅ applied" if migration["status"] == "applied" else "⏳ pending"
            table.add_row(migration["revision"][:12], migration["message"], status_icon)

        console.print(table)

    except Exception as e:
        error(f"Failed to get history: {e}")
        raise typer.Exit(1)


@app.command()
def current():
    """Show current revision"""
    try:
        config = MigratorConfig.load()
        backend = AlembicBackend(config)

        revision = backend.current()
        if revision:
            success(f"Current revision: {revision}")
        else:
            info("No migrations applied yet")

    except Exception as e:
        error(f"Failed to get current revision: {e}")
        raise typer.Exit(1)


@app.command()
def stamp(revision: str = typer.Argument("head", help="Target revision to stamp")):
    """Mark database as migrated without running migrations"""
    try:
        config = MigratorConfig.load()
        backend = AlembicBackend(config)

        info(f"Stamping database to revision: {revision}")
        backend.stamp(revision)

        success(f"Database marked as {revision}")

    except Exception as e:
        error(f"Stamp failed: {e}")
        raise typer.Exit(1)


@app.command()
def status():
    """Show migration status and pending migrations"""
    try:
        config = MigratorConfig.load()
        backend = AlembicBackend(config)

        current = backend.current()
        pending = backend.get_pending_migrations()
        existing_tables = backend.check_existing_tables()

        console.print("\n📊 Migration Status\n")
        console.print(f"Current revision: {current or 'None'}")
        console.print(f"Existing tables: {len(existing_tables)}")
        console.print(f"Pending migrations: {len(pending)}")

        if pending:
            console.print("\n⏳ Pending Migrations:")
            for mig in pending:
                console.print(f"  • {mig['revision'][:12]} - {mig['message']}")
        else:
            console.print("\n✅ All migrations applied")

    except Exception as e:
        error(f"Failed to get status: {e}")
        raise typer.Exit(1)
