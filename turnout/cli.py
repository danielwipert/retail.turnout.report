"""Command line: `python -m turnout <command>`.

Commands
  resolve-ciks   Look up each chain's SEC CIK number and save it to data/universe.json
  fetch          Download and cache filings (default: the 3 Phase 1 test chains)
  status         Show what's cached and any quarters that need a human look
"""

from __future__ import annotations

import argparse
import json
import sys

from turnout import cache, filings
from turnout.config import RAW_DIR, ConfigError, sec_user_agent
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"Setup needed: {exc}", file=sys.stderr)
        return 2
