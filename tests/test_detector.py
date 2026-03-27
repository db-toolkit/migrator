import os

from migrator.core.detector import ModelDetector


def test_find_base_returns_none_when_not_found(temp_dir):
    """Test that find_base returns None when no Base found"""
    result = ModelDetector.find_base()
    assert result is None


def test_scan_project_skips_excluded_dirs(temp_dir):
    """Test that scan skips venv and other excluded directories"""
    venv_dir = temp_dir / "venv"
    venv_dir.mkdir()

    model_file = venv_dir / "models.py"
    model_file.write_text("class Base: pass")

    result = ModelDetector.find_base()
    assert result is None


def test_find_model_modules_detects_subclasses(temp_dir):
    """find_model_modules returns modules that define Base subclasses"""
    (temp_dir / "mydb.py").write_text(
        "from sqlalchemy.orm import declarative_base\nBase = declarative_base()\n"
    )
    (temp_dir / "user_model.py").write_text(
        "from mydb import Base\nfrom sqlalchemy import Column, Integer\n"
        "class User(Base):\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True)\n"
    )
    (temp_dir / "post_model.py").write_text(
        "from mydb import Base\nfrom sqlalchemy import Column, Integer, String\n"
        "class Post(Base):\n    __tablename__ = 'posts'\n    id = Column(Integer, primary_key=True)\n"
        "    title = Column(String)\n"
    )

    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        base = ModelDetector.find_base(explicit_path="mydb:Base")
        assert base is not None

        modules = ModelDetector.find_model_modules(base)
        assert "user_model" in modules
        assert "post_model" in modules
    finally:
        os.chdir(original_cwd)


def test_find_model_modules_excludes_base_module(temp_dir):
    """find_model_modules does not include the module that defines Base"""
    (temp_dir / "mydb.py").write_text(
        "from sqlalchemy.orm import declarative_base\nBase = declarative_base()\n"
    )
    (temp_dir / "user_model.py").write_text(
        "from mydb import Base\nfrom sqlalchemy import Column, Integer\n"
        "class User(Base):\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True)\n"
    )

    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        base = ModelDetector.find_base(explicit_path="mydb:Base")
        modules = ModelDetector.find_model_modules(base)
        assert "mydb" not in modules
    finally:
        os.chdir(original_cwd)


def test_find_model_modules_empty_when_no_subclasses(temp_dir):
    """find_model_modules returns empty list when no models subclass Base"""
    (temp_dir / "mydb.py").write_text(
        "from sqlalchemy.orm import declarative_base\nBase = declarative_base()\n"
    )

    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        base = ModelDetector.find_base(explicit_path="mydb:Base")
        modules = ModelDetector.find_model_modules(base)
        assert modules == []
    finally:
        os.chdir(original_cwd)


def test_env_py_contains_model_imports(temp_dir):
    """init generates env.py with auto-detected model imports"""
    (temp_dir / "mydb.py").write_text(
        "from sqlalchemy.orm import declarative_base\nBase = declarative_base()\n"
    )
    (temp_dir / "user_model.py").write_text(
        "from mydb import Base\nfrom sqlalchemy import Column, Integer\n"
        "class User(Base):\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True)\n"
    )

    import os
    from pathlib import Path

    from typer.testing import CliRunner

    from migrator.cli import app

    runner = CliRunner()
    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        db_path = temp_dir / "test.db"
        result = runner.invoke(app, ["init", "--base", "mydb:Base"], env={"DATABASE_URL": f"sqlite:///{db_path}"})
        assert result.exit_code == 0, result.stdout

        env_content = Path("migrations/env.py").read_text()
        assert "import user_model" in env_content
    finally:
        os.chdir(original_cwd)

