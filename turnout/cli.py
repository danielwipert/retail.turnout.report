"""Command line: `python -m turnout <command>`.

Commands
  resolve-ciks   Look up each chain's SEC CIK number and save it to data/universe.json
  fetch          Download and cache filings (default: the 3 Phase 1 test chains)
  status         Show what's cached and any quarters that need a human look
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from turnout import cache, filings
from turnout.config import DATA_DIR, RAW_DIR, ConfigError, sec_user_agent
from turnout.sources.sec import SecHttpFetcher
from turnout.universe import load_universe, resolve_ciks, save_universe, select

PHASE1_TEST_CHAINS = ["TXRH", "WMT", "FND"]


def _fetcher() -> SecHttpFetcher:
    return SecHttpFetcher(sec_user_agent())


def cmd_resolve_ciks(args: argparse.Namespace) -> int:
    chains = load_universe()
    missing = resolve_ciks(chains, _fetcher())
    save_universe(chains)
    print(f"CIKs saved for {len(chains) - len(missing)} of {len(chains)} chains.")
    if missing:
        print("Not found in SEC ticker list (check the ticker):", ", ".join(missing))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    chains = load_universe()
    fetcher = _fetcher()
    if any(c.cik is None for c in chains):
        resolve_ciks(chains, fetcher)
        save_universe(chains)

    tickers = None if args.all else (args.tickers or PHASE1_TEST_CHAINS)
    targets = select(chains, tickers)

    problems = 0
    for chain in targets:
        if not chain.cik:
            print(f"{chain.ticker}: no CIK, skipping")
            problems += 1
            continue
        print(f"\n{chain.ticker}  ({chain.name}, CIK {chain.cik})")
        try:
            quarters = filings.discover(chain.cik, fetcher, n_quarters=args.quarters)
        except Exception as exc:  # keep going with the other chains
            print(f"  ERROR finding filings: {exc}")
            problems += 1
            continue
        for quarter in quarters:
            label = f"  {quarter.period_end}  {quarter.periodic.form:<5}"
            if not args.force and cache.is_cached(chain.ticker, quarter):
                print(f"{label}  cached")
                continue
            try:
                manifest = cache.fetch_quarter(chain.ticker, chain.cik, quarter, fetcher)
            except Exception as exc:
                print(f"{label}  ERROR: {exc}")
                problems += 1
                continue
            ex = manifest["earnings_8k"]
            release = f"8-K {ex['filing_date']} ({len(manifest['exhibits'])} ex-99)" if ex else "no 8-K"
            flags = f"  ! {', '.join(manifest['flags'])}" if manifest["flags"] else ""
            print(f"{label}  saved  {release}{flags}")
    print(f"\nDone. Files are in {RAW_DIR}")
    return 1 if problems else 0


def cmd_status(args: argparse.Namespace) -> int:
    if not RAW_DIR.exists():
        print("Nothing cached yet. Run: python -m turnout fetch")
        return 0
    for ticker_dir in sorted(p for p in RAW_DIR.iterdir() if p.is_dir()):
        print(ticker_dir.name)
        for qdir in sorted((p for p in ticker_dir.iterdir() if p.is_dir()), reverse=True):
            mpath = qdir / cache.MANIFEST
            if not mpath.exists():
                print(f"  {qdir.name}  incomplete")
                continue
            m = json.loads(mpath.read_text())
            flags = f"  ! {', '.join(m['flags'])}" if m.get("flags") else ""
            print(f"  {qdir.name}  {m['periodic']['form']:<5}  ex-99: {len(m['exhibits'])}{flags}")
            if m.get("earnings_8k"):
                e = m["earnings_8k"]
                print(f"      8-K {e['filing_date']} score {e.get('score')}: {e.get('headline', '')}")
    return 0


def _settings() -> dict:
    return json.loads((DATA_DIR / "settings.json").read_text())


def cmd_storage(args: argparse.Namespace) -> int:
    from turnout import storage

    store = storage.R2Store()
    if args.action == "pull":
        n = storage.pull(store, args.tickers)
        print(f"Downloaded {n} files from R2.")
    else:
        n = storage.push(store)
        print(f"Uploaded {n} new or changed files to R2.")
    return 0


def _targets(args: argparse.Namespace) -> list:
    chains = load_universe()
    tickers = None if args.all else (args.tickers or PHASE1_TEST_CHAINS)
    return select(chains, tickers)


def _run_model(model: str, targets: list, out_dir: Path | None, force: bool,
               max_quarters: int | None = None) -> list[dict]:
    from turnout.extract.llm import OpenRouterExtractor
    from turnout.extract.run import extract_quarter, quarter_dirs, result_path, reverify

    extractor = OpenRouterExtractor(model)
    results = []
    for chain in targets:
        for qdir in quarter_dirs(chain.ticker)[:max_quarters]:
            print(f"  {chain.ticker} {qdir.name} ...", flush=True)
            path = result_path(chain.ticker, qdir.name, out_dir) if out_dir else result_path(chain.ticker, qdir.name)
            if not force and path.exists() and json.loads(path.read_text()).get("model") == model:
                saved = reverify(json.loads(path.read_text()), chain, qdir)
                path.write_text(json.dumps(saved, indent=2) + "\n")
                results.append(saved)
                print(f"  {chain.ticker} {qdir.name}  reused saved answer (re-checked)")
                continue
            try:
                result = extract_quarter(chain, qdir, extractor)
            except Exception as exc:  # keep going
                print(f"  {chain.ticker} {qdir.name}  ERROR: {exc}")
                results.append({"ticker": chain.ticker, "period_end": qdir.name, "error": str(exc)})
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, indent=2) + "\n")
            counts = {}
            for r in result["fields"].values():
                counts[r["status"]] = counts.get(r["status"], 0) + 1
            summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
            print(f"  {chain.ticker} {qdir.name}  {summary}  ${result['usage']['cost_usd']:.4f}")
            results.append(result)
    return results


def cmd_extract(args: argparse.Namespace) -> int:
    model = args.model or _settings().get("extraction_model")
    if not model:
        print("No extraction model set yet. Run the bake-off first, or pass --model.")
        return 2
    print(f"Extracting with {model}")
    results = _run_model(model, _targets(args), None, args.force, args.quarters)
    return 1 if any("error" in r for r in results) else 0


def cmd_bakeoff(args: argparse.Namespace) -> int:
    from turnout.extract import bakeoff

    models = args.models or _settings()["bakeoff_models"]
    targets = _targets(args)
    all_results = {}
    for model in models:
        print(f"\n=== {model} ===")
        out = DATA_DIR / "bakeoff" / model.replace("/", "__")
        all_results[model] = _run_model(model, targets, out, args.force, args.quarters)
    n = max((len(v) for v in all_results.values()), default=0)
    report = bakeoff.report_markdown(bakeoff.compare(all_results), n)
    (DATA_DIR / "bakeoff").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "bakeoff" / "report.md").write_text(report)
    print("\n" + report)
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from turnout import review

    tracker = review.GitHubIssues()
    if args.action == "open":
        print(f"Opened {review.open_issues(tracker)} review issues.")
        return 0
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    issue, comment = event["issue"], event["comment"]
    msg = review.apply_comment(issue.get("body", ""), comment.get("body", ""),
                               comment.get("html_url", ""), comment["user"]["login"])
    if msg is None:
        print("No review command in this comment.")
        return 0
    print(msg)
    Path("review_message.txt").write_text(msg)
    return 0


def cmd_bakeoff_report(args: argparse.Namespace) -> int:
    from turnout.extract import bakeoff

    base = DATA_DIR / "bakeoff"
    all_results = {}
    for model_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        model = model_dir.name.replace("__", "/")
        all_results[model] = [json.loads(p.read_text()) for p in sorted(model_dir.glob("*/*.json"))]
    n = max((len(v) for v in all_results.values()), default=0)
    report = bakeoff.report_markdown(bakeoff.compare(all_results), n)
    (base / "report.md").write_text(report)
    print(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m turnout", description="The Turnout Report pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("resolve-ciks", help="Look up CIK numbers").set_defaults(func=cmd_resolve_ciks)

    fetch = sub.add_parser("fetch", help="Download and cache filings")
    fetch.add_argument("--tickers", nargs="+", help="Tickers to fetch (default: TXRH WMT FND)")
    fetch.add_argument("--all", action="store_true", help="Fetch every chain in the universe")
    fetch.add_argument("--quarters", type=int, default=8, help="How many quarters back (default 8)")
    fetch.add_argument("--force", action="store_true", help="Re-download even if cached")
    fetch.set_defaults(func=cmd_fetch)

    sub.add_parser("status", help="Show cached filings").set_defaults(func=cmd_status)

    st = sub.add_parser("storage", help="Sync data/raw with Cloudflare R2")
    st.add_argument("action", choices=["pull", "push"])
    st.add_argument("--tickers", nargs="+", help="Only these tickers (pull only)")
    st.set_defaults(func=cmd_storage)

    for name, func, help_text in [
        ("extract", cmd_extract, "Extract numbers with the chosen model"),
        ("bakeoff", cmd_bakeoff, "Compare several models on the same quarters"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--tickers", nargs="+", help="Tickers (default: TXRH WMT FND)")
        p.add_argument("--all", action="store_true", help="Every chain")
        p.add_argument("--force", action="store_true", help="Redo even if already extracted")
        p.add_argument("--quarters", type=int, default=None, help="Only the latest N quarters per chain (quick tests)")
        if name == "extract":
            p.add_argument("--model", help="OpenRouter model id (default: data/settings.json)")
        else:
            p.add_argument("--models", nargs="+", help="Model ids (default: data/settings.json)")
        p.set_defaults(func=func)

    sub.add_parser("bakeoff-report", help="Build the bake-off report from saved results").set_defaults(
        func=cmd_bakeoff_report)

    rv = sub.add_parser("review", help="Open review issues, or apply a reviewer's reply")
    rv.add_argument("action", choices=["open", "apply"])
    rv.set_defaults(func=cmd_review)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"Setup needed: {exc}", file=sys.stderr)
        return 2
