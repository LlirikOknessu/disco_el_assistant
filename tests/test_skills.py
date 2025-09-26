from __future__ import annotations

from typing import Any, Dict, List

from skills.persona import PersonaSkill


def _build_context(messages: List[Dict[str, str]], guidance: str, extra: str | None = None) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "recent_messages": messages,
        "orchestrator_prompt": guidance,
        "user_input": messages[-1]["content"] if messages else "",
    }
    if extra is not None:
        context["extra_guidance"] = extra
    return context


def test_persona_skill_uses_configuration(openai_client_stub) -> None:
    config = {
        "name": "logic",
        "persona": "Analytical Strategist",
        "style": "Concise",
        "temperature": 0.3,
        "response_preamble": "Highlight assumptions.",
        "model_params": {"top_p": 0.85},
    }
    messages = [
        {"role": "user", "content": "How do we plan this investigation?"},
        {"role": "assistant", "content": "Consider every clue."},
        {"role": "user", "content": "Focus on logic."},
    ]
    context = _build_context(messages, guidance="Base guidance")

    skill = PersonaSkill(config=config, openai_client=openai_client_stub)
    result = skill.generate_response(context)

    assert result.startswith("response::logic")
    prompt_kwargs = openai_client_stub.formatted_skill_prompts[-1]
    assert prompt_kwargs["skill_name"] == "logic"
    assert prompt_kwargs["persona"] == "Analytical Strategist"
    assert prompt_kwargs["style"] == "Concise"
    assert "Additional guidance: Highlight assumptions." in prompt_kwargs["guidance"]

    call = openai_client_stub.generated_calls[-1]
    assert call["skill_name"] == "logic"
    assert call["kwargs"]["temperature"] == 0.3
    assert call["kwargs"]["top_p"] == 0.85


def test_persona_skill_prefers_context_extra_guidance(openai_client_stub) -> None:
    config = {
        "name": "empathy",
        "persona": "Supportive Listener",
        "style": "Warm",
        "response_preamble": "Default guidance",
    }
    messages = [
        {"role": "user", "content": "I'm feeling uncertain."},
    ]
    context = _build_context(messages, guidance="Orchestrator says stay calm", extra="Use gentle tone.")

    skill = PersonaSkill(config=config, openai_client=openai_client_stub)
    skill.generate_response(context)

    prompt_kwargs = openai_client_stub.formatted_skill_prompts[-1]
    assert prompt_kwargs["skill_name"] == "empathy"
    assert prompt_kwargs["persona"] == "Supportive Listener"
    assert prompt_kwargs["style"] == "Warm"
    assert prompt_kwargs["guidance"].endswith("Use gentle tone.")
    assert "Default guidance" not in prompt_kwargs["guidance"]
