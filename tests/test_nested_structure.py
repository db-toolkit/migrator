import os

from migrator.core.detector import ModelDetector


def test_nested_base_detection(temp_dir):
    """Test Base detection in nested structure"""
    app_dir = temp_dir / "app" / "core"
    app_dir.mkdir(parents=True)

    (app_dir / "__init__.py").write_text("")
    (temp_dir / "app" / "__init__.py").write_text("")

    (app_dir / "database.py").write_text("""
from sqlalchemy.orm import declarative_base
Base = declarative_base()
""")

    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        base = ModelDetector.find_base()
        assert base is not None
    finally:
        os.chdir(original_cwd)


def test_explicit_base_path(temp_dir):
    """Test explicit Base path"""
    app_dir = temp_dir / "app" / "core"
    app_dir.mkdir(parents=True)

    (app_dir / "__init__.py").write_text("")
    (temp_dir / "app" / "__init__.py").write_text("")

    (app_dir / "database.py").write_text("""
from sqlalchemy.orm import declarative_base
Base = declarative_base()
""")

    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        base = ModelDetector.find_base(explicit_path="app.core.database:Base")
        assert base is not None
    finally:
        os.chdir(original_cwd)


def test_explicit_base_path_with_custom_name(temp_dir):
    """Test explicit Base path with custom attribute name"""
    app_dir = temp_dir / "app" / "db"
    app_dir.mkdir(parents=True)

    (app_dir / "__init__.py").write_text("")
    (temp_dir / "app" / "__init__.py").write_text("")

    (app_dir / "models.py").write_text("""
from sqlalchemy.orm import declarative_base
DBBase = declarative_base()
""")

    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        base = ModelDetector.find_base(explicit_path="app.db.models:DBBase")
        assert base is not None
    finally:
        os.chdir(original_cwd)


def test_searched_paths_tracking(temp_dir):
    """Test that searched paths are tracked"""
    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        ModelDetector.find_base()
        searched = ModelDetector.get_searched_paths()
        assert len(searched) > 0
        assert "app.models" in searched
        assert "app.core.database" in searched
    finally:
        os.chdir(original_cwd)


def test_explicit_path_searched_first(temp_dir):
    """Test that explicit path is searched first"""
    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        ModelDetector.find_base(explicit_path="custom.path:Base")
        searched = ModelDetector.get_searched_paths()
        assert searched[0] == "custom.path:Base"
    finally:
        os.chdir(original_cwd)
