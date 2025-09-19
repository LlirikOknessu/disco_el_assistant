"""Analytical reasoning skill."""
from __future__ import annotations

from typing import Dict, Any

from skills.base import BaseSkill


class LogicSkill(BaseSkill):
    """Skill focusing on structured, analytical reasoning."""

    def generate_response(self, context: Dict[str, Any]) -> str:
        extra = self.config.get(
            "response_preamble",
            "Respond with step-by-step reasoning and reference evidence from the conversation.",
        )
        prompt = self.build_prompt(context, extra_guidance=extra)
        return self.openai_client.generate_for_skill(self.name, prompt, temperature=0.2)
