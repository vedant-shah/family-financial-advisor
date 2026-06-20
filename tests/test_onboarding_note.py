"""The onboarding free-text note must reach the agent.

Previously the note (checks.note) was captured in the UI and sent to the backend
but persist_member_data never read it, so it was silently dropped and never
loaded into the prompt. These tests pin that the note (1) lands in a narrative
notes.md and (2) shows up in the assembled prompt the agent sees.
"""
from __future__ import annotations

import pytest

from backend.agent.assembler import assemble
from backend.agent.onboarding_persist import persist_member_data
from backend.config import settings

_NOTE = "I switched jobs recently and got a joining bonus."


def test_note_persisted_to_notes_file(tmp_memory):
    persist_member_data(tmp_memory, "vedant", {"checks": {"note": _NOTE}}, today="2026-06-19")
    notes = (tmp_memory / "members" / "vedant" / "notes.md").read_text()
    assert _NOTE in notes


def test_empty_note_writes_nothing(tmp_memory):
    persist_member_data(tmp_memory, "vedant", {"checks": {"note": "   "}}, today="2026-06-19")
    assert not (tmp_memory / "members" / "vedant" / "notes.md").exists()


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    # Mirror the real layout so resolve_path (project_root-based) and the writers
    # (memory_dir-based) point at the SAME tmp tree — in production they coincide.
    (tmp_path / "skills").mkdir()
    persona = (settings.project_root / "skills" / "core_system.md").read_text()
    (tmp_path / "skills" / "core_system.md").write_text(persona)

    mem = tmp_path / "memory"
    (mem / "family").mkdir(parents=True)
    (mem / "members" / "vedant").mkdir(parents=True)
    (mem / "family" / "household.md").write_text("---\n---\n# Household\n- vedant self\n")
    (mem / "members" / "vedant" / "profile.md").write_text(
        "## identity.name\n- name: vedant\n- status: CURRENT\n"
    )

    monkeypatch.setattr(settings, "project_root", tmp_path)
    monkeypatch.setattr(settings, "memory_dir", mem)
    monkeypatch.setattr(settings, "sessions_dir", tmp_path / "sessions")
    return mem


def test_note_reaches_assembled_prompt(seeded):
    persist_member_data(seeded, "vedant", {"checks": {"note": _NOTE}}, today="2026-06-19")

    prompt = assemble(
        active_member="vedant",
        classifier_output={"context_level": "FULL", "relevant_memory_files": [], "is_followup": False},
        in_session_history=[],
        user_message="hi",
        memory_root=seeded,
        skills_root=settings.resolve(settings.skills_dir),
    )
    text = "\n\n".join(block.text for block in prompt.system)
    assert _NOTE in text
