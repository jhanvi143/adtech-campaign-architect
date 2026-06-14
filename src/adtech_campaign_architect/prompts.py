"""Prompt loading and rendering helpers for the campaign planner."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
PROMPT_MODULE = ROOT / "prompts" / "templates.py"


def _load_prompt_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("disco_prompt_templates", PROMPT_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load prompt templates from {PROMPT_MODULE}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROMPTS = _load_prompt_module().PROMPTS


def render_prompt(name: str, values: dict[str, str]) -> str:
    template = PROMPTS[name]
    for key, value in values.items():
        template = template.replace("{{ " + key + " }}", str(value))
        template = template.replace("{{" + key + "}}", str(value))
    return template
