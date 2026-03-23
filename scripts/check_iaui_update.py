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
from pathlib import Path
from typing import Sequence
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_PAGE_URL = "https://www.iaui.gov.lv/lv/precu-un-pakalpojumu-loteriju-registra-dati?="
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; lotteries-iaui-check/1.0; +https://github.com/kosjak0ff/lotteries)"

DOWNLOAD_LINK_PATTERN = re.compile(
    r'<a[^>]+href="(?P<href>[^"]*download[^"]*)"[^>]*>(?P<text>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
UPDATED_AT_PATTERN = re.compile(r"Atjaunināts:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def clean_whitespace(text: str) -> str:
    return " ".join(text.split())


def fetch_page(url: str) -> str:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def discover_download_link(page_html: str, page_url: str) -> tuple[str, str]:
    first_download_url = None
    first_download_text = None

    for match in DOWNLOAD_LINK_PATTERN.finditer(page_html):
        href = html.unescape(match.group("href"))
        text = clean_whitespace(strip_tags(html.unescape(match.group("text"))))
        absolute_url = urljoin(page_url, href)

        if first_download_url is None:
            first_download_url = absolute_url
            first_download_text = text

        if "Izsniegtās preču un pakalpojumu loteriju atļaujas" in text:
            return absolute_url, text

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
    page_html = fetch_page(args.page_url)
    download_url, link_text = discover_download_link(page_html, args.page_url)
    updated_at = extract_updated_at(page_html)

    payload = {
        "page_url": args.page_url,
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
