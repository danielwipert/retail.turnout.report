import json

import pytest

from turnout.config import UNIVERSE_PATH
from turnout.universe import load_universe, resolve_ciks, select

from conftest import FakeFetcher


def test_universe_matches_the_spec():
    chains = load_universe()
    core = [c for c in chains if c.tier == "core"]
    assert len(core) == 30
    groups = {}
    for c in core:
        groups[c.group] = groups.get(c.group, 0) + 1
    assert groups == {"limited_service": 8, "full_service": 8, "mass_club_value": 6, "home_specialty": 8}
    assert "DENN" not in {c.ticker for c in chains}
    assert len({c.ticker for c in chains}) == len(chains)  # no duplicates


def test_resolve_ciks_pads_to_ten_digits_and_reports_missing():
    chains = [c for c in load_universe() if c.ticker in {"TXRH", "WMT"}]
    for c in chains:
        c.cik = None
    table = {"0": {"cik_str": 1289460, "ticker": "TXRH", "title": "Texas Roadhouse"}}
    missing = resolve_ciks(chains, FakeFetcher({"https://www.sec.gov/files/company_tickers.json": table}))
    assert next(c for c in chains if c.ticker == "TXRH").cik == "0001289460"
    assert missing == ["WMT"]


def test_select_rejects_unknown_tickers():
    with pytest.raises(ValueError):
        select(load_universe(), ["TXRH", "NOPE"])


def test_universe_file_is_valid_json():
    json.loads(UNIVERSE_PATH.read_text())
