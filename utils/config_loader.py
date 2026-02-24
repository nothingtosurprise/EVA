#!/usr/bin/env python3

import importlib
import importlib.util
import sys
from importlib import metadata
from pathlib import Path


def _resolve_app_version():
    try:
        return metadata.version("eva-exploit")
    except metadata.PackageNotFoundError:
        return "3.4.3"


def _default_config_source():
    app_version = _resolve_app_version()
    return f"""#!/usr/bin/env python3
import getpass
from pathlib import Path

APP_NAME = "EVA"
APP_VERSION = "{app_version}"
GITHUB_REPO = "arcangel0/EVA"
PYPI_PACKAGE = "eva-exploit"
API_ENDPOINT = "NOT_SET"
CUSTOM_API_HANDLER = "custom.py"
G4F_MODEL = "gpt-oss-120b"
G4F_URL = "https://api.gpt4free.workers.dev/api/novaai/chat/completions"
OLLAMA_MODEL = "ALIENTELLIGENCE/whiterabbitv2"
SEARCHVULN_MODEL = "gpt-oss:120b-cloud"
SEARCVULN_URL = "https://ollama.com/api/chat"
OLLAMA_API_KEY = "NOT_SET"
OPENAI_API_KEY = "NOT_SET"
ANTHROPIC_API_KEY = "NOT_SET"
GEMINI_API_KEY = "NOT_SET"
ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
GEMINI_MODEL = "gemini-2.0-flash"
OLLAMA_CLOUD_TIMEOUT = 45
CONFIG_DIR = Path.home() / "EVA_data"
SESSIONS_DIR = CONFIG_DIR / "sessions"
REPORTS_DIR = CONFIG_DIR / "reports"
MAPS_DIR = CONFIG_DIR / "attack_maps"
TERMS_ACCEPTEDTHING = CONFIG_DIR / ".confirm"
try:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    CONFIG_DIR = Path("/tmp") / "EVA_data"
    SESSIONS_DIR = CONFIG_DIR / "sessions"
    REPORTS_DIR = CONFIG_DIR / "reports"
    MAPS_DIR = CONFIG_DIR / "attack_maps"
    TERMS_ACCEPTEDTHING = CONFIG_DIR / ".confirm"
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
username = getpass.getuser()
MAX_RETRIES = 10
RETRY_DELAY = 10
"""


def _load_module_from_path(path):
    spec = importlib.util.spec_from_file_location("config", str(path))
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules["config"] = module
    return module


def _load_module_from_source(source, source_name="<eva-generated-config>"):
    spec = importlib.util.spec_from_loader("config", loader=None, origin=source_name)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = source_name
    exec(compile(source, source_name, "exec"), module.__dict__)
    sys.modules["config"] = module
    return module


def _candidate_fallback_paths():
    return [
        Path.home() / "EVA_data" / "config.py",
        Path("/tmp") / "eva_config.py",
    ]


def _load_or_create_fallback(path, source):
    if path.exists():
        return _load_module_from_path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    except OSError:
        return None
    return _load_module_from_path(path)


def ensure_config_module():
    existing = sys.modules.get("config")
    if existing is not None:
        return existing

    try:
        return importlib.import_module("config")
    except ModuleNotFoundError:
        pass

    repo_config = Path(__file__).resolve().parents[1] / "config.py"
    if repo_config.exists():
        loaded = _load_module_from_path(repo_config)
        if loaded is not None:
            return loaded

    source = _default_config_source()
    for path in _candidate_fallback_paths():
        loaded = _load_or_create_fallback(path, source)
        if loaded is not None:
            return loaded

    return _load_module_from_source(source)


config_module = ensure_config_module()
