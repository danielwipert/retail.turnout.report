import json

from turnout import cache
from turnout.filings import Candidate, Exhibit, Filing, Quarter
from turnout.text import html_to_text

from conftest import FakeFetcher

BASE = "https://www.sec.gov/Archives/edgar/data/1/"


def test_html_to_text_keeps_sentences_and_table_rows():
    html = """<html><head><style>p{}</style></head><body>
    <p>Comparable sales increased&nbsp;4.3%, driven by a 3.6% increase in average check.</p>
    <div style="display:none">hidden xbrl junk</div>
    <table><tr><td>Company</td><td>(0.9 %)</td></tr><tr><td>System</td><td>(1.1 %)</td></tr></table>
    </body></html>"""
    text = html_to_text(html)
    assert "Comparable sales increased 4.3%, driven by a 3.6% increase in average check." in text
    assert "Company | (0.9 %)" in text
    assert "System | (1.1 %)" in text
    assert "hidden xbrl junk" not in text


def _quarter():
    periodic = Filing("10-Q", "0000000001-26-000010", "2026-11-05", "2026-09-29", "", "q3.htm")
    prelim = Filing("8-K", "0000000001-26-000008", "2026-10-10", "", "2.02", "p.htm")
    final = Filing("8-K", "0000000001-26-000009", "2026-11-05", "", "2.02", "f.htm")
    return Quarter(
        period_end="2026-09-29",
        periodic=periodic,
        candidates=[
            Candidate(prelim, [Exhibit("EX-99.1", "prelim991.htm", "Preliminary sales")]),
            Candidate(final, [Exhibit("EX-99.1", "ex991.htm", "Press release"),
                              Exhibit("EX-99.2", "ex992.htm", "Supplement")]),
        ],
    )


def _pages():
    return {
        BASE + "000000000126000010/q3.htm": "<p>Quarterly report. Comparable transactions declined 2.9%.</p>",
        BASE + "000000000126000008/prelim991.htm": "<p>Company announces preliminary third quarter sales.</p>",
        BASE + "000000000126000009/ex991.htm": "<p>Company Reports Third Quarter 2026 Results. Comparable store sales decreased 1.4%.</p>",
        BASE + "000000000126000009/ex992.htm": "<p>Supplemental tables.</p>",
    }


def test_fetch_quarter_saves_files_and_picks_the_real_release(tmp_path):
    quarter = _quarter()
    manifest = cache.fetch_quarter("TEST", "0000000001", quarter, FakeFetcher(_pages()), root=tmp_path)

    folder = tmp_path / "TEST" / "2026-09-29"
    assert (folder / "periodic.txt").read_text().startswith("Quarterly report.")
    assert "Third Quarter 2026 Results" in (folder / "ex99_1.txt").read_text()
    assert (folder / "ex99_2.txt").exists()
    assert manifest["earnings_8k"]["accession"] == "0000000001-26-000009"
    assert "multiple_8k_candidates" in manifest["flags"]
    assert "low_confidence_8k_choice" not in manifest["flags"]

    saved = json.loads((folder / "manifest.json").read_text())
    assert saved["complete"] is True
    assert [c["chosen"] for c in saved["candidates"]] == [False, True]


def test_is_cached_skips_unchanged_quarters(tmp_path):
    quarter = _quarter()
    assert not cache.is_cached("TEST", quarter, root=tmp_path)
    cache.fetch_quarter("TEST", "0000000001", quarter, FakeFetcher(_pages()), root=tmp_path)
    assert cache.is_cached("TEST", quarter, root=tmp_path)

    # A new 8-K candidate appearing means the quarter must be refetched.
    quarter.candidates.append(Candidate(Filing("8-K", "new", "2026-11-06", "", "2.02", "n.htm")))
    assert not cache.is_cached("TEST", quarter, root=tmp_path)


def test_quarter_with_no_8k_is_flagged(tmp_path):
    quarter = _quarter()
    quarter.candidates = []
    manifest = cache.fetch_quarter("TEST", "0000000001", quarter, FakeFetcher(_pages()), root=tmp_path)
    assert manifest["earnings_8k"] is None
    assert manifest["flags"] == ["no_earnings_8k_found"]
