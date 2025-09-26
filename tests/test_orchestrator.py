from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.memory import MemoryManager
from core.orchestrator import DialogueOrchestrator


class RecordingSkill:
    """Minimal skill implementation that records invocation context."""

    def __init__(self, *, config: Dict[str, Any], openai_client: Any) -> None:
        self.config = config
        self.name = config.get("name", "anonymous")
        self.openai_client = openai_client
        self.calls = []

    def generate_response(self, context: Dict[str, Any]) -> str:  # pragma: no cover - exercised via tests
        self.calls.append(context)
        return f"skill::{self.name}::{len(self.calls)}"


def _write_skill_environment(base_dir: Path) -> Dict[str, Path]:
    config_dir = base_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = base_dir / "matrix.json"

    logic_config = {
        "name": "logic",
        "persona": "Analytical Strategist",
        "style": "Concise",
        "keywords": ["plan", "logic"],
        "base_weight": 1.0,
    }
    drama_config = {
        "name": "drama",
        "persona": "Dramatic Performer",
        "style": "Expressive",
        "keywords": ["story"],
        "base_weight": 1.0,
    }

    (config_dir / "logic.json").write_text(json.dumps(logic_config), encoding="utf-8")
    (config_dir / "drama.json").write_text(json.dumps(drama_config), encoding="utf-8")

    matrix = {
        "default_skill": "logic",
        "priorities": {"logic": 1.0, "drama": 1.0},
        "transition_weights": {},
        "conflict_resolution": {"logic": {"overrides": ["drama"]}},
    }
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    return {"config_dir": config_dir, "matrix_path": matrix_path}


def _build_orchestrator(
    tmp_path: Path,
    openai_client_stub: Any,
    *,
    history_limit: int = 3,
) -> DialogueOrchestrator:
    paths = _write_skill_environment(tmp_path)
    orchestrator = DialogueOrchestrator(
        memory=MemoryManager(),
        openai_client=openai_client_stub,
        skill_registry={"logic": RecordingSkill, "drama": RecordingSkill},
        skill_config_dir=paths["config_dir"],
        skill_matrix_path=paths["matrix_path"],
        history_limit=history_limit,
    )
    return orchestrator


def test_keyword_routing_selects_logic_skill(tmp_path: Path, openai_client_stub: Any) -> None:
    orchestrator = _build_orchestrator(tmp_path, openai_client_stub)
    try:
        result = orchestrator.process_user_input("We should plan our next steps logically.")
        assert result["skill"] == "logic"
    finally:
        orchestrator.reset()


def test_conflict_resolution_prefers_matrix_override(
    tmp_path: Path, openai_client_stub: Any
) -> None:
    orchestrator = _build_orchestrator(tmp_path, openai_client_stub)
    try:
        # No keyword hits -> both skills have identical scores and rely on the matrix rule.
        result = orchestrator.process_user_input("Tell me something interesting.")
        assert result["skill"] == "logic"
    finally:
        orchestrator.reset()


def test_recent_history_respects_limit(tmp_path: Path, openai_client_stub: Any) -> None:
    orchestrator = _build_orchestrator(tmp_path, openai_client_stub, history_limit=2)
    logic_skill = orchestrator.skills["logic"]
    try:
        orchestrator.process_user_input("Plan alpha")
        orchestrator.process_user_input("Plan beta")
        orchestrator.process_user_input("Plan gamma")
    finally:
        orchestrator.reset()

    # The skill contexts are recorded before the assistant reply is stored.
    assert len(logic_skill.calls) == 3
    recent_messages = logic_skill.calls[-1]["recent_messages"]
    assert len(recent_messages) == 2
    roles = [record.role for record in recent_messages]
    assert roles == ["assistant", "user"]
