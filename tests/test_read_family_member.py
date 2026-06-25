"""The cross-member read door (`read_family_member`): the ONE explicit place the
agent can reach another family member's data.

These tests pin the boundary: only an allowlisted slice of a member's money
picture is reachable, the member must be a real roster member (a bogus or
path-traversal id is refused), and private files never cross the member line.
"""
from backend.agent.tools.dispatch import default_dispatch
from backend.agent.tools.read_family_member import (
    CROSS_MEMBER_READABLE,
    handle_read_family_member,
)
from backend.agent.tools.specs import READ_FAMILY_MEMBER, tool_specs
from backend.config import settings


def _seed(tmp_path, member, filename, body):
    d = tmp_path / "memory" / "members" / member
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(body)


def test_reads_another_members_money_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    _seed(tmp_path, "mom", "finances.md", "---\nx: 1\n---\n## income.salary\n- value: 140000\n")
    # vedant's session reaches mom's finances through the explicit door.
    result = handle_read_family_member(
        {"member": "mom", "name": "member.finances"}, "vedant"
    )
    assert result.ok
    assert "140000" in result.content
    assert "---" not in result.content  # frontmatter stripped


def test_allowlist_is_the_money_picture_only(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    for fname in ("profile.md", "finances.md", "portfolio_summary.md", "goals.md"):
        _seed(tmp_path, "mom", fname, f"# {fname}\n- ok\n")
    for name in CROSS_MEMBER_READABLE:
        result = handle_read_family_member({"member": "mom", "name": name}, "vedant")
        assert result.ok, name


def test_rejects_private_files(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    # A member's private prose / chat history / behavioral inferences never cross
    # the member boundary, even though they are valid registry names.
    _seed(tmp_path, "mom", "notes.md", "# private\n- mom's private note\n")
    _seed(tmp_path, "mom", "conversations.md", "# chats\n- mom chat\n")
    for name in ("member.notes", "member.conversations", "member.inferences"):
        result = handle_read_family_member({"member": "mom", "name": name}, "vedant")
        assert not result.ok, name
        assert "private note" not in result.content


def test_rejects_unknown_member(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    _seed(tmp_path, "vedant", "finances.md", "# v\n- vedant only\n")
    result = handle_read_family_member(
        {"member": "ghost", "name": "member.finances"}, "vedant"
    )
    assert not result.ok


def test_rejects_path_traversal_member(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    _seed(tmp_path, "vedant", "finances.md", "# v\n- secret\n")
    # A traversal id is not a real member dir, so it is refused before any read.
    result = handle_read_family_member(
        {"member": "../../../etc", "name": "member.finances"}, "vedant"
    )
    assert not result.ok


def test_missing_file_reports_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    # mom is a real member (has a profile) but never wrote a goals file.
    _seed(tmp_path, "mom", "profile.md", "# mom\n")
    result = handle_read_family_member(
        {"member": "mom", "name": "member.goals"}, "vedant"
    )
    assert not result.ok
    assert "not found" in result.content.lower()


def test_dispatch_routes_read_family_member(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_root", tmp_path)
    _seed(tmp_path, "mom", "portfolio_summary.md", "# mom assets\n- gold\n")
    result = default_dispatch().execute(
        "read_family_member",
        {"member": "mom", "name": "member.portfolio_summary"},
        active_member="vedant",
    )
    assert result.ok
    assert "gold" in result.content


def test_spec_advertises_door_with_allowlist():
    spec = next(s for s in tool_specs() if s["name"] == READ_FAMILY_MEMBER)
    props = spec["input_schema"]["properties"]
    assert set(props) == {"member", "name"}
    assert set(props["name"]["enum"]) == set(CROSS_MEMBER_READABLE)
    assert spec["input_schema"]["required"] == ["member", "name"]
