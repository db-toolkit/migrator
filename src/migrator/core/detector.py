import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any, List, Optional

from migrator.core.constants import COMMON_MODEL_PATHS, EXCLUDED_DIRS


class ModelDetector:
    """Auto-detect SQLAlchemy Base classes"""

    searched_paths: List[str] = []

    @classmethod
    def find_base(cls, explicit_path: Optional[str] = None) -> Optional[Any]:
        """Find SQLAlchemy declarative base"""
        cls.searched_paths = []
        cls._detected_import_path = None

        # Ensure cwd is on path once — not repeated in every helper
        cwd = str(Path.cwd())
        if cwd not in sys.path:
            sys.path.insert(0, cwd)

        # Clear cached project modules whose file is not under current cwd
        _project_roots = {p.split(".")[0] for p in COMMON_MODEL_PATHS}
        for key in list(sys.modules.keys()):
            if key.split(".")[0] not in _project_roots:
                continue
            mod_file = getattr(sys.modules[key], "__file__", None)
            if mod_file is None or not mod_file.startswith(cwd):
                del sys.modules[key]

        if explicit_path:
            cls.searched_paths.append(explicit_path)
            base = cls._try_explicit_path(explicit_path)
            if base:
                cls._detected_import_path = explicit_path if ":" in explicit_path else f"{explicit_path}.Base"
                return base

        for path in COMMON_MODEL_PATHS:
            cls.searched_paths.append(path)
            base = cls._try_import(path)
            if base:
                cls._detected_import_path = f"{path}.Base"
                return base

        cls.searched_paths.append("project scan")
        return cls._scan_project()

    @classmethod
    def get_searched_paths(cls) -> List[str]:
        return cls.searched_paths

    @classmethod
    def get_detected_import_path(cls) -> Optional[str]:
        return getattr(cls, '_detected_import_path', None)

    @classmethod
    def find_model_modules(cls, base: Any) -> List[str]:
        """Find all modules that define subclasses of the given Base.

        Returns importable module paths e.g. ['app.models.user', 'app.models.post'].
        Excludes the module that defines Base itself.
        """
        base_module = getattr(base, '__module__', None)

        # Collect project files under cwd
        project_files: set = set()
        for py_file in Path.cwd().rglob("*.py"):
            if any(excluded in str(py_file) for excluded in EXCLUDED_DIRS):
                continue
            try:
                relative_path = py_file.relative_to(Path.cwd())
                module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
                module_path = ".".join(module_parts)
                project_files.add(module_path)

                if module_path == base_module or module_path in sys.modules:
                    continue

                try:
                    importlib.import_module(module_path)
                except Exception:
                    continue
            except Exception:
                continue

        # Collect all mapped subclass modules once after all imports
        result: List[str] = []
        seen: set = set()
        for mapper in base.registry.mappers:
            mn = mapper.class_.__module__
            if mn and mn not in seen and mn != base_module and not mn.startswith("sqlalchemy"):
                seen.add(mn)
                result.append(mn)

        return [m for m in result if m in project_files]

    @staticmethod
    def _try_explicit_path(path: str) -> Optional[Any]:
        """Load Base from explicit path like 'app.core.database:Base'"""
        try:
            if ":" in path:
                module_path, attr_name = path.split(":", 1)
            else:
                module_path = path
                attr_name = "Base"

            module = importlib.import_module(module_path)

            if hasattr(module, attr_name):
                obj = getattr(module, attr_name)
                if hasattr(obj, "metadata") and hasattr(obj, "registry"):
                    return obj
        except (ImportError, AttributeError, ValueError):
            pass

        return None

    @staticmethod
    def _try_import(module_path: str) -> Optional[Any]:
        try:
            module = importlib.import_module(module_path)

            if hasattr(module, "Base"):
                return module.Base

            for name, obj in inspect.getmembers(module):
                if hasattr(obj, "metadata") and hasattr(obj, "registry"):
                    return obj
        except (ImportError, AttributeError):
            pass
        return None

    @classmethod
    def _scan_project(cls) -> Optional[Any]:
        """Scan .py files for Base classes and return with proper import path"""
        for py_file in Path.cwd().rglob("*.py"):
            if any(excluded in str(py_file) for excluded in EXCLUDED_DIRS):
                continue

            try:
                relative_path = py_file.relative_to(Path.cwd())
                module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
                module_path = ".".join(module_parts)

                try:
                    module = importlib.import_module(module_path)
                except ImportError:
                    spec = importlib.util.spec_from_file_location(module_path, py_file)
                    if not spec or not spec.loader:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_path] = module
                    spec.loader.exec_module(module)

                for name, obj in inspect.getmembers(module):
                    if (
                        name == "Base"
                        and hasattr(obj, "metadata")
                        and hasattr(obj, "registry")
                        and not obj.__module__.startswith("sqlalchemy")
                    ):
                        cls._detected_import_path = f"{module_path}.Base"
                        return obj
            except Exception:
                continue
        return None
