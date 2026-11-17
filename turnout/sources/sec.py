"""SEC EDGAR client.

Everything that talks to sec.gov goes through `Fetcher`. Tests swap in a fake
fetcher so they never touch the network.
"""

from __future__ import annotations

import time
from typing import Any, Protocol

import httpx

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
SUBMISSIONS_PAGE_URL = "https://data.sec.gov/submissions/{name}"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/"
FILING_INDEX_URL = ARCHIVE_BASE + "{acc}-index.htm"

# SEC asks for at most 10 requests per second. Stay well under it.
MIN_SECONDS_BETWEEN_REQUESTS = 0.15
RETRY_STATUSES = {429, 500, 502, 503, 504}


class Fetcher(Protocol):
    """Anything that can GET a URL and return text or parsed JSON."""

    def get_text(self, url: str) -> str: ...

    def get_json(self, url: str) -> Any: ...


class SecHttpFetcher:
    """Real fetcher: polite, rate-limited, retries on temporary errors."""

    def __init__(self, user_agent: str, max_retries: int = 4, timeout: float = 30.0):
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=timeout,
            follow_redirects=True,
        )
        self._max_retries = max_retries
        self._last_request = 0.0

    def _wait_turn(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < MIN_SECONDS_BETWEEN_REQUESTS:
            time.sleep(MIN_SECONDS_BETWEEN_REQUESTS - elapsed)
        self._last_request = time.monotonic()

    def _get(self, url: str) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            self._wait_turn()
            response = self._client.get(url)
            if response.status_code not in RETRY_STATUSES:
                response.raise_for_status()
                return response
            time.sleep(2 ** attempt)  # 1, 2, 4, 8 seconds
        response.raise_for_status()
        return response

    def get_text(self, url: str) -> str:
        return self._get(url).text

    def get_json(self, url: str) -> Any:
        return self._get(url).json()

    def close(self) -> None:
        self._client.close()


def cik10(cik: str | int) -> str:
    """CIK as the 10-digit zero-padded string the SEC uses in URLs."""
    return str(int(cik)).zfill(10)


def archive_base(cik: str | int, accession: str) -> str:
    return ARCHIVE_BASE.format(cik_int=int(cik), acc_nodash=accession.replace("-", ""))


def filing_index_url(cik: str | int, accession: str) -> str:
    return FILING_INDEX_URL.format(
        cik_int=int(cik), acc_nodash=accession.replace("-", ""), acc=accession
    )
