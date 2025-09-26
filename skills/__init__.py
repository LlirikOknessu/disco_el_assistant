"""Skill registry for the dialogue system."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Type

from skills.base import BaseSkill
from skills.persona import PersonaSkill
from skills.empathy import EmpathySkill
from skills.logic import LogicSkill


def _discover_persona_skills() -> Dict[str, Type[BaseSkill]]:
    """Register every skill configuration with :class:`PersonaSkill`."""

    config_dir = Path(__file__).resolve().parent / "config"
    registry: Dict[str, Type[BaseSkill]] = {}
    for path in config_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        registry[path.stem] = PersonaSkill

    # Maintain explicit aliases for legacy imports.
    if "empathy" in registry:
        registry["empathy"] = EmpathySkill
    if "logic" in registry:
        registry["logic"] = LogicSkill

    return registry


SKILL_REGISTRY: Dict[str, Type[BaseSkill]] = _discover_persona_skills()

__all__ = [
    "SKILL_REGISTRY",
    "BaseSkill",
    "PersonaSkill",
    "EmpathySkill",
    "LogicSkill",
]
