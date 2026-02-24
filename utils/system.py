#!/usr/bin/env python3
# made by:    _    ____   ____    _    _   _  ____ _____ _     ___
#▄████▄ █████▄  ▄█████ ▄████▄ ███  ██  ▄████  ██████ ██     ▄████▄
#██▄▄██ ██▄▄██▄ ██     ██▄▄██ ██ ▀▄██ ██  ▄▄▄ ██▄▄   ██     ██  ██
#██  ██ ██   ██ ▀█████ ██  ██ ██   ██  ▀███▀  ██▄▄▄▄ ██████ ▀████▀
# --------------------------------------------------------------------- 

import json
import os
import re
import socket
import signal
import shlex
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path
from urllib import error, request
import tomllib
from utils.config_loader import ensure_config_module

ensure_config_module()
import config as config_module

from colorama import Fore, Style

from config import (
    ANTHROPIC_API_KEY,
    API_ENDPOINT,
    APP_NAME,
    APP_VERSION,
    CONFIG_DIR,
    CUSTOM_API_HANDLER,
    GEMINI_API_KEY,
    GITHUB_REPO,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    PYPI_PACKAGE,
)
from utils.ui import clear, cyber


# ═══════════════════════════════════════════════════════════════
#  :: Utilities
#  Utility functions such as ApiKEY verifier and signal handler
# ═══════════════════════════════════════════════════════════════
def checkAPI():
    endpoint = str(getattr(config_module, "API_ENDPOINT", API_ENDPOINT) or "").strip()
    handler = str(getattr(config_module, "CUSTOM_API_HANDLER", CUSTOM_API_HANDLER) or "").strip()
    endpoint_ok = endpoint and endpoint != "NOT_SET"
    handler_ok = handler and handler != "NOT_SET"
    if not endpoint_ok and not handler_ok:
        configure_custom_api(open_handler=True)
        endpoint = str(getattr(config_module, "API_ENDPOINT", API_ENDPOINT) or "").strip()
        handler = str(getattr(config_module, "CUSTOM_API_HANDLER", CUSTOM_API_HANDLER) or "").strip()
        endpoint_ok = endpoint and endpoint != "NOT_SET"
        handler_ok = handler and handler != "NOT_SET"
    if not endpoint_ok and not handler_ok:
        print(Fore.RED + "\nNo custom API set. Configure it with eva --custom-api")
        sys.exit(0)


def _default_custom_api_handler_path():
    return Path(CONFIG_DIR).expanduser().resolve() / "custom_api_handler.py"


def _custom_api_template(endpoint):
    target = str(endpoint or "").strip()
    if not target or target == "NOT_SET":
        target = "http://127.0.0.1:8000/gpt4"
    return (
        "#!/usr/bin/env python3\n"
        "import requests\n\n"
        f"API_ENDPOINT = {json.dumps(target)}\n\n"
        "def query_custom_api(history, endpoint=None, session=None, prompt=None):\n"
        "    target = endpoint or API_ENDPOINT\n"
        "    compiled_prompt = str(prompt or \"\").strip()\n"
        "    if not compiled_prompt:\n"
        "        for item in reversed(history):\n"
        "            if item.get(\"role\") == \"user\":\n"
        "                compiled_prompt = str(item.get(\"content\", \"\")).strip()\n"
        "                break\n"
        "    payload = {\n"
        "        \"prompt\": compiled_prompt,\n"
        "        \"conversation\": history,\n"
        "        \"session\": session,\n"
        "    }\n"
        "    r = requests.post(target, json=payload, timeout=None)\n"
        "    try:\n"
        "        data = r.json()\n"
        "    except ValueError:\n"
        "        return r.text\n"
        "    if isinstance(data, dict):\n"
        "        for key in (\"analysis\", \"response\", \"answer\", \"text\", \"content\", \"message\"):\n"
        "            value = data.get(key)\n"
        "            if isinstance(value, str) and value.strip():\n"
        "                return value\n"
        "    return str(data)\n"
    )


def _ensure_custom_api_handler_file(path, endpoint):
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(_custom_api_template(endpoint), encoding="utf-8")
    return target


def configure_custom_api(open_handler=True):
    endpoint_current = str(getattr(config_module, "API_ENDPOINT", API_ENDPOINT) or "").strip()
    handler_current = str(getattr(config_module, "CUSTOM_API_HANDLER", CUSTOM_API_HANDLER) or "").strip()
    if not handler_current or handler_current == "NOT_SET":
        handler_current = str(_default_custom_api_handler_path())
        _persist_key_to_config("CUSTOM_API_HANDLER", handler_current)
        setattr(config_module, "CUSTOM_API_HANDLER", handler_current)

    clear()
    cyber("CUSTOM API HANDLER", color=Fore.CYAN)
    endpoint_value = endpoint_current or "NOT_SET"
    handler_value = handler_current

    try:
        handler_path = _ensure_custom_api_handler_file(handler_value, endpoint_value)
    except OSError:
        fallback_handler = Path(config_module.__file__).resolve().parent / "custom_api_handler.py"
        handler_value = str(fallback_handler)
        _persist_key_to_config("CUSTOM_API_HANDLER", handler_value)
        setattr(config_module, "CUSTOM_API_HANDLER", handler_value)
        try:
            handler_path = _ensure_custom_api_handler_file(handler_value, endpoint_value)
        except OSError as exc:
            cyber(f"Could not prepare custom API handler: {exc}", color=Fore.RED)
            return False

    if open_handler:
        ok, msg = open_in_default_editor(handler_path)
        color = Fore.GREEN if ok else Fore.YELLOW
        cyber(msg, color=color)

    return True


def _read_key(name, config_value):
    env_key = os.getenv(name, "").strip()
    if env_key:
        os.environ[name] = env_key
        return env_key
    cfg_key = str(config_value or "").strip()
    if cfg_key and cfg_key != "NOT_SET":
        os.environ[name] = cfg_key
        return cfg_key
    return ""


def _persist_key_to_config(name, key):
    cfg_path = Path(config_module.__file__).resolve()
    try:
        raw = cfg_path.read_text(encoding="utf-8")
    except OSError:
        return False

    serialized = json.dumps(str(key))
    line = f"{name} = {serialized}"
    pattern = rf"^{re.escape(name)}\s*=.*$"
    if re.search(pattern, raw, flags=re.MULTILINE):
        updated = re.sub(pattern, line, raw, flags=re.MULTILINE)
    else:
        updated = raw.rstrip() + f"\n{line}\n"

    if updated == raw:
        return True

    try:
        cfg_path.write_text(updated, encoding="utf-8")
        return True
    except OSError:
        return False


def _ensure_provider_key(name, label, config_value):
    key = _read_key(name, config_value)
    if key:
        return key

    os.system("clear")
    cyber(f"{label} key not found! :: Please insert it below", color=Fore.RED)
    print("\nYour API key will be stored locally in config.py\n")
    key = input("#key > ").strip()
    if not key:
        print(Fore.RED + "\nNo key provided. Aborting.")
        sys.exit(1)

    os.environ[name] = key
    if _persist_key_to_config(name, key):
        print(Fore.GREEN + f"\n✔ {label} API key saved in config.py.")
    else:
        print(Fore.YELLOW + f"\n[!] Could not persist {label} key in config.py, using this session only.")
    time.sleep(1)
    return key


def checkOpenAIKey():
    return _ensure_provider_key("OPENAI_API_KEY", "OpenAI", OPENAI_API_KEY)


def checkAnthropicKey():
    return _ensure_provider_key("ANTHROPIC_API_KEY", "Anthropic", ANTHROPIC_API_KEY)


def checkGeminiKey():
    return _ensure_provider_key("GEMINI_API_KEY", "Gemini", GEMINI_API_KEY)


def ctrl_c_handler(signum, frame):
    raise KeyboardInterrupt


def register_signal_handler():
    signal.signal(signal.SIGINT, ctrl_c_handler)


def graceful_exit():
    cyber("EVA OFFLINE :: SESSION IS SAVED", color=Fore.RED)
    print(Fore.YELLOW + "🜂  E x i t i n g  E V A ...")
    time.sleep(2.5)
    clear()
    sys.exit(0)


def _split_version(value):
    clean = str(value).strip().lower().lstrip("v")
    parts = []
    for part in clean.split("."):
        digits = ""
        for char in part:
            if char.isdigit():
                digits += char
            else:
                break
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _is_newer(latest, current):
    return _split_version(latest) > _split_version(current)


_UPDATE_STATUS_CACHE = None


def _module_git_root():
    here = Path(__file__).resolve()
    for base in (here.parent, *here.parents):
        if (base / ".git").exists():
            return base
    return None


def _installed_package_version():
    try:
        return metadata.version(PYPI_PACKAGE)
    except metadata.PackageNotFoundError:
        return None


def _is_path_in_repo(raw_path, repo_root):
    if not raw_path:
        return False
    try:
        candidate = Path(raw_path).expanduser()
        if not candidate.exists():
            return False
        candidate = candidate.resolve()
        return candidate.is_relative_to(repo_root.resolve())
    except OSError:
        return False


def _running_from_repo_checkout(repo_root):
    main_module = sys.modules.get("__main__")
    main_file = getattr(main_module, "__file__", "")
    if _is_path_in_repo(main_file, repo_root):
        return True
    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and Path(argv0).expanduser().exists() and _is_path_in_repo(argv0, repo_root):
        return True
    return False


def _read_local_version(base_path):
    pyproject = base_path / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            version = data.get("project", {}).get("version")
            if version:
                return str(version).strip()
        except (tomllib.TOMLDecodeError, OSError):
            pass

    cfg_path = base_path / "config.py"
    if cfg_path.exists():
        try:
            raw = cfg_path.read_text(encoding="utf-8")
        except OSError:
            return None
        match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', raw, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _git_branch():
    repo_root = _module_git_root()
    if repo_root is None:
        return "main"
    branch_detect = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True
    )
    if branch_detect.returncode == 0 and branch_detect.stdout.strip():
        return branch_detect.stdout.strip()
    return "main"


def _update_source():
    repo_root = _module_git_root()
    installed_version = _installed_package_version()
    if repo_root is not None and command_exists("git") and _running_from_repo_checkout(repo_root):
        return "github"
    if installed_version:
        return "pypi"
    if repo_root is not None and command_exists("git"):
        return "github"
    return "pypi"


def _can_reach_tls_host(host):
    try:
        sock = socket.create_connection((host, 443), timeout=2)
        sock.close()
        return True
    except OSError:
        return False


def get_current_version():
    repo_root = _module_git_root()
    installed_version = _installed_package_version()

    if repo_root is not None and _running_from_repo_checkout(repo_root):
        local_version = _read_local_version(repo_root)
        if local_version:
            return local_version

    if installed_version:
        return installed_version

    if repo_root is not None:
        local_version = _read_local_version(repo_root)
        if local_version:
            return local_version

    local_version = _read_local_version(Path.cwd())
    if local_version:
        return local_version
    return APP_VERSION


def fetch_latest_pypi_version():
    url = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"
    req = request.Request(url, headers={"Accept": "application/json", "User-Agent": "eva-update-check"})
    try:
        with request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("info", {}).get("version")
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def fetch_latest_github_version(branch=None):
    target_branch = branch or _git_branch()
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{target_branch}/config.py"
    req = request.Request(url, headers={"Accept": "text/plain", "User-Agent": "eva-update-check"})
    try:
        with request.urlopen(req, timeout=5) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except (error.URLError, TimeoutError):
        return None
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', raw, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def get_update_status(force=False):
    global _UPDATE_STATUS_CACHE
    if _UPDATE_STATUS_CACHE is not None and not force:
        return _UPDATE_STATUS_CACHE

    current = get_current_version()
    source = _update_source()
    branch = _git_branch() if source == "github" else None
    if source == "github" and _can_reach_tls_host("raw.githubusercontent.com"):
        latest = fetch_latest_github_version(branch)
    elif source == "pypi" and _can_reach_tls_host("pypi.org"):
        latest = fetch_latest_pypi_version()
    else:
        latest = None
    available = bool(latest) and _is_newer(latest, current)

    repo_root = _module_git_root()
    if source == "github" and repo_root is not None:
        command = f"git -C {shlex.quote(str(repo_root))} pull --tags origin {branch}"
    else:
        command = "eva -u"
    prefix = "|> Update github checkout running " if source == "github" else "|> Update eva to latest version running "

    _UPDATE_STATUS_CACHE = {
        "available": available,
        "current": current,
        "latest": latest,
        "source": source,
        "command": command,
        "hint_prefix": prefix,
    }
    return _UPDATE_STATUS_CACHE


def checkupdts():
    status = get_update_status()
    if status.get("available"):
        current = status.get("current")
        latest = status.get("latest")
        hint_prefix = status.get("hint_prefix")
        command = status.get("command")
        print("\n" + Fore.CYAN + "." * 40)
        print(Fore.CYAN + f"[!] U P D A T E   A V A I L A B L E: {current} → {latest}")
        print(Fore.GREEN + hint_prefix + Style.BRIGHT + Fore.YELLOW + command + Style.RESET_ALL)
        print("." * 40 + Fore.CYAN + "\n")


def run_self_update():
    print(Fore.CYAN + f"\nChecking updates for {APP_NAME}...\n")
    status = get_update_status(force=True)
    if not status.get("available"):
        cyber("EVA is already up to date.", color=Fore.CYAN)
        return 0

    latest = status.get("latest") or "latest"
    source = status.get("source")
    print(Style.BRIGHT + Fore.MAGENTA + f"Update {latest} found! Installing . . . . " + Style.RESET_ALL)

    repo_root = _module_git_root()
    updated = False
    if source == "github" and repo_root is not None and command_exists("git"):
        branch = _git_branch()
        pull_result = subprocess.run(
            ["git", "-C", str(repo_root), "pull", "--tags", "origin", branch],
            text=True
        )
        updated = pull_result.returncode == 0
    else:
        pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", PYPI_PACKAGE, "--break-system-packages"]
        pip_result = subprocess.run(pip_cmd, text=True, capture_output=True)
        if pip_result.returncode != 0 and "no such option: --break-system-packages" in (pip_result.stderr or "").lower():
            pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", PYPI_PACKAGE]
            pip_result = subprocess.run(pip_cmd, text=True)
        updated = pip_result.returncode == 0

    print(Fore.CYAN + "Almost done . . . . ")
    if updated:
        global _UPDATE_STATUS_CACHE
        _UPDATE_STATUS_CACHE = None
        cyber("✔ Update process finished. Restart EVA to use the latest version.", color=Fore.GREEN)
        return 0

    print(Fore.RED + "\n[!] Could not auto-update EVA in this environment.")
    if source == "github":
        if repo_root is not None:
            print(Fore.YELLOW + f"Try manually: git -C {shlex.quote(str(repo_root))} pull --tags origin {_git_branch()}")
        else:
            print(Fore.YELLOW + f"Try manually: git pull --tags origin {_git_branch()}")
    else:
        print(Fore.YELLOW + f"Try manually: {sys.executable} -m pip install --upgrade {PYPI_PACKAGE}")
    return 1


# ================= STARTUP OF EVA here =================
def command_exists(cmd):
    return subprocess.call(
        ["which", cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ) == 0


def ollama_running():
    try:
        subprocess.check_output(['ollama', 'list'], stderr=subprocess.STDOUT, text=True)
        return True
    except subprocess.CalledProcessError as e:
        if "server not responding" in e.output.lower():
            return False
        return False


def start_ollama():
    clear()
    print("\n\n\n")
    print(Fore.YELLOW + "🜂 OLLAMA NOT RUNNING :: Starting for you...\n\n")

    with open(os.devnull, 'w') as DEVNULL:
        subprocess.Popen(
            ['ollama', 'serve'],
            stdout=DEVNULL,
            stderr=DEVNULL,
            stdin=DEVNULL,
            close_fds=True,
            start_new_session=True
        )

    time.sleep(3)


def model_exists():
    r = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True
    )
    return OLLAMA_MODEL in r.stdout


def open_in_default_editor(path):
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return False, f"File not found: {target}"

    editor = os.environ.get("EDITOR", "").strip()
    try:
        if editor:
            editor_args = shlex.split(editor)
            terminal_editors = {"vi", "vim", "nvim", "nano", "micro", "emacs", "hx", "kak"}
            base = Path(editor_args[0]).name if editor_args else ""
            if base in terminal_editors:
                if sys.stdin.isatty() and sys.stdout.isatty():
                    proc = subprocess.run([*editor_args, str(target)])
                    if proc.returncode == 0:
                        return True, f"::EVA Configuration Saved"
                    return False, f":: Error [{proc.returncode}]::"
            else:
                subprocess.Popen([*editor_args, str(target)])
                return True, f"::Opened EVA config files::"
    except OSError:
        pass

    try:
        if sys.platform.startswith("darwin"):
            proc = subprocess.run(
                ["open", str(target)],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if proc.returncode == 0:
                return True, f"Opened config file: {target}"
            err = (proc.stderr or proc.stdout or "").strip()
            return False, f"Failed to open file: {err or 'open returned non-zero status'}"
        if os.name == "nt":
            os.startfile(str(target))
            return True, f"Opened config file: {target}"
        proc = subprocess.run(
            ["xdg-open", str(target)],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if proc.returncode == 0:
            return True, f"Opened config file: {target}"
        err = (proc.stderr or proc.stdout or "").strip()
        return False, f"Failed to open file: {err or 'xdg-open returned non-zero status'}"
    except OSError as exc:
        return False, f"Failed to open file: {exc}"
    except subprocess.TimeoutExpired:
        return False, "Failed to open file: opener timed out"
