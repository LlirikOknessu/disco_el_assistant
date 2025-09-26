"""Reusable persona-driven skill implementation."""
from __future__ import annotations

from typing import Any, Dict

from skills.base import BaseSkill


class PersonaSkill(BaseSkill):
    """Skill that relies entirely on configuration metadata."""

    def __init__(self, *, config: Dict[str, Any], openai_client) -> None:  # type: ignore[override]
        super().__init__(config=config, openai_client=openai_client)
        self.temperature = float(config.get("temperature", 0.7))
        self.response_preamble = config.get("response_preamble", "")
        model_params = config.get("model_params", {})
        if not isinstance(model_params, dict):
            raise TypeError("'model_params' must be a mapping if provided")
        self.model_params: Dict[str, Any] = dict(model_params)
        self.model_params.setdefault("temperature", self.temperature)

    def _build_extra_guidance(self, context: Dict[str, Any]) -> str:
        """Return persona-specific guidance for the prompt."""
        additional = context.get("extra_guidance")
        if isinstance(additional, str) and additional.strip():
            return additional
        return self.response_preamble

    def generate_response(self, context: Dict[str, Any]) -> str:
        extra_guidance = self._build_extra_guidance(context)
        prompt = self.build_prompt(context, extra_guidance=extra_guidance)
        params = dict(self.model_params)
        return self.openai_client.generate_for_skill(self.name, prompt, **params)
