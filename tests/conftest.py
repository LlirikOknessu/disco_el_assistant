"""Shared fixtures and stubs for the test suite."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest


@dataclass
class StubOpenAIClient:
    """Deterministic stand-in for :class:`~services.openai_client.OpenAIClient`."""

    formatted_skill_prompts: List[Dict[str, Any]] = field(default_factory=list)
    formatted_orchestrator_prompts: List[Dict[str, Any]] = field(default_factory=list)
    generated_calls: List[Dict[str, Any]] = field(default_factory=list)

    def format_skill_prompt(self, **kwargs: Any) -> str:
        self.formatted_skill_prompts.append(dict(kwargs))
        skill = kwargs.get("skill_name", "")
        user_input = kwargs.get("user_input", "")
        return f"skill-prompt::{skill}::{user_input}"

    def format_orchestrator_prompt(self, **kwargs: Any) -> str:
        self.formatted_orchestrator_prompts.append(dict(kwargs))
        user_input = kwargs.get("user_input", "")
        return f"orchestrator-prompt::{user_input}"

    def generate_for_skill(self, skill_name: str, prompt: str, **kwargs: Any) -> str:
        call = {"skill_name": skill_name, "prompt": prompt, "kwargs": dict(kwargs)}
        self.generated_calls.append(call)
        if kwargs:
            extras = ", ".join(f"{key}={value}" for key, value in sorted(kwargs.items()))
            return f"response::{skill_name}::{extras}"
        return f"response::{skill_name}"


@pytest.fixture()
def openai_client_stub() -> StubOpenAIClient:
    """Provide a fresh OpenAI client stub for each test."""

    return StubOpenAIClient()
