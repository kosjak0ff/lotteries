"""
Check the IAUI lottery registry page and emit normalized metadata for the currently published file.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_PAGE_URL = "https://www.vid.gov.lv/lv/loterijas"
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; lotteries-iaui-check/1.0; +https://github.com/kosjak0ff/lotteries)"
TARGET_LINK_TEXT = "Izsniegtās preču un pakalpojumu loteriju atļaujas"
UPDATED_AT_PATTERN = re.compile(r"Atjaunināts:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})\.?")


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_attrs: dict[str, str] = {}
        self._current_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        self._current_href = ""
        self._current_attrs = {key: value or "" for key, value in attrs}
        self._current_chunks = []

    def handle_data(self, data: str) -> None:
        if self._current_href is None:
            return
        self._current_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return
        href = self._current_attrs.get("href", "")
        text = clean_whitespace("".join(self._current_chunks))
        aria_label = clean_whitespace(self._current_attrs.get("aria-label", ""))
        title = clean_whitespace(self._current_attrs.get("title", ""))
        self.links.append(
            {
                "href": href,
                "text": text,
                "aria_label": aria_label,
                "title": title,
            }
        )
        self._current_href = None
        self._current_attrs = {}
        self._current_chunks = []


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def clean_whitespace(text: str) -> str:
    return " ".join(text.split())


def fetch_page(url: str) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace"), response.geturl()


def discover_download_link(page_html: str, page_url: str) -> tuple[str, str]:
    parser = LinkExtractor()
    parser.feed(page_html)

    first_download_url = None
    first_download_text = None

    for link in parser.links:
        href = html.unescape(link["href"])
        if not href:
            continue

        combined_text = clean_whitespace(
            " ".join(part for part in (link["text"], link["aria_label"], link["title"]) if part)
        )
        absolute_url = urljoin(page_url, href)
        is_download = "download?attachment" in href or "/media/" in href

        if is_download and first_download_url is None:
            first_download_url = absolute_url
            first_download_text = combined_text

        if TARGET_LINK_TEXT in combined_text:
            return absolute_url, TARGET_LINK_TEXT

    if first_download_url:
        return first_download_url, first_download_text or "IAUI lottery registry"

    raise RuntimeError("Could not find a download link on the IAUI page")


def extract_updated_at(page_html: str) -> str | None:
    match = UPDATED_AT_PATTERN.search(page_html)
    return match.group(1) if match else None


def build_fingerprint(download_url: str, link_text: str, updated_at: str | None) -> str:
    raw = json.dumps(
        {
            "download_url": download_url,
            "link_text": link_text,
            "updated_at": updated_at or "",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check IAUI registry metadata.")
    parser.add_argument("--page-url", default=DEFAULT_PAGE_URL, help="IAUI registry page URL")
    parser.add_argument("--output", default="-", help="Output JSON path or '-' for stdout")
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    page_html, final_url = fetch_page(args.page_url)
    download_url, link_text = discover_download_link(page_html, final_url)
    updated_at = extract_updated_at(page_html)

    payload = {
        "page_url": final_url,
        "download_url": download_url,
        "link_text": link_text,
        "updated_at": updated_at,
        "fingerprint": build_fingerprint(download_url, link_text, updated_at),
    }

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(rendered)
    else:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
