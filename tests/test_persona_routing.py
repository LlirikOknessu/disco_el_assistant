from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.orchestrator import DialogueOrchestrator
from core.memory import MemoryManager
from services.openai_client import OpenAIClient
from skills import SKILL_REGISTRY


@pytest.fixture()
def orchestrator():
    skill_config_dir = ROOT / "skills" / "config"
    skill_matrix_path = ROOT / "config" / "skill_matrix.yaml"
    client = OpenAIClient(api_key="", model="gpt-4o-mini")
    manager = MemoryManager()
    orchestrator = DialogueOrchestrator(
        memory=manager,
        openai_client=client,
        skill_config_dir=skill_config_dir,
        skill_matrix_path=skill_matrix_path,
    )
    try:
        yield orchestrator
    finally:
        orchestrator.reset()


def test_registry_includes_persona_skills():
    expected = {
        "authority",
        "volition",
        "drama",
        "half_light",
        "encyclopedia",
        "inland_empire",
        "empathy",
        "logic",
    }
    assert expected.issubset(SKILL_REGISTRY.keys())


@pytest.mark.parametrize(
    "text, expected",
    [
        ("We must command respect and enforce discipline in the precinct.", "authority"),
        (
            "My conscience insists we uphold our principles and take responsibility.",
            "volition",
        ),
        ("Time to perform, spin a theatrical lie and savour the drama!", "drama"),
        ("There's danger lurking, a threat waiting to ambush us from the dark.", "half_light"),
        ("History and reference archives confirm the fact beyond doubt.", "encyclopedia"),
        (
            "A dreamlike whisper from the spirit world guides my intuition tonight.",
            "inland_empire",
        ),
    ],
)
def test_keyword_routing_selects_persona(orchestrator, text, expected):
    result = orchestrator.process_user_input(text)
    assert result["skill"] == expected
