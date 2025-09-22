"""Base classes shared across skill implementations."""
from __future__ import annotations

from typing import Any, Dict

from services.openai_client import OpenAIClient


class BaseSkill:
    """Base skill implementation providing prompt helpers."""

    def __init__(self, *, config: Dict[str, Any], openai_client: OpenAIClient) -> None:
        self.config = config
        self.openai_client = openai_client
        self.name = config.get("name", self.__class__.__name__)

    def build_prompt(self, context: Dict[str, Any], extra_guidance: str = "") -> str:
        recent_dialogue = context.get("recent_messages_text")
        if recent_dialogue is None:
            from core.memory import MemoryRecord  # Local import to avoid cycle.

            recent_messages = context.get("recent_messages", [])
            lines = []
            for record in recent_messages:
                if isinstance(record, MemoryRecord):
                    role = record.role
                    content = record.content
                elif isinstance(record, dict):
                    role = record.get("role", "unknown")
                    content = record.get("content", "")
                else:
                    role = str(record)
                    content = ""
                lines.append(f"{role}: {content}")
            recent_dialogue = "\n".join(lines)
        persona = self.config.get("persona", self.name)
        style = self.config.get("style", "")
        user_input = context.get("user_input", "")
        guidance = context.get("orchestrator_prompt", "")
        if extra_guidance:
            guidance = f"{guidance}\nAdditional guidance: {extra_guidance}".strip()
        return self.openai_client.format_skill_prompt(
            skill_name=self.name,
            persona=persona,
            style=style,
            recent_dialogue=recent_dialogue,
            user_input=user_input,
            guidance=guidance,
        )

    def generate_response(self, context: Dict[str, Any]) -> str:
        prompt = context.get("skill_prompt")
        if not prompt:
            prompt = self.build_prompt(context)
        return self.openai_client.generate_for_skill(self.name, prompt)
