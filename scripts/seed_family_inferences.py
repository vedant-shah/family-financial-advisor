#!/usr/bin/env python3
"""One-off backfill: seed the cross-member relevance index from existing chats.

Re-runs the summarizer's cross-member extraction over every member's session
transcripts and writes the financially-relevant observations into
`memory/family/inferences.md` (the always-loaded relevance index). It ONLY writes
that index, never re-touching member files, and is idempotent: re-running uses
the same dedup ids (session + subject + topic), so nothing duplicates. Processed
oldest-first, so the newest observation about a given subject+topic ends up the
CURRENT one.

Usage (from the repo root, so `backend` is importable):
    python -m scripts.seed_family_inferences
"""
from __future__ import annotations

import asyncio


async def _seed() -> int:
    # Imports live here (not at module load) so the script follows the repo
    # convention and `backend` is resolved from the repo root.
    from backend.agent.llm_provider import SystemBlock, get_provider
    from backend.agent.memory_updater import (
        _SUMMARIZE_TOOL,
        _SUMMARIZER_SYSTEM,
        _conversation_date,
        _date_instruction,
        _dedup_id,
        _roster_context,
    )
    from backend.agent.promotion import _split_about
    from backend.agent.roster import slugify
    from backend.agent.writers import write_family_inference
    from backend.config import settings
    from backend.utils.markdown_io import list_member_dirs, read_markdown_or_none

    memory_root = settings.resolve(settings.memory_dir)
    sessions_root = settings.resolve(settings.sessions_dir)
    provider = get_provider()
    roster = _roster_context(memory_root)  # lets the extractor name `about` by member_id

    written = 0
    for member in list_member_dirs(memory_root):
        member_dir = sessions_root / member
        if not member_dir.exists():
            continue

        # (conv_date, session_id, content), oldest first so a later session's
        # take on the same subject+topic supersedes an earlier one.
        items: list[tuple[str, str, str]] = []
        for p in sorted(member_dir.glob("*.jsonl")):
            content = read_markdown_or_none(p)
            if content:
                items.append((_conversation_date(content), p.stem, content))
        items.sort(key=lambda t: t[0])

        for conv_date, session_id, content in items:
            print(f"[{member}/{session_id}] {conv_date} ...")
            system = [
                SystemBlock(text=_SUMMARIZER_SYSTEM),
                SystemBlock(text=_date_instruction(conv_date)),
            ]
            if roster:
                system.append(SystemBlock(text=roster))
            raw = await provider.complete_json(
                system=system,
                messages=[{"role": "user", "content": content}],
                tool=_SUMMARIZE_TOOL,
                model=settings.summarizer_model,
                max_tokens=8000,
                thinking_budget=settings.summarizer_thinking_budget,
                label="seed_family_inferences",
            )
            if not raw:
                print("  (no extraction)")
                continue
            for obs in raw.get("cross_member_observations", []):
                about = obs.get("about")
                topic = obs.get("topic")
                relevance = obs.get("relevance")
                if not (about and topic and relevance):
                    continue  # not financially relevant -> roster-only, skip index
                about_id = slugify(_split_about(about)[0])
                write_family_inference(
                    member,
                    about=about_id,
                    topic=topic,
                    relevance=relevance,
                    pointer=obs.get("pointer", ""),
                    source="inference",
                    confidence="low",
                    as_of=conv_date,
                    dedup_id=_dedup_id(session_id, "famidx", about_id, topic),
                )
                written += 1
                print(f"  + {about_id}.{topic}: {relevance}")

    return written


def main() -> None:
    written = asyncio.run(_seed())
    print(f"\nDone. {written} entries written to memory/family/inferences.md")


if __name__ == "__main__":
    main()
