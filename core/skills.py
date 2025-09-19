"""Skill definitions for the Disco EL assistant orchestrator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass
class SkillResponse:
    """Represents a single response produced by a skill."""

    skill: str
    content: str

    def to_dict(self) -> dict:
        return {"skill": self.skill, "content": self.content}


class Skill:
    """Protocol-like base class for simple rule based skills."""

    name: str

    def respond(self, message: str, context: dict) -> Optional[SkillResponse]:
        raise NotImplementedError


class SmallTalkSkill(Skill):
    """Minimal small-talk skill used for greetings and chitchat."""

    name = "small_talk"

    def __init__(self, greetings: Optional[Iterable[str]] = None) -> None:
        self.greetings = [g.lower() for g in (greetings or ("hi", "hello", "hey"))]

    def respond(self, message: str, context: dict) -> Optional[SkillResponse]:
        lowered = message.lower()
        if any(greeting in lowered for greeting in self.greetings):
            reply = "Hello! How can I help you today?"
            return SkillResponse(skill=self.name, content=reply)
        if "thank" in lowered:
            return SkillResponse(skill=self.name, content="You're welcome!")
        return None


class KnowledgeBaseSkill(Skill):
    """Skill that answers based on a keyword search in a local knowledge base."""

    name = "knowledge_base"

    def __init__(self, entries: Optional[List[dict]] = None) -> None:
        self.entries = entries or []

    def respond(self, message: str, context: dict) -> Optional[SkillResponse]:
        if not self.entries:
            return None
        lowered = message.lower()
        for entry in self.entries:
            keywords = [kw.lower() for kw in entry.get("keywords", [])]
            if any(keyword in lowered for keyword in keywords):
                response = entry.get("response") or entry.get("answer")
                if response:
                    response = response.strip()
                    title = entry.get("title")
                    if title:
                        response = f"{title}: {response}"
                    return SkillResponse(skill=self.name, content=response)
        return None


class FallbackSkill(Skill):
    """Default skill that is triggered when nothing else matches."""

    name = "fallback"

    def __init__(self, message: str = "I am not sure how to help with that yet.") -> None:
        self.message = message

    def respond(self, message: str, context: dict) -> Optional[SkillResponse]:
        return SkillResponse(skill=self.name, content=self.message)
