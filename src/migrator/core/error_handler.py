"""Troubleshooting tips and error formatting for CLI commands."""
from rich.console import Console

console = Console()


def handle_init_no_base(searched: list[str]) -> None:
    if searched:
        from migrator.core.logger import info
        info(f"Searched in: {', '.join(searched[:5])}")
        if len(searched) > 5:
            info(f"... and {len(searched) - 5} more locations")
    console.print("\n💡 Troubleshooting Tips:")
    console.print("  1. Ensure your models inherit from Base")
    console.print("  2. Check if Base = declarative_base() exists")
    console.print("  3. Verify models are imported in __init__.py")
    console.print("  4. Use --base flag: migrator init --base app.core.database:Base")
    console.print("  5. Check that DATABASE_URL is correctly set")


def handle_migrate_error(error_msg: str) -> None:
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


def handle_no_base_tips() -> None:
    console.print("\n💡 Troubleshooting Tips:")
    console.print("  1. Ensure your models inherit from Base")
    console.print("  2. Check if Base = declarative_base() exists")
    console.print("  3. Verify models are imported in __init__.py")
    console.print("  4. Use --base flag: migrator makemigrations --base app.db:Base")
