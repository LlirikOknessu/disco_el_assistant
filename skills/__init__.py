"""Skill registry for the dialogue system."""
from __future__ import annotations

from typing import Dict, Type

from skills.empathy import EmpathySkill
from skills.logic import LogicSkill
from skills.base import BaseSkill

SKILL_REGISTRY: Dict[str, Type[BaseSkill]] = {
    "empathy": EmpathySkill,
    "logic": LogicSkill,
}

__all__ = ["SKILL_REGISTRY", "BaseSkill", "EmpathySkill", "LogicSkill"]
