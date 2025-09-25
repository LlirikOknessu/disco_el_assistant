from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config_loader import build_assistant, load_profile
from core.memory import SQLiteLongTermMemory
from core.orchestrator import DialogueOrchestrator


@pytest.fixture(autouse=True)
def clear_environment(monkeypatch):
    monkeypatch.delenv("WORKSPACE_DIR", raising=False)
    yield


def test_work_profile_inherits_base_values():
    config = load_profile("work")

    assert config["openai"]["model"] == "gpt-4o-mini"
    assert config["app"]["profile"] == "work"
    assert config["vector_db"]["collection"] == "work_memory"


def test_workspace_path_resolves_environment_variable(tmp_path, monkeypatch):
    workspace_dir = tmp_path / "work_env"
    monkeypatch.setenv("WORKSPACE_DIR", str(workspace_dir))

    config = load_profile("work")

    assert config["paths"]["workspace"] == str(workspace_dir)


def test_build_assistant_initialises_orchestrator_with_memory(tmp_path, monkeypatch):
    workspace_dir = tmp_path / "assistant_workspace"
    monkeypatch.setenv("WORKSPACE_DIR", str(workspace_dir))

    config = load_profile("work")
    orchestrator = build_assistant(config)

    try:
        assert isinstance(orchestrator, DialogueOrchestrator)
        resolved_workspace = workspace_dir.resolve()
        assert resolved_workspace.exists()
        assert isinstance(orchestrator.memory.long_term, SQLiteLongTermMemory)
        assert orchestrator.memory.long_term.db_path == resolved_workspace / "memory.sqlite3"
        assert orchestrator.openai_client.model == config["openai"]["model"]

        expected_skill_config_dir = Path(config["paths"]["skill_config_dir"]).expanduser().resolve()
        expected_skill_matrix_path = Path(config["paths"]["skill_matrix"]).expanduser().resolve()
        assert orchestrator.skill_config_dir == expected_skill_config_dir
        assert orchestrator.skill_matrix_path == expected_skill_matrix_path
    finally:
        orchestrator.memory.close()

