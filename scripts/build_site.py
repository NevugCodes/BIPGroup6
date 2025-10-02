
# -*- coding: utf-8 -*-
import os
import re
import html
from pathlib import Path

import pandas as pd

# ---------- Config ----------
BASE_DIR = Path(".")  # run from your project root
IMAGES_ROOTS = [
    BASE_DIR / "output" / "aeg",
    BASE_DIR / "output" / "schreibmaschinen",
    BASE_DIR / "images",  # supports year subfolders like 1996, 1997...
]
DESCRIPTIONS_XLSX = BASE_DIR / "output" / "descriptions" / "descriptions.xlsx"
SITE_DIR = BASE_DIR / "site"
OBJECT_DIR = SITE_DIR / "object"

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# match "1-1997-0457-000-003" to sort by the two last numeric blocks
SUFFIX_RE = re.compile(r"^\d+-\d{4}-\d{4}-(\d{3})-(\d{3})$", re.IGNORECASE)

def suffix_sort_key(p: Path):
    m = SUFFIX_RE.match(p.stem)
    if m:
        a, b = m.groups()
        return (int(a), int(b), p.name.lower())
    return (999999, 999999, p.name.lower())

def collect_images_for_object(obj_id: str):
    """
    Find all images whose filename starts with '<obj_id>-', searching recursively
    under IMAGES_ROOTS (supports images/1996, images/1997, etc.).
    De-duplicate by (basename, size) case-insensitively, so the same photo stored
    in multiple roots only appears once.
    Preference order: first time we see a (name,size) pair wins (which is in the
    order of IMAGES_ROOTS defined above).
    """
    candidates = []
    prefix_lower = (obj_id + "-").lower()

    # collect
    for root in IMAGES_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in ALLOWED_EXTS:
                continue
            if not p.name.lower().startswith(prefix_lower):
                continue
            try:
                size = p.stat().st_size
            except OSError:
                size = -1
            candidates.append((p, p.name.lower(), size))

    # de-duplicate by (basename, size), keep first occurrence (root order respected)
    seen = set()
    unique = []
    for p, name_lower, size in candidates:
        key = (name_lower, size)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    # final sort by numeric suffix if present
    unique = sorted(unique, key=suffix_sort_key)
    return unique


def ensure_dirs():
    OBJECT_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "assets").mkdir(parents=True, exist_ok=True)

def write_assets():
    # Minimal CSS
    css = """
    *{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;background:#0b0e14;color:#e6e6e6}
    a{color:inherit;text-decoration:none}
    .container{display:flex;gap:16px;padding:16px;max-width:1400px;margin:0 auto}
    .left{flex:1;display:flex;flex-direction:column;gap:12px}
    .right{width:45%;min-width:420px;max-height:calc(100vh - 32px);overflow:auto;border:1px solid #2a2f3a;background:#121621;padding:16px;border-radius:12px}
    .hero{width:100%;aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;background:#11151f;border:1px solid #2a2f3a;border-radius:12px;overflow:hidden}
    .hero img{width:100%;height:100%;object-fit:contain}
    .thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:10px}
    .thumb{border:1px solid #2a2f3a;border-radius:10px;background:#11151f;cursor:pointer;overflow:hidden}
    .thumb img{width:100%;height:90px;object-fit:cover;display:block;filter:saturate(0.9)}
    .thumb.active{outline:2px solid #4b8bff}
    header.top{position:sticky;top:0;background:#0b0e14;border-bottom:1px solid #1a1f2b;padding:12px 16px;display:flex;gap:12px;align-items:center;z-index:2}
    header.top .title{font-weight:600}
    .pill{font-size:12px;padding:4px 8px;border:1px solid #2a2f3a;border-radius:999px;background:#121621}
    .meta{font-size:13px;opacity:0.9;margin-bottom:12px;line-height:1.4}
    .desc{line-height:1.6;white-space:pre-wrap}
    .index-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;padding:16px;max-width:1400px;margin:0 auto}
    .card{border:1px solid #2a2f3a;border-radius:12px;background:#121621;overflow:hidden;display:flex;flex-direction:column}
    .card .img{aspect-ratio:4/3;background:#11151f;display:flex;align-items:center;justify-content:center}
    .card .img img{width:100%;height:100%;object-fit:cover}
    .card .body{padding:12px}
    .small{opacity:.8;font-size:12px}
    """
    (SITE_DIR / "assets" / "styles.css").write_text(css, encoding="utf-8")

    # Minimal index template (filled later)
    index_html = """
    <!doctype html><html lang="en"><head>
      <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <title>Catalogue – Index</title>
      <link rel="stylesheet" href="./assets/styles.css">
    </head><body>
      <header class="top"><div class="title">Catalogue Index</div></header>
      <main class="index-list">
        <!--CARDS-->
      </main>
    </body></html>
    """
    (SITE_DIR / "index.html").write_text(index_html.strip(), encoding="utf-8")

def rel_from(page_dir: Path, target: Path) -> str:
    """Return a POSIX-style relative path from a page directory to the target file."""
    try:
        rel = os.path.relpath(target, start=page_dir)
    except ValueError:
        # different drives on Windows -> fall back to absolute path
        rel = str(target)
    return Path(rel).as_posix()

def render_object_page(obj_id: str, description: str, images: list[Path]):
    # Escapes
    safe_obj = html.escape(obj_id)
    safe_desc = html.escape(description or "No description").replace("\n", "\n")

    # Convert image paths relative to the OBJECT_DIR (where pages live)
    img_srcs = [rel_from(OBJECT_DIR, p) for p in images]

    thumbs_html = "\n".join(
        f'<div class="thumb" data-src="{html.escape(src)}"><img src="{html.escape(src)}" alt=""></div>'
        for src in img_srcs
    ) if img_srcs else '<div class="small">No images found for this object.</div>'

    hero_img = html.escape(img_srcs[0]) if img_srcs else ""

    html_doc = f"""
    <!doctype html><html lang="en"><head>
      <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <title>{safe_obj} – Catalogue</title>
      <link rel="stylesheet" href="../assets/styles.css">
    </head><body>
      <header class="top">
        <a class="pill" href="../index.html">← Back</a>
        <div class="title">{safe_obj}</div>
        <div class="pill">Images: {len(img_srcs)}</div>
      </header>
      <div class="container">
        <section class="left">
          <div class="hero" id="hero">{('<img id="heroImg" src="' + hero_img + '" alt="">') if hero_img else '<div class="small">No image</div>'}</div>
          <div class="thumbs" id="thumbs">
            {thumbs_html}
          </div>
        </section>
        <aside class="right">
          <div class="meta"><strong>Object ID:</strong> {safe_obj}</div>
          <div class="desc" id="desc">{safe_desc}</div>
        </aside>
      </div>
      <script>
        (function() {{
          const thumbs = document.querySelectorAll('.thumb');
          const hero = document.getElementById('hero');
          let heroImg = document.getElementById('heroImg');
          function setActive(el) {{
            document.querySelectorAll('.thumb.active').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
          }}
          thumbs.forEach((t,i) => {{
            if (i===0) setActive(t);
            t.addEventListener('click', () => {{
              const src = t.getAttribute('data-src');
              if (!heroImg) {{
                heroImg = document.createElement('img');
                heroImg.id = 'heroImg';
                hero.appendChild(heroImg);
              }}
              heroImg.src = src;
              setActive(t);
            }});
          }});
        }})();
      </script>
    </body></html>
    """
    out_path = (Path(OBJECT_DIR) / f"{obj_id}.html")
    out_path.write_text(html_doc, encoding="utf-8")
    return out_path

def append_index_card(cards: list[str], obj_id: str, first_img_path: Path | None):
    if first_img_path is not None:
        img_html = f"<img src=\"{html.escape(rel_from(SITE_DIR, first_img_path))}\" alt=\"\">"
    else:
        img_html = "<div class=\"small\">No image</div>"
    card = f"""
    <a class="card" href="object/{html.escape(obj_id)}.html">
      <div class="img">{img_html}</div>
      <div class="body">
        <div><strong>{html.escape(obj_id)}</strong></div>
        <div class="small">Open entry -></div>
      </div>
    </a>
    """
    cards.append(card)

def finalize_index(cards: list[str]):
    index_file = SITE_DIR / "index.html"
    raw = index_file.read_text(encoding="utf-8")
    html_doc = raw.replace("<!--CARDS-->", "\n".join(cards))
    index_file.write_text(html_doc, encoding="utf-8")

def main():
    ensure_dirs()
    write_assets()

    if not DESCRIPTIONS_XLSX.exists():
        raise SystemExit(f"File not found: {DESCRIPTIONS_XLSX}")

    df = pd.read_excel(DESCRIPTIONS_XLSX)
    # Accept typical headings from your pipeline
    col_map = {c.lower(): c for c in df.columns}
    if "object_id" not in col_map or "description" not in col_map:
        raise SystemExit("Expected columns 'object_id' and 'description' in descriptions.xlsx")
    obj_col = col_map["object_id"]
    desc_col = col_map["description"]

    cards = []
    total = 0

    for row in df.itertuples(index=False):
        obj_id = str(getattr(row, obj_col))
        description = str(getattr(row, desc_col, "") or "")
        images = collect_images_for_object(obj_id)
        render_object_page(obj_id, description, images)
        first_img = images[0] if images else None
        append_index_card(cards, obj_id, first_img)
        total += 1

    finalize_index(cards)
    print(f"Generated site for {total} objects in: {SITE_DIR.resolve()}")

if __name__ == "__main__":
    main()
