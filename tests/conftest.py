"""Shared test helpers. Tests never touch the real SEC website."""

from __future__ import annotations

import json
from typing import Any

import pytest


class FakeFetcher:
    """Serves canned responses by URL and records every URL asked for."""

    def __init__(self, pages: dict[str, Any]):
        self.pages = pages
        self.requested: list[str] = []

    def _lookup(self, url: str) -> Any:
        self.requested.append(url)
        if url not in self.pages:
            raise KeyError(f"FakeFetcher has no page for {url}")
        return self.pages[url]

    def get_text(self, url: str) -> str:
        value = self._lookup(url)
        return value if isinstance(value, str) else json.dumps(value)

    def get_json(self, url: str) -> Any:
        value = self._lookup(url)
        return json.loads(value) if isinstance(value, str) else value


def submissions_block(rows: list[dict]) -> dict:
    """Build SEC's column-style arrays from a list of row dicts."""
    keys = ["accessionNumber", "filingDate", "reportDate", "form", "items", "primaryDocument"]
    return {k: [r.get(k, "") for r in rows] for k in keys}


def index_html(exhibits: list[tuple[str, str, str]]) -> str:
    """A minimal EDGAR -index.htm page. exhibits = [(type, file, description)]."""
    rows = "".join(
        f"<tr><td>{i}</td><td>{desc}</td>"
        f'<td><a href="/Archives/edgar/data/1/000000000026000001/{doc}">{doc}</a></td>'
        f"<td>{etype}</td><td>1000</td></tr>"
        for i, (etype, doc, desc) in enumerate(exhibits, start=1)
    )
    return (
        "<html><body><table class='tableFile' summary='Document Format Files'>"
        "<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>"
        f'<tr><td>1</td><td>8-K</td><td><a href="/ix?doc=/Archives/edgar/data/1/x/form8k.htm">form8k.htm</a></td>'
        f"<td>8-K</td><td>500</td></tr>{rows}</table></body></html>"
    )


@pytest.fixture
def fake_fetcher_cls():
    return FakeFetcher
