"""Save filings to disk so we never download the same document twice.

Layout:
    data/raw/{TICKER}/{period_end}/
        manifest.json         what was fetched, from where, which 8-K was chosen and why
        periodic.htm / .txt   the 10-Q or 10-K
        ex99_1.htm / .txt     the chosen earnings press release (ex99_2... if present)
        candidates/{acc}/     every Item 2.02 8-K considered for this quarter
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from turnout.config import RAW_DIR
from turnout.filings import Quarter, headline, pick_earnings_release, score_release
from turnout.sources.sec import Fetcher, archive_base
from turnout.text import html_to_text

MANIFEST = "manifest.json"
CONFIDENT_SCORE = 3  # below this, the quarter is flagged for a human look


def _exhibit_stem(exhibit_type: str, position: int) -> str:
    match = re.search(r"99\.(\d+)", exhibit_type)
    return f"ex99_{match.group(1) if match else position}"


def quarter_dir(ticker: str, period_end: str, root: Path = RAW_DIR) -> Path:
    return root / ticker.upper() / period_end


def is_cached(ticker: str, quarter: Quarter, root: Path = RAW_DIR) -> bool:
    """Cached = same 10-Q/10-K and same set of candidate 8-Ks already saved."""
    path = quarter_dir(ticker, quarter.period_end, root) / MANIFEST
    if not path.exists():
        return False
    saved = json.loads(path.read_text())
    saved_candidates = {c["accession"] for c in saved.get("candidates", [])}
    want_candidates = {c.filing.accession for c in quarter.candidates}
    return (
        saved.get("complete") is True
        and saved.get("periodic", {}).get("accession") == quarter.periodic.accession
        and saved_candidates == want_candidates
    )


def _save(folder: Path, stem: str, html: str) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}.htm").write_text(html, encoding="utf-8")
    text = html_to_text(html)
    (folder / f"{stem}.txt").write_text(text, encoding="utf-8")
    return {"html": f"{stem}.htm", "text": f"{stem}.txt", "text_chars": len(text), "_text": text}


def fetch_quarter(ticker: str, cik: str, quarter: Quarter, fetcher: Fetcher,
                  root: Path = RAW_DIR) -> dict:
    folder = quarter_dir(ticker, quarter.period_end, root)
    if folder.exists():
        shutil.rmtree(folder)  # start clean so stale files never linger
    folder.mkdir(parents=True)

    periodic_url = quarter.periodic.url(cik)
    periodic = _save(folder, "periodic", fetcher.get_text(periodic_url))
    periodic.pop("_text")

    # Download every candidate 8-K's EX-99 exhibits.
    candidate_rows = []
    texts: dict[str, str] = {}
    dates: dict[str, str] = {}
    for cand in quarter.candidates:
        acc = cand.filing.accession
        cand_dir = folder / "candidates" / acc.replace("-", "")
        base = archive_base(cik, acc)
        exhibits = []
        combined = []
        for position, ex in enumerate(cand.exhibits, start=1):
            url = base + ex.document
            saved = _save(cand_dir, _exhibit_stem(ex.exhibit_type, position), fetcher.get_text(url))
            combined.append(saved.pop("_text"))
            exhibits.append({"type": ex.exhibit_type, "url": url, "description": ex.description, **saved})
        texts[acc] = "\n\n".join(combined)
        dates[acc] = cand.filing.filing_date
        candidate_rows.append({
            "accession": acc,
            "filing_date": cand.filing.filing_date,
            "score": score_release(texts[acc]),
            "headline": headline(texts[acc]),
            "exhibits": exhibits,
            "folder": str(cand_dir.relative_to(folder)),
        })

    chosen = pick_earnings_release(texts, dates)
    chosen_row = next((c for c in candidate_rows if c["accession"] == chosen), None)
    for row in candidate_rows:
        row["chosen"] = row["accession"] == chosen

    # Copy the chosen release up to the quarter folder for easy reading.
    top_exhibits = []
    if chosen_row:
        for ex in chosen_row["exhibits"]:
            for key in ("html", "text"):
                shutil.copy(folder / chosen_row["folder"] / ex[key], folder / ex[key])
            top_exhibits.append({k: v for k, v in ex.items()})

    flags = []
    if not quarter.candidates:
        flags.append("no_earnings_8k_found")
    elif chosen_row and not chosen_row["exhibits"]:
        flags.append("earnings_8k_has_no_ex99")
    elif chosen_row and chosen_row["score"] < CONFIDENT_SCORE:
        flags.append("low_confidence_8k_choice")
    if len(quarter.candidates) > 1:
        flags.append("multiple_8k_candidates")

    manifest = {
        "ticker": ticker.upper(),
        "cik": cik,
        "period_end": quarter.period_end,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "periodic": {
            "form": quarter.periodic.form,
            "accession": quarter.periodic.accession,
            "filing_date": quarter.periodic.filing_date,
            "url": periodic_url,
            **periodic,
        },
        "earnings_8k": (
            {"accession": chosen_row["accession"], "filing_date": chosen_row["filing_date"],
             "score": chosen_row["score"], "headline": chosen_row["headline"]}
            if chosen_row else None
        ),
        "exhibits": top_exhibits,
        "candidates": candidate_rows,
        "flags": flags,
        "complete": True,
    }
    (folder / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
