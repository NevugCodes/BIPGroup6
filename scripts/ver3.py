# -*- coding: utf-8 -*-
import re
import shutil
from pathlib import Path
import pandas as pd

# ------------------ Pfade anpassen ------------------
IMAGES_ROOT = Path("images")

SCHREIB_EXCEL = Path("data/Liste_Schreibmaschinen.xls")
AEG_EXCEL     = Path(r"data/Liste_AEG Produktsammlung.xls")

# Zielordner
OUT_SCHREIB = Path("output/schreibmaschinen")
OUT_AEG     = Path("output/aeg")
LOG_DIR     = Path("output/logs")

# ------------------ Einstellungen -------------------
T1_HEADER = "t1"  # Spaltenüberschrift mit den Objektnummern
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# Beispiel-Format innerhalb eines Strings:
# "1/1997/1063 0"  -> wir extrahieren 1 (g1), 1997 (year), 1063 (g3), 0 (g4)
# Nicht geankert (search!), toleriert zusätzlichen Text in der Zelle.
OBJ_RE = re.compile(r"(\d+)\s*/\s*(\d{4})\s*/\s*(\d{3,4})\s+(\d+)", re.IGNORECASE)


def read_excel_column(path: Path, header_name: str) -> pd.Series:
    """Liest eine Spalte (per Überschrift) aus .xls/.xlsx. Fällt robust auf Auto-Engine zurück."""
    try:
        df = pd.read_excel(path, engine="xlrd")
    except Exception:
        df = pd.read_excel(path)  # Auto-Engine
    if header_name not in df.columns:
        raise KeyError(
            f"Spaltenüberschrift '{header_name}' nicht gefunden. "
            f"Verfügbare Spalten: {list(df.columns)} in Datei {path}"
        )
    return df[header_name]


def parse_object_number(raw) -> dict | None:
    """
    Extrahiert Objektnummer aus beliebigem Zelltext.
    Gibt Basispräfix zurück, das ALLE Serienblöcke matcht:
      base_prefix = '{g1}-{year}-{g3}-'   (z. B. '1-1997-1063-')
    Außerdem year für den Jahresordner.
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
    Sucht in images/<year>/ nach Dateien, die mit base_prefix beginnen
    (z. B. '1-1997-1063-') – dadurch werden *alle* Serienblöcke (000, 001, …) erfasst.
    """
    year_dir = images_root / year
    if not year_dir.is_dir():
        return [], f"Jahresordner fehlt: {year_dir}"

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
    Kopiert gefundene Dateien in out_dir.
    - vermeidet doppelte Zielnamen (seen_outputs)
    - vermeidet das Kopieren derselben QUELLDATEI mehrfach (seen_src_paths)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(files):
        # gleiche Quelle nicht erneut kopieren
        src_key = str(src.resolve()).lower()
        if src_key in seen_src_paths:
            continue
        seen_src_paths.add(src_key)

        dst = out_dir / src.name
        final_dst = dst
        n = 1
        # Zielnamen-Kollisionen vermeiden
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
    Verarbeitet eine Liste:
    - Liest Spalte `header_name`
    - Optional nur Slice der Zeilen
    - dedupliziert Eingaben
    - Sucht Bilder und kopiert sie ins Ziel
    - Schreibt Logs
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    series = read_excel_column(path_excel, header_name)
    if row_slice is not None:
        series = series.iloc[row_slice]

    # NaN entfernen, Whitespace trimmen, Duplikate entfernen
    series = series.dropna().map(lambda x: x.strip() if isinstance(x, str) else x).drop_duplicates()

    copied_rows = []
    misses_rows = []

    seen_outputs = set()      # Ziel-Dateinamen (lower)
    seen_src_paths = set()    # absolute Quellpfade (lower)
    seen_prefixes = set()     # (year, base_prefix) Paare

    for idx, raw in series.items():
        parsed = parse_object_number(raw)
        if not parsed:
            misses_rows.append({
                "row_index": idx,
                "raw_T1": raw,
                "reason": "Keine Objektnummer im Format '1/1997/1063 0' gefunden"
            })
            continue

        base_prefix = parsed["base_prefix"]
        year = parsed["year"]

        # Falls dieselbe Objektgruppe mehrfach in der Liste steht → nur einmal verarbeiten
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
                "reason": f"Keine Dateien mit Präfix '{base_prefix}' in images/{year}"
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

    # Logs schreiben
    copied_df = pd.DataFrame(copied_rows)
    misses_df = pd.DataFrame(misses_rows)

    copied_csv = LOG_DIR / f"{log_prefix}_copied.csv"
    misses_csv = LOG_DIR / f"{log_prefix}_misses.csv"

    copied_df.to_csv(copied_csv, index=False, encoding="utf-8")
    misses_df.to_csv(misses_csv, index=False, encoding="utf-8")

    print(f"== {log_prefix}: Zusammenfassung ==")
    print(f"Gefundene/Exportierte Bilddateien: {len(copied_rows)}")
    print(f"Nicht gematchte Einträge: {len(misses_rows)}")
    print(f"Log (Treffer): {copied_csv}")
    print(f"Log (Fehler/Keine Treffer): {misses_csv}")
    print(f"Ausgabeverzeichnis: {out_dir.resolve()}")


def main():
    # 1) Schreibmaschinen: alle Zeilen
    process_list(
        path_excel=SCHREIB_EXCEL,
        out_dir=OUT_SCHREIB,
        log_prefix="schreibmaschinen",
        row_slice=None,  # alle
        header_name=T1_HEADER
    )

    # 2) AEG: nur Excel-Zeilen 2000–2500
    # Excel zählt ab 1 inkl. Header; pandas iloc ist 0-basiert, end-exklusiv.
    # => 2000..2500 ≈ iloc[1999:2500]
    process_list(
        path_excel=AEG_EXCEL,
        out_dir=OUT_AEG,
        log_prefix="aeg_2000_2500",
        row_slice=slice(3500, 4500),
        header_name=T1_HEADER
    )


if __name__ == "__main__":
    main()
