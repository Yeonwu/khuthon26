#!/usr/bin/env python3
"""Download publicly exposed Backtracks4all preview audio from a song page.

The full WAV stem links on paid song pages usually point to sign-in/download
flows. This script does not bypass those gates; it downloads only audio URLs
that are already embedded in the public page player and records gated WAV
entries in a manifest.
"""

from __future__ import annotations

import argparse
import csv
import http.client
import json
import re
import sys
import time
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (compatible; khuthon-mert-backtracks-downloader/1.0)"
TRANSIENT_HTTP_CODES = {408, 429, 500, 502, 503, 504}
TRANSIENT_ERRORS = (TimeoutError, URLError, ConnectionError, http.client.RemoteDisconnected)


class FetchError(RuntimeError):
    pass


class LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if href:
            self._current_href = urljoin(self.base_url, href)
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href:
            text = " ".join(part.strip() for part in self._current_text if part.strip())
            self.links.append({"href": self._current_href, "text": unescape(text)})
            self._current_href = None
            self._current_text = []


def describe_error(exc: BaseException) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code} {exc.reason}"
    if isinstance(exc, URLError):
        return str(exc.reason)
    return str(exc) or exc.__class__.__name__


def is_retryable(exc: BaseException) -> bool:
    return (
        isinstance(exc, HTTPError)
        and exc.code in TRANSIENT_HTTP_CODES
    ) or isinstance(exc, TRANSIENT_ERRORS)


def fetch_bytes_with_retry(url: str, timeout: float, retries: int, retry_delay: float) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    last_error: BaseException | None = None

    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except (HTTPError, *TRANSIENT_ERRORS) as exc:
            if not is_retryable(exc):
                raise FetchError(f"failed to fetch {url}: {describe_error(exc)}") from exc
            last_error = exc
            if attempt == retries:
                break
            delay = retry_delay * (2 ** (attempt - 1))
            print(
                f"retrying fetch ({attempt}/{retries}) after {describe_error(exc)}: {url}",
                file=sys.stderr,
            )
            time.sleep(delay)

    assert last_error is not None
    raise FetchError(
        f"failed to fetch {url} after {retries} attempts: {describe_error(last_error)}"
    ) from last_error


def fetch_text(url: str, timeout: float, retries: int, retry_delay: float) -> str:
    return fetch_bytes_with_retry(url, timeout, retries, retry_delay).decode("utf-8", errors="replace")


def fetch_bytes(url: str, timeout: float, retries: int, retry_delay: float) -> bytes:
    return fetch_bytes_with_retry(url, timeout, retries, retry_delay)


def safe_filename(value: str) -> str:
    value = value.strip().replace("/", "_").replace("\\", "_")
    value = re.sub(r"[^0-9A-Za-z媛�-��._ -]+", "_", value)
    return re.sub(r"\s+", "_", value).strip("_") or "audio"


def extract_player_tracks(html: str) -> list[dict[str, Any]]:
    match = re.search(r"playlist\.load\((\[.*?\])\)\.then", html, re.DOTALL)
    if not match:
        return []
    return json.loads(match.group(1))


def extract_gated_wav_links(html: str, page_url: str) -> list[dict[str, str]]:
    parser = LinkParser(page_url)
    parser.feed(html)
    return [
        {"filename": link["text"], "href": link["href"]}
        for link in parser.links
        if link["text"].lower().endswith(".wav")
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Backtracks4all public preview MP3s from a song page.")
    parser.add_argument("url")
    parser.add_argument("--out-dir", type=Path, default=Path("data/backtracks4all_downloads"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--timeout", type=float, default=90, help="Per-request timeout in seconds.")
    parser.add_argument("--retries", type=int, default=8, help="Number of fetch attempts for transient failures.")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Initial retry delay in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        html = fetch_text(args.url, args.timeout, args.retries, args.retry_delay)
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    (args.out_dir / "page.html").write_text(html, encoding="utf-8")

    preview_tracks = extract_player_tracks(html)
    gated_wavs = extract_gated_wav_links(html, args.url)

    preview_rows = []
    for index, track in enumerate(preview_tracks, start=1):
        name = str(track.get("name") or f"track_{index:02d}")
        src = str(track.get("src") or "")
        if not src:
            continue
        filename = f"{index:02d}_{safe_filename(name)}.mp3"
        path = args.out_dir / filename
        status = "skipped_existing"
        if args.overwrite or not path.exists():
            try:
                path.write_bytes(fetch_bytes(src, args.timeout, args.retries, args.retry_delay))
            except FetchError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            status = "downloaded"
        preview_rows.append({
            "index": index,
            "name": name,
            "src": src,
            "path": str(path),
            "status": status,
        })
        print(f"[{index}/{len(preview_tracks)}] {status} {name} -> {path}")

    manifest = {
        "source_url": args.url,
        "preview_tracks": preview_rows,
        "gated_wav_links": gated_wavs,
        "note": "Public page exposes preview MP3s. Full WAV links point to sign-in/download flow.",
    }
    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = args.out_dir / "preview_tracks.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["index", "name", "src", "path", "status"])
        writer.writeheader()
        writer.writerows(preview_rows)

    gated_path = args.out_dir / "gated_wav_links.csv"
    with gated_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["filename", "href"])
        writer.writeheader()
        writer.writerows(gated_wavs)

    print(f"preview_tracks={len(preview_rows)}")
    print(f"gated_wav_links={len(gated_wavs)}")
    print(f"out_dir={args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
	
