"""Long-term home for downloaded filings: Cloudflare R2 (decision P2-1).

The pipeline always works on the local folder `data/raw/`. Before a run, `pull`
copies what R2 already has into that folder; after a run, `push` uploads
anything new. So the rest of the code never needs to know about R2.

R2 speaks the S3 API, so we use boto3 pointed at Cloudflare's endpoint.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from turnout.config import RAW_DIR, ConfigError

PREFIX = "raw/"


class ObjectStore(Protocol):
    def list(self, prefix: str) -> dict[str, int]:
        """{key: size_in_bytes} for every object under prefix."""

    def upload(self, path: Path, key: str) -> None: ...

    def download(self, key: str, path: Path) -> None: ...


class R2Store:
    def __init__(self) -> None:
        import boto3  # imported here so tests don't need it

        # Pasted secrets often carry stray spaces, quotes or line breaks.
        env = {
            name: os.environ.get(name, "").strip().strip('"').strip("'").strip()
            for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
        }
        missing = [name for name, value in env.items() if not value]
        if missing:
            raise ConfigError(f"Missing R2 secrets: {', '.join(missing)}")
        self.bucket = env["R2_BUCKET"]
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=env["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )
        # Lengths only (never the values) so a bad paste is easy to spot in the log.
        print(f"R2: bucket={self.bucket} account_id_len={len(env['R2_ACCOUNT_ID'])} "
              f"access_key_len={len(env['R2_ACCESS_KEY_ID'])} secret_len={len(env['R2_SECRET_ACCESS_KEY'])}")

    def list(self, prefix: str) -> dict[str, int]:
        found: dict[str, int] = {}
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                found[obj["Key"]] = obj["Size"]
        return found

    def upload(self, path: Path, key: str) -> None:
        self.client.upload_file(str(path), self.bucket, key)

    def download(self, key: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(path))


def _key(path: Path, root: Path) -> str:
    return PREFIX + path.relative_to(root).as_posix()


def push(store: ObjectStore, root: Path = RAW_DIR) -> int:
    """Upload files that R2 doesn't have yet (or that changed size). Returns count."""
    if not root.exists():
        return 0
    remote = store.list(PREFIX)
    sent = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        key = _key(path, root)
        if remote.get(key) != path.stat().st_size:
            store.upload(path, key)
            sent += 1
    return sent


def pull(store: ObjectStore, tickers: list[str] | None = None, root: Path = RAW_DIR) -> int:
    """Download files that aren't in the local folder yet. Returns count."""
    prefixes = [PREFIX + t.upper() + "/" for t in tickers] if tickers else [PREFIX]
    got = 0
    for prefix in prefixes:
        for key, size in store.list(prefix).items():
            path = root / key[len(PREFIX):]
            if not path.exists() or path.stat().st_size != size:
                store.download(key, path)
                got += 1
    return got
