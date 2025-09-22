"""Adapter around the OpenAI chat completion API."""
from __future__ import annotations

from typing import Any, Optional
import logging
import os

LOGGER = logging.getLogger(__name__)


class OpenAIClient:
    """Thin wrapper around the OpenAI SDK with prompt helpers."""

    ORCHESTRATOR_PROMPT_TEMPLATE = (
        "You are the dialogue orchestrator coordinating a team of specialised skills.\n"
        "Conversation history:\n{recent_dialogue}\n\n"
        "Latest user input: {user_input}\n"
        "Available skills:\n{skill_descriptions}\n\n"
        "Last responding skill: {last_skill}\n"
        "Current scoring matrix: {skill_scores}\n\n"
        "Relevant memories:\n{long_term_context}\n\n"
        "Provide guidance for the next response keeping role boundaries clear."
    )

    SKILL_PROMPT_TEMPLATE = (
        "You are acting as the \"{skill_name}\" persona.\n"
        "Persona description: {persona}\n"
        "Communication style: {style}\n\n"
        "Conversation history:\n{recent_dialogue}\n\n"
        "User input to address: {user_input}\n\n"
        "Strategy guidance from orchestrator:\n{guidance}\n\n"
        "Craft a response that fits the persona while respecting the guidance."
    )

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = self._initialise_client()

    def _initialise_client(self) -> Optional[Any]:
        try:
            import openai  # type: ignore

            openai.api_key = self.api_key
            return openai
        except ImportError:
            LOGGER.info("OpenAI SDK not installed; falling back to simulated responses.")
            return None

    # ------------------------------------------------------------------
    # Formatting helpers
    def format_orchestrator_prompt(self, **kwargs: Any) -> str:
        return self.ORCHESTRATOR_PROMPT_TEMPLATE.format(**kwargs)

    def format_skill_prompt(self, **kwargs: Any) -> str:
        return self.SKILL_PROMPT_TEMPLATE.format(**kwargs)

    # ------------------------------------------------------------------
    def generate(self, prompt: str, *, temperature: float = 0.7, **kwargs: Any) -> str:
        """Return a response either via the OpenAI API or a local fallback."""
        if self._client is None or not self.api_key:
            return self._simulate_response(prompt)

        try:
            response = self._client.ChatCompletion.create(  # type: ignore[attr-defined]
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                **kwargs,
            )
        except Exception as exc:  # pragma: no cover - network failure handling
            LOGGER.error("OpenAI request failed: %s", exc)
            return self._simulate_response(prompt)

        message = response["choices"][0]["message"]["content"].strip()
        return message

    def _simulate_response(self, prompt: str) -> str:
        """Deterministic stub used when the OpenAI SDK is unavailable."""
        preview = prompt.strip().splitlines()
        preview = [line for line in preview if line]
        summary = preview[-1] if preview else ""
        return f"[Simulated response based on prompt: {summary[:120]}]"

    # Convenience wrappers -------------------------------------------------
    def generate_for_skill(self, skill_name: str, prompt: str, **kwargs: Any) -> str:
        LOGGER.debug("Generating response for skill %s", skill_name)
        return self.generate(prompt, **kwargs)
