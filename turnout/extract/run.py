"""Extract one quarter: snippets → LLM → checks → (retry missing on full text) → result.

Result file: data/extracted/{TICKER}/{period_end}.json  (small; committed to the repo)
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from turnout.config import DATA_DIR, RAW_DIR
from turnout.extract import verify
from turnout.extract.fields import Field, fields_for, json_schema
from turnout.extract.llm import Extractor, Usage, build_prompt
from turnout.extract.snippets import snippets
from turnout.universe import Chain

EXTRACTED_DIR = DATA_DIR / "extracted"
FULL_TEXT_LIMIT = 80_000  # characters per document on the full-text retry (~20k tokens each; fits 128k-context models)


def load_documents(quarter_dir: Path) -> tuple[dict, dict[str, str]]:
    manifest = json.loads((quarter_dir / "manifest.json").read_text())
    press = "\n\n".join(
        (quarter_dir / ex["text"]).read_text(encoding="utf-8")
        for ex in manifest.get("exhibits", [])
        if (quarter_dir / ex["text"]).exists()
    )
    periodic_path = quarter_dir / "periodic.txt"
    periodic = periodic_path.read_text(encoding="utf-8") if periodic_path.exists() else ""
    return manifest, {"press_release": press, "periodic": periodic}


def _ask(extractor: Extractor, chain: Chain, period_end: str, fields: list[Field],
         documents: dict[str, str], usage: Usage) -> dict:
    prompt = build_prompt(chain.name, chain.segment, period_end, fields, documents, chain.field_notes)
    answer = extractor.extract(prompt, json_schema(fields))
    usage.add(answer.usage)
    return answer.data


def extract_quarter(chain: Chain, quarter_dir: Path, extractor: Extractor) -> dict:
    manifest, documents = load_documents(quarter_dir)
    fields = fields_for(chain.tier)
    usage = Usage()

    # Pass 1: keyword snippets only.
    short_docs = {name: snippets(text) for name, text in documents.items()}
    data = _ask(extractor, chain, manifest["period_end"], fields, short_docs, usage)

    results: dict[str, dict] = {}
    for f in fields:
        ans = data.get(f.name) or {}
        check = verify.check_field(f, ans, documents, chain.segment_keywords, chain.quote_must_include.get(f.name))
        results[f.name] = {**ans, "status": check.status, "reasons": check.reasons, "pass": "snippets"}

    # Pass 2: anything still missing gets one retry on the full documents.
    missing = [f for f in fields if results[f.name]["status"] == "missing"]
    if missing:
        full_docs = {name: text[:FULL_TEXT_LIMIT] for name, text in documents.items()}
        data2 = _ask(extractor, chain, manifest["period_end"], missing, full_docs, usage)
        for f in missing:
            ans = data2.get(f.name) or {}
            check = verify.check_field(f, ans, documents, chain.segment_keywords, chain.quote_must_include.get(f.name))
            if check.status != "missing":
                results[f.name] = {**ans, "status": check.status, "reasons": check.reasons, "pass": "full_text"}

    flags = []
    if chain.tier == "core":
        val = lambda n: results[n]["value"] if results[n]["status"] == "verified" else None  # noqa: E731
        comp, traffic, ticket = val("comp_sales_pct"), val("comp_traffic_pct"), val("comp_ticket_pct")
        if ticket is None and comp is not None and traffic is not None:
            results["comp_ticket_pct"] = {
                "value": round(comp - traffic, 2), "quote": None, "source": None,
                "status": "derived", "reasons": ["ticket = comp - traffic"], "pass": "derived",
            }
        if verify.arithmetic_ok(comp, traffic, ticket) is False:
            flags.append("comp_not_equal_traffic_plus_ticket")

    return {
        "ticker": chain.ticker,
        "tier": chain.tier,
        "period_end": manifest["period_end"],
        "periodic_accession": manifest["periodic"]["accession"],
        "periodic_url": manifest["periodic"]["url"],
        "earnings_8k_accession": (manifest.get("earnings_8k") or {}).get("accession"),
        "press_release_urls": [ex["url"] for ex in manifest.get("exhibits", [])],
        "model": extractor.model,
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fields": results,
        "flags": flags,
        "usage": asdict(usage),
    }


def result_path(ticker: str, period_end: str, out_dir: Path = EXTRACTED_DIR) -> Path:
    return out_dir / ticker.upper() / f"{period_end}.json"


def quarter_dirs(ticker: str, raw_dir: Path = RAW_DIR) -> list[Path]:
    base = raw_dir / ticker.upper()
    if not base.exists():
        return []
    return sorted(
        (p for p in base.iterdir() if p.is_dir() and (p / "manifest.json").exists()),
        reverse=True,
    )


def needs_review(result: dict) -> list[str]:
    return [name for name, r in result["fields"].items() if r["status"] == "flagged"]


def reverify(result: dict, chain: Chain, quarter_dir: Path) -> dict:
    """Re-run the deterministic checks on saved answers (no LLM call).

    Lets checker fixes apply to earlier runs for free. Reviewed fields are left alone.
    """
    _, documents = load_documents(quarter_dir)
    by_name = {f.name: f for f in fields_for(chain.tier)}
    for name, r in result["fields"].items():
        if name not in by_name or r["status"] in {"approved_manual", "rejected", "derived"}:
            continue
        check = verify.check_field(by_name[name], r, documents, chain.segment_keywords, chain.quote_must_include.get(name))
        r["status"], r["reasons"] = check.status, check.reasons
    if chain.tier == "core":
        f = result["fields"]
        val = lambda n: f[n]["value"] if f[n]["status"] in {"verified", "approved_manual"} else None  # noqa: E731
        result["flags"] = (
            ["comp_not_equal_traffic_plus_ticket"]
            if verify.arithmetic_ok(val("comp_sales_pct"), val("comp_traffic_pct"), val("comp_ticket_pct")) is False
            else []
        )
    return result


# How far a value may sit from BOTH neighbouring quarters before it's flagged.
SERIES_LIMITS = {"ending_units": ("ratio", 0.15), "margin_pct": ("points", 4.0)}


def check_series(results: list[dict]) -> int:
    """Flag a count or margin that is far out of line with both adjacent quarters.

    Catches "right number, wrong row" (e.g. square footage or another segment)
    that a quote check can't see. Returns how many fields were newly flagged.
    """
    ordered = sorted((r for r in results if "fields" in r), key=lambda r: r["period_end"])
    flagged = 0
    for name, (mode, limit) in SERIES_LIMITS.items():
        vals = [r["fields"].get(name, {}) for r in ordered]
        good = [v.get("value") if v.get("status") in {"verified", "approved_manual"} else None for v in vals]
        for i in range(1, len(ordered) - 1):
            cur, prev, nxt = good[i], good[i - 1], good[i + 1]
            if None in (cur, prev, nxt) or vals[i].get("status") == "approved_manual":
                continue
            if mode == "ratio":
                off = lambda a, b: abs(a - b) / max(abs(b), 1e-9) > limit  # noqa: E731
            else:
                off = lambda a, b: abs(a - b) > limit  # noqa: E731
            if off(cur, prev) and off(cur, nxt):
                vals[i]["status"] = "flagged"
                vals[i].setdefault("reasons", []).append("out_of_line_with_adjacent_quarters")
                flagged += 1
    return flagged
