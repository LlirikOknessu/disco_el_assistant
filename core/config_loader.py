"""Helpers for loading assistant configuration profiles."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Dict, Set
import json
import os
import re

from core.memory import MemoryManager, ShortTermMemory, SQLiteLongTermMemory
from core.orchestrator import DialogueOrchestrator
from services.openai_client import OpenAIClient

try:  # Optional dependency for YAML parsing.
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - fallback when PyYAML is unavailable.
    yaml = None


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


def merge_configs(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``overrides`` into ``base`` and return a new mapping."""

    result: Dict[str, Any] = dict(base)
    for key, value in overrides.items():
        base_value = result.get(key)
        if isinstance(base_value, Mapping) and isinstance(value, Mapping):
            result[key] = merge_configs(base_value, value)
        else:
            result[key] = value
    return result


def load_profile(profile: str, config_dir: Path = Path("config")) -> Dict[str, Any]:
    """Load a configuration profile and resolve inheritance and environment vars."""

    config_dir = Path(config_dir)
    merged = _load_profile_recursive(profile, config_dir, seen=set())
    return _substitute_environment_variables(merged)


def build_assistant(config: Dict[str, Any]) -> DialogueOrchestrator:
    """Initialise the dialogue orchestrator according to ``config``."""

    openai_model = config.get("openai", {}).get("model", "gpt-3.5-turbo")
    openai_client = OpenAIClient(model=openai_model)

    paths = config.get("paths", {})
    workspace_dir = Path(paths.get("workspace", "workspace")).expanduser().resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    long_term_memory_path = workspace_dir / "memory.sqlite3"
    long_term_memory = SQLiteLongTermMemory(long_term_memory_path)
    short_term_memory = ShortTermMemory()
    memory_manager = MemoryManager(short_term=short_term_memory, long_term=long_term_memory)

    skill_config_dir = Path(paths.get("skill_config_dir", Path("skills") / "config")).expanduser().resolve()
    skill_matrix_path = Path(paths.get("skill_matrix", Path("config") / "skill_matrix.yaml")).expanduser().resolve()

    return DialogueOrchestrator(
        memory=memory_manager,
        openai_client=openai_client,
        skill_config_dir=skill_config_dir,
        skill_matrix_path=skill_matrix_path,
    )


def _load_profile_recursive(profile: str, config_dir: Path, seen: Set[str]) -> Dict[str, Any]:
    if profile in seen:
        raise ValueError(f"Circular profile inheritance detected for '{profile}'")

    path = _resolve_profile_path(profile, config_dir)
    data = _load_structured_file(path)

    inherits = data.pop("inherits", None)
    parents = _normalise_inherits(inherits)

    base_config: Dict[str, Any] = {}
    next_seen = set(seen)
    next_seen.add(profile)
    for parent in parents:
        parent_config = _load_profile_recursive(parent, config_dir, next_seen)
        base_config = merge_configs(base_config, parent_config)

    return merge_configs(base_config, data)


def _resolve_profile_path(profile: str, config_dir: Path) -> Path:
    for suffix in (".yaml", ".yml", ".json"):
        candidate = config_dir / f"{profile}{suffix}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Configuration profile '{profile}' not found in {config_dir}")


def _load_structured_file(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if yaml is not None:
        return yaml.safe_load(text)
    # YAML is a superset of JSON; fall back to JSON parsing when PyYAML is missing.
    return json.loads(text)


def _normalise_inherits(value: Any) -> Iterable[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        raise TypeError("'inherits' must not be a mapping")
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    raise TypeError("'inherits' must be a string or iterable of strings")


def _substitute_environment_variables(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _substitute_environment_variables(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_substitute_environment_variables(item) for item in value]
    if isinstance(value, str):
        return _ENV_PATTERN.sub(_replace_env_match, value)
    return value


def _replace_env_match(match: re.Match[str]) -> str:
    variable, default = match.group(1), match.group(2) or ""
    return os.environ.get(variable, default)

