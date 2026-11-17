"""Find each chain's quarterly filings on EDGAR.

For every quarter we want two things:
  1. The periodic report (10-Q, or 10-K for the fiscal fourth quarter).
  2. The earnings-release 8-K (Item 2.02) and its Exhibit 99 press release(s).

The 10-Q/10-K defines the quarter (its "report date" is the period end).

Matching the earnings 8-K is trickier than it looks. Between a period end and
its 10-Q, a company can file several Item 2.02 8-Ks:
  - the real quarterly results release (what we want),
  - a "preliminary results" release (common for restaurants at the January
    ICR conference),
  - a monthly sales update.
So every Item 2.02 8-K in the window is kept as a *candidate*, its press release
is downloaded, and `pick_earnings_release` scores the text to choose one.
All candidates stay in the manifest so the choice can be audited.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from bs4 import BeautifulSoup

from turnout.sources.sec import (
    SUBMISSIONS_PAGE_URL,
    SUBMISSIONS_URL,
    Fetcher,
    archive_base,
    cik10,
    filing_index_url,
)

PERIODIC_FORMS = {"10-Q", "10-K"}
MAX_DAYS_AFTER_PERIOD = 75  # an earnings 8-K must be filed within this many days
DAYS_AFTER_PERIODIC = 7  # ...and no later than this many days after the 10-Q/10-K


@dataclass
class Filing:
    form: str
    accession: str
    filing_date: str
    report_date: str
    items: str
    primary_document: str

    def url(self, cik: str) -> str:
        return archive_base(cik, self.accession) + self.primary_document


@dataclass
class Exhibit:
    exhibit_type: str  # e.g. "EX-99.1"
    document: str  # file name inside the filing folder
    description: str = ""


@dataclass
class Candidate:
    filing: Filing
    exhibits: list[Exhibit] = field(default_factory=list)


@dataclass
class Quarter:
    period_end: str
    periodic: Filing
    candidates: list[Candidate] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- submissions

def _rows_from_block(block: dict) -> list[Filing]:
    """Turn SEC's column-style arrays into a list of Filing rows."""
    count = len(block.get("accessionNumber", []))
    blank = [""] * count
    return [
        Filing(
            form=block["form"][i],
            accession=block["accessionNumber"][i],
            filing_date=block["filingDate"][i],
            report_date=(block.get("reportDate") or blank)[i] or "",
            items=(block.get("items") or blank)[i] or "",
            primary_document=block["primaryDocument"][i],
        )
        for i in range(count)
    ]


def load_filings(cik: str, fetcher: Fetcher, min_periodic: int) -> list[Filing]:
    """All filings from the submissions feed, paging back only as far as needed."""
    data = fetcher.get_json(SUBMISSIONS_URL.format(cik10=cik10(cik)))
    rows = _rows_from_block(data["filings"]["recent"])
    for page in data["filings"].get("files", []):
        if sum(r.form in PERIODIC_FORMS for r in rows) >= min_periodic + 1:
            break
        older = fetcher.get_json(SUBMISSIONS_PAGE_URL.format(name=page["name"]))
        rows.extend(_rows_from_block(older))
    return rows


def is_earnings_8k(filing: Filing) -> bool:
    items = {item.strip() for item in filing.items.split(",")}
    return filing.form == "8-K" and "2.02" in items


def match_quarters(filings: list[Filing], n_quarters: int) -> list[Quarter]:
    """The latest N periodic reports, each with its candidate earnings 8-Ks. Newest first."""
    periodic = sorted(
        (f for f in filings if f.form in PERIODIC_FORMS and f.report_date),
        key=lambda f: (f.report_date, f.filing_date),
    )
    # One periodic report per period end: keep the first one filed.
    by_period: dict[str, Filing] = {}
    for f in periodic:
        by_period.setdefault(f.report_date, f)
    latest = sorted(by_period.values(), key=lambda f: f.report_date, reverse=True)[:n_quarters]

    earnings = sorted((f for f in filings if is_earnings_8k(f)), key=lambda f: f.filing_date)
    quarters = []
    for report in latest:
        period_end = date.fromisoformat(report.report_date)
        last_ok = min(
            period_end + timedelta(days=MAX_DAYS_AFTER_PERIOD),
            date.fromisoformat(report.filing_date) + timedelta(days=DAYS_AFTER_PERIODIC),
        )
        candidates = [
            Candidate(filing=f)
            for f in earnings
            if period_end < date.fromisoformat(f.filing_date) <= last_ok
        ]
        quarters.append(Quarter(period_end=report.report_date, periodic=report, candidates=candidates))
    return quarters


# ------------------------------------------------------------------- exhibits

def _clean_href(href: str) -> str:
    """Index links can be '/ix?doc=/Archives/...'. Return just the file name."""
    href = href.split("?doc=")[-1]
    return href.rstrip("/").split("/")[-1]


def parse_exhibits(index_html: str) -> list[Exhibit]:
    """Read a filing's -index.htm page and return its EX-99 exhibits, 99.1 first."""
    soup = BeautifulSoup(index_html, "html.parser")
    found = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        link = cells[2].find("a")
        exhibit_type = cells[3].get_text(strip=True).upper()
        if not link or not exhibit_type.startswith("EX-99"):
            continue
        found.append(
            Exhibit(
                exhibit_type=exhibit_type,
                document=_clean_href(link.get("href", "")),
                description=cells[1].get_text(" ", strip=True),
            )
        )

    def sort_key(ex: Exhibit) -> tuple[int, str]:
        return (0 if ex.exhibit_type in {"EX-99.1", "EX-99"} else 1, ex.exhibit_type)

    return sorted(found, key=sort_key)


def attach_exhibits(quarter: Quarter, cik: str, fetcher: Fetcher) -> None:
    for candidate in quarter.candidates:
        html = fetcher.get_text(filing_index_url(cik, candidate.filing.accession))
        candidate.exhibits = parse_exhibits(html)


# ------------------------------------------------------------- picking the 8-K

_QUARTER_RESULTS = re.compile(
    r"\b(first|second|third|fourth|1st|2nd|3rd|4th|q[1-4])\b[^.]{0,40}\bquarter\b"
    r"|\bquarter(ly)?\b[^.]{0,60}\b(results|earnings)\b"
    r"|\b(fiscal )?(year|quarter)[- ]end(ed)?\b",
    re.IGNORECASE,
)
_PRELIMINARY = re.compile(r"\bpreliminar(y|ily)\b", re.IGNORECASE)
# Monthly sales releases. ("thirteen weeks ended" is normal in quarterly releases, so not that.)
_MONTHLY = re.compile(r"\b(month of|monthly sales|(four|five) weeks ended)\b", re.IGNORECASE)
_COMPS_WORDS = re.compile(r"\b(comparable|same[- ](store|restaurant|shop|shack|club))\b", re.IGNORECASE)


def headline(text: str, limit: int = 160) -> str:
    """First meaningful line of a press release, for humans to eyeball."""
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 25 and not re.fullmatch(r"(exhibit\s*)?99[.\d]*", line, re.IGNORECASE):
            return line[:limit]
    return ""


def score_release(text: str) -> int:
    """Higher = more likely to be the real quarterly results release."""
    # The headline and first paragraphs decide it. Headlines often wrap across lines.
    head = re.sub(r"\s+", " ", text[:4000])
    score = 0
    if _QUARTER_RESULTS.search(head):
        score += 3
    if _COMPS_WORDS.search(text):
        score += 1
    if _PRELIMINARY.search(head):
        score -= 4
    if _MONTHLY.search(head):
        score -= 2
    return score


def pick_earnings_release(texts: dict[str, str], filing_dates: dict[str, str]) -> str | None:
    """Choose one accession from {accession: press-release text}.

    Highest score wins. Ties go to the latest filing (a final release
    supersedes an earlier preliminary one).
    """
    if not texts:
        return None
    return max(texts, key=lambda acc: (score_release(texts[acc]), filing_dates.get(acc, "")))


def discover(cik: str, fetcher: Fetcher, n_quarters: int = 8) -> list[Quarter]:
    filings = load_filings(cik, fetcher, min_periodic=n_quarters)
    quarters = match_quarters(filings, n_quarters)
    for quarter in quarters:
        attach_exhibits(quarter, cik, fetcher)
    return quarters
