"""
Synchronize the latest IAUI lottery registry XLS into the repository and regenerate the site dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PAGE_URL = "https://www.iaui.gov.lv/lv/precu-un-pakalpojumu-loteriju-registra-dati?="
DEFAULT_FALLBACK_DOWNLOAD_URL = "https://www.iaui.gov.lv/lv/media/981/download?attachment="
DEFAULT_SOURCE_PATH = ROOT / "data" / "source" / "iaui_lottery_registry.xls"
DEFAULT_JSON_OUTPUT = ROOT / "assets" / "active_lotteries.json"
DEFAULT_TIMEZONE = "Europe/Riga"
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; lotteries-sync/1.0; +https://github.com/kosjak0ff/lotteries)"

DOWNLOAD_LINK_PATTERN = re.compile(
    r'<a[^>]+href="(?P<href>[^"]*download[^"]*)"[^>]*>(?P<text>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
UPDATED_AT_PATTERN = re.compile(r"Atjaunināts:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def clean_whitespace(text: str) -> str:
    return " ".join(text.split())


def fetch_url(url: str) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=60) as response:
        payload = response.read()
        final_url = response.geturl()
    return payload, final_url


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


def build_source_label(link_text: str, updated_at: str | None) -> str:
    if updated_at:
        return f"Loteriju reģistrs {updated_at}"
    if link_text:
        return link_text
    return "Loteriju reģistrs"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_reference_date(value: str) -> str:
    if value == "today":
        return datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).date().isoformat()
    return value


def write_if_changed(path: Path, data: bytes) -> bool:
    current_hash = sha256_path(path)
    new_hash = sha256_bytes(data)
    if current_hash == new_hash:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def run_extract(
    input_path: Path,
    output_path: Path,
    reference_date: str,
    source_label: str,
    updated_at: str | None,
    source_url: str,
) -> None:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "extract_lotteries.py"),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--date",
        reference_date,
        "--source-label",
        source_label,
        "--source-url",
        source_url,
    ]
    if updated_at:
        command.extend(["--source-updated-at", updated_at])

    subprocess.run(command, cwd=ROOT, check=True)


def validate_generated_json(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    count = payload.get("count", 0)
    items = payload.get("items", [])
    if count == 0 or not items:
        raise RuntimeError("Generated JSON is empty; refusing to publish an empty dataset")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync the latest IAUI lottery registry into the repository.")
    parser.add_argument("--page-url", default=DEFAULT_PAGE_URL, help="IAUI page that links to the current XLS")
    parser.add_argument(
        "--fallback-download-url",
        default=DEFAULT_FALLBACK_DOWNLOAD_URL,
        help="Fallback direct download URL if page parsing fails",
    )
    parser.add_argument(
        "--source-output",
        default=str(DEFAULT_SOURCE_PATH),
        help="Stable path for the downloaded XLS inside the repository",
    )
    parser.add_argument(
        "--json-output",
        default=str(DEFAULT_JSON_OUTPUT),
        help="Path to the generated active lotteries JSON",
    )
    parser.add_argument(
        "--reference-date",
        default="today",
        help="Reference date for filtering active lotteries (YYYY-MM-DD or 'today')",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate JSON even when the downloaded XLS did not change",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)

    source_output = Path(args.source_output)
    json_output = Path(args.json_output)
    reference_date = resolve_reference_date(args.reference_date)

    print(f"Fetching IAUI page: {args.page_url}")
    page_bytes, _ = fetch_url(args.page_url)
    page_html = page_bytes.decode("utf-8", errors="replace")

    updated_at = extract_updated_at(page_html)
    try:
        download_url, link_text = discover_download_link(page_html, args.page_url)
    except Exception as error:
        print(f"Could not parse a download link from the page ({error}); using fallback URL.")
        download_url = args.fallback_download_url
        link_text = "Izsniegtās preču un pakalpojumu loteriju atļaujas"

    print(f"Downloading XLS: {download_url}")
    xls_bytes, final_download_url = fetch_url(download_url)

    changed = write_if_changed(source_output, xls_bytes)
    if changed:
        print(f"Updated source XLS: {source_output}")
    else:
        print("Source XLS is unchanged")

    if changed or args.force:
        source_label = build_source_label(link_text, updated_at)
        print(f"Regenerating JSON for reference date {reference_date}")
        run_extract(source_output, json_output, reference_date, source_label, updated_at, final_download_url)
        validate_generated_json(json_output)
    else:
        print("Skipping JSON regeneration because the source file did not change")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
