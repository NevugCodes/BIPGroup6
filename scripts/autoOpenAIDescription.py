# -*- coding: utf-8 -*-
import os
import base64
import re
import time
import random
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv, find_dotenv
import pandas as pd
from openai import OpenAI

# Optional: Pillow to resize images
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# =============== Configuration ===============
# Load .env (overrides existing system variables if present)
load_dotenv(find_dotenv(), override=True)

INPUT_DIRS = [Path(r"output\aeg"), Path(r"output\schreibmaschinen")]
DESCRIPTIONS_XLSX = Path(r"output\descriptions\descriptions.xlsx")

# Excel sources for metadata
SCHREIB_EXCEL = Path(r"data/Liste_Schreibmaschinen.xls")
AEG_EXCEL     = Path(r"data/Liste_AEG Produktsammlung.xls")

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
MAX_IMAGES_PER_OBJECT = 5            # only 5 images per object
RESIZE_MAX_SIDE = 1024               # longest side (px); None = don't resize
REQUEST_COOLDOWN_SEC = 2.5
MAX_RETRIES = 6

# >>> New: per-run batch limit <<<
BATCH_LIMIT = 10

# Prompt template with placeholders – filled dynamically per object
PROMPT_TEMPLATE = """You are a professional museum curator and historian. You write accurate, source-based catalogue entries for museums. Always follow the strict style of museum documentation: precise, academic, structured, multilingual. You must not invent facts. If information is missing, mark as “not available” and, if appropriate, cautiously estimate and clearly label it as an assumption. Never fabricate sources, catalogue numbers, or provenance. If no valid reference is found, write “not available”.
 Create a museum catalogue entry for the following object using the provided photos and metadata.
Perform a systematic visual analysis of the photos and directly integrate it into the Description section. There are multiple pictures, but they all present one object.  Do not output the analysis separately. In the description, use only what is (a) visible, (b) in the metadata, or (c) in cited sources. Mark any inference as an assumption.
Inscriptions & labels
 Read and transcribe all visible inscriptions, plaques, decals and stamps (brand, model, factory, voltage/amps plates, patent marks, serials). Quote them in double quotes in the text. If characters are unclear, mark them as [?] without guessing.
Controls & layout
 Identify the functional layout: keyboard (QWERTY/QWERTZ/AZERTY; accents/umlauts; special keys such as Tab, Margin Release, Shift Lock), levers, selectors, knobs, scales, rulers.
Materials & finish
 Describe materials you can see with certainty (painted steel, nickel-plated parts, glass keytops, rubber platen, plastic/Bakelite, wood). Place any uncertain materials after the certain ones, labelled “assumption”.
Condition / alterations
 Record visible wear, replacements (non-original cable, missing covers), repairs or added labels.
Scale / dimensions
 Do not estimate dimensions from photos unless a calibrated scale or ruler is visible. If it is, you may give an approximate measurement and mark it as an assumption.
Conflict check
 If metadata and photos conflict (e.g., different model name), explicitly flag “inconsistency detected” in the description. Do not attempt to resolve inconsistencies; only report them clearly.
Provenance evidence
 Note any inventory tags, transport labels or collection stickers visible on the object (without inventing history).
Output rule: keep the main Description in full paragraphs. Use phrases like (visible in photos), (metadata), (source), or (assumption) only the first time a new category of information is introduced (e.g., first mention of inscriptions, materials, or controls). Afterwards, continue the narrative smoothly without repeating the tag each time.
At the beginning of each catalogue entry, include a dedicated section Metadata. This block contains the raw information provided from the collection database or Excel file. It is not to be repeated as a separate subsection later, but its data must be integrated into the descriptive text and relevant sections (e.g., Object Title, Description, Materials, Dimensions).
Metadata:
Inventory number: [InventoryNo]
Contributors: [Contributors]
Materials: [Materials]
Dimensions: [Dimensions]
Location: [Location]
Descriptions of Location: [LocationDescription]
Detailed Object Name: [DetailedObjectName]
Year of Manufacture: [YearOfManufacture]

Languages: Provide four separate full versions of the entry in: English, German, Polish, French.
 All four versions must be identical in structure and detail. Do not summarize or shorten. Always keep all four versions detailed, don’t ask if it needs to be shorten.

Structure (always follow this order):
Object Title / Type:
 • Write in the museum style: [Object type] [Brand + Model] [Function/identifier], Nr. [inventory/catalogue number]
 • Always include an inventory/catalogue number in the title if metadata provides it; otherwise write ‘Nr. not available’.
Source Availability Statement:
 • At the start of each language version, write one clear sentence stating whether an online description for this object was found.
 • If an online source exists about the exact model (e.g., “Mercedes Elektra”), write: “Online description available: [source]”.
 • If only general sources about the manufacturer or brand exist, write: “General online background available (e.g., manufacturer history), but no specific description of this model found.”
 Important: If only general background exists, never treat it as object-specific.
 • If nothing relevant exists, write: “No online description found. Entry generated from metadata and photo analysis.”
 • Always specify explicitly the exact type of source found (e.g., Wikipedia page, company official website, museum online database, literature reference). Do not write only ‘manufacturer history’ or ‘general background’ – always name the concrete source.
Description:
 • Provide a long, detailed, academic-style description (length depends on available info). Keep it informative but avoid redundant repetition.
 • Include technical details (mechanism, function, materials, innovations).
 • Add social/cultural/historical context (role of this object in society, industry, or everyday life). Explain the significance of the object in its historical moment (e.g., design philosophy, industrial competition, company expansion). If designers are known, highlight their later influence in design culture.
 • If possible, compare to earlier or later models.
 • If assumptions are made, explicitly mark them (e.g., “likely from the 1930s [assumption based on design style]”).
 • Important: If no production year is provided in the metadata and no reliable source is found online, do not mention the production year at all.
 • Include relevant manufacturer/company details if available.
 • Always cite sources when general knowledge is used (e.g., museum catalogues, manufacturer archives, reliable literature).
Material / Technique:
 Refer to metadata values if provided; otherwise describe based on photos. If not available, write not available. If possible, estimate.
 Always list certain materials first, and assumptions separately at the end of the Materials section.
Dimensions:
 Refer to metadata values if provided; otherwise describe based on photos. If not available, write not available. If possible, estimate (mark as assumption).
Provenance / Ownership history:
 Write collection history if available, otherwise not available.
Links / Sources:
 - Always include references for facts that are not visible in the photos (e.g., museum archives, catalogues, manufacturer websites, literature).
 - If no sources are available, note: “No external sources found, description based on visual analysis of the photos.”
 - Format the sources into three categories:
  Primary museum metadata (inventory numbers, collection notes, archive references).
 – Literature references (books, catalogues, academic papers).
 – Web resources (official museum websites, online databases).
 - If a category has no data, mark it as “not available”.

Important Rules:
• Do NOT hallucinate or invent facts.
• If uncertain, state clearly (“uncertain / not available”).
• Ensure consistency with museum catalogue style.
• Write in full paragraphs (not bullet points) for the description.
• Adapt technical/historical language to sound professional, not promotional.
"""

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found! Make sure it is set in .env or as an environment variable.")
client = OpenAI(api_key=api_key)

# Short auth test (optional)
try:
    _ping = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "ping"}],
        temperature=0
    )
    print("[Auth Test] OK")
except Exception as e:
    raise RuntimeError(f"[Auth Test] failed: {e}")

# =============== Regex & Constants ===============
# Matches only the first three blocks: 1-1997-0457
OBJ_ID_PATTERN = re.compile(r"^(\d+)-(\d{4})-(\d{4})", re.IGNORECASE)
# For numeric sorting of suffixes: 1-1997-0457-000-003
SUFFIX_PATTERN = re.compile(r"^\d+-\d{4}-\d{4}-(\d{3})-(\d{3})", re.IGNORECASE)
# Rate-limit hint extracted from error messages
WAIT_HINT_PATTERN = re.compile(r"try again in ([0-9]+(\.[0-9]+)?)s", re.IGNORECASE)

# =============== Helpers (Object ID & Images) ===============
def extract_object_id(filename: str) -> str | None:
    """Extract the object ID (first three blocks) from the filename."""
    m = OBJ_ID_PATTERN.match(filename)
    return "-".join(m.groups()) if m else None

def suffix_sort_key(path: Path):
    """
    Provides a stable numeric sort order for files like
    1-1997-0457-000-000, 1-1997-0457-000-001, ...
    """
    stem = path.stem  # without extension
    m = SUFFIX_PATTERN.match(stem)
    if m:
        a, b = m.groups()
        return (int(a), int(b), stem.lower())
    # Fallback: lexicographic (ends up "later")
    return (999999, 999999, path.name.lower())

def is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in ALLOWED_EXTS

def unique_by_filename(paths: list[Path]) -> list[Path]:
    """Remove duplicates by filename (case-insensitive)."""
    seen = set()
    out = []
    for p in paths:
        key = p.name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out

def collect_images_by_object(dirs: list[Path]) -> dict[str, list[Path]]:
    """
    Scan all images in INPUT_DIRS and group them by object ID (first three blocks).
    Remove duplicates (same filename) and sort numerically by suffixes.
    """
    groups: dict[str, list[Path]] = defaultdict(list)
    for root in dirs:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not is_image_file(path):
                continue
            obj_id = extract_object_id(path.name)
            if obj_id:
                groups[obj_id].append(path)

    # Remove duplicates per object + numeric sort
    for k in list(groups.keys()):
        groups[k] = unique_by_filename(groups[k])
        groups[k] = sorted(groups[k], key=suffix_sort_key)

    return dict(groups)

def load_and_optionally_resize(path: Path) -> tuple[str, bytes]:
    """Read an image, optionally downscale it, and return (mime, bytes)."""
    ext = path.suffix.lower()
    mime = "image/jpeg" if ext in [".jpg", ".jpeg"] else \
           "image/png" if ext == ".png" else \
           "image/tiff" if ext in [".tif", ".tiff"] else \
           "image/bmp" if ext == ".bmp" else "application/octet-stream"

    raw = path.read_bytes()

    if not PIL_AVAILABLE or RESIZE_MAX_SIDE is None:
        return mime, raw

    try:
        with Image.open(path) as im:
            im = im.convert("RGB")  # more robust for exotic modes
            w, h = im.size
            max_side = max(w, h)
            if max_side > RESIZE_MAX_SIDE:
                scale = RESIZE_MAX_SIDE / float(max_side)
                new_size = (int(w * scale), int(h * scale))
                im = im.resize(new_size, Image.LANCZOS)
            # Export as JPEG at moderate quality to reduce tokens/size
            from io import BytesIO
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=80, optimize=True)
            return "image/jpeg", buf.getvalue()
    except Exception:
        # If Pillow fails, return original
        return mime, raw

# =============== Helpers (Excel Metadata) ===============
OBJ_FROM_T1_PATTERN = re.compile(r"^\s*(\d+)[/-](\d{4})[/-](\d{4})")

def normalize_obj_id_from_excel(value: str | None) -> str | None:
    """
    Accepts Excel formats like '1/1997/1063 0' or '1-1997-1063' and returns '1-1997-1063'.
    """
    if value is None:
        return None
    s = str(value).strip()
    m = OBJ_FROM_T1_PATTERN.search(s)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

def safe_str(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "No Data"
    s = str(x).strip()
    return s if s else "No Data"

# Column letters (identical in both files)
USECOLS_STR = "E,F,BT,BV,BY,BZ,CC,CE"

# Mapping: Excel header -> target field
EXCEL_TO_FIELDS = {
    "t1":  "InventoryNo",
    "t2":  "Contributors",
    "t3":  "Materials",
    "t5":  "Dimensions",
    "t8":  "Location",
    "t9":  "LocationDescription",
    "t12": "DetailedObjectName",
    "t14": "YearOfManufacture",
}

FIELDS_ORDER = [
    "InventoryNo",
    "Contributors",
    "Materials",
    "Dimensions",
    "Location",
    "LocationDescription",
    "DetailedObjectName",
    "YearOfManufacture",
]

def read_metadata_excel(path: Path) -> dict[str, dict]:
    """
    Reads an Excel list (XLS) and builds a mapping:
        '1-1997-1063' -> {
            'InventoryNo': ...,
            'Contributors': ...,
            ...
        }
    Uses Excel column letters via usecols.
    """
    if not path.exists():
        print(f"[WARN] Excel not found: {path}")
        return {}

    df = pd.read_excel(
        path,
        engine="xlrd",
        dtype=str,
        usecols=USECOLS_STR,
        keep_default_na=False
    )

    # Header names (expects t1, t2, t3, t5, t8, t9, t12, t14)
    cols_lower = {c.lower(): c for c in df.columns}

    # Ensure missing headers exist as empty columns
    for hx in ["t1", "t2", "t3", "t5", "t8", "t9", "t12", "t14"]:
        if hx not in cols_lower:
            df[hx] = ""

    # Normalize to lowercase column names
    for c in list(df.columns):
        if c.lower() != c:
            df.rename(columns={c: c.lower()}, inplace=True)

    mapping: dict[str, dict] = {}
    for _, row in df.iterrows():
        obj_norm = normalize_obj_id_from_excel(row.get("t1"))
        if not obj_norm:
            continue
        entry = {}
        for excel_key, field in EXCEL_TO_FIELDS.items():
            entry[field] = safe_str(row.get(excel_key))
        if entry["InventoryNo"] == "No Data":
            entry["InventoryNo"] = obj_norm
        mapping[obj_norm] = entry

    return mapping

def build_metadata_for_object(obj_id: str, maps: list[dict[str, dict]]) -> dict:
    """
    Look up obj_id in multiple metadata mappings (typewriters, AEG).
    Returns a complete dict with all FIELDS_ORDER keys ("No Data" as fallback).
    If found in both, prefer the first mapping in 'maps'.
    """
    base = {k: "No Data" for k in FIELDS_ORDER}
    for mp in maps:
        if obj_id in mp:
            found = mp[obj_id]
            for k in FIELDS_ORDER:
                if base[k] == "No Data" and k in found and safe_str(found[k]) != "No Data":
                    base[k] = safe_str(found[k])
            if all(base[k] != "No Data" for k in FIELDS_ORDER):
                break
    if base["InventoryNo"] == "No Data":
        base["InventoryNo"] = obj_id
    return base

def metadata_csv_line(meta: dict) -> str:
    """Comma-separated line in fixed order for the 3rd column."""
    return ", ".join(meta.get(k, "No Data") for k in FIELDS_ORDER)

def fill_prompt(template: str, meta: dict) -> str:
    """Replace placeholders in the prompt template with metadata."""
    text = template
    for k in FIELDS_ORDER:
        text = text.replace(f"[{k}]", meta.get(k, "No Data"))
    return text

# =============== OpenAI Call ===============
def build_message_content(prompt_text: str, image_paths: list[Path]) -> list[dict]:
    """Build the chat content array: first text, then images as data URLs."""
    content = [{"type": "text", "text": prompt_text}]
    for p in image_paths:
        try:
            mime, data = load_and_optionally_resize(p)
            b64 = base64.b64encode(data).decode("utf-8")
        except Exception as e:
            print(f"[WARN] Could not process image: {p} ({e})")
            continue
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"}
        })
    return content

def call_openai_with_retry(content: list[dict]) -> str:
    """Send request to OpenAI with backoff on rate limits/server errors."""
    wait = 2.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": content}],
                temperature=0.2,
            )
            time.sleep(REQUEST_COOLDOWN_SEC)  # base cooldown after success
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate_limit" in msg.lower():
                m = WAIT_HINT_PATTERN.search(msg)
                hinted = float(m.group(1)) if m else None
                sleep_for = hinted + 0.5 if hinted else wait
                sleep_for += random.uniform(0, 0.5)  # jitter
                print(f"[RATE LIMIT] Waiting {sleep_for:.2f}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(sleep_for)
                wait = min(wait * 1.8, 30.0)
                continue
            if any(code in msg for code in ["500", "502", "503", "504"]):
                sleep_for = wait + random.uniform(0, 0.5)
                print(f"[SERVER] Waiting {sleep_for:.2f}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(sleep_for)
                wait = min(wait * 1.8, 30.0)
                continue
            raise
    raise RuntimeError("Maximum retry attempts reached (rate limit / server error).")

def describe_object(obj_id: str, image_paths: list[Path], meta: dict) -> str:
    """
    Selects the first 5 images (numerically sorted), builds the prompt from metadata,
    and sends everything to the model.
    """
    selected = image_paths[:MAX_IMAGES_PER_OBJECT]  # limit active
    print("  -> Sending:", ", ".join(p.name for p in selected))
    prompt_text = fill_prompt(PROMPT_TEMPLATE, meta)
    content = build_message_content(prompt_text, selected)
    return call_openai_with_retry(content)

# =============== Main ===============
def main():
    # 1) Collect images
    groups = collect_images_by_object(INPUT_DIRS)
    if not groups:
        print("No images found.")
        return

    # 2) Read metadata tables and build mappings
    print("Loading metadata index...")
    md_schreib = read_metadata_excel(SCHREIB_EXCEL)
    md_aeg     = read_metadata_excel(AEG_EXCEL)
    md_maps = [md_schreib, md_aeg]  # order = priority

    # 3) Resume: load existing Excel
    DESCRIPTIONS_XLSX.parent.mkdir(parents=True, exist_ok=True)
    if DESCRIPTIONS_XLSX.exists():
        df_exist = pd.read_excel(DESCRIPTIONS_XLSX)
        done = {str(x).strip() for x in df_exist.get("object_id", []) if pd.notna(x)}
        rows = df_exist.to_dict("records")
        print(f"Resume: {len(done)} already present – will be skipped.")
    else:
        done = set()
        rows = []

    all_objs = sorted(groups.keys())
    total = len(all_objs)
    already_done_count = len(done)
    print(f"Objects found: {total}")

    # >>> New: counter for this run <<<
    processed_this_run = 0

    for obj_id in all_objs:
        if obj_id in done:
            # Already in Excel – does NOT count toward the 10
            # (We keep display index logic but skip printing per-item message here)
            continue

        # Check batch limit
        if processed_this_run >= BATCH_LIMIT:
            print(f"Batch limit {BATCH_LIMIT} reached – stopping after {processed_this_run} new descriptions.")
            break

        imgs = groups[obj_id]
        to_send = min(len(imgs), MAX_IMAGES_PER_OBJECT)

        # Display index: continues after the number already present
        display_idx = already_done_count + processed_this_run + 1
        print(f"[{display_idx}] Describe object {obj_id}: {len(imgs)} found, sending {to_send} ...")

        # 4) Build metadata for this object
        meta = build_metadata_for_object(obj_id, md_maps)
        meta_line = metadata_csv_line(meta)

        # 5) Generate description
        try:
            description = describe_object(obj_id, imgs, meta)
        except Exception as e:
            print(f"[ERROR] Description failed for {obj_id}: {e}")
            description = f"[Error during description: {e}]"

        # 6) Append row (3 columns: object_id, description, metadata)
        rows.append({
            "object_id": obj_id,
            "description": description,
            "metadata": meta_line
        })

        # Also extend 'done' immediately if the loop continues
        done.add(obj_id)
        processed_this_run += 1

        # 7) Save after each object (robust against interruptions)
        pd.DataFrame(rows, columns=["object_id", "description", "metadata"]).to_excel(
            DESCRIPTIONS_XLSX, index=False
        )

    print(f"Done. File written: {DESCRIPTIONS_XLSX}")

if __name__ == "__main__":
    main()
