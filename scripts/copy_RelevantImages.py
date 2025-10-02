# -*- coding: utf-8 -*-
import re
import shutil
from pathlib import Path
import pandas as pd

# ------------------ Adjust paths ------------------
IMAGES_ROOT = Path("images")

SCHREIB_EXCEL = Path("data/Liste_Schreibmaschinen.xls")
AEG_EXCEL     = Path(r"data/Liste_AEG Produktsammlung.xls")

# Target folders
OUT_SCHREIB = Path("output/schreibmaschinen")
OUT_AEG     = Path("output/aeg")
LOG_DIR     = Path("output/logs")

# ------------------ Settings -------------------
T1_HEADER = "t1"  # Column header with the object numbers
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# Example format inside a string:
# "1/1997/1063 0"  -> we extract 1 (g1), 1997 (year), 1063 (g3), 0 (g4)
# Not anchored (search!), tolerates extra text in the cell.
OBJ_RE = re.compile(r"(\d+)\s*/\s*(\d{4})\s*/\s*(\d{3,4})\s+(\d+)", re.IGNORECASE)


def read_excel_column(path: Path, header_name: str) -> pd.Series:
    """Reads a column (by header name) from .xls/.xlsx. Robustly falls back to auto-engine."""
    try:
        df = pd.read_excel(path, engine="xlrd")
    except Exception:
        df = pd.read_excel(path)  # Auto-engine
    if header_name not in df.columns:
        raise KeyError(
            f"Column header '{header_name}' not found. "
            f"Available columns: {list(df.columns)} in file {path}"
        )
    return df[header_name]


def parse_object_number(raw) -> dict | None:
    """
    Extracts the object number from arbitrary cell text.
    Returns a base prefix that matches ALL series blocks:
      base_prefix = '{g1}-{year}-{g3}-'   (e.g., '1-1997-1063-')
    Also returns year for the year folder.
    """
    if not isinstance(raw, str):
        return None
    m = OBJ_RE.search(raw)
    if not m:
        return None
    g1, year, g3, _g4 = m.groups()
    base_prefix = f"{g1}-{year}-{g3}-"
    return {"base_prefix": base_prefix, "year": year}


def find_matching_files(images_root: Path, year: str, base_prefix: str):
    """
    Searches in images/<year>/ for files that start with base_prefix
    (e.g., '1-1997-1063-') – this captures *all* series blocks (000, 001, …).
    """
    year_dir = images_root / year
    if not year_dir.is_dir():
        return [], f"Missing year folder: {year_dir}"

    matches = []
    bp_l = base_prefix.lower()
    for p in year_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in ALLOWED_EXTS:
            continue
        if p.name.lower().startswith(bp_l):
            matches.append(p)
    return matches, None


def copy_matches(files, out_dir: Path, seen_outputs: set, seen_src_paths: set,
                 meta_row: dict, copied_rows: list):
    """
    Copies matched files into out_dir.
    - avoids duplicate destination names (seen_outputs)
    - avoids copying the same SOURCE FILE multiple times (seen_src_paths)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(files):
        # do not copy the same source again
        src_key = str(src.resolve()).lower()
        if src_key in seen_src_paths:
            continue
        seen_src_paths.add(src_key)

        dst = out_dir / src.name
        final_dst = dst
        n = 1
        # avoid destination name collisions
        while final_dst.name.lower() in seen_outputs or final_dst.exists():
            final_dst = out_dir / (dst.stem + f"_{n}" + dst.suffix)
            n += 1
        shutil.copy2(src, final_dst)
        seen_outputs.add(final_dst.name.lower())
        copied_rows.append({
            **meta_row,
            "source_path": str(src),
            "target_path": str(final_dst),
        })


def process_list(path_excel: Path,
                 out_dir: Path,
                 log_prefix: str,
                 row_slice: slice | None = None,
                 header_name: str = T1_HEADER):
    """
    Processes a list:
    - Reads column `header_name`
    - Optionally only a slice of rows
    - Deduplicates inputs
    - Searches images and copies them to the target
    - Writes logs
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    series = read_excel_column(path_excel, header_name)
    if row_slice is not None:
        series = series.iloc[row_slice]

    # drop NaN, trim whitespace, drop duplicates
    series = series.dropna().map(lambda x: x.strip() if isinstance(x, str) else x).drop_duplicates()

    copied_rows = []
    misses_rows = []

    seen_outputs = set()      # destination filenames (lower)
    seen_src_paths = set()    # absolute source paths (lower)
    seen_prefixes = set()     # (year, base_prefix) pairs

    for idx, raw in series.items():
        parsed = parse_object_number(raw)
        if not parsed:
            misses_rows.append({
                "row_index": idx,
                "raw_T1": raw,
                "reason": "No object number in format '1/1997/1063 0' found"
            })
            continue

        base_prefix = parsed["base_prefix"]
        year = parsed["year"]

        # If the same object group appears multiple times in the list → process only once
        key = (year, base_prefix.lower())
        if key in seen_prefixes:
            continue
        seen_prefixes.add(key)

        files, err = find_matching_files(IMAGES_ROOT, year, base_prefix)
        if err:
            misses_rows.append({
                "row_index": idx,
                "raw_T1": raw,
                "reason": err
            })
            continue

        if not files:
            misses_rows.append({
                "row_index": idx,
                "raw_T1": raw,
                "reason": f"No files with prefix '{base_prefix}' in images/{year}"
            })
            continue

        copy_matches(
            files=files,
            out_dir=out_dir,
            seen_outputs=seen_outputs,
            seen_src_paths=seen_src_paths,
            meta_row={
                "row_index": idx,
                "raw_T1": raw,
                "year": year,
                "base_prefix": base_prefix,
            },
            copied_rows=copied_rows
        )

    # Write logs
    copied_df = pd.DataFrame(copied_rows)
    misses_df = pd.DataFrame(misses_rows)

    copied_csv = LOG_DIR / f"{log_prefix}_copied.csv"
    misses_csv = LOG_DIR / f"{log_prefix}_misses.csv"

    copied_df.to_csv(copied_csv, index=False, encoding="utf-8")
    misses_df.to_csv(misses_csv, index=False, encoding="utf-8")

    print(f"== {log_prefix}: Summary ==")
    print(f"Found/Exported image files: {len(copied_rows)}")
    print(f"Unmatched entries: {len(misses_rows)}")
    print(f"Log (hits): {copied_csv}")
    print(f"Log (errors/no hits): {misses_csv}")
    print(f"Output directory: {out_dir.resolve()}")


def main():
    # 1) Typewriters: all rows
    process_list(
        path_excel=SCHREIB_EXCEL,
        out_dir=OUT_SCHREIB,
        log_prefix="schreibmaschinen",
        row_slice=None,  # all
        header_name=T1_HEADER
    )

    # 2) AEG: only Excel rows 3500–4500
    # Excel counts from 1 including header; pandas iloc is 0-based, end-exclusive.
    # => 3500..4500 ≈ iloc[3500:4500]
    process_list(
        path_excel=AEG_EXCEL,
        out_dir=OUT_AEG,
        log_prefix="aeg_3500_4500",
        row_slice=slice(3500, 4500),
        header_name=T1_HEADER
    )


if __name__ == "__main__":
    main()
