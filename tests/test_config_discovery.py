import os

from migrator.utils.config_loader import ConfigLoader


def test_env_file_in_parent_directory(temp_dir):
    """Test .env discovery in parent directory"""
    backend_dir = temp_dir / "backend"
    backend_dir.mkdir()

    (temp_dir / ".env").write_text("DATABASE_URL=postgresql://test")

    original_cwd = os.getcwd()
    try:
        os.chdir(backend_dir)
        env_file = ConfigLoader._find_env_file()
        assert env_file is not None
        assert env_file.resolve() == (temp_dir / ".env").resolve()
    finally:
        os.chdir(original_cwd)


def test_env_file_in_current_directory(temp_dir):
    """Test .env discovery in current directory"""
    (temp_dir / ".env").write_text("DATABASE_URL=postgresql://test")

    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        env_file = ConfigLoader._find_env_file()
        assert env_file is not None
        assert env_file.resolve() == (temp_dir / ".env").resolve()
    finally:
        os.chdir(original_cwd)


def test_async_url_conversion_asyncpg():
    """Test async URL conversion for asyncpg"""
    url = "postgresql+asyncpg://user:pass@localhost/db"
    converted = ConfigLoader._normalize_database_url(url)
    assert "+asyncpg" not in converted
    assert converted == "postgresql://user:pass@localhost/db"


def test_async_url_conversion_aiomysql():
    """Test async URL conversion for aiomysql"""
    url = "mysql+aiomysql://user:pass@localhost/db"
    converted = ConfigLoader._normalize_database_url(url)
    assert "+aiomysql" not in converted
    assert converted == "mysql+pymysql://user:pass@localhost/db"


def test_async_url_conversion_aiosqlite():
    """Test async URL conversion for aiosqlite"""
    url = "sqlite+aiosqlite:///test.db"
    converted = ConfigLoader._normalize_database_url(url)
    assert "+aiosqlite" not in converted
    assert converted == "sqlite:///test.db"


def test_sync_url_unchanged():
    """Test that sync URLs are not modified"""
    url = "postgresql://user:pass@localhost/db"
    converted = ConfigLoader._normalize_database_url(url)
    assert converted == url


def test_explicit_config_python(temp_dir):
    """Test explicit Python config file"""
    config_file = temp_dir / "settings.py"
    config_file.write_text('DATABASE_URL = "postgresql://explicit"')

    url = ConfigLoader._try_explicit_config(config_file)
    assert url == "postgresql://explicit"


def test_explicit_config_yaml(temp_dir):
    """Test explicit YAML config file"""
    config_file = temp_dir / "config.yaml"
    config_file.write_text("database:\n  url: postgresql://yaml")

    url = ConfigLoader._try_explicit_config(config_file)
    assert url == "postgresql://yaml"


def test_explicit_config_nonexistent(temp_dir):
    """Test explicit config with nonexistent file"""
    config_file = temp_dir / "nonexistent.py"
    url = ConfigLoader._try_explicit_config(config_file)
    assert url is None


def test_explicit_config_toml(temp_dir):
    """Test explicit TOML config file"""
    config_file = temp_dir / "config.toml"
    config_file.write_text('[database]\nurl = "postgresql://toml"\n')
    url = ConfigLoader._try_explicit_config(config_file)
    assert url == "postgresql://toml"


def test_explicit_config_python_sqlalchemy_uri(temp_dir):
    """Test explicit Python config using SQLALCHEMY_DATABASE_URI"""
    config_file = temp_dir / "settings.py"
    config_file.write_text('SQLALCHEMY_DATABASE_URI = "postgresql://sqlalchemy"')
    url = ConfigLoader._try_explicit_config(config_file)
    assert url == "postgresql://sqlalchemy"


def test_load_database_url_no_source_raises(temp_dir, monkeypatch):
    """load_database_url raises ValueError when no source found"""
    import os
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SQLALCHEMY_DATABASE_URI", raising=False)
    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        try:
            ConfigLoader.load_database_url()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "DATABASE_URL" in str(e)
    finally:
        os.chdir(original_cwd)


def test_find_env_file_returns_none_when_missing(temp_dir):
    """_find_env_file returns None when no .env exists in hierarchy"""
    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        result = ConfigLoader._find_env_file()
        assert result is None
    finally:
        os.chdir(original_cwd)
