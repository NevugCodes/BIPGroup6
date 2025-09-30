# -*- coding: utf-8 -*-
import base64
import re
import time
import random
from pathlib import Path
from collections import defaultdict
import pandas as pd
from openai import OpenAI

# Optional: Pillow zum Verkleinern der Bilder
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# ---------------- Einstellungen ----------------
INPUT_DIRS = [Path(r"output\aeg"), Path(r"output\schreibmaschinen")]
DESCRIPTIONS_XLSX = Path(r"output\descriptions\descriptions.xlsx")

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
MAX_IMAGES_PER_OBJECT = 6            # <— weniger Bilder = weniger Tokens
RESIZE_MAX_SIDE = 1024               # <— längste Seite (px); None = nicht skalieren
REQUEST_COOLDOWN_SEC = 2.5           # <— Pause zwischen erfolgreichen Requests
MAX_RETRIES = 6                      # <— wie oft bei 429/Serverfehlern erneut versuchen
PROMPT = """You are a professional museum curator and historian. You write accurate, source-based catalogue entries for museums. Always follow the strict style of museum documentation: precise, academic, structured, multilingual. You must not invent facts. If information is missing, mark as “not available” and, if appropriate, cautiously estimate and clearly label it as an assumption. Never fabricate sources, catalogue numbers, or provenance. If no valid reference is found, write “not available”.
Create a museum catalogue entry for the following object using the provided photos and metadata.
Perform a systematic visual analysis of the photos and directly integrate it into the Description section. Do not output the analysis separately. In the description, use only what is (a) visible, (b) in the metadata, or (c) in cited sources. Mark any inference as an assumption.
1. Inscriptions & labels
Read and transcribe all visible inscriptions, plaques, decals and stamps (brand, model, factory, voltage/amps plates, patent marks, serials). Quote them in double quotes in the text. If characters are unclear, mark them as [?] without guessing.
2. Controls & layout
Identify the functional layout: keyboard (QWERTY/QWERTZ/AZERTY; accents/umlauts; special keys such as Tab, Margin Release, Shift Lock), levers, selectors, knobs, scales, rulers.
3. Materials & finish
Describe materials you can see with certainty (painted steel, nickel-plated parts, glass keytops, rubber platen, plastic/Bakelite, wood). Place any uncertain materials after the certain ones, labelled “assumption”.
4. Condition / alterations
Record visible wear, replacements (non-original cable, missing covers), repairs or added labels.
5. Dating cues (use cautiously)
Mention style cues only as assumptions (e.g. plug style, logo typography, key legends). Never date solely from style if metadata contradicts it.
6. Scale / dimensions
Do not estimate dimensions from photos unless a calibrated scale or ruler is visible. If it is, you may give an approximate measurement and mark it as an assumption.
7. Conflict check
If metadata and photos conflict (e.g., different model name), explicitly flag “inconsistency detected” in the description. Do not attempt to resolve inconsistencies; only report them clearly.
8. Provenance evidence
Note any inventory tags, transport labels or collection stickers visible on the object (without inventing history).
Output rule: keep the main Description in full paragraphs. Use phrases like (visible in photos), (metadata), (source), or (assumption) only the first time a new category of information is introduced (e.g., first mention of inscriptions, materials, or controls). Afterwards, continue the narrative smoothly without repeating the tag each time.______________
Languages: Provide four separate full versions of the entry in: English, German, Polish, French.
All four versions must be identical in structure and detail. Do not summarize or shorten. Always keep all four versions detailed, don’t ask if it needs to be shorten.______________
Structure (always follow this order):
Object Title / Type:
* Write in the museum style: [Object type] [Brand + Model] [Function/identifier], Nr. [inventory/catalogue number]
* Always include an inventory/catalogue number in the title if metadata provides it; otherwise write ‘Nr. not available’.
Source Availability Statement:
* At the start of each language version, write one clear sentence stating whether an online description for this object was found.
* If an online source exists about the exact model (e.g., “Mercedes Elektra”), write: “Online description available: [source]”.
* If only general sources about the manufacturer or brand exist, write: “General online background available (e.g., manufacturer history), but no specific description of this model found.”
* If nothing relevant exists, write: “No online description found. Entry generated from metadata and photo analysis.”
* Always specify explicitly the exact type of source found (e.g., Wikipedia page, company official website, museum online database, literature reference). Do not write only ‘manufacturer history’ or ‘general background’ – always name the concrete source.
Description:
* Provide a long, detailed, academic-style description (length depends on available info). Keep it informative but avoid redundant repetition.
* Include technical details (mechanism, function, materials, innovations).
* Add social/cultural/historical context (role of this object in society, industry, or everyday life). Explain the significance of the object in its historical moment (e.g., design philosophy, industrial competition, company expansion). If designers are known, highlight their later influence in design culture.• If possible, compare to earlier or later models.
* If assumptions are made, explicitly mark them (e.g., “likely from the 1930s [assumption based on design style]”).
* Include relevant manufacturer/company details if available.
* Always cite sources when general knowledge is used (e.g., museum catalogues, manufacturer archives, reliable literature).
Material / Technique:
List materials (metal, rubber, fabric, wood, etc.). If not available, write not available. If possible, estimate.
Always list certain materials first, and assumptions separately at the end of the Materials section.
Dimensions:
H x W x D (mm) + weight (kg). If not available, write not available. If possible, estimate (mark as assumption).
Provenance / Ownership history:
Write collection history if available, otherwise not available.
Links / Sources:
* Always include references for facts that are not visible in the photos (e.g., museum archives, catalogues, manufacturer websites, literature).
* If no sources are available, note: “No external sources found, description based on visual analysis of the photos.”
* Format the sources into three categories:
– Primary museum metadata (inventory numbers, collection notes, archive references).
– Literature references (books, catalogues, academic papers).
– Web resources (official museum websites, online databases).
* If a category has no data, mark it as “not available”.
______________
Important Rules:
* Do NOT hallucinate or invent facts.
* If uncertain, state clearly (“uncertain / not available”).
* Ensure consistency with museum catalogue style.
* Write in full paragraphs (not bullet points) for the description.
* Adapt technical/historical language to sound professional, not promotional."""


client = OpenAI()  # nutzt OPENAI_API_KEY aus der Umgebung

# --------------- Hilfsfunktionen ---------------
OBJ_ID_PATTERN = re.compile(r"^(\d+)-(\d{4})-(\d{4})", re.IGNORECASE)
WAIT_HINT_PATTERN = re.compile(r"try again in ([0-9]+(\.[0-9]+)?)s", re.IGNORECASE)

def extract_object_id(filename: str) -> str | None:
    m = OBJ_ID_PATTERN.match(filename)
    return "-".join(m.groups()) if m else None

def is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in ALLOWED_EXTS

def collect_images_by_object(dirs: list[Path]) -> dict[str, list[Path]]:
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
    for k in list(groups.keys()):
        groups[k] = sorted(groups[k], key=lambda p: p.name.lower())
    return dict(groups)

def load_and_optionally_resize(path: Path) -> tuple[str, bytes]:
    """Liest ein Bild, skaliert optional herunter und gibt (mime, bytes) zurück."""
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
            im = im.convert("RGB")  # stabiler für exotische Modi
            w, h = im.size
            max_side = max(w, h)
            if max_side > RESIZE_MAX_SIDE:
                scale = RESIZE_MAX_SIDE / float(max_side)
                new_size = (int(w * scale), int(h * scale))
                im = im.resize(new_size, Image.LANCZOS)
            # Für Token-/Größenreduktion als JPEG in moderater Qualität exportieren
            from io import BytesIO
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=80, optimize=True)
            return "image/jpeg", buf.getvalue()
    except Exception:
        # Falls Pillow scheitert, gib Original zurück
        return mime, raw

def build_message_content(prompt: str, image_paths: list[Path]) -> list[dict]:
    content = [{"type": "text", "text": prompt}]
    for p in image_paths:
        try:
            mime, data = load_and_optionally_resize(p)
            b64 = base64.b64encode(data).decode("utf-8")
        except Exception as e:
            print(f"[WARN] Konnte Bild nicht verarbeiten: {p} ({e})")
            continue
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"}
        })
    return content

def call_openai_with_retry(content: list[dict]) -> str:
    wait = 2.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": content}],
                temperature=0.2,
            )
            time.sleep(REQUEST_COOLDOWN_SEC)  # Grund-Cooldown nach Erfolg
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate_limit" in msg.lower():
                # Versuche, die empfohlene Wartezeit aus der Meldung zu lesen
                m = WAIT_HINT_PATTERN.search(msg)
                hinted = float(m.group(1)) if m else None
                sleep_for = hinted + 0.5 if hinted else wait
                sleep_for += random.uniform(0, 0.5)  # jitter
                print(f"[RATE LIMIT] Warte {sleep_for:.2f}s (Versuch {attempt}/{MAX_RETRIES})")
                time.sleep(sleep_for)
                wait = min(wait * 1.8, 30.0)  # exponentiell, gedeckelt
                continue
            # Server-Fehler (5xx) ebenfalls retryen
            if any(code in msg for code in ["500", "502", "503", "504"]):
                sleep_for = wait + random.uniform(0, 0.5)
                print(f"[SERVER] Warte {sleep_for:.2f}s (Versuch {attempt}/{MAX_RETRIES})")
                time.sleep(sleep_for)
                wait = min(wait * 1.8, 30.0)
                continue
            # andere Fehler nicht retryen
            raise
    raise RuntimeError("Maximale Anzahl Retries erreicht (Rate Limit / Serverfehler).")

def describe_object(obj_id: str, image_paths: list[Path]) -> str:
    selected = image_paths[:MAX_IMAGES_PER_OBJECT]
    content = build_message_content(PROMPT, selected)
    return call_openai_with_retry(content)

# --------------------- Main ---------------------
def main():
    groups = collect_images_by_object(INPUT_DIRS)
    if not groups:
        print("Keine Bilder gefunden.")
        return

    # Resume: bereits vorhandene Excel laden
    DESCRIPTIONS_XLSX.parent.mkdir(parents=True, exist_ok=True)
    if DESCRIPTIONS_XLSX.exists():
        df_exist = pd.read_excel(DESCRIPTIONS_XLSX)
        done = {str(x).strip() for x in df_exist.get("object_id", []) if pd.notna(x)}
        rows = df_exist.to_dict("records")
        print(f"Resume: {len(done)} bereits vorhanden – werden übersprungen.")
    else:
        done = set()
        rows = []

    all_objs = sorted(groups.keys())
    total = len(all_objs)
    print(f"Gefundene Objekte: {total}")

    for i, obj_id in enumerate(all_objs, start=1):
        if obj_id in done:
            print(f"[{i}/{total}] Überspringe {obj_id} (bereits in Excel).")
            continue
        imgs = groups[obj_id]
        print(f"[{i}/{total}] Beschreibe Objekt {obj_id} mit {len(imgs)} Bild(er)n...")
        try:
            description = describe_object(obj_id, imgs)
        except Exception as e:
            print(f"[ERROR] Beschreibung fehlgeschlagen für {obj_id}: {e}")
            description = f"[Fehler bei der Beschreibung: {e}]"
        rows.append({"object_id": obj_id, "description": description})

        # Nach jedem Objekt zwischenspeichern (robust bei Abbrüchen)
        pd.DataFrame(rows, columns=["object_id", "description"]).to_excel(
            DESCRIPTIONS_XLSX, index=False
        )

    print(f"Fertig. Datei geschrieben: {DESCRIPTIONS_XLSX}")

if __name__ == "__main__":
    main()
