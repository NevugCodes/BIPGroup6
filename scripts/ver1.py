# copy_images_from_T1.py
# -*- coding: utf-8 -*-
import re
import shutil
from pathlib import Path
import pandas as pd

# --- Pfade anpassen, falls nötig ---
EXCEL_PATH = Path("data/Liste_Schreibmaschinen.xls")  # falls du schon xls nutzt
IMAGES_ROOT = Path("images")

# Zielordner für Schreibmaschinen
OUTPUT_DIR = Path("output/schreibmaschinen")
LOG_DIR = Path("output/logs")

# --- Einstellungen ---
T1_HEADER = "t1"  # Spaltenüberschrift mit den Objektnummern
# Erlaube diese Bild-Endungen (Groß/klein egal)
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# Regex: "1/2024/0501 0" -> groups: 1, 2024, 0501, 0
OBJ_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d{4})\s*/\s*(\d{3,4})\s+(\d+)\s*$")

def read_excel_column(path: Path, header_name: str) -> pd.Series:
    # Pandas kann .xls mit xlrd lesen (xlrd<=1.2.0). Für .xlsx wird openpyxl genutzt.
    try:
        df = pd.read_excel(path, engine="xlrd")
    except Exception:
        # Fallback ohne Engine (falls pandas selbst wählen kann)
        df = pd.read_excel(path)
    if header_name not in df.columns:
        raise KeyError(f"Spaltenüberschrift '{header_name}' nicht gefunden. Verfügbare Spalten: {list(df.columns)}")
    return df[header_name]

def normalize_object_number(raw: str):
    """
    '1/2024/0501 0' -> {
        'prefix' : '1-2024-0501-000-',
        'year'   : '2024'
    }
    Logik: letzter Block (z.B. 0) wird zu 3-stelligem Teil '-000-'
    """
    if not isinstance(raw, str):
        return None
    m = OBJ_RE.match(raw)
    if not m:
        return None
    g1, year, g3, g4 = m.groups()
    # g3 (z.B. 0501) belassen wie gesehen (führende Nullen sind wichtig)
    # g4 als dreistellig (000, 001, ...)
    g4_3 = f"{int(g4):03d}"
    prefix = f"{g1}-{year}-{g3}-{g4_3}-"  # z.B. 1-2024-0501-000-
    return {"prefix": prefix, "year": year}

def find_matching_files(images_root: Path, year: str, prefix: str):
    """
    Sucht im Ordner images/<year>/ nach Dateien, die mit prefix beginnen
    und eine der erlaubten Endungen besitzen (case-insensitiv).
    """
    year_dir = images_root / year
    if not year_dir.is_dir():
        return [], f"Jahresordner fehlt: {year_dir}"

    matches = []
    # Durch alle Dateien laufen (schnell genug; wenn sehr groß, könnte man vorsortieren)
    for p in year_dir.iterdir():
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in ALLOWED_EXTS:
            continue
        # Case-insensitives Startswith: vergleiche in gleicher Groß/Kleinschreibung
        if p.name.lower().startswith(prefix.lower()):
            matches.append(p)
    return matches, None

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    t1_series = read_excel_column(EXCEL_PATH, T1_HEADER)

    copied_rows = []
    misses_rows = []

    seen_outputs = set()  # um doppelte Kopien zu vermeiden

    for idx, raw in t1_series.items():
        norm = normalize_object_number(raw)
        if not norm:
            misses_rows.append({
                "row_index": idx,
                "raw_T1": raw,
                "reason": "Format nicht erkannt (sollte z.B. '1/2024/0501 0' sein)"
            })
            continue

        prefix = norm["prefix"]
        year = norm["year"]

        files, err = find_matching_files(IMAGES_ROOT, year, prefix)
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
                "reason": f"Keine Dateien mit Präfix '{prefix}' in images/{year}"
            })
            continue

        # Alle Treffer ins output kopieren
        for src in sorted(files):
            dst = OUTPUT_DIR / src.name
            # Kollisionen vermeiden: wenn Name schon kopiert wurde, hänge Index an
            final_dst = dst
            n = 1
            while final_dst.name.lower() in seen_outputs or final_dst.exists():
                final_dst = OUTPUT_DIR / (dst.stem + f"_{n}" + dst.suffix)
                n += 1
            shutil.copy2(src, final_dst)
            seen_outputs.add(final_dst.name.lower())

            copied_rows.append({
                "row_index": idx,
                "raw_T1": raw,
                "year": year,
                "prefix": prefix,
                "source_path": str(src),
                "target_path": str(final_dst)
            })

    # Logs schreiben
    copied_df = pd.DataFrame(copied_rows)
    misses_df = pd.DataFrame(misses_rows)

    copied_csv = LOG_DIR / "copied.csv"
    misses_csv = LOG_DIR / "misses.csv"

    copied_df.to_csv(copied_csv, index=False, encoding="utf-8")
    misses_df.to_csv(misses_csv, index=False, encoding="utf-8")

    print("== Zusammenfassung ==")
    print(f"Gefundene/Exportierte Bilddateien: {len(copied_rows)}")
    print(f"Nicht gematchte Einträge: {len(misses_rows)}")
    print(f"Log (Treffer): {copied_csv}")
    print(f"Log (Fehler/Keine Treffer): {misses_csv}")
    print(f"Ausgabeverzeichnis: {OUTPUT_DIR.resolve()}")

if __name__ == "__main__":
    main()
