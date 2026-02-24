#!/usr/bin/env python3
# made by:    _    ____   ____    _    _   _  ____ _____ _     ___
#▄████▄ █████▄  ▄█████ ▄████▄ ███  ██  ▄████  ██████ ██     ▄████▄
#██▄▄██ ██▄▄██▄ ██     ██▄▄██ ██ ▀▄██ ██  ▄▄▄ ██▄▄   ██     ██  ██
#██  ██ ██   ██ ▀█████ ██  ██ ██   ██  ▀███▀  ██▄▄▄▄ ██████ ▀████▀
# ---------------------------------------------------------------------
import json
import argparse
import os
import subprocess
import sys
import time
import shutil
from utils.config_loader import ensure_config_module

ensure_config_module()
import config as config_module
# ============ Check modules, and autoinstall if not present ============
try:
    from colorama import Fore, Style
    import openai
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "colorama", "--break-system-packages"])
    subprocess.run([sys.executable, "-m", "pip", "install", "openai", "--break-system-packages"])
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "--break-system-packages"])
    from colorama import Fore
    import openai
    import requests

from config import TERMS_ACCEPTEDTHING, OLLAMA_MODEL, SESSIONS_DIR, CONFIG_DIR
from modules.exploit_search import run_exploit_search
from sessions.eva_session import Eva
from utils.system import (
    checkAnthropicKey,
    checkAPI,
    checkGeminiKey,
    checkOpenAIKey,
    checkupdts,
    command_exists,
    configure_custom_api,
    get_current_version,
    model_exists,
    ollama_running,
    register_signal_handler,
    run_self_update,
    start_ollama,
    open_in_default_editor,
)
from utils.ui import banner, clear, cyber, menu, get_sessions


def main():
    banner(get_current_version())
    if not TERMS_ACCEPTEDTHING.exists():
        print(Fore.RED + """
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
➤ THIS TOOL IS FOR:
- CTFs
- LABS
- SYSTEMS YOU OWN
🜂 UNAUTHORIZED USE IS ILLEGAL
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
""")

        if input("Do you have authorization to proceed with this tool? (yes/no): ").strip().lower() != "yes":
            sys.exit()
        TERMS_ACCEPTEDTHING.write_text("acknowledged\n", encoding="utf-8")
    
    sessions = list(SESSIONS_DIR.glob("*.json"))
    opts = [f"[{i+1}] {s.stem}" for i, s in enumerate(sessions)]
    opts.append("[+] NEW SESSION")
    opts.append("[:>] UPDATE EVA")
    opts.append("[-] EXIT EVA")

    sel = get_sessions("EVA SESSIONS", opts,get_current_version())

    # =========================
    # GETS EXISTING SESSION
    # =========================
    if sel < len(sessions):
        session = sessions[sel]
        data = json.loads(session.read_text())
        backend = data.get("backend", "ollama")

        Eva(session, backend, main).chat()
        return

    if sel == len(sessions) + 2:
        print("\n")
        cyber("[+] Leaving EVA", color=Fore.RED)
        time.sleep(1.2)
        raise SystemExit(0)

    if sel == len(sessions) + 1:
        code = run_self_update()
        if code == 0:
            cyber("[+] Restarting EVA", color=Fore.CYAN)
            time.sleep(1)
            try:
                os.execv(sys.executable, [sys.executable, *sys.argv])
            except OSError as exc:
                cyber(f"[!] Failed to auto-restart EVA: {exc}", color=Fore.RED)
                time.sleep(1.2)
        return main()

    # =========================
    # NEW SESSION
    # =========================
    model = menu(
        "SELECT BACKEND",
        [
            "< GO BACK",
            "Use WhiteRabbit-Neo LLM locally (recommended)",
            "GPT-5 (Needs OpenAI ApiKey)",
            "G4F.dev (Free API endpoint with gpt-5.1)",
            "Anthropic Claude (Needs Anthropic API key)",
            "Google Gemini (Needs Gemini API key)",
            "Use Custom API endpoint (Please check configs to set your own endpoint)"
        ]
    )

    if model == 0:
        return main()

    if model == 1:
        backend = "ollama"

        if not command_exists("ollama"):
            clear()
            cyber("// Ollama is not installed. Install it first.", color=Fore.RED)
            time.sleep(3)
            return main()
        if not ollama_running():
            start_ollama()

        if not model_exists():
            clear()
            pull = menu(f"Model {OLLAMA_MODEL} not found. Pull it?", ["Yes", "No"])
            if pull == 0:
                subprocess.run(["ollama", "pull", OLLAMA_MODEL])
            else:
                return main()

    elif model == 2:
        backend = "gpt"
        checkOpenAIKey()
    elif model == 3:
        backend = "g4f"
    elif model == 4:
        backend = "anthropic"
        checkAnthropicKey()
    elif model == 5:
        backend = "gemini"
        checkGeminiKey()
    elif model == 6:
        backend = "api"
        checkAPI()
    else:
        return main()

    session = SESSIONS_DIR / f"session{len(sessions) + 1}.json"
    Eva(session, backend, main).chat()


def cli():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("-u", "--update", action="store_true", help="Update EVA")
    parser.add_argument("-v", "--version", action="store_true", help="Show EVA version")
    parser.add_argument("-d", "--delete", action="store_true", help="Delete stored sessions & files")
    parser.add_argument("-c", "--config", action="store_true", help="Open EVA config.py in your default editor")
    parser.add_argument("--custom-api", action="store_true", help="Open the active custom API handler file")
    parser.add_argument(
        "-s",
        "--search",
        nargs="*",
        metavar="QUERY",
        help="Search vulnerability/exploit intelligence with EVA sources",
    )
    args = parser.parse_args()

    register_signal_handler()

    if args.config:
        ok, msg = open_in_default_editor(config_module.__file__)
        color = Fore.GREEN if ok else Fore.RED
        cyber(msg, color=color)
        raise SystemExit(0 if ok else 1)
    if args.custom_api:
        ok = configure_custom_api(open_handler=True)
        raise SystemExit(0 if ok else 1)

    if args.search is not None:
        query = " ".join(args.search).strip()
        if not query:
            query = input("EVA search query > ").strip()
        raise SystemExit(run_exploit_search(query))

    if args.version:
        cyber(f":: E.V.A {get_current_version()} 🍎", color=Fore.CYAN)
        raise SystemExit(0)

    if args.update:
        raise SystemExit(run_self_update())
    if args.delete:
        if CONFIG_DIR.exists() and CONFIG_DIR.is_dir():
            shutil.rmtree(CONFIG_DIR)
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)  
            print(f"\n{Style.BRIGHT + Fore.GREEN}[+] All EVA data deleted from {CONFIG_DIR}")
            sys.exit(0)
        else:
            print(f"\n{Style.BRIGHT + Fore.YELLOW}[!] EVA_files directory does not exist")
            sys.exit(0)

    checkupdts()
    main()


if __name__ == "__main__":
    cli()
