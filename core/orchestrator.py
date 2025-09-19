"""Dialogue orchestrator that coordinates skills and memory."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional
import json
import logging

from core.memory import MemoryManager, MemoryRecord
from services.openai_client import OpenAIClient

try:  # Optional dependency for YAML.
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - fallback when PyYAML is unavailable.
    yaml = None


LOGGER = logging.getLogger(__name__)


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
                configs[path.stem] = self._load_structured_file(path)
            except Exception as exc:  # pragma: no cover - logging side effect
                LOGGER.exception("Failed to load skill configuration %s: %s", path, exc)
        return configs

    def _load_skill_matrix(self, path: Path) -> Dict[str, Any]:
        if path.exists():
            try:
                return self._load_structured_file(path)
            except Exception as exc:  # pragma: no cover - logging side effect
                LOGGER.exception("Failed to load skill matrix %s: %s", path, exc)
        return {
            "default_skill": next(iter(self.skill_configs), ""),
            "priorities": {},
            "transition_weights": {},
            "conflict_resolution": {},
        }

    def _load_structured_file(self, path: Path) -> Dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return json.loads(text)
        if yaml is not None:
            return yaml.safe_load(text)
        # YAML is a superset of JSON, so fall back to JSON parsing.
        return json.loads(text)

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
        user_record = self.memory.add_message("user", user_input, persist_long_term=persist_long_term)
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
            lines.append(f"{record.timestamp.isoformat()} - {record.role}{skill_note}: {record.content}")
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
