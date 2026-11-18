from turnout.extract.bakeoff import compare, recommend, report_markdown


def q(ticker, value, status="verified", cost=0.01):
    return {
        "ticker": ticker, "period_end": "2026-09-29",
        "usage": {"cost_usd": cost, "prompt_tokens": 1000, "calls": 1},
        "fields": {"comp_sales_pct": {"value": value, "status": status}},
    }


def test_majority_marks_the_odd_model_as_false_pass():
    results = {
        "cheap/a": [q("TXRH", 4.3, cost=0.001)],
        "mid/b": [q("TXRH", 4.3, cost=0.01)],
        "mid/c": [q("TXRH", -0.9, cost=0.02)],  # picked the wrong line
    }
    comp = compare(results)
    assert comp["stats"]["mid/c"]["suspected_false_pass"] == 1
    assert comp["stats"]["cheap/a"]["suspected_false_pass"] == 0
    assert recommend(comp["stats"]) == "cheap/a"
    assert "Recommended:** `cheap/a`" in report_markdown(comp, 1)


def test_model_with_far_fewer_verified_is_not_recommended():
    results = {
        "cheap/a": [q("TXRH", 4.3, status="flagged", cost=0.001), q("WMT", 4.5, status="flagged", cost=0.001)],
        "mid/b": [q("TXRH", 4.3), q("WMT", 4.5)],
    }
    assert recommend(compare(results)["stats"]) == "mid/b"
