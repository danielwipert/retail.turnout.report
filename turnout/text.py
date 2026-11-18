"""Turn filing HTML into plain text that an LLM (and our quote checker) can read."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

_SPACES = re.compile(r"[ \t   ]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    # Hidden inline-XBRL header blocks repeat data and add noise.
    for tag in soup.find_all(style=re.compile(r"display:\s*none", re.I)):
        tag.decompose()

    # Keep table rows on one line, cells separated by " | ".
    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        # Drop empty and zero-width-only cells (common in EDGAR tables).
        cells = [c for c in cells if c.strip("\u200b\u200c\u200d\ufeff \u00a0")]
        row.replace_with(soup.new_string("\n" + " | ".join(cells) + "\n"))

    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
        block.insert_after("\n")

    text = soup.get_text()
    lines = [_SPACES.sub(" ", line).strip() for line in text.splitlines()]
    text = "\n".join(lines)
    return _BLANK_LINES.sub("\n\n", text).strip() + "\n"
