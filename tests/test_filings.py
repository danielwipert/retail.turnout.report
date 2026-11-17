from turnout import filings
from turnout.filings import Filing, match_quarters, parse_exhibits, pick_earnings_release, score_release

from conftest import FakeFetcher, index_html, submissions_block


def f(form, acc, filed, report="", items="", doc="doc.htm"):
    return Filing(form=form, accession=acc, filing_date=filed, report_date=report, items=items, primary_document=doc)


def test_matches_each_10q_to_its_earnings_8k():
    rows = [
        f("10-Q", "q3", "2026-11-05", "2026-09-29"),
        f("8-K", "e3", "2026-11-05", items="2.02,9.01"),
        f("10-Q", "q2", "2026-08-06", "2026-06-30"),
        f("8-K", "e2", "2026-08-05", items="2.02,9.01"),
        f("8-K", "other", "2026-08-20", items="5.02"),  # not an earnings 8-K
    ]
    quarters = match_quarters(rows, n_quarters=8)
    assert [q.period_end for q in quarters] == ["2026-09-29", "2026-06-30"]
    assert [c.filing.accession for c in quarters[0].candidates] == ["e3"]
    assert [c.filing.accession for c in quarters[1].candidates] == ["e2"]


def test_keeps_preliminary_and_final_8k_as_candidates():
    # Restaurants often pre-announce at the January ICR conference.
    rows = [
        f("10-K", "k", "2026-02-25", "2025-12-28"),
        f("8-K", "prelim", "2026-01-12", items="2.02,7.01"),
        f("8-K", "final", "2026-02-24", items="2.02,9.01"),
    ]
    (quarter,) = match_quarters(rows, n_quarters=1)
    assert [c.filing.accession for c in quarter.candidates] == ["prelim", "final"]


def test_8k_filed_long_after_the_10q_is_not_a_candidate():
    rows = [
        f("10-Q", "q", "2026-08-06", "2026-06-30"),
        f("8-K", "later", "2026-08-30", items="2.02"),  # > 7 days after the 10-Q
    ]
    (quarter,) = match_quarters(rows, n_quarters=1)
    assert quarter.candidates == []


def test_limits_to_n_quarters_and_ignores_duplicate_periods():
    rows = [f("10-Q", f"q{i}", f"2026-0{i}-15", f"2026-0{i}-01") for i in range(1, 6)]
    rows.append(f("10-Q", "q5-amended-dup", "2026-05-30", "2026-05-01"))
    quarters = match_quarters(rows, n_quarters=3)
    assert [q.periodic.accession for q in quarters] == ["q5", "q4", "q3"]


def test_parse_exhibits_returns_ex99_only_with_99_1_first():
    html = index_html([
        ("EX-99.2", "deck.htm", "Investor presentation"),
        ("EX-99.1", "a2026-q3_ex991.htm", "Press release"),
        ("EX-104", "cover.htm", "Cover page"),
    ])
    exhibits = parse_exhibits(html)
    assert [(e.exhibit_type, e.document) for e in exhibits] == [
        ("EX-99.1", "a2026-q3_ex991.htm"),
        ("EX-99.2", "deck.htm"),
    ]


def test_scoring_prefers_real_results_over_preliminary_and_monthly():
    final = "Texas Roadhouse, Inc. Announces Third Quarter 2026 Results. Comparable restaurant sales increased 4.3%."
    prelim = "Company Announces Preliminary Fourth Quarter Sales. Comparable sales increased 2%."
    monthly = "Costco reports sales results for the month of October. Comparable sales were up 6%."
    assert score_release(final) > score_release(prelim)
    assert score_release(final) > score_release(monthly)
    chosen = pick_earnings_release(
        {"p": prelim, "f": final}, {"p": "2026-01-12", "f": "2026-02-24"}
    )
    assert chosen == "f"


def test_tie_goes_to_latest_filing():
    text = "Announces Fourth Quarter Results."
    assert pick_earnings_release({"a": text, "b": text}, {"a": "2026-01-10", "b": "2026-02-20"}) == "b"


def test_discover_pages_back_through_older_submission_files():
    cik = "0000000001"
    recent = submissions_block([
        {"accessionNumber": "q2", "filingDate": "2026-08-06", "reportDate": "2026-06-30", "form": "10-Q", "primaryDocument": "q2.htm"},
        {"accessionNumber": "e2", "filingDate": "2026-08-05", "form": "8-K", "items": "2.02", "primaryDocument": "e2.htm"},
    ])
    older = submissions_block([
        {"accessionNumber": "q1", "filingDate": "2026-05-06", "reportDate": "2026-03-31", "form": "10-Q", "primaryDocument": "q1.htm"},
        {"accessionNumber": "e1", "filingDate": "2026-05-05", "form": "8-K", "items": "2.02", "primaryDocument": "e1.htm"},
    ])
    pages = {
        f"https://data.sec.gov/submissions/CIK{cik}.json": {
            "filings": {"recent": recent, "files": [{"name": "CIK0000000001-submissions-001.json"}]}
        },
        "https://data.sec.gov/submissions/CIK0000000001-submissions-001.json": older,
        "https://www.sec.gov/Archives/edgar/data/1/e2/e2-index.htm": index_html([("EX-99.1", "pr2.htm", "")]),
        "https://www.sec.gov/Archives/edgar/data/1/e1/e1-index.htm": index_html([("EX-99.1", "pr1.htm", "")]),
    }
    quarters = filings.discover(cik, FakeFetcher(pages), n_quarters=2)
    assert [q.period_end for q in quarters] == ["2026-06-30", "2026-03-31"]
    assert quarters[1].candidates[0].exhibits[0].document == "pr1.htm"
