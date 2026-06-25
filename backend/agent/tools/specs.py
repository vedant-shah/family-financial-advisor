"""Tool schemas advertised to the main agent.

The `read_context` name-enum is generated from the registry's agent-invokable
entries, so the model can only ever name a real on-demand file — never a Tier 1
file or an arbitrary path. This is the first of the scope guards.
"""
from __future__ import annotations

from backend.agent.context_registry import entries_by_policy
from backend.agent.tools.read_family_member import CROSS_MEMBER_READABLE

READ_CONTEXT = "read_context"
RECALL_CONVERSATION = "recall_conversation"
READ_FAMILY_MEMBER = "read_family_member"


def _agent_invoked_names() -> list[str]:
    return [e.name for e in entries_by_policy("agent_invoked")]


def tool_specs() -> list[dict]:
    return [
        {
            "name": READ_CONTEXT,
            "description": (
                "Load one on-demand context file by name: a skill playbook or a "
                "memory file you need but that wasn't already in your context. "
                "Returns the file's text, or a short error if it can't be read. "
                "Only call this when you actually need data you don't already have. "
                "If you already know you need several files, call this once per file "
                "in the SAME turn instead of waiting for each result, they are fetched "
                "together. Only read one and wait when a later read depends on what an "
                "earlier one returns."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": _agent_invoked_names(),
                        "description": "Registry name of the context to load.",
                    }
                },
                "required": ["name"],
            },
        },
        {
            "name": RECALL_CONVERSATION,
            "description": (
                "Keyword-search this person's OLDER conversations, further back "
                "than the recent summaries already in your context. Returns dated "
                "excerpts of the best-matching past turns. Use when they refer to "
                "something you discussed a while ago that you don't already have."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords to search past conversations for.",
                    }
                },
                "required": ["query"],
            },
        },
        {
            "name": READ_FAMILY_MEMBER,
            "description": (
                "Read one part of ANOTHER family member's money picture, by member "
                "id (as listed in the household roster) and file. Use when this "
                "person's decision turns on a relative's situation: a shared goal, "
                "who depends on whom, a household-level call. Returns the file's "
                "text, or a short error if it can't be read."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "member": {
                        "type": "string",
                        "description": "Member id from the household roster (e.g. 'mom').",
                    },
                    "name": {
                        "type": "string",
                        "enum": list(CROSS_MEMBER_READABLE),
                        "description": "Which part of that member's money picture to read.",
                    },
                },
                "required": ["member", "name"],
            },
        },
    ]
