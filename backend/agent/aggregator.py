from __future__ import annotations

import logging
from pathlib import Path

import frontmatter

from backend.utils.markdown_io import read_markdown_or_none

logger = logging.getLogger(__name__)


def read_family_name(memory_root: Path) -> str | None:
    """Extract family_id from memory/family/household.md frontmatter, title-cased."""
    content = read_markdown_or_none(memory_root / "family" / "household.md")
    if content is None:
        return None
    try:
        post = frontmatter.loads(content)
        raw_id = post.metadata.get("family_id")
        return str(raw_id).strip().title() if raw_id else None
    except Exception as exc:
        logger.warning("aggregator: could not parse household.md frontmatter: %s", exc)
        return None
