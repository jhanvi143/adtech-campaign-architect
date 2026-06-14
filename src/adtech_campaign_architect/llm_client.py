from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

try:
    from json_repair import repair_json
except ImportError:  # pragma: no cover - dependency is declared, but keep fallback runnable.
    repair_json = None


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:0.8b"
DEFAULT_OLLAMA_KEEP_ALIVE = "30m"


def ollama_url() -> str:
    return os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")


def ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)


def ollama_keep_alive() -> str:
    return os.environ.get("OLLAMA_KEEP_ALIVE", DEFAULT_OLLAMA_KEEP_ALIVE)


def engine_name() -> str:
    return f"ollama:{ollama_model()}" if is_available() else "deterministic-fallback"


def is_available(timeout: float = 1) -> bool:
    request = urllib.request.Request(f"{ollama_url()}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except (OSError, TimeoutError, urllib.error.URLError):
        return False


def model_is_available(model: str, timeout: float = 2) -> bool:
    try:
        with urllib.request.urlopen(f"{ollama_url()}/api/tags", timeout=timeout) as response:
            payload = json.loads(response.read())
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return False
    return any(item.get("name") == model for item in payload.get("models", []))


def pull_model(model: str, timeout: float = 600) -> bool:
    request = urllib.request.Request(
        f"{ollama_url()}/api/pull",
        data=json.dumps({"name": model, "stream": False}).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return False
    return bool(payload.get("status") == "success" or payload.get("completed"))


def generate_json(prompt: str, temperature: float = 0.1, timeout: float = 45) -> dict[str, Any] | None:
    response = generate(prompt, temperature=temperature, json_mode=True, timeout=timeout)
    if not response:
        return None
    return extract_json_object(response)


def generate(prompt: str, temperature: float = 0.1, json_mode: bool = False, timeout: float = 45) -> str | None:
    request_payload: dict[str, Any] = {
        "model": ollama_model(),
        "prompt": prompt,
        "stream": False,
        "keep_alive": ollama_keep_alive(),
        "options": {"temperature": temperature},
    }
    if json_mode:
        request_payload["format"] = "json"

    request = urllib.request.Request(
        f"{ollama_url()}/api/generate",
        data=json.dumps(request_payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return None
    return str(payload.get("response") or payload.get("thinking") or "").strip()


def extract_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    repaired = _repair_json_object(text)
    if repaired is not None:
        return repaired

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return _repair_json_object(match.group(0))
    return parsed if isinstance(parsed, dict) else None


def _repair_json_object(text: str) -> dict[str, Any] | None:
    if repair_json is None:
        return None
    try:
        repaired = repair_json(text)
        parsed = json.loads(repaired)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None
