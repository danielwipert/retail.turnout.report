"""Pull just the relevant lines out of a long filing (decision P2-3).

Plain Python, no LLM: keep every line that mentions a comps/traffic/ticket/
margin/store-count keyword, plus a couple of lines around it for context.
"""

from __future__ import annotations

import re

KEYWORDS = re.compile(
    r"comparable|same[- ](store|restaurant|shop|shack|club)|\bcomps?\b"
    r"|traffic|transactions?|guest (counts?|traffic)|customer (counts?|visits)"
    r"|average (check|ticket|transaction|basket|order)|\bticket\b|\bbasket\b|price[/ ]and[/ ]mix|price/mix|\bmix\b"
    r"|restaurant[- ]level|restaurant margin|gross (profit )?(margin|rate)"
    r"|(stores?|restaurants?|shops?|clubs?|units?) (open|in operation|at (the )?end)"
    r"|ended the (quarter|period|year) with|total (stores|restaurants)",
    re.IGNORECASE,
)

CONTEXT_LINES = 2
MAX_CHARS = 30_000


def snippets(text: str, max_chars: int = MAX_CHARS, context: int = CONTEXT_LINES) -> str:
    lines = text.splitlines()
    keep: set[int] = set()
    for i, line in enumerate(lines):
        if KEYWORDS.search(line):
            keep.update(range(max(0, i - context), min(len(lines), i + context + 1)))
    if not keep:
        return ""

    blocks, current, last = [], [], None
    for i in sorted(keep):
        if last is not None and i != last + 1:
            blocks.append("\n".join(current))
            current = []
        if lines[i].strip():
            current.append(lines[i])
        last = i
    if current:
        blocks.append("\n".join(current))

    out, used = [], 0
    for block in blocks:
        if used + len(block) > max_chars:
            break
        out.append(block)
        used += len(block) + 5
    return "\n...\n".join(out)
