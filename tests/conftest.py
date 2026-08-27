"""
Shared pytest fixtures for the Omi Companion backend

`backend/main.py` pulls in the whole capture stack (bleak, whisper, mediapipe,
easyocr, ...) transitively through its sibling modules, and instantiates each
processor in `OmiCompanionSystem.__init__`. None of that is needed to exercise
routing, so the sibling modules are replaced with mocks before `main` is
imported. Third-party packages are left alone - only this repo's own modules are
stubbed, so a real import error in `main.py` still surfaces.
"""
import importlib
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# module path -> attribute names main.py imports from it
_STUBBED_MODULES = {
    "ble.manager": ["BLEManager"],
    "audio.processor": ["AudioProcessor"],
    "vision.processor": ["VisionProcessor"],
    "ai.ollama_client": ["OllamaClient"],
    "ai.omi_client": ["OmiClient"],
    "utils.event_logger": ["EventLogger"],
}


def _install_stubs():
    """Register mock stand-ins for the heavy capture modules"""
    for module_path, attributes in _STUBBED_MODULES.items():
        package_name, _, module_name = module_path.rpartition(".")

        # Import the real package - `utils` also holds config.py and auth.py,
        # which must not be shadowed by a synthetic namespace module.
        package = importlib.import_module(package_name)

        module = types.ModuleType(module_path)
        for attribute in attributes:
            setattr(module, attribute, MagicMock(return_value=AsyncMock()))
        sys.modules[module_path] = module
        setattr(package, module_name, module)


@pytest.fixture(scope="session")
def main_module():
    """The imported `main` module, with the capture stack stubbed out"""
    _install_stubs()
    import main

    return main


@pytest.fixture
def app(main_module, monkeypatch):
    """A fresh FastAPI app. No API key is configured unless a test sets one."""
    from utils import auth

    monkeypatch.delenv(auth.API_KEY_ENV_VAR, raising=False)
    return main_module.create_app()


@pytest.fixture
def client(app):
    """Test client for the app, with startup/shutdown events suppressed"""
    from fastapi.testclient import TestClient

    # The startup handler only logs; the shutdown handler would await the mocked
    # capture system. Neither is under test, so the context manager is skipped.
    return TestClient(app)


@pytest.fixture
def api_key(monkeypatch):
    """Configure a known API key for the duration of one test"""
    from utils import auth

    key = "test-key-0123456789abcdef"
    monkeypatch.setenv(auth.API_KEY_ENV_VAR, key)
    return key
