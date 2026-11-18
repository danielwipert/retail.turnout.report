"""The LLM reader. LLMs only *read*: they return a number and the exact sentence
it came from. Python checks everything afterwards (verify.py).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from turnout.config import ConfigError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You read SEC filings and copy out specific numbers.

Rules:
- Only use what is written in the text you are given. Never compute, convert, round or infer a number.
- For every value, copy the supporting sentence or table row EXACTLY as it appears, character for character, into "quote". Keep it short: one sentence or one table row.
- The quote must contain the number you report.
- A decrease is a negative number. A table value in parentheses, like (2.9)%, is negative.
- Report percentages as plain numbers: "increased 4.3%" -> 4.3. "decreased 290 basis points" -> -2.9.
- "source" is "press_release" or "periodic", whichever part the quote came from.
- Use the current quarter, not year-to-date, not a prior year, not guidance.
- Use the segment the user names. If only a different segment's number is given, return null.
- If a figure is given both with and without fuel, use the one without fuel.
- If the text gives both a quarter and a year-to-date figure, use the quarter.
- If something is not stated, return null for value, quote and source. A null is always better than a guess."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0

    def add(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.cost_usd += other.cost_usd
        self.calls += other.calls


@dataclass
class Answer:
    data: dict
    usage: Usage = field(default_factory=Usage)


class Extractor(Protocol):
    model: str

    def extract(self, user_prompt: str, schema: dict) -> Answer: ...


class OpenRouterExtractor:
    def __init__(self, model: str, api_key: str | None = None, timeout: float = 90.0):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise ConfigError("OPENROUTER_API_KEY is not set (add it as a repository secret).")
        self._client = httpx.Client(timeout=timeout)

    def extract(self, user_prompt: str, schema: dict) -> Answer:
        body = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 4000,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "extraction", "strict": True, "schema": schema},
            },
            # Only route to providers that actually support structured output.
            "provider": {"require_parameters": True},
            "usage": {"include": True},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/danielwipert/retail.turnout.report",
            "X-Title": "The Turnout Report",
        }
        last_error = None
        for attempt in range(3):
            started = time.monotonic()
            try:
                resp = self._client.post(OPENROUTER_URL, json=body, headers=headers)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
                if resp.status_code >= 400:
                    # Bad key, unknown model, unsupported schema...: retrying won't help.
                    raise RuntimeError(f"{self.model}: HTTP {resp.status_code}: {resp.text[:500]}")
                resp.raise_for_status()
                payload = resp.json()
                content = payload["choices"][0]["message"].get("content")
                if not content:
                    raise ValueError("model returned an empty answer")
                data = json.loads(content)
                u = payload.get("usage", {}) or {}
                usage = Usage(
                    prompt_tokens=u.get("prompt_tokens", 0),
                    completion_tokens=u.get("completion_tokens", 0),
                    cost_usd=float(u.get("cost", 0) or 0),
                    calls=1,
                )
                print(f"    llm call ok: {len(user_prompt):,} chars in, "
                      f"{time.monotonic() - started:.1f}s, ${usage.cost_usd:.4f}", flush=True)
                return Answer(data=data, usage=usage)
            except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
                print(f"    llm call failed (try {attempt + 1}/3) after "
                      f"{time.monotonic() - started:.1f}s: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
                last_error = exc
                time.sleep(2 ** attempt * 2)
        raise RuntimeError(f"{self.model}: extraction failed after retries: {last_error}")


def build_prompt(chain_name: str, segment: str, period_end: str, fields: list, documents: dict[str, str],
                 field_notes: dict[str, str] | None = None) -> str:
    notes = field_notes or {}
    asks = "\n".join(
        f'- "{f.name}": {f.ask}' + (f" FOR THIS COMPANY: {notes[f.name]}" if f.name in notes else "")
        for f in fields
    )
    docs = "\n\n".join(
        f"===== {name.upper()} =====\n{text}" for name, text in documents.items() if text
    )
    return (
        f"Company: {chain_name}\n"
        f"Segment to use: {segment or 'the company total'}\n"
        f"Quarter ending: {period_end}\n\n"
        f"Find these fields:\n{asks}\n\n"
        f"Text from the filings (\"...\" marks skipped parts):\n\n{docs}"
    )
