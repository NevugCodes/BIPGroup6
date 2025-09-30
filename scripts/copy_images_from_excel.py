#!/usr/bin/env python3
"""
Copy images for objects listed in an Excel sheet to the output folder.

- Reads object numbers from a column (default: T1) in an .xls file, e.g. "1/2024/0501 0".
- Extracts year (second number) to find correct subfolder in images/<year>/.
- Builds a search prefix, e.g. "1-2024-0501 0" and copies all files whose filenames start with that prefix.
- Writes a CSV report to output/copy_report.csv.

Usage example:
  python scripts/copy_images_from_excel.py \
    --excel data/Liste_Schreibmaschinen.xls \
    --images images \
    --output output \
    --column T1 \
    --make-subdirs

Note: Requires openpyxl for Excel file support
"""

import argparse
import csv
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union

def get_excel_reader(file_path: Union[str, Path], sheet_name: Optional[str] = None):
    """Helper function to read Excel files with different engines."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")
    
    # First try to determine file type by content
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)  # Read first 8 bytes to check file signature
            
        # Check for Excel file signatures
        if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1') or header.startswith(b'\x50\x4b\x03\x04'):
            # Try openpyxl first (for .xlsx and newer .xls)
            try:
                return pd.read_excel(file_path, engine='openpyxl', sheet_name=sheet_name)
            except Exception as e1:
                print(f"Warning: openpyxl failed with: {e1}")
                # Try xlrd as fallback (for older .xls)
                try:
                    return pd.read_excel(file_path, engine='xlrd', sheet_name=sheet_name)
                except Exception as e2:
                    print(f"Warning: xlrd failed with: {e2}")
                    # Try default engine
                    return pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            # If not a standard Excel file, try pandas with default engine
            print("Warning: File doesn't match standard Excel signatures, trying default reader...")
            return pd.read_excel(file_path, sheet_name=sheet_name)
            
    except Exception as e:
        raise Exception(f"Failed to read Excel file {file_path}: {str(e)}")

import pandas as pd

OBJECT_REGEX = re.compile(
    r"^\s*(?P<prefix>\d+)[\/-](?P<year>\d{4})[\/-](?P<code>\d{4})\s+(?P<variant>\d+)\s*$"
)


def parse_object_number(value: str) -> Optional[Tuple[str, str, str, str, str]]:
    """Parse strings like "1/2024/0501 0" or "1-2024-0501 0".

    Returns tuple: (original, prefix, year, code, variant) or None if no match.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    m = OBJECT_REGEX.match(s)
    if not m:
        return None
    prefix = m.group("prefix")
    year = m.group("year")
    code = m.group("code")
    variant = m.group("variant")
    return s, prefix, year, code, variant


def build_search_prefix(prefix: str, year: str, code: str, variant: str) -> str:
    """Build filename search prefix like: 1-2024-0501 0"""
    return f"{prefix}-{year}-{code} {variant}"


def find_matching_files(images_root: Path, year: str, search_prefix: str) -> List[Path]:
    year_dir = images_root / year
    if not year_dir.is_dir():
        return []
    # Iterate files in year folder and filter by startswith
    matches: List[Path] = []
    for entry in year_dir.iterdir():
        if entry.is_file() and entry.name.startswith(search_prefix):
            matches.append(entry)
    return matches


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Copy images based on Excel object list")
    parser.add_argument("--excel", type=str, default=str(Path("data") / "Liste_Schreibmaschinen.xls"),
                        help="Path to Excel .xls file containing object numbers")
    parser.add_argument("--images", type=str, default=str(Path("images")),
                        help="Path to images root directory (contains year subfolders)")
    parser.add_argument("--output", type=str, default=str(Path("output")),
                        help="Path to output directory for copied images and report")
    parser.add_argument("--column", type=str, default="T1",
                        help="Column name containing object numbers (fallback: auto-detect any matching values)")
    parser.add_argument("--make-subdirs", action="store_true",
                        help="Create per-object subdirectories in output to avoid collisions")

    args = parser.parse_args()
    excel_path = Path(args.excel)
    images_root = Path(args.images)
    output_root = Path(args.output)

    if not excel_path.exists():
        raise SystemExit(f"Excel file not found: {excel_path}")
    if not images_root.exists():
        raise SystemExit(f"Images root not found: {images_root}")

    ensure_dir(output_root)

    # Read Excel file with better error handling
    print(f"Reading Excel file: {excel_path}")
    try:
        df = get_excel_reader(excel_path)
        if df is None or df.empty:
            raise ValueError("The Excel file is empty or could not be read")
        print(f"Successfully read Excel file with {len(df)} rows")
    except Exception as e:
        print(f"Error: {e}")
        # Try reading as CSV as last resort
        try:
            print("Trying to read as CSV...")
            df = pd.read_csv(excel_path, sep=None, engine='python')
            print(f"Successfully read as CSV with {len(df)} rows")
        except Exception as csv_err:
            print(f"Failed to read as CSV: {csv_err}")
            raise SystemExit("Could not read the input file as Excel or CSV")

    colnames = [str(c) for c in df.columns]

    values: List[str] = []
    if args.column in df.columns:
        values = [str(v) for v in df[args.column].dropna().tolist()]
    else:
        # Auto-detect across all columns
        for c in df.columns:
            for v in df[c].dropna().tolist():
                s = str(v).strip()
                if OBJECT_REGEX.match(s):
                    values.append(s)

    # Deduplicate while preserving order
    seen = set()
    unique_values: List[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            unique_values.append(v)

    report_rows = []
    total_copied = 0

    for raw in unique_values:
        parsed = parse_object_number(raw)
        if not parsed:
            report_rows.append({
                "object": raw,
                "year": "",
                "pattern": "",
                "matches": 0,
                "copied": 0,
                "note": "parse_failed",
            })
            continue
        original, prefix, year, code, variant = parsed
        search_prefix = build_search_prefix(prefix, year, code, variant)
        matches = find_matching_files(images_root, year, search_prefix)

        if args.make_subdirs:
            dest_dir = output_root / search_prefix
        else:
            dest_dir = output_root
        ensure_dir(dest_dir)

        copied_for_object = 0
        for src in matches:
            dest = dest_dir / src.name
            try:
                shutil.copy2(src, dest)
                copied_for_object += 1
            except Exception as e:
                report_rows.append({
                    "object": original,
                    "year": year,
                    "pattern": search_prefix,
                    "matches": len(matches),
                    "copied": copied_for_object,
                    "note": f"copy_error:{e}",
                })
        total_copied += copied_for_object

        report_rows.append({
            "object": original,
            "year": year,
            "pattern": search_prefix,
            "matches": len(matches),
            "copied": copied_for_object,
            "note": "ok" if copied_for_object == len(matches) else "partial_or_none",
        })

    # Write report CSV
    report_path = output_root / "copy_report.csv"
    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["object", "year", "pattern", "matches", "copied", "note"])
        writer.writeheader()
        for row in report_rows:
            writer.writerow(row)

    print(f"Processed {len(unique_values)} objects. Total files copied: {total_copied}.")
    print(f"Report written to: {report_path}")


if __name__ == "__main__":
    main()
