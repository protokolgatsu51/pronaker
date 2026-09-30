# Name Table Generator (KEMNAKER)

Turns a name + position into a print-ready PDF name table, matching your
reference design exactly: real Myriad Pro font, both orientations (normal +
180°-flipped for two-sided table cards), automatic line wrap for long
position titles.

## What's inside

- **Live web preview** (`templates/index.html`) — type a name/position, see
  the exact card render instantly in your browser using the real Myriad Pro
  webfont.
- **PDF export** (`generate_html.py`) — renders the *same* markup through
  headless Chromium (Playwright) to produce a pixel-accurate PDF. This is the
  primary engine, used by the web app.
- **CLI fallback engine** (`generate.py`) — a reportlab/Helvetica version
  that needs no browser at all. Used automatically if Playwright/Chromium
  isn't available in your environment.
- **Flask app** (`app.py`) — the web server: single-entry form + CSV batch
  upload → zip.

## Setup

```bash
cd nametag_generator
pip install -r requirements.txt
playwright install chromium   # one-time, downloads the browser binary
```

## Run the web app

```bash
python3 app.py
```

Open **http://localhost:5000** — type a name and position, watch the live
preview, click **Generate PDF**. For bulk, upload a CSV with `name,position`
columns under **Batch (CSV)** to get a zip of one PDF per row.

## Run from the command line

```bash
# single card, real Myriad Pro (Playwright)
python3 generate_html.py "Ismail Pakaya" "Direktur Jenderal Pembinaan Pengawasan Ketenagakerjaan Keselamatan dan Kesehatan Kerja"

# single card, no-browser fallback (Helvetica)
python3 generate.py "Ismail Pakaya" "Direktur Jenderal..."

# batch from CSV (fallback engine; wire generate_html in similarly if wanted)
python3 generate.py --csv sample_names.csv --outdir output/
```

## How it's built

- `assets/bg_template.png` / `static/bg_template.png` — the card background
  (logos, bars, decorative pattern), extracted from your PSD with every
  name/position placeholder layer excluded, so it's a clean blank template.
- `static/nametag.js` — the single source of truth for layout: page size,
  center line, name/position baselines, line-wrap width. Used by **both**
  the live preview and the PDF-print target (`templates/card.html`), so
  what you see in the browser is exactly what prints.
- All geometry (page size 832.08 × 372.72pt, name baseline, the 45pt
  name→position gap, the 20pt between wrapped position lines, center line)
  was measured directly from your reference PDF with `pdfplumber` — not
  eyeballed — then verified by re-rendering and diffing against your
  original.
- `fonts/MyriadPro-*.ttf` — converted from your uploaded webfont zip for the
  reportlab fallback engine. `static/fonts/*.woff` — the originals, used
  directly by the browser/Playwright engine (no conversion needed there,
  which is also why it's the more accurate of the two engines).

## Extending it

1. **Auto-shrink name font size** for very long names that would overflow
   the card width (currently fixed at 45.86pt per spec).
2. **Batch mode on the Playwright engine** — right now batch CSV uses
   `build_pdf_with_fallback`, which already prefers Playwright per-row; for
   very large batches, reuse a single browser instance across rows instead
   of launching one per card (change loop in `app.py`/`generate_html.py`
   to launch Chromium once, open one page per row).
3. **Multi-up print layout** — combine several cards into one sheet for
   printing/cutting.
