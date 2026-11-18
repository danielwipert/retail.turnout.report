import json

from turnout import review


class FakeTracker:
    def __init__(self):
        self.issues = {}

    def create_issue(self, title, body, labels):
        n = len(self.issues) + 1
        self.issues[n] = {"title": title, "body": body, "labels": labels}
        return n

    def comment(self, number, body):
        pass

    def close(self, number):
        self.issues[number]["closed"] = True

    def open_review_issues(self):
        return [{"number": n, **i} for n, i in self.issues.items() if not i.get("closed")]


def _result(tmp_path):
    d = tmp_path / "extracted" / "TXRH"
    d.mkdir(parents=True)
    result = {
        "ticker": "TXRH", "period_end": "2026-09-29", "model": "m", "periodic_url": "u",
        "press_release_urls": ["p"],
        "fields": {
            "comp_sales_pct": {"value": 4.3, "quote": "x", "status": "verified", "reasons": []},
            "comp_traffic_pct": {"value": 1.7, "quote": "traffic grew 0.7%", "status": "flagged",
                                 "reasons": ["number_not_in_quote"]},
        },
    }
    (d / "2026-09-29.json").write_text(json.dumps(result))
    return tmp_path / "extracted"


def test_opens_one_issue_per_flagged_field_once(tmp_path):
    ex = _result(tmp_path)
    tracker = FakeTracker()
    assert review.open_issues(tracker, ex, tmp_path / "raw") == 1
    assert review.open_issues(tracker, ex, tmp_path / "raw") == 0  # not reopened
    body = tracker.issues[1]["body"]
    assert "comp_traffic_pct" in body and "turnout-review" in body


def test_parse_commands():
    assert review.parse_command("/approve") == ("approve", None)
    assert review.parse_command("Looks wrong.\n/value -0.7") == ("value", -0.7)
    assert review.parse_command("/value (2.9)") == ("value", -2.9)
    assert review.parse_command("/value down") == ("value", "down")
    assert review.parse_command("/reject") == ("reject", None)
    assert review.parse_command("thanks!") is None


def test_apply_value_updates_the_file(tmp_path):
    ex = _result(tmp_path)
    tracker = FakeTracker()
    review.open_issues(tracker, ex, tmp_path / "raw")
    msg = review.apply_comment(tracker.issues[1]["body"], "/value 0.7", "https://c", "danielwipert", ex)
    assert "approved_manual" in msg
    saved = json.loads((ex / "TXRH" / "2026-09-29.json").read_text())
    f = saved["fields"]["comp_traffic_pct"]
    assert f["value"] == 0.7 and f["status"] == "approved_manual"
    assert f["review"]["model_value"] == 1.7 and f["review"]["by"] == "danielwipert"


def test_stale_issue_is_closed_after_reextraction(tmp_path):
    ex = _result(tmp_path)
    tracker = FakeTracker()
    review.open_issues(tracker, ex, tmp_path / "raw")
    path = ex / "TXRH" / "2026-09-29.json"
    r = json.loads(path.read_text())
    r["fields"]["comp_traffic_pct"] = {"value": 0.7, "quote": "q", "status": "verified", "reasons": []}
    path.write_text(json.dumps(r))
    assert review.close_stale(tracker, ex) == 1
    assert tracker.issues[1]["closed"]
