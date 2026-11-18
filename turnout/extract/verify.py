"""Deterministic checks on every LLM answer (spec section 5.2).

A field is "verified" only if every check passes. Anything else goes to review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from turnout.extract.fields import DIRECTIONS, SOURCES, Field

_TRANSLATE = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", " ": " ", " ": " ", " ": " ",
})


_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
MAX_TOKEN_GAP = 3  # filing tokens allowed between two consecutive quote tokens
_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\ufeff]")


def normalize(s: str) -> str:
    """Lowercase, unify quotes/dashes, and ignore table-cell separators and spacing."""
    s = _ZERO_WIDTH.sub("", s.translate(_TRANSLATE)).replace("|", " ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([%)])", r"\1", s)  # "4.5 %" -> "4.5%", "(2.9 )" -> "(2.9)"
    s = re.sub(r"([($])\s+", r"\1", s)
    return s.strip().lower()


NEG_WORDS = re.compile(r"\b(decreas\w*|declin\w*|fell|down|lower|negative|drop\w*|softer|reduc\w*)\b", re.I)
POS_WORDS = re.compile(r"\b(increas\w*|grew|growth|up|higher|rose|positive|gain\w*|improv\w*)\b", re.I)
FLAT_WORDS = re.compile(r"\b(flat|unchanged|consistent|in line|stable)\b", re.I)

# A number, maybe in parentheses or with a minus, maybe followed by % / percent / bps.
_NUMBER = re.compile(
    r"(?P<open>\()?\s*(?P<minus>-)?\s*(?P<num>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*"
    r"(?P<unit>%|percent\b|bps\b|basis points?\b)?\s*(?P<close>\))?",
    re.I,
)

SEGMENT_LOOKBACK = 6000  # characters before the quote where a segment heading may sit

RANGES = {"pct": (-40.0, 40.0), "margin": (0.0, 70.0), "count": (1, 100_000)}


@dataclass
class Check:
    status: str  # "verified", "flagged", "missing"
    reasons: list[str] = field(default_factory=list)


def _token_match(nq: str, nt: str) -> int:
    """Every word/number of the quote appears in the filing, in order, with small gaps.

    Handles table rows whose cell separators, blank cells or punctuation differ
    from the saved text, while still rejecting paraphrases (a word that isn't
    there breaks the chain).
    """
    q = _TOKEN.findall(nq)
    if len(q) < 2:
        return -1
    t = [(m.group(0), m.start()) for m in _TOKEN.finditer(nt)]
    words = [w for w, _ in t]
    for start in (i for i, w in enumerate(words) if w == q[0]):
        j = start
        ok = True
        for token in q[1:]:
            window = words[j + 1: j + 2 + MAX_TOKEN_GAP]
            if token not in window:
                ok = False
                break
            j = j + 1 + window.index(token)
        if ok:
            return t[start][1]
    return -1


def quote_in_text(quote: str, text: str) -> int:
    """Position of the quote in the text (normalized), or -1. '...' gaps are allowed."""
    nq, nt = normalize(quote), normalize(text)
    if "..." not in nq and "…" not in nq:
        exact = nt.find(nq)
        if exact >= 0:
            return exact
        return _token_match(nq, nt)
    parts = [p.strip() for p in re.split(r"\.\.\.|…", nq) if p.strip()]
    if not parts:
        return -1
    start = nt.find(parts[0])
    if start < 0:
        return -1
    pos = start + len(parts[0])
    for part in parts[1:]:
        nxt = nt.find(part, pos)
        if nxt < 0:
            return -1
        pos = nxt + len(part)
    return start


def numbers_in(quote: str) -> list[tuple[float, bool, str]]:
    """[(absolute value, shown as negative?, unit)] for every number in the quote."""
    found = []
    for m in _NUMBER.finditer(quote.translate(_TRANSLATE)):
        raw = float(m.group("num").replace(",", ""))
        unit = (m.group("unit") or "").lower()
        negative = bool(m.group("minus")) or bool(m.group("open") and m.group("close"))
        if unit.startswith("b"):
            raw = raw / 100.0
        found.append((raw, negative, unit))
    return found


_COUNT_NOUN = re.compile(r"\b(stores?|restaurants?|units?|clubs?|shops?|locations?|warehouses?|bakery-cafes?)\b", re.I)
_NOT_A_COUNT = re.compile(r"square\s*f(ee|oo)t|sq\.?\s*ft|square footage", re.I)


def check_field(f: Field, answer: dict, documents: dict[str, str], segment_keywords: list[str],
                must_include: list[str] | None = None) -> Check:
    value, quote, source = answer.get("value"), answer.get("quote"), answer.get("source")
    if value is None:
        return Check("missing")
    reasons = []
    if not quote:
        return Check("flagged", ["no_quote"])
    if source not in SOURCES:
        reasons.append("bad_source")

    # 1. The quote really is in the filing.
    where, pos = None, -1
    order = [source] + [s for s in SOURCES if s != source] if source in SOURCES else SOURCES
    for name in order:
        pos = quote_in_text(quote, documents.get(name, ""))
        if pos >= 0:
            where = name
            break
    if where is None:
        reasons.append("quote_not_in_filing")

    if f.kind == "direction":
        if value not in DIRECTIONS:
            reasons.append("bad_direction")
        elif value == "down" and not NEG_WORDS.search(quote):
            reasons.append("direction_words_mismatch")
        elif value == "up" and not POS_WORDS.search(quote):
            reasons.append("direction_words_mismatch")
        elif value == "flat" and not FLAT_WORDS.search(quote):
            reasons.append("direction_words_mismatch")
        return Check("flagged" if reasons else "verified", reasons)

    try:
        value = float(value)
    except (TypeError, ValueError):
        return Check("flagged", ["not_a_number"])

    # 2. The number is in the quote.
    nums = numbers_in(quote)
    tolerance = 0.5 if f.kind == "count" else 0.051
    matches = [n for n in nums if abs(n[0] - abs(value)) <= tolerance]
    if f.kind != "count":
        # Percent fields: prefer numbers that carry a % / bps unit when any do.
        with_unit = [n for n in matches if n[2]]
        matches = with_unit or matches
    if not matches:
        reasons.append("number_not_in_quote")

    # 3. The sign matches the words.
    if matches and f.kind == "pct" and value != 0:
        shown_negative = any(n[1] for n in matches)
        neg, pos_w = bool(NEG_WORDS.search(quote)), bool(POS_WORDS.search(quote))
        if value > 0 and (shown_negative or (neg and not pos_w)):
            reasons.append("sign_mismatch")
        if value < 0 and not shown_negative and pos_w and not neg:
            reasons.append("sign_mismatch")

    # 3b. Counts must be counts of stores, not square feet or dollars.
    if f.kind == "count":
        if _NOT_A_COUNT.search(quote):
            reasons.append("count_is_square_footage")
        elif not _COUNT_NOUN.search(quote):
            reasons.append("count_word_missing")

    # 3c. Company-specific words the quote must contain (e.g. "company" for TXRH store counts).
    if must_include and not any(w.lower() in quote.lower() for w in must_include):
        reasons.append("required_words_missing")

    # 4. Plausible range.
    lo, hi = RANGES[f.kind]
    if not lo <= value <= hi:
        reasons.append("out_of_range")

    # 5. Segment: a keyword appears in the quote or shortly before it.
    if segment_keywords and f.name in {"comp_sales_pct", "comp_traffic_pct", "comp_ticket_pct"} and where:
        full = normalize(documents[where])
        window = full[max(0, pos - SEGMENT_LOOKBACK): pos] + " " + normalize(quote)
        if not any(normalize(k) in window for k in segment_keywords):
            reasons.append("segment_unconfirmed")

    return Check("flagged" if reasons else "verified", reasons)


def arithmetic_ok(comp: float | None, traffic: float | None, ticket: float | None) -> bool | None:
    """comp ≈ traffic + ticket (within 0.5). None if any is missing."""
    if None in (comp, traffic, ticket):
        return None
    return abs(comp - (traffic + ticket)) <= 0.5
