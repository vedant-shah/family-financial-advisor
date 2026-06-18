"""Memory loads on every turn, regardless of the classifier's context level.

MINIMAL no longer starves the prompt: a greeting/chit-chat message the classifier
tags MINIMAL must still load the member's stored memory, so the agent can never
go blind and deny knowledge it has on file. The persona/texting voice must also
survive (it loads as part of Tier 1) and the generic advisor stamp stays out.
"""
from __future__ import annotations

import pytest

from backend.agent.assembler import assemble
from backend.config import settings

# A greeting the classifier tags MINIMAL — the worst case for the old design,
# which loaded no memory here.
MINIMAL_CLASSIFICATION = {
    "context_level": "MINIMAL",
    "relevant_memory_files": [],
    "is_followup": False,
}


@pytest.fixture
def seeded_root(tmp_path, monkeypatch):
    (tmp_path / "skills").mkdir()
    persona = (settings.project_root / "skills" / "core_system.md").read_text()
    (tmp_path / "skills" / "core_system.md").write_text(persona)

    mem = tmp_path / "memory"
    (mem / "family").mkdir(parents=True)
    d = mem / "members" / "vedant"
    d.mkdir(parents=True)
    (mem / "family" / "household.md").write_text(
        "---\nlast_updated: 2026-06-14\n---\n# Household\n- vedant self\n"
    )
    (d / "profile.md").write_text("## identity.name\n- name: vedant\n- status: CURRENT\n")
    (d / "finances.md").write_text("## income.salary\n- value: 137000\n- status: CURRENT\n")

    monkeypatch.setattr(settings, "project_root", tmp_path)
    monkeypatch.setattr(settings, "memory_dir", mem)
    return mem


def _system_text(mem, member="vedant") -> str:
    prompt = assemble(
        active_member=member,
        classifier_output=MINIMAL_CLASSIFICATION,
        in_session_history=[],
        user_message="hey",
        memory_root=mem,
        skills_root=settings.resolve(settings.skills_dir),
    )
    return "\n\n".join(block.text for block in prompt.system)


def test_chitchat_turn_still_loads_member_memory(seeded_root) -> None:
    # The fix: even a MINIMAL-classified greeting loads the member's stored
    # memory, so the agent can't go blind and deny what it has on file.
    text = _system_text(seeded_root)
    assert "137000" in text  # income (finances) is loaded


def test_persona_voice_is_present(seeded_root) -> None:
    text = _system_text(seeded_root).lower()
    assert "em dash" in text
    assert "preamble" in text


def test_no_generic_advisor_stamp(seeded_root) -> None:
    text = _system_text(seeded_root)
    assert "You are a personal financial advisor" not in text


def test_session_context_present(seeded_root) -> None:
    text = _system_text(seeded_root)
    assert "Today's date" in text
    assert "vedant" in text
