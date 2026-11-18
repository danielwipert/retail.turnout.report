"""Review loop on GitHub Issues (decision P2-4).

`open`  : one issue per flagged field that doesn't have one yet.
`apply` : reads a reply on a review issue (/approve, /value X, /reject),
          updates the result file, and closes the issue.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import httpx

from turnout.config import RAW_DIR, ConfigError
from turnout.extract.run import EXTRACTED_DIR, load_documents
from turnout.extract.verify import normalize, quote_in_text
from turnout.extract.snippets import snippets

LABEL = "review"
MARKER = re.compile(r"<!-- turnout-review (\{.*?\}) -->")
COMMAND = re.compile(r"^\s*/(approve|reject|value)\b\s*([-+]?\(?\d+(?:\.\d+)?\)?|up|down|flat)?", re.I | re.M)


class IssueTracker(Protocol):
    def create_issue(self, title: str, body: str, labels: list[str]) -> int: ...

    def comment(self, number: int, body: str) -> None: ...

    def close(self, number: int) -> None: ...

    def open_review_issues(self) -> list[dict]: ...


class GitHubIssues:
    def __init__(self, repo: str | None = None, token: str | None = None):
        self.repo = repo or os.environ.get("GITHUB_REPOSITORY", "")
        token = token or os.environ.get("GITHUB_TOKEN", "")
        if not self.repo or not token:
            raise ConfigError("GITHUB_REPOSITORY and GITHUB_TOKEN are needed (they're automatic in Actions).")
        self.client = httpx.Client(
            base_url=f"https://api.github.com/repos/{self.repo}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=30,
        )

    def create_issue(self, title, body, labels):
        r = self.client.post("/issues", json={"title": title, "body": body, "labels": labels})
        r.raise_for_status()
        return r.json()["number"]

    def comment(self, number, body):
        self.client.post(f"/issues/{number}/comments", json={"body": body}).raise_for_status()

    def close(self, number):
        self.client.patch(f"/issues/{number}", json={"state": "closed"}).raise_for_status()

    def open_review_issues(self):
        out, page = [], 1
        while True:
            r = self.client.get("/issues", params={"labels": LABEL, "state": "open", "per_page": 100, "page": page})
            r.raise_for_status()
            batch = r.json()
            out += [i for i in batch if "pull_request" not in i]
            if len(batch) < 100:
                return out
            page += 1


def _context(field: dict, documents: dict[str, str]) -> str:
    """The filing text a reviewer needs to see: around the quote if found, else the snippets."""
    quote = field.get("quote") or ""
    for name, text in documents.items():
        if quote and quote_in_text(quote, text) >= 0:
            flat = re.sub(r"\s+", " ", text)
            idx = normalize(flat).find(normalize(quote).split("...")[0].strip())
            if idx >= 0:
                return f"({name}) …{flat[max(0, idx - 500): idx + len(quote) + 500]}…"
    return snippets(documents.get("press_release", ""), max_chars=2500) or "(no matching text found)"


def issue_body(result: dict, field_name: str, documents: dict[str, str]) -> str:
    f = result["fields"][field_name]
    marker = json.dumps({"ticker": result["ticker"], "period_end": result["period_end"], "field": field_name})
    links = "\n".join(f"- [Press release]({u})" for u in result.get("press_release_urls", []))
    return f"""**{result['ticker']} · quarter ending {result['period_end']} · `{field_name}`**

| | |
|---|---|
| Value the model gave | `{f.get('value')}` |
| Why it was flagged | {', '.join(f.get('reasons', [])) or '—'} |
| Model | `{result.get('model')}` |

**Quote the model gave**
> {f.get('quote') or '(none)'}

**Filing text nearby**
```
{_context(f, documents)[:3000]}
```

**Sources**
{links}
- [10-Q / 10-K]({result.get('periodic_url')})

---
**Reply with one line:**
- `/approve`: the value is right
- `/value -2.9`: the right value is -2.9 (for directions: `/value down`)
- `/reject`: there's no such number in the filing; leave it blank

<!-- turnout-review {marker} -->
"""


def close_stale(tracker: IssueTracker, extracted_dir: Path = EXTRACTED_DIR) -> int:
    """Close open review issues whose field is no longer flagged (e.g. after a re-extraction)."""
    closed = 0
    for issue in tracker.open_review_issues():
        m = MARKER.search(issue.get("body") or "")
        if not m:
            continue
        key = json.loads(m.group(1))
        path = extracted_dir / key["ticker"] / f"{key['period_end']}.json"
        if not path.exists():
            continue
        f = json.loads(path.read_text())["fields"].get(key["field"], {})
        if f.get("status") != "flagged" or f.get("review_issue") not in (None, issue["number"]):
            tracker.comment(issue["number"], f"Re-extracted; this field is now **{f.get('status')}** "
                                             f"(value `{f.get('value')}`). Closing.")
            tracker.close(issue["number"])
            closed += 1
    return closed


def open_issues(tracker: IssueTracker, extracted_dir: Path = EXTRACTED_DIR, raw_dir: Path = RAW_DIR) -> int:
    opened = 0
    for path in sorted(extracted_dir.glob("*/*.json")):
        result = json.loads(path.read_text())
        changed = False
        for name, f in result["fields"].items():
            if f["status"] != "flagged" or f.get("review_issue"):
                continue
            qdir = raw_dir / result["ticker"] / result["period_end"]
            documents = load_documents(qdir)[1] if (qdir / "manifest.json").exists() else {}
            title = f"Review: {result['ticker']} {result['period_end']} {name}"
            f["review_issue"] = tracker.create_issue(title, issue_body(result, name, documents), [LABEL])
            changed = True
            opened += 1
        if changed:
            path.write_text(json.dumps(result, indent=2) + "\n")
    return opened


def parse_command(comment: str) -> tuple[str, object] | None:
    m = COMMAND.search(comment)
    if not m:
        return None
    action, arg = m.group(1).lower(), m.group(2)
    if action == "value":
        if arg is None:
            return None
        arg = arg.lower()
        if arg in ("up", "down", "flat"):
            return ("value", arg)
        negative = arg.startswith("(") and arg.endswith(")")
        number = float(arg.strip("()"))
        return ("value", -number if negative else number)
    return (action, None)


def apply_comment(issue_body_text: str, comment: str, comment_url: str, reviewer: str,
                  extracted_dir: Path = EXTRACTED_DIR) -> str | None:
    """Apply a reviewer command. Returns a confirmation message, or None if nothing to do."""
    marker = MARKER.search(issue_body_text or "")
    command = parse_command(comment or "")
    if not marker or not command:
        return None
    key = json.loads(marker.group(1))
    path = extracted_dir / key["ticker"] / f"{key['period_end']}.json"
    result = json.loads(path.read_text())
    f = result["fields"][key["field"]]
    action, value = command

    review = {"by": reviewer, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "comment": comment_url, "action": action, "model_value": f.get("value")}
    if action == "approve":
        f["status"] = "approved_manual"
    elif action == "value":
        f["value"] = value
        f["status"] = "approved_manual"
    else:
        f["value"] = None
        f["status"] = "rejected"
    f["review"] = review
    path.write_text(json.dumps(result, indent=2) + "\n")
    return f"Saved: `{key['field']}` for {key['ticker']} {key['period_end']} → **{f['status']}** (value `{f['value']}`)."
