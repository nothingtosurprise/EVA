#!/usr/bin/env python3
import requests

API_ENDPOINT = "NOT_SET"

def query_custom_api(history, endpoint=None, session=None, prompt=None):
    target = endpoint or API_ENDPOINT
    compiled_prompt = str(prompt or "").strip()
    if not compiled_prompt:
        for item in reversed(history):
            if item.get("role") == "user":
                compiled_prompt = str(item.get("content", "")).strip()
                break

    payload = {
        "prompt": compiled_prompt,
        "conversation": history,
        "session": session,
    }

    r = requests.post(target, json=payload, timeout=None)
    try:
        data = r.json()
    except ValueError:
        return r.text
    if isinstance(data, dict):
        for key in ("analysis", "response", "answer", "text", "content", "message"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return str(data)
