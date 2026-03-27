# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0] - 2026-03-27

### Added
- Auto-detection of model modules — `migrator init` now scans the project for all classes that subclass the detected `Base` and adds them as imports in the generated `env.py`, so Alembic autogenerate sees all tables without manual configuration
- MySQL support via `uv add migrator-cli[mysql]` (includes `pymysql` and `cryptography`)
- `[all]` extra installs all database drivers: `uv add migrator-cli[all]`
- Minimum Python version raised to 3.11

### Changed
- `psycopg2-binary` moved from core dependencies to `[postgres]` / `[all]` optional extras — SQLite and MySQL users no longer install it unnecessarily
- `alembic.ini` no longer contains hardcoded database credentials — URL is loaded from `DATABASE_URL` at runtime in `env.py`, making `alembic.ini` safe to commit

### Fixed
- `migrate` command no longer silently fails in non-interactive environments (CI, pipes) — confirmation prompts default to proceeding
- `show_migration_sql` (`--dry-run`, `--show-sql`) now correctly captures and displays SQL output
- `history` command applied/pending status is now correct for branched migration histories
- `ModelDetector` no longer returns stale results when called multiple times in the same process

## [0.4.2] - 2025-12-20

### Changed
- Migrated repository to db-toolkit organization
- Updated all GitHub URLs from personal repo to https://github.com/db-toolkit/migrator

## [0.4.1] - 2025-12-02

### Added
- Optional migration messages with auto-generation
- Better error messages with context-specific troubleshooting tips
- `--version` command to show CLI version
- Timestamped migration filenames (YYYYMMDD_HHMMSS_message)
- `--show-sql` flag for makemigrations command
- `--dry-run` flag for migrate command to preview SQL
- `--yes` flag for migrate command to skip confirmation
- Confirmation prompt before applying migrations

### Fixed
- Base class import path detection for nested project structures

## [0.4.0] - 2025-11-17

### Fixed
- Automatic Python path handling in migration environment
- History status calculation showing correct applied/pending status

### Improved
- Better migration status tracking after downgrade and stamp operations
- Enhanced env.py template with automatic path resolution

## [0.3.0] - 2025-11-14

### Added
- `--base` flag to specify Base class location explicitly (e.g., `app.core.database:Base`)
- `--config` flag to specify config file path
- `--verbose` flag for detailed detection output
- Automatic async URL conversion (asyncpg, aiomysql, aiosqlite)
- Multi-directory .env file search (searches up 5 parent directories)
- Support for nested project structures (app.core.database)
- Expanded common model paths for better auto-detection (12 new paths)
- Search path tracking for better error messages

### Fixed
- .env file not found in parent directories
- Base class detection in nested structures
- Async SQLAlchemy URL compatibility
- Poor error messages - now shows searched paths and helpful hints

## [0.2.0] - 2025-11-11

### Added
- `stamp` command to mark database as migrated without running migrations
- `status` command to show pending migrations and database state
- Pre-migration check for existing tables with interactive prompt
- `--dry-run` flag for migrate command (documentation)
- Better error messages for foreign key constraint failures

### Fixed
- Added `psycopg2-binary` as core dependency for PostgreSQL support
- Improved handling of existing database schemas
- Added helpful tips when migration conflicts occur

## [0.1.0] - 2025-11-11

### Added
- Initial release
- CLI commands: init, makemigrations, migrate, downgrade, history, current
- Auto-detect SQLAlchemy Base classes
- Auto-detect database URL from multiple sources (.env, settings.py, config.py, config.yaml, config.toml)
- Alembic backend integration
- Custom templates with auto-import
- Rich terminal output with colors and emojis
