"""Conversation orchestrators and configuration helpers."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from dotenv import load_dotenv

from core.memory import MemoryManager, MemoryRecord
from services.openai_client import OpenAIClient

from .skills import (
    FallbackSkill,
    KnowledgeBaseSkill,
    Skill,
    SkillResponse,
    SmallTalkSkill,
)

try:  # Optional dependency for YAML support.
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - YAML becomes optional.
    yaml = None


load_dotenv()

LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


# ---------------------------------------------------------------------------
# Configuration helpers

def _load_structured_file(path: Path) -> Any:
    """Load a YAML or JSON file and return the parsed structure."""

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError(
                f"PyYAML is required to read YAML configuration files such as {path}."
            )
        return yaml.safe_load(text)
    if suffix == ".json":
        return json.loads(text)
    raise ValueError(f"Unsupported configuration format for {path}")


def _ensure_mapping(data: Any, *, path: Path) -> Dict[str, Any]:
    if data is None:
        return {}
    if isinstance(data, Mapping):
        return dict(data)
    raise ValueError(f"Configuration file {path} must contain a mapping, got {type(data).__name__}")


def _merge_dicts(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(base)
    for key, value in overrides.items():
        if key in merged and isinstance(merged[key], Mapping) and isinstance(value, Mapping):
            merged[key] = _merge_dicts(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def _resolve_profile_path(identifier: str, config_dir: Path) -> Path:
    raw_path = Path(identifier)
    candidates: List[Path] = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
        if not raw_path.suffix:
            candidates.append(raw_path.with_suffix(".yaml"))
    else:
        candidates.append(config_dir / raw_path)
        if not raw_path.suffix:
            candidates.append((config_dir / raw_path).with_suffix(".yaml"))
            candidates.append(config_dir / f"{identifier}.yaml")
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    available = sorted(p.stem for p in config_dir.glob("*.yaml"))
    available_text = ", ".join(available) or "none"
    raise FileNotFoundError(
        f"Profile '{identifier}' is not available. Existing profiles: {available_text}"
    )


def _normalise_inherits(value: Any) -> Sequence[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _load_profile_file(path: Path, config_dir: Path, visited: Set[Path]) -> Dict[str, Any]:
    resolved = path.resolve()
    if resolved in visited:
        raise ValueError(f"Circular profile inheritance detected for {resolved}")
    visited.add(resolved)

    data = _ensure_mapping(_load_structured_file(resolved), path=resolved)
    inherits = _normalise_inherits(data.pop("inherits", None))

    merged: Dict[str, Any] = {}
    for parent in inherits:
        parent_path = _resolve_profile_path(parent, config_dir)
        parent_data = _load_profile_file(parent_path, config_dir, visited)
        merged = _merge_dicts(merged, parent_data)

    visited.remove(resolved)
    return _merge_dicts(merged, data)


def load_profile_config(profile: str, *, config_dir: Path = CONFIG_DIR) -> Dict[str, Any]:
    """Load a profile configuration with support for inheritance."""

    path = _resolve_profile_path(profile, config_dir)
    config = _load_profile_file(path, config_dir, visited=set())
    config.setdefault("profile", profile)
    return config


# ---------------------------------------------------------------------------
# Simple rule-based orchestrator used by CLI/web demos


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


def _load_optional_structure(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return _load_structured_file(path)
    except Exception as exc:  # pragma: no cover - logging side effect only
        LOGGER.warning("Failed to load structured data from %s: %s", path, exc)
        return None


class Orchestrator:
    """Simple rule-based orchestrator that routes requests to configured skills."""

    def __init__(self, profile: str, config: Dict[str, Any]) -> None:
        self.profile = profile
        self.config = config
        self.history: List[ConversationTurn] = []
        fallback_message = config.get(
            "fallback_message", "I'm still learning how to respond to that."
        )
        self.fallback = FallbackSkill(message=fallback_message)
        self.skills = self._build_skills(config)

    @classmethod
    def from_profile(cls, profile: str) -> "Orchestrator":
        config = load_profile_config(profile)
        return cls(profile=profile, config=config)

    def _build_skills(self, config: Dict[str, Any]) -> List[Skill]:
        skills: List[Skill] = [SmallTalkSkill()]
        knowledge_entries = self._load_knowledge_base(config)
        if knowledge_entries:
            skills.append(KnowledgeBaseSkill(entries=knowledge_entries))
        return skills

    def _load_knowledge_base(self, config: Dict[str, Any]) -> List[dict]:
        integrations = config.get("integrations", {})
        knowledge_cfg = integrations.get("knowledge_base", {})
        if not knowledge_cfg.get("enabled", True):
            return []
        entries: List[dict] = []
        entries.extend(knowledge_cfg.get("entries", []))
        path_value = knowledge_cfg.get("path")
        if path_value:
            kb_path = Path(str(path_value))
            if not kb_path.is_absolute():
                kb_path = (PROJECT_ROOT / kb_path).resolve()
            data = _load_optional_structure(kb_path)
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


# ---------------------------------------------------------------------------
# Advanced dialogue orchestrator with memory and skill routing


@dataclass
class SkillDecision:
    """Represents the decision process for a single assistant turn."""

    skill_name: str
    scores: Dict[str, float]
    prompt: str


class DialogueOrchestrator:
    """Route user input to the best suited skill while tracking context."""

    def __init__(
        self,
        memory: Optional[MemoryManager] = None,
        openai_client: Optional[OpenAIClient] = None,
        skill_registry: Optional[Mapping[str, Any]] = None,
        skill_config_dir: Optional[Path] = None,
        skill_matrix_path: Optional[Path] = None,
        history_limit: int = 6,
    ) -> None:
        from skills import SKILL_REGISTRY  # Imported lazily to avoid cycles.

        self.memory = memory or MemoryManager()
        self.openai_client = openai_client or OpenAIClient()
        self.history_limit = history_limit
        self.skill_config_dir = Path(skill_config_dir or Path("skills") / "config")
        self.skill_matrix_path = Path(skill_matrix_path or Path("config") / "skill_matrix.yaml")
        self.skill_configs = self._load_skill_configs(self.skill_config_dir)
        registry = dict(skill_registry or SKILL_REGISTRY)
        self.skill_matrix = self._load_skill_matrix(self.skill_matrix_path)
        self.skills = self._instantiate_skills(registry)
        self._turn_history: List[str] = []
        self._awaiting_user_input = True
        self._last_decision: Optional[SkillDecision] = None

    # ------------------------------------------------------------------
    # Loading helpers
    def _load_skill_configs(self, directory: Path) -> Dict[str, Dict[str, Any]]:
        configs: Dict[str, Dict[str, Any]] = {}
        if not directory.exists():
            LOGGER.warning("Skill configuration directory %s does not exist", directory)
            return configs

        for path in directory.iterdir():
            if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
                continue
            try:
                data = _load_structured_file(path)
                if isinstance(data, Mapping):
                    configs[path.stem] = dict(data)
                else:
                    LOGGER.warning(
                        "Skill configuration %s did not contain a mapping and was skipped", path
                    )
            except Exception as exc:  # pragma: no cover - logging side effect
                LOGGER.exception("Failed to load skill configuration %s: %s", path, exc)
        return configs

    def _load_skill_matrix(self, path: Path) -> Dict[str, Any]:
        if path.exists():
            try:
                data = _load_structured_file(path)
                if isinstance(data, Mapping):
                    return dict(data)
                LOGGER.warning("Skill matrix %s did not contain a mapping", path)
            except Exception as exc:  # pragma: no cover - logging side effect
                LOGGER.exception("Failed to load skill matrix %s: %s", path, exc)
        return {
            "default_skill": next(iter(self.skill_configs), ""),
            "priorities": {},
            "transition_weights": {},
            "conflict_resolution": {},
        }

    def _instantiate_skills(self, registry: Mapping[str, Any]) -> Dict[str, Any]:
        instances: Dict[str, Any] = {}
        for name, cls in registry.items():
            config = self.skill_configs.get(name, {"name": name})
            instances[name] = cls(config=config, openai_client=self.openai_client)
        return instances

    # ------------------------------------------------------------------
    # Public API
    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """Process a user utterance and return the generated assistant reply."""

        user_input = user_input.strip()
        if not user_input:
            raise ValueError("User input must not be empty")

        if not self._awaiting_user_input:
            LOGGER.info("Received user input while assistant turn was pending; resetting state.")
        self._awaiting_user_input = False

        persist_long_term = getattr(self.memory, "long_term", None) is not None
        user_record = self.memory.add_message(
            "user", user_input, persist_long_term=persist_long_term
        )
        context = self._build_context(user_record)
        scores = self._score_skills(user_input)
        skill_name = self._resolve_conflicts(scores)

        skill = self.skills[skill_name]
        guidance = self._build_orchestrator_prompt(context, scores)
        prompt = self.openai_client.format_skill_prompt(
            skill_name=skill_name,
            persona=self.skill_configs.get(skill_name, {}).get("persona", skill_name),
            style=self.skill_configs.get(skill_name, {}).get("style", ""),
            recent_dialogue=self._format_messages(context["recent_messages"]),
            user_input=user_input,
            guidance=guidance,
        )
        response = skill.generate_response(
            {
                **context,
                "orchestrator_prompt": guidance,
                "skill_prompt": prompt,
                "skill_scores": scores,
            }
        )

        assistant_metadata = {"skill": skill_name, "scores": scores}
        assistant_record = self.memory.add_message(
            "assistant", response, metadata=assistant_metadata, persist_long_term=persist_long_term
        )
        self._turn_history.append(skill_name)
        self._awaiting_user_input = True

        decision = SkillDecision(skill_name=skill_name, scores=scores, prompt=prompt)
        self._last_decision = decision

        return {
            "response": response,
            "skill": skill_name,
            "decision": decision,
            "records": {
                "user": user_record.to_dict(),
                "assistant": assistant_record.to_dict(),
            },
        }

    def reset(self) -> None:
        """Clear internal state and memory."""

        self.memory.clear()
        self._turn_history.clear()
        self._awaiting_user_input = True
        self._last_decision = None

    # ------------------------------------------------------------------
    # Internal helpers
    def _build_context(self, user_record: MemoryRecord) -> Dict[str, Any]:
        recent_messages = self.memory.get_recent(self.history_limit)
        long_term = self.memory.search_long_term(user_record.content, limit=3)
        return {
            "recent_messages": recent_messages,
            "long_term_memories": long_term,
            "user_input": user_record.content,
            "turn_history": list(self._turn_history),
            "last_skill": self._turn_history[-1] if self._turn_history else None,
        }

    def _format_messages(self, messages: Iterable[MemoryRecord]) -> str:
        lines = []
        for record in messages:
            meta = record.metadata.get("skill") if record.metadata else None
            skill_note = f" ({meta})" if meta else ""
            lines.append(
                f"{record.timestamp.isoformat()} - {record.role}{skill_note}: {record.content}"
            )
        return "\n".join(lines)

    def _score_skills(self, user_input: str) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        lower_input = user_input.lower()
        last_skill = self._turn_history[-1] if self._turn_history else None
        transitions: Dict[str, Dict[str, float]] = self.skill_matrix.get("transition_weights", {})
        priorities: Dict[str, float] = self.skill_matrix.get("priorities", {})
        for name, config in self.skill_configs.items():
            base = float(config.get("base_weight", 1.0))
            keywords = [kw.lower() for kw in config.get("keywords", [])]
            hits = sum(1 for kw in keywords if kw in lower_input)
            weight = base + hits
            if last_skill:
                weight *= transitions.get(last_skill, {}).get(name, 1.0)
            weight *= priorities.get(name, 1.0)
            scores[name] = weight
        # Ensure that every known skill receives a score.
        for name in self.skills:
            scores.setdefault(name, 1.0)
        return scores

    def _resolve_conflicts(self, scores: Dict[str, float]) -> str:
        if not scores:
            raise RuntimeError("No skills registered")
        max_score = max(scores.values())
        candidates = [name for name, score in scores.items() if score == max_score]
        if len(candidates) == 1:
            return candidates[0]
        winner = self._apply_conflict_rules(candidates)
        if winner is not None:
            return winner
        default_skill = self.skill_matrix.get("default_skill")
        if default_skill in candidates:
            return default_skill
        # Fallback to deterministic ordering to avoid randomness.
        return sorted(candidates)[0]

    def _apply_conflict_rules(self, candidates: List[str]) -> Optional[str]:
        rules = self.skill_matrix.get("conflict_resolution", {})
        priorities = self.skill_matrix.get("priorities", {})
        # Rule-based overrides.
        for candidate in candidates:
            overrides = rules.get(candidate, {}).get("overrides", [])
            if any(other in candidates for other in overrides):
                return candidate
        # Priority-based resolution.
        if priorities:
            sorted_candidates = sorted(
                candidates, key=lambda name: priorities.get(name, 0), reverse=True
            )
            top = sorted_candidates[0]
            if len(sorted_candidates) == 1:
                return top
            top_priority = priorities.get(top, 0)
            second_priority = priorities.get(sorted_candidates[1], top_priority)
            if top_priority != second_priority:
                return top
        return None

    def _build_orchestrator_prompt(
        self, context: Dict[str, Any], scores: Dict[str, float]
    ) -> str:
        descriptions = []
        for name, config in self.skill_configs.items():
            descriptions.append(
                f"- {name}: {config.get('description', 'No description provided.')}"
            )
        long_term_lines = [f"* {record.content}" for record in context["long_term_memories"]]
        return self.openai_client.format_orchestrator_prompt(
            recent_dialogue=self._format_messages(context["recent_messages"]),
            user_input=context["user_input"],
            skill_descriptions="\n".join(descriptions),
            last_skill=context.get("last_skill") or "None",
            skill_scores=json.dumps(scores, ensure_ascii=False, indent=2),
            long_term_context="\n".join(long_term_lines) if long_term_lines else "None",
        )


__all__ = ["load_profile_config", "Orchestrator", "DialogueOrchestrator", "ConversationTurn", "SkillDecision"]
