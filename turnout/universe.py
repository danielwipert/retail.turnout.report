"""The list of chains we track (`data/universe.json`) and CIK lookup."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from turnout.config import UNIVERSE_PATH
from turnout.sources.sec import TICKERS_URL, Fetcher, cik10


@dataclass
class Chain:
    ticker: str
    name: str
    tier: str  # "core" or "watch"
    group: str  # limited_service, full_service, mass_club_value, home_specialty
    segment: str = ""
    segment_keywords: list[str] = field(default_factory=list)
    calendar: str = "calendar"  # calendar, nrf, or fiscal_aug, fiscal_jul, ...
    status: str = ""  # "confirmed" (checked in a 2026 filing) or "to_confirm"
    cik: str | None = None
    notes: str = ""
    field_notes: dict[str, str] = field(default_factory=dict)  # per-field instructions for the LLM


def load_universe(path: Path = UNIVERSE_PATH) -> list[Chain]:
    raw = json.loads(path.read_text())
    return [Chain(**row) for row in raw["chains"]]


def save_universe(chains: list[Chain], path: Path = UNIVERSE_PATH) -> None:
    raw = json.loads(path.read_text())
    raw["chains"] = [chain.__dict__ for chain in chains]
    path.write_text(json.dumps(raw, indent=2) + "\n")


def resolve_ciks(chains: list[Chain], fetcher: Fetcher) -> list[str]:
    """Fill in missing CIKs from SEC's ticker list. Returns tickers it couldn't find."""
    table = fetcher.get_json(TICKERS_URL)
    by_ticker = {row["ticker"].upper(): row["cik_str"] for row in table.values()}
    missing = []
    for chain in chains:
        if chain.cik:
            continue
        found = by_ticker.get(chain.ticker.upper())
        if found is None:
            missing.append(chain.ticker)
        else:
            chain.cik = cik10(found)
    return missing


def select(chains: list[Chain], tickers: list[str] | None) -> list[Chain]:
    if not tickers:
        return chains
    wanted = {t.upper() for t in tickers}
    chosen = [c for c in chains if c.ticker.upper() in wanted]
    unknown = wanted - {c.ticker.upper() for c in chosen}
    if unknown:
        raise ValueError(f"Not in data/universe.json: {', '.join(sorted(unknown))}")
    return chosen
