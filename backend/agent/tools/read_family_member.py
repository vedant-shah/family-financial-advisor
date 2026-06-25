"""The `read_family_member` handler: the single, explicit cross-member read door.

Kept separate from `read_context` (which is hard-scoped to the active member) on
purpose — this is the ONE place the agent can reach another member's data, so the
boundary stays greppable and lockable. Two guards hold the line: only an
allowlisted slice of a member's money picture is readable (private prose, chat
history, behavioral inferences never cross), and the requested member must be a
real roster member — a bogus or path-traversal id is refused before any read.
"""
from __future__ import annotations

from backend.agent.context_registry import entry_by_name, resolve_path
from backend.agent.tools.dispatch import ToolResult
from backend.config import settings
from backend.utils.markdown_io import (
    list_member_dirs,
    read_markdown_or_none,
    strip_frontmatter,
)

# A family member's money picture, and nothing more. Private files (notes,
# narrative, conversations, behavioral inferences, agent notes, recommendations,
# life events) are intentionally NOT reachable across the member boundary.
CROSS_MEMBER_READABLE: tuple[str, ...] = (
    "member.profile",
    "member.finances",
    "member.portfolio_summary",
    "member.goals",
)


def handle_read_family_member(tool_input: dict, active_member: str) -> ToolResult:
    name = tool_input.get("name")
    member = tool_input.get("member")
    if not isinstance(name, str) or name not in CROSS_MEMBER_READABLE:
        return ToolResult(f"[tool error] not a readable family context: {name!r}", ok=False)
    if not isinstance(member, str):
        return ToolResult(f"[tool error] no family member named: {member!r}", ok=False)

    # Membership in the roster is both the existence check and the traversal
    # guard: a "../.." id is never a real member directory.
    memory_root = settings.resolve(settings.memory_dir)
    if member not in list_member_dirs(memory_root):
        return ToolResult(f"[tool error] no family member named: {member!r}", ok=False)

    entry = entry_by_name(name)  # in the allowlist, so always a real member-scoped entry
    path = resolve_path(entry, member, settings.project_root)
    content = read_markdown_or_none(path)
    if content is None:
        return ToolResult(f"[not found] {name} for {member}", ok=False)

    return ToolResult(strip_frontmatter(content).strip(), ok=True)
