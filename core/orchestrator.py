"""Conversation orchestrator used by the CLI and the web interfaces."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from dotenv import load_dotenv

from .skills import FallbackSkill, KnowledgeBaseSkill, SkillResponse, SmallTalkSkill

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


@dataclass
class ConversationTurn:
    """Represents a single conversation turn."""

    user: str
    responses: List[SkillResponse] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "user": self.user,
            "responses": [response.to_dict() for response in self.responses],
        }


def load_profile_config(profile: str) -> Dict:
    """Load a profile configuration from the config directory."""

    config_path = CONFIG_DIR / f"{profile}.yaml"
    if not config_path.exists():
        available = ", ".join(p.stem for p in CONFIG_DIR.glob("*.yaml"))
        raise FileNotFoundError(
            f"Profile '{profile}' is not available. Existing profiles: {available}"
        )
    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


def _load_yaml(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class Orchestrator:
    """Simple rule-based orchestrator that routes requests to configured skills."""

    def __init__(self, profile: str, config: Dict) -> None:
        self.profile = profile
        self.config = config
        self.history: List[ConversationTurn] = []
        self.fallback = FallbackSkill(
            message=config.get("fallback_message", "I'm still learning how to respond to that.")
        )
        self.skills = self._build_skills(config)

    @classmethod
    def from_profile(cls, profile: str) -> "Orchestrator":
        config = load_profile_config(profile)
        return cls(profile=profile, config=config)

    def _build_skills(self, config: Dict) -> List:
        skills: List = [SmallTalkSkill()]
        knowledge_entries = self._load_knowledge_base(config)
        if knowledge_entries:
            skills.append(KnowledgeBaseSkill(entries=knowledge_entries))
        return skills

    def _load_knowledge_base(self, config: Dict) -> List[dict]:
        integrations = config.get("integrations", {})
        knowledge_cfg = integrations.get("knowledge_base", {})
        if not knowledge_cfg.get("enabled", True):
            return []
        entries: List[dict] = []
        entries.extend(knowledge_cfg.get("entries", []))
        path_value = knowledge_cfg.get("path")
        if path_value:
            kb_path = (PROJECT_ROOT / path_value).resolve()
            data = _load_yaml(kb_path)
            if isinstance(data, dict):
                entries.extend(data.get("entries", []))
            elif isinstance(data, list):
                entries.extend(data)
        return entries

    def handle_message(self, message: str) -> List[SkillResponse]:
        """Dispatch a message to all skills and update the history."""

        context = {"history": [turn.to_dict() for turn in self.history], "config": self.config}
        responses: List[SkillResponse] = []
        for skill in self.skills:
            result = skill.respond(message, context)
            if result:
                responses.append(result)
        if not responses:
            responses.append(self.fallback.respond(message, context))
        turn = ConversationTurn(user=message, responses=responses)
        self.history.append(turn)
        return responses

    def get_history(self) -> List[dict]:
        """Return a serialisable representation of the conversation history."""

        return [turn.to_dict() for turn in self.history]


__all__ = ["Orchestrator", "load_profile_config"]
