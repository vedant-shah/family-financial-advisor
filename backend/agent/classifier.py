"""
Per-turn intent classifier — Haiku forced-JSON, history-aware, safe fallback.

One `complete_json` call per turn selects context_level + intent + is_followup.
The intent maps (via intent_map) to the Tier 2 memory files the assembler loads.

The classifier sees the last few turns of the session so it can resolve
follow-ups correctly: a short message that continues the prior topic ("why?")
and one that shifts topic ("and my home loan?") are told apart by context, not
by a length heuristic. The most recent user message is the one being classified;
earlier turns are context only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.agent.assembler import ClassifierOutput
from backend.agent.intent_map import INTENT_FILES, files_for_intent
from backend.agent.llm_provider import LLMProvider, SystemBlock
from backend.config import settings

logger = logging.getLogger(__name__)

# How many recent in-session messages (user+assistant) to show the classifier as
# follow-up context. 4 ≈ the last two turns.
_HISTORY_MESSAGES = 4

# Safe fallback when the model returns {} or an unrecognized intent: load full
# context with a broad intent so the agent is never starved of memory.
_FALLBACK_CONTEXT_LEVEL = "FULL"
_FALLBACK_INTENT = "portfolio_review"


@dataclass(frozen=True)
class Classification:
    output: ClassifierOutput
    intent: str


_CLASSIFIER_SYSTEM = (
    "You route a family member's message to a personal financial advisor. You "
    "are given the recent conversation for context and the latest message to "
    "classify. Classify ONLY the latest message; earlier turns are there to "
    "resolve follow-ups. Pick the single best intent and a context_level.\n\n"
    "context_level — default to FULL. The advisor needs the member's financial "
    "memory to answer well, so almost every real message is FULL.\n"
    "  FULL: any message with financial substance — questions, statements about "
    "money/assets/goals/debt/tax/insurance, decisions, life events, or anything "
    "you would need their financial history to answer. Examples: 'where do I "
    "park 5L', 'should I prepay my loan', 'I just got a raise', 'is my "
    "retirement on track', 'what's an ELSS'.\n"
    "  MINIMAL: ONLY pure greetings, thanks, or chit-chat with zero financial "
    "content. Examples: 'hi', 'hey', 'thanks!', 'good morning', 'how are you'.\n"
    "  If a message is borderline or you are unsure, choose FULL. Never use "
    "MINIMAL just because the message is short.\n\n"
    "intent — for a follow-up, choose the intent of the topic it continues "
    "(use the conversation context); for a topic shift, choose the new topic's "
    "intent.\n\n"
    "is_followup — true only when the latest message clearly continues the "
    "previous turn ('why?', 'and the other one?') rather than opening a new "
    "topic. Use the conversation context to decide."
)

# NOTE (context_level 2 vs 3 values): PRD §6 lists three levels
# (minimal | standard | deep). The FROZEN ClassifierOutput contract allows only
# two (MINIMAL | FULL), so the tool emits only those — standard+deep collapse to
# FULL. The frozen Day 1 contract wins.
_CLASSIFY_TOOL = {
    "name": "classify",
    "description": "Classify the user's financial question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "context_level": {
                "type": "string",
                "enum": ["MINIMAL", "FULL"],
                "description": (
                    "FULL for any message with financial substance (default). "
                    "MINIMAL only for pure greetings/thanks/chit-chat. When "
                    "unsure, choose FULL."
                ),
            },
            "intent": {
                "type": "string",
                "enum": list(INTENT_FILES.keys()),
                "description": "The single best-matching intent for the message.",
            },
            "is_followup": {
                "type": "boolean",
                "description": (
                    "True only when this message continues the prior turn rather "
                    "than opening a new topic."
                ),
            },
        },
        "required": ["context_level", "intent", "is_followup"],
    },
}


def _build(raw: dict, member: str) -> Classification:
    """Validate the model's raw tool output and build a Classification.

    Falls back to FULL / portfolio_review / is_followup=False on missing keys or
    an intent outside the known vocabulary."""
    intent = raw.get("intent")
    context_level = raw.get("context_level")
    if intent not in INTENT_FILES or context_level not in ("MINIMAL", "FULL"):
        intent = _FALLBACK_INTENT
        context_level = _FALLBACK_CONTEXT_LEVEL
        is_followup = False
    else:
        is_followup = bool(raw.get("is_followup", False))

    relevant = files_for_intent(intent, member) if context_level == "FULL" else []
    output: ClassifierOutput = {
        "context_level": context_level,
        "relevant_memory_files": relevant,
        "is_followup": is_followup,
    }
    return Classification(output=output, intent=intent)


def _format_prompt(history: list[dict], user_message: str) -> str:
    """Render recent history + the message to classify into one user turn.

    A single text block (rather than real alternating messages) sidesteps the
    role-alternation rules and makes the 'classify the latest message' framing
    explicit."""
    recent = history[-_HISTORY_MESSAGES:]
    if not recent:
        return f"Message to classify:\n{user_message}"
    lines = ["Recent conversation (context only):"]
    for msg in recent:
        speaker = "advisor" if msg.get("role") == "assistant" else "member"
        lines.append(f"{speaker}: {msg.get('content', '')}")
    lines.append("")
    lines.append(f"Message to classify:\n{user_message}")
    return "\n".join(lines)


async def classify(
    *,
    provider: LLMProvider,
    member: str,
    user_message: str,
    history: list[dict],
    session_id: str = "",
) -> Classification:
    """Classify one turn with recent history as context. One forced-JSON Haiku
    call with a safe fallback. `session_id` is used only for log correlation."""
    raw = await provider.complete_json(
        system=[SystemBlock(text=_CLASSIFIER_SYSTEM)],
        messages=[{"role": "user", "content": _format_prompt(history, user_message)}],
        tool=_CLASSIFY_TOOL,
        model=settings.classifier_model,
        max_tokens=256,
        label="classifier",
    )
    result = _build(raw or {}, member)  # None (API error) → {} → safe FULL fallback
    logger.info(
        "classifier: %s/%s intent=%s level=%s followup=%s",
        member,
        session_id,
        result.intent,
        result.output["context_level"],
        result.output["is_followup"],
    )
    return result
