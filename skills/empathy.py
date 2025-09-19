"""Empathetic conversation skill."""
from __future__ import annotations

from typing import Dict, Any

from skills.base import BaseSkill


class EmpathySkill(BaseSkill):
    """Skill that emphasises compassionate and supportive communication."""

    def generate_response(self, context: Dict[str, Any]) -> str:
        extra = self.config.get(
            "response_preamble",
            "Acknowledge the user's emotions, validate their feelings and offer supportive language.",
        )
        prompt = self.build_prompt(context, extra_guidance=extra)
        return self.openai_client.generate_for_skill(self.name, prompt, temperature=0.8)
