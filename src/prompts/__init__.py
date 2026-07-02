"""
Prompt registry — YAML-based externalized prompt management.
Supports version switching and instant rollback without code changes.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class PromptRegistry:
    """Singleton prompt registry with version control."""

    def __init__(self, prompts_dir: str | None = None):
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        self._prompts_dir = Path(prompts_dir)
        self._cache: dict[str, dict[str, Any]] = {}
        self._versions: dict[str, str] = {}
        self._load_versions()
        self._preload()

    def _load_versions(self):
        versions_file = self._prompts_dir / "versions.yaml"
        if versions_file.exists():
            with open(versions_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for name, config in data.get("prompts", {}).items():
                self._versions[name] = config.get("active", "v1")

    def _preload(self):
        """Preload all prompt YAML files into cache."""
        for yaml_file in self._prompts_dir.glob("*.yaml"):
            name = yaml_file.stem
            if name == "versions":
                continue
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self._cache[name] = data
            except Exception:
                pass

    def get_system_prompt(self, name: str, default: str = "") -> str:
        """Get system prompt by name. Returns default if not found."""
        data = self._cache.get(name, {})
        return data.get("system", default).strip() or default

    def get_user_prompt_template(self, name: str) -> str:
        """Get user prompt template if defined."""
        data = self._cache.get(name, {})
        return data.get("user_template", "").strip()

    @property
    def active_versions(self) -> dict[str, str]:
        return dict(self._versions)

    def reload(self):
        """Hot-reload prompts from disk."""
        self._cache.clear()
        self._versions.clear()
        self._load_versions()
        self._preload()


# Global singleton
prompt_registry = PromptRegistry()
