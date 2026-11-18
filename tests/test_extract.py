import json

from turnout.extract import verify
from turnout.extract.fields import CORE_FIELDS, WATCH_FIELDS, json_schema
from turnout.extract.llm import Answer, Usage
from turnout.extract.run import extract_quarter
from turnout.extract.snippets import snippets
from turnout.universe import Chain

F = {f.name: f for f in CORE_FIELDS}
W = {f.name: f for f in WATCH_FIELDS}

PRESS = (
    "Texas Roadhouse, Inc. Announces Third Quarter 2026 Results\n"
    "Comparable restaurant sales increased 4.3% at company restaurants.\n"
    "Average check increased 3.6% and traffic grew 0.7%.\n"
    "Restaurant margin, as a percentage of restaurant sales, increased 30 basis points to 14.6%.\n"
    "The company ended the quarter with 812 restaurants.\n"
)
DOCS = {"press_release": PRESS, "periodic": "Comparable restaurant sales | 4.3 % | (0.9)%\n"}


def ans(value, quote, source="press_release"):
    return {"value": value, "quote": quote, "source": source}


def test_verified_when_quote_and_number_match():
    c = verify.check_field(F["comp_sales_pct"], ans(4.3, "Comparable restaurant sales increased 4.3% at company restaurants."), DOCS, [])
    assert c.status == "verified", c.reasons


def test_quote_not_in_filing_is_flagged():
    c = verify.check_field(F["comp_sales_pct"], ans(4.3, "Comparable sales rose 4.3% this quarter."), DOCS, [])
    assert "quote_not_in_filing" in c.reasons


def test_wrong_number_is_flagged():
    c = verify.check_field(F["comp_traffic_pct"], ans(1.7, "Average check increased 3.6% and traffic grew 0.7%."), DOCS, [])
    assert "number_not_in_quote" in c.reasons


def test_sign_mismatch_and_parentheses():
    docs = {"press_release": "Comparable transactions decreased 2.9%.", "periodic": ""}
    bad = verify.check_field(F["comp_traffic_pct"], ans(2.9, "Comparable transactions decreased 2.9%."), docs, [])
    good = verify.check_field(F["comp_traffic_pct"], ans(-2.9, "Comparable transactions decreased 2.9%."), docs, [])
    assert "sign_mismatch" in bad.reasons and good.status == "verified"
    table = verify.check_field(F["comp_sales_pct"], ans(-0.9, "Comparable restaurant sales | 4.3 % | (0.9)%", "periodic"), DOCS, [])
    assert table.status == "verified", table.reasons


def test_basis_points_and_counts():
    m = verify.check_field(F["margin_pct"], ans(14.6, "Restaurant margin, as a percentage of restaurant sales, increased 30 basis points to 14.6%."), DOCS, [])
    u = verify.check_field(F["ending_units"], ans(812, "The company ended the quarter with 812 restaurants."), DOCS, [])
    assert m.status == "verified" and u.status == "verified"


def test_segment_keyword_required_nearby():
    docs = {"press_release": "International comparable sales increased 6.0%.", "periodic": ""}
    c = verify.check_field(F["comp_sales_pct"], ans(6.0, "International comparable sales increased 6.0%."), docs, ["Walmart U.S."])
    assert "segment_unconfirmed" in c.reasons


def test_direction_fields():
    docs = {"press_release": "Sales reflected a decline in transactions, partially offset by an increase in price.", "periodic": ""}
    q = "Sales reflected a decline in transactions, partially offset by an increase in price."
    assert verify.check_field(W["traffic_direction"], ans("down", q), docs, []).status == "verified"
    assert verify.check_field(W["traffic_direction"], ans("sideways", q), docs, []).status == "flagged"


def test_snippets_keep_relevant_lines_only():
    text = "\n".join(["Boilerplate about forward-looking statements."] * 50 + ["Comparable sales increased 2.0%."] + ["Legal text."] * 50)
    out = snippets(text, context=1)
    assert "Comparable sales increased 2.0%." in out
    assert out.count("Boilerplate") <= 1


def test_schema_is_strict():
    schema = json_schema(CORE_FIELDS)
    assert set(schema["required"]) == {f.name for f in CORE_FIELDS}
    assert schema["additionalProperties"] is False


class FakeExtractor:
    model = "fake/model"

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def extract(self, prompt, schema):
        self.prompts.append(prompt)
        return Answer(self.answers.pop(0), Usage(100, 10, 0.001, 1))


def _quarter_dir(tmp_path):
    q = tmp_path / "TXRH" / "2026-09-29"
    q.mkdir(parents=True)
    (q / "ex99_1.txt").write_text(PRESS)
    (q / "periodic.txt").write_text("Quarterly report. Comparable restaurant sales increased 4.3%.")
    (q / "manifest.json").write_text(json.dumps({
        "period_end": "2026-09-29",
        "periodic": {"accession": "p", "url": "https://sec/p"},
        "earnings_8k": {"accession": "e"},
        "exhibits": [{"text": "ex99_1.txt", "url": "https://sec/e"}],
    }))
    return q


def test_extract_quarter_end_to_end_with_retry(tmp_path):
    chain = Chain(ticker="TXRH", name="Texas Roadhouse", tier="core", group="full_service",
                  segment="Company restaurants", segment_keywords=["company restaurants"])
    first = {
        "comp_sales_pct": ans(4.3, "Comparable restaurant sales increased 4.3% at company restaurants."),
        "comp_traffic_pct": ans(0.7, "Average check increased 3.6% and traffic grew 0.7%."),
        "comp_ticket_pct": ans(3.6, "Average check increased 3.6% and traffic grew 0.7%."),
        "ending_units": ans(None, None, None),  # missing → triggers full-text retry
        "margin_pct": ans(14.9, "Restaurant margin, as a percentage of restaurant sales, increased 30 basis points to 14.6%."),
    }
    retry = {"ending_units": ans(812, "The company ended the quarter with 812 restaurants.")}
    ex = FakeExtractor([first, retry])
    result = extract_quarter(chain, _quarter_dir(tmp_path), ex)

    f = result["fields"]
    assert f["comp_sales_pct"]["status"] == "verified"
    assert f["ending_units"]["status"] == "verified" and f["ending_units"]["pass"] == "full_text"
    assert f["margin_pct"]["status"] == "flagged"  # 14.9 isn't in the quote
    assert result["usage"]["calls"] == 2
    assert result["flags"] == []


def test_table_row_quotes_with_odd_cell_separators_match():
    docs = {"press_release": "", "periodic": "Company restaurants\nGuest traffic counts | 4.5 | % | 1.1 | %\n"}
    quote = "Guest traffic counts | \t | 4.5 | % | \t | 1.1 | %"
    c = verify.check_field(F["comp_traffic_pct"], ans(4.5, quote, "periodic"), docs, ["company restaurants"])
    assert c.status == "verified", c.reasons


def test_token_match_handles_blank_cells_and_zero_width_but_rejects_paraphrase():
    text = "Guest traffic counts | 4.5 | % | | 1.1 | %\nComparable restaurant sales | 7.1 | % | \u200b | 3.5 | %"
    docs = {"press_release": "", "periodic": text}
    q1 = "Comparable restaurant sales | 7.1 | % | \u200b | 3.5 | %"
    assert verify.quote_in_text(q1, text) >= 0
    q2 = "Guest traffic counts | | | 4.5 | % | | | 1.1 | %"
    assert verify.quote_in_text(q2, text) >= 0
    q3 = "Guest traffic counts increased 4.5%"  # 'increased' is not in the filing
    assert verify.quote_in_text(q3, text) == -1


def test_field_notes_go_into_the_prompt():
    from turnout.extract.llm import build_prompt
    p = build_prompt("Walmart", "Walmart U.S.", "2026-07-31", CORE_FIELDS, {"press_release": "x"},
                     {"ending_units": "Walmart U.S. store count only."})
    assert "FOR THIS COMPANY: Walmart U.S. store count only." in p


def test_square_footage_is_not_a_store_count():
    docs = {"press_release": "", "periodic": "Unit counts at period end | 4,606\nRetail square feet at period end | 698\n"}
    bad = verify.check_field(F["ending_units"], ans(698, "Retail square feet at period end | 698", "periodic"), docs, [])
    good = verify.check_field(F["ending_units"], ans(4606, "Unit counts at period end | 4,606", "periodic"), docs, [])
    assert "count_is_square_footage" in bad.reasons and good.status == "verified", good.reasons


def test_required_words():
    docs = {"press_release": "Total restaurants | 840\nTotal company restaurants | 737\n", "periodic": ""}
    bad = verify.check_field(F["ending_units"], ans(840, "Total restaurants | 840"), docs, [], ["company"])
    good = verify.check_field(F["ending_units"], ans(737, "Total company restaurants | 737"), docs, [], ["company"])
    assert "required_words_missing" in bad.reasons and good.status == "verified"


def test_series_check_flags_value_out_of_line_with_both_neighbours():
    from turnout.extract.run import check_series
    def r(p, units, margin):
        return {"period_end": p, "fields": {"ending_units": {"value": units, "status": "verified"},
                                            "margin_pct": {"value": margin, "status": "verified"}}}
    rs = [r("2026-01", 4611, 24.0), r("2026-04", 698, 24.3), r("2026-07", 4614, 29.0), r("2026-10", 4620, 24.4)]
    assert check_series(rs) == 2
    assert rs[1]["fields"]["ending_units"]["status"] == "flagged"
    assert rs[2]["fields"]["margin_pct"]["status"] == "flagged"
    assert rs[2]["fields"]["ending_units"]["status"] == "verified"
