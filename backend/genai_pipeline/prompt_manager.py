"""
genai_pipeline/prompt_manager.py

SRS Steps 40-41 / xiv -- controlled, versioned prompt templates.

Prompts live in prompt_templates/*.txt and are registered in
prompt_templates/prompt_versions.json. Code never contains prompt text; it
asks this module for "the active onboarding_plan prompt" and receives the
text plus the version string, which is stored on every generated plan.
"""

import json
import os
from functools import lru_cache

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompt_templates")
REGISTRY_FILE = os.path.join(TEMPLATE_DIR, "prompt_versions.json")


class PromptTemplateError(Exception):
    pass


@lru_cache(maxsize=1)
def _registry() -> dict:
    try:
        with open(REGISTRY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise PromptTemplateError(f"Prompt registry not found: {REGISTRY_FILE}")
    except json.JSONDecodeError as e:
        raise PromptTemplateError(f"prompt_versions.json is not valid JSON: {e}")


def reload() -> None:
    _registry.cache_clear()
    _read.cache_clear()


@lru_cache(maxsize=32)
def _read(filename: str) -> str:
    path = os.path.join(TEMPLATE_DIR, filename)
    if not os.path.exists(path):
        raise PromptTemplateError(f"Prompt template file missing: {filename}")
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        raise PromptTemplateError(f"Prompt template file is empty: {filename}")
    return text


def get_prompt(name: str, version: str | None = None) -> dict:
    """
    Returns {"name", "version", "system", "user_template"} for a prompt.
    `version` defaults to the active version in prompt_versions.json.
    """
    reg = _registry()
    version = version or reg.get("active", {}).get(name)
    if not version:
        raise PromptTemplateError(f"No active version configured for prompt '{name}'")
    entry = reg.get("templates", {}).get(name, {}).get(version)
    if not entry:
        raise PromptTemplateError(f"Prompt '{name}' has no version '{version}'")
    return {
        "name": name,
        "version": version,
        "label": f"{name}@{version}",
        "system": _read(entry["system"]),
        "user_template": _read(entry["user"]) if entry.get("user") else None,
    }


def render(template: str, **values) -> str:
    """Fills {{placeholders}}. Missing values render as 'Not specified'."""
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", "" if value is None else str(value))
    import re
    return re.sub(r"\{\{\s*\w+\s*\}\}", "Not specified", out)


def list_versions() -> dict:
    reg = _registry()
    return {"active": reg.get("active", {}), "templates": reg.get("templates", {})}
