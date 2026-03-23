"""
Extract active Latvian lotteries for a specific date and emit JSON for the static site.

Usage:
  python scripts/extract_lotteries.py           # writes assets/active_lotteries.json for default date 2026-03-20
  python scripts/extract_lotteries.py --date 2026-03-20 --input "Loteriju reģistrs_16.03.2026..xls"
  python scripts/extract_lotteries.py --check   # runs extraction and exits non-zero on validation issues, no write
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import List, Sequence

import pandas as pd

DEFAULT_DATE = "2026-03-20"
DEFAULT_INPUT = "Loteriju reģistrs_16.03.2026..xls"
DEFAULT_OUTPUT = Path("assets/active_lotteries.json")

# Keywords to exclude magazine/newspaper related lotteries (accent-insensitive).
MEDIA_KEYWORDS = [
    "žurn",
    "zurn",
    "avīz",
    "aviz",
    "magazin",
    "newspaper",
    "press",
]


def strip_accents(text: str) -> str:
    """Remove diacritics so keyword matching is accent-insensitive."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if unicodedata.category(c) != "Mn"
    )


def find_input_path(path_str: str) -> Path:
    """Return a usable path, falling back to 8.3 short name if necessary."""
    path = Path(path_str)
    if path.exists():
        return path
    # Fallback to 8.3 short filename if available (Windows)
    short = Path("LOTERI~1.XLS")
    if short.exists():
        return short
    # Last resort: first .xls in directory
    for candidate in Path(".").glob("*.xls"):
        return candidate
    raise FileNotFoundError(f"Input XLS not found (tried '{path_str}' and 'LOTERI~1.XLS')")


def load_dataframe(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Atlaujas")
    cols = list(df.columns)
    rename = {
        cols[0]: "permit",
        cols[1]: "org",
        cols[2]: "org_reg",
        cols[3]: "product",
        cols[4]: "name",
        cols[5]: "start",
        cols[6]: "end",
        cols[7]: "place",
    }
    df = df.rename(columns=rename)
    df["start"] = pd.to_datetime(df["start"], errors="coerce", dayfirst=True)
    df["end"] = pd.to_datetime(df["end"], errors="coerce", dayfirst=True)
    return df


def filter_active(df: pd.DataFrame, ref_date: pd.Timestamp) -> pd.DataFrame:
    return df[(df["start"] <= ref_date) & (df["end"] >= ref_date)].copy()


def exclude_media(df: pd.DataFrame) -> pd.DataFrame:
    def is_media(row) -> bool:
        text_parts: Sequence[str] = [row.get("name", ""), row.get("org", ""), row.get("product", "")]
        text = strip_accents(" ".join(str(x) for x in text_parts if pd.notna(x)).lower())
        return any(k in text for k in MEDIA_KEYWORDS)

    mask = df.apply(is_media, axis=1)
    return df[~mask].copy()


def df_to_records(df: pd.DataFrame) -> List[dict]:
    records: List[dict] = []
    for _, row in df.iterrows():
        records.append(
            {
                "permit": str(row.get("permit", "")).strip(),
                "name": str(row.get("name", "")).strip(),
                "org": str(row.get("org", "")).strip(),
                "org_reg": str(row.get("org_reg", "")).strip(),
                "product": str(row.get("product", "")).strip(),
                "start": row.get("start").date().isoformat() if pd.notna(row.get("start")) else None,
                "end": row.get("end").date().isoformat() if pd.notna(row.get("end")) else None,
                "place": str(row.get("place", "")).strip(),
            }
        )
    return records


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract active Latvian lotteries as JSON.")
    parser.add_argument("--date", default=DEFAULT_DATE, help="Reference date (YYYY-MM-DD). Default: 2026-03-20")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to XLS file (default: original name)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path (default: assets/active_lotteries.json)")
    parser.add_argument("--check", action="store_true", help="Validation only; do not write output")
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    ref_date = pd.to_datetime(args.date)
    input_path = find_input_path(args.input)

    df = load_dataframe(input_path)
    active = filter_active(df, ref_date)
    filtered = exclude_media(active)

    records = df_to_records(filtered)
    output_path = Path(args.output)

    print(f"Input: {input_path}")
    print(f"Reference date: {ref_date.date().isoformat()}")
    print(f"Active count before media filter: {len(active)}")
    print(f"Excluded as media: {len(active) - len(filtered)}")
    print(f"Remaining: {len(filtered)}")

    if args.check:
        if len(filtered) == 0:
            print("❌ No lotteries remaining after filtering", file=sys.stderr)
            return 2
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "reference_date": ref_date.date().isoformat(),
        "count": len(records),
        "items": records,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output_path} ({len(records)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
