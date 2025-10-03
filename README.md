# Museum Object Description Automation

This project automates the creation of multilingual, museum-style catalogue entries for digitized objects (such as typewriters and AEG machines) and generates a browsable static website for curators, researchers, and visitors.

It was developed in collaboration with **HTW Berlin**, **Akademia Leona Koźmińskiego**, **ESSCA**, **ISM** and the **Technisches Museum Berlin** as part of a collaboration project.

---

## Overview

The workflow consists of three main stages:

### 1. Image Preparation (`copy_RelevantImages.py`)
- Reads object numbers from Excel lists provided by the museum (e.g., *Liste_Schreibmaschinen.xls*, *Liste_AEG Produktsammlung.xls*).  
- Extracts and copies relevant image files from the raw `images/<year>/` folders into structured `output/` directories.  
- Logs successes and missing entries into CSV files for transparency.

### 2. Automated Descriptions (`autoOpenAIDescription.py`)
- Uses the **OpenAI API** to generate detailed, structured catalogue entries.  
- Inputs:  
  - Up to **5 images per object** (first five numerically sorted).  
  - Metadata fields from Excel (inventory number, contributors, materials, dimensions, location, detailed name, year of manufacture).  
- Outputs:  
  - Multilingual descriptions in **English, German, Polish, and French**.  
  - Strict museum documentation style (no invented facts, assumptions clearly labeled, conflicts flagged).  
  - Saved in `output/descriptions/descriptions.xlsx` with metadata and generated text.  
- Features:  
  - Batch processing limit (default: 10 objects per run).  
  - Automatic retry on API rate limits with exponential backoff.  
  - Resume support (skips already processed objects).

### 3. Website Generation (`build_site.py`)
- Converts the `descriptions.xlsx` output into a static HTML site.  
- Each object gets its own page with:  
  - Hero image and clickable thumbnails.  
  - Object ID, description text, and metadata.  
- Generates an **index page with cards** for browsing the collection.  
- Styling is lightweight, responsive, and dark-themed.

---

## Project Structure

```
.
├── data/                          # Excel lists from the museum
│   ├── Liste_Schreibmaschinen.xls
│   └── Liste_AEG Produktsammlung.xls
├── images/                        # Raw image archive (subfolders by year, e.g. 1996, 1997…)
├── output/
│   ├── schreibmaschinen/          # Copied & relevant typewriter images
│   ├── aeg/                       # Copied & relevant AEG images
│   ├── logs/                      # Logs of copied/missing images
│   └── descriptions/              # AI-generated descriptions (.xlsx)
├── site/                          # Generated static website
│   ├── index.html
│   ├── assets/styles.css
│   └── object/                    # One HTML page per object
├── copy_RelevantImages.py
├── autoOpenAIDescription.py
├── build_site.py
└── .env                           # Must contain OPENAI_API_KEY
```

---

## Requirements

- Python 3.10+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```
- Dependencies:
  - `pandas`
  - `openai`
  - `python-dotenv`
  - `xlrd`
  - `pillow` (optional, for image resizing)

---

## Usage

### 1. Copy Relevant Images
```bash
python copy_RelevantImages.py
```
- Extracts and copies relevant object images into `output/`.
- Creates CSV logs of copied and missing files.

### 2. Generate Descriptions
```bash
python autoOpenAIDescription.py
```
- Reads object metadata and images.  
- Sends them to the OpenAI API with a structured prompt.  
- Writes multilingual descriptions into `output/descriptions/descriptions.xlsx`.  
- Processes 10 new objects per run (skipping already completed).  

⚠️ Requires an **OpenAI API key** in a `.env` file:
```env
OPENAI_API_KEY=sk-...
```

### 3. Build Static Website
```bash
python build_site.py
```
- Reads `descriptions.xlsx` and images.  
- Generates a fully browsable static site in `site/`.  
- Open `site/index.html` in your browser.

---

## Example Workflow

1. Place museum Excel lists in `/data/` and raw image archive in `/images/YYYY/`.  
2. Run `copy_RelevantImages.py` → curated images in `/output/`.  
3. Run `autoOpenAIDescription.py` → AI-generated catalogue entries in `/output/descriptions/descriptions.xlsx`.  
4. Run `build_site.py` → website in `/site/`.  
5. Open `site/index.html` and browse the results.

---

## Notes

- Each object description is **non-hallucinatory**:  
  - Facts must be either visible in photos, in metadata, or from cited sources.  
  - If uncertain → marked as *assumption* or *not available*.  
  - Conflicts between photos and metadata are flagged as *inconsistencies*.  

- The project was designed to support **museum professionals** by:  
  - Reducing manual cataloguing workload.  
  - Ensuring multilingual access.  
  - Providing a clean, visual browsing interface.

---

## License

```
Custom License for HTW Berlin and Technisches Museum Berlin

Copyright (c) 2025 
Contributors: 
- Güven Adak
- Fatih Koc
- Alizée Mullard
- Katsiaryna Lagutkowa
- Gladys Toukam

Permission is hereby granted to HTW Berlin and the Technisches Museum Berlin
to use, copy, modify, and distribute this software and its documentation for
academic, research, and institutional purposes, free of charge.

No other individuals or organizations are granted rights under this license
without the express written permission of the copyright holders.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
```
