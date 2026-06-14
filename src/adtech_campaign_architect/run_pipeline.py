from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import llm_client
from .planner import build_campaign


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = llm_client.ollama_model()
DEFAULT_URL = llm_client.ollama_url()
DEFAULT_FALLBACK_MODEL = os.environ.get("OLLAMA_FALLBACK_MODEL", "qwen3.5:0.8b")
DEFAULT_KEEP_ALIVE = llm_client.ollama_keep_alive()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the full local Adtech Campaign Architect pipeline.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--fallback-model", default=DEFAULT_FALLBACK_MODEL)
    parser.add_argument("--example", type=int, help="Run one advertiser example from data/example_advertisers.txt and exit.")
    parser.add_argument("--skip-pull", action="store_true", help="Do not run `ollama pull` if the model is missing.")
    args = parser.parse_args()

    server_process = None
    try:
        if not ollama_is_up():
            if not _uses_local_ollama() or not _ollama_binary():
                raise SystemExit(
                    "Ollama is not reachable. Install/run Ollama locally, or set OLLAMA_URL "
                    "to a reachable Ollama service."
                )
            _log("Starting Ollama local API...")
            server_env = os.environ.copy()
            server_env["OLLAMA_KEEP_ALIVE"] = DEFAULT_KEEP_ALIVE
            server_process = subprocess.Popen([_ollama_binary(), "serve"], env=server_env)
            wait_for_ollama()

        active_model = args.model
        if not args.skip_pull and not model_is_available(args.model):
            _log(f"Pulling {args.model}. This can take a few minutes the first time...")
            if not _pull_model(args.model):
                _log(f"Primary model pull failed for {args.model}. Falling back to {args.fallback_model}.")
                if not model_is_available(args.fallback_model):
                    _log(f"Pulling fallback model {args.fallback_model}...")
                    if not _pull_model(args.fallback_model):
                        raise SystemExit(
                            f"Could not pull either {args.model} or fallback {args.fallback_model}."
                        )
                active_model = args.fallback_model

        env = os.environ.copy()
        env["OLLAMA_MODEL"] = active_model
        env["OLLAMA_URL"] = DEFAULT_URL
        env["OLLAMA_KEEP_ALIVE"] = DEFAULT_KEEP_ALIVE
        env["PYTHONPATH"] = str(ROOT / "src")
        env["OLLAMA_FALLBACK_MODEL"] = args.fallback_model

        if args.example:
            os.environ.update(
                {
                    "OLLAMA_MODEL": active_model,
                    "OLLAMA_URL": DEFAULT_URL,
                    "OLLAMA_KEEP_ALIVE": DEFAULT_KEEP_ALIVE,
                    "OLLAMA_FALLBACK_MODEL": args.fallback_model,
                }
            )
            campaign = build_campaign(_load_example(args.example))
            print(json.dumps(campaign, indent=2))
            return

        _log(f"Starting Adtech Campaign Architect with {active_model} at http://127.0.0.1:{args.port}")
        subprocess.run(
            [sys.executable, "-m", "adtech_campaign_architect.app", "--port", str(args.port)],
            cwd=ROOT,
            env=env,
            check=True,
        )
    finally:
        if server_process and server_process.poll() is None:
            server_process.terminate()


def ollama_is_up() -> bool:
    return llm_client.is_available()


def wait_for_ollama() -> None:
    for _ in range(30):
        if ollama_is_up():
            return
        time.sleep(0.5)
    raise SystemExit("Ollama did not start within 15 seconds.")


def model_is_available(model: str) -> bool:
    return llm_client.model_is_available(model)


def _pull_model(model: str) -> bool:
    for attempt in range(1, 4):
        try:
            if _ollama_binary() and _uses_local_ollama():
                subprocess.run(
                    [_ollama_binary(), "pull", model],
                    check=True,
                    stdout=sys.stderr,
                    stderr=sys.stderr,
                )
                return True
            if llm_client.pull_model(model):
                return True
        except subprocess.CalledProcessError:
            pass
        if attempt < 3:
            _log(f"Pull failed; retrying {model} ({attempt + 1}/3)...")
            time.sleep(2)
    return False


def _uses_local_ollama() -> bool:
    return DEFAULT_URL in {"http://127.0.0.1:11434", "http://localhost:11434"}


def _ollama_binary() -> str | None:
    preferred_paths = [
        "/opt/homebrew/opt/ollama/bin/ollama",
        "/opt/homebrew/bin/ollama",
        "/usr/local/bin/ollama",
    ]
    for path in preferred_paths:
        if Path(path).exists():
            return path
    return shutil.which("ollama")


def _load_example(example_number: int) -> str:
    examples_file = ROOT / "data" / "example_advertisers.txt"
    for line in examples_file.read_text().splitlines():
        stripped = line.strip()
        prefix = f"{example_number}."
        if stripped.startswith(prefix):
            return stripped.removeprefix(prefix).strip()
    raise SystemExit(f"No example #{example_number} found in {examples_file}.")


def _log(message: str) -> None:
    print(message, file=sys.stderr)


if __name__ == "__main__":
    main()
