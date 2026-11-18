"""Model bake-off (decision P2-2): run several models on the same quarters and compare.

We don't have an answer key, so "false pass" is estimated by agreement: when at
least two models verify the same field and agree, a model that verified a
*different* value has a suspected false pass.
"""

from __future__ import annotations

from collections import Counter, defaultdict

PASS_STATUSES = {"verified"}


def compare(results: dict[str, list[dict]]) -> dict:
    """results = {model: [quarter result, ...]} → per-model stats and disagreements."""
    stats = {}
    verified_values: dict[tuple, dict[str, object]] = defaultdict(dict)
    for model, quarters in results.items():
        s = {"verified": 0, "flagged": 0, "missing": 0, "derived": 0, "fields": 0,
             "cost_usd": 0.0, "prompt_tokens": 0, "calls": 0, "errors": 0, "suspected_false_pass": 0}
        for q in quarters:
            if "error" in q:
                s["errors"] += 1
                continue
            s["cost_usd"] += q["usage"]["cost_usd"]
            s["prompt_tokens"] += q["usage"]["prompt_tokens"]
            s["calls"] += q["usage"]["calls"]
            for name, r in q["fields"].items():
                s["fields"] += 1
                s[r["status"]] = s.get(r["status"], 0) + 1
                if r["status"] in PASS_STATUSES:
                    verified_values[(q["ticker"], q["period_end"], name)][model] = round(float(r["value"]), 2) \
                        if not isinstance(r["value"], str) else r["value"]
        stats[model] = s

    disagreements = []
    for key, by_model in verified_values.items():
        counts = Counter(by_model.values())
        if len(counts) < 2:
            continue
        top_value, top_n = counts.most_common(1)[0]
        majority = top_value if top_n >= 2 else None
        disagreements.append({"key": key, "values": by_model, "majority": majority})
        if majority is not None:
            for model, v in by_model.items():
                if v != majority:
                    stats[model]["suspected_false_pass"] += 1
    return {"stats": stats, "disagreements": disagreements}


def recommend(stats: dict) -> str | None:
    """Cheapest model with zero suspected false passes, no errors, and ≥90% of the best verified count."""
    if not stats:
        return None
    best = max(s["verified"] for s in stats.values())
    ok = [m for m, s in stats.items()
          if s["suspected_false_pass"] == 0 and s["errors"] == 0 and s["verified"] >= 0.9 * best]
    if not ok:
        return None
    return min(ok, key=lambda m: stats[m]["cost_usd"])


def report_markdown(comparison: dict, quarters_per_model: int) -> str:
    stats = comparison["stats"]
    lines = [
        "## Model bake-off",
        "",
        f"Quarters per model: {quarters_per_model}",
        "",
        "| Model | Verified | Flagged | Missing | Derived | Suspected false passes | Errors | Cost (USD) | Input tokens |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for model, s in sorted(stats.items(), key=lambda kv: kv[1]["cost_usd"]):
        lines.append(
            f"| `{model}` | {s['verified']} | {s['flagged']} | {s['missing']} | {s['derived']} | "
            f"{s['suspected_false_pass']} | {s['errors']} | ${s['cost_usd']:.4f} | {s['prompt_tokens']:,} |"
        )
    pick = recommend(stats)
    lines += ["", f"**Recommended:** `{pick}`" if pick else "**Recommended:** none passed. Look at the disagreements below.", ""]
    if comparison["disagreements"]:
        lines += ["### Disagreements (verified values that differ between models)", "",
                  "| Chain | Quarter | Field | Values | Majority |", "|---|---|---|---|---|"]
        for d in sorted(comparison["disagreements"], key=lambda d: d["key"]):
            t, p, f = d["key"]
            vals = ", ".join(f"{m.split('/')[-1]}={v}" for m, v in d["values"].items())
            lines.append(f"| {t} | {p} | {f} | {vals} | {d['majority']} |")
    return "\n".join(lines) + "\n"
