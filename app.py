"""
Simple web UI for the name-table generator.

Run:  python3 app.py
Then open http://localhost:5000
"""

import csv
import io
import os
import re
import zipfile
from urllib.parse import parse_qs

from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify, send_from_directory

from paths import resource_path, output_dir, slugify, base_dir, is_frozen

app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)
app.secret_key = "dev-only-not-secret"  # fine for a local prototype
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400

class VercelPathMiddleware:
    """WSGI middleware to normalize PATH_INFO from Vercel proxy/rewrites."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = parse_qs(environ.get("QUERY_STRING", ""))
        if "path" in qs and qs["path"]:
            p = "/" + qs["path"][0].lstrip("/")
            environ["PATH_INFO"] = p
        elif environ.get("HTTP_X_FORWARDED_URI"):
            environ["PATH_INFO"] = environ["HTTP_X_FORWARDED_URI"].split("?")[0]
        elif environ.get("HTTP_X_MATCHED_PATH"):
            environ["PATH_INFO"] = environ["HTTP_X_MATCHED_PATH"].split("?")[0]
        else:
            path = environ.get("PATH_INFO", "")
            if path in ("/api/index.py", "/api/index", "/api", ""):
                environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)

OUTPUT_DIR = output_dir()


@app.route("/", methods=["GET"])
@app.route("/nametable", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/notepad", methods=["GET"])
def notepad():
    return render_template("notepad.html")


@app.route("/generate_notepad", methods=["POST"])
def generate_notepad_route():
    import json
    import generate_notepad
    data = None
    if request.is_json:
        data = request.get_json(silent=True)
    if not data:
        data = request.form.to_dict()
        if "pendamping_list" in data and isinstance(data["pendamping_list"], str):
            try:
                data["pendamping_list"] = json.loads(data["pendamping_list"])
            except Exception:
                data["pendamping_list"] = []
        if "peserta_list" in data and isinstance(data["peserta_list"], str):
            try:
                data["peserta_list"] = json.loads(data["peserta_list"])
            except Exception:
                data["peserta_list"] = []
        if "use_numbering" in data:
            data["use_numbering"] = data["use_numbering"] in ("true", "1", "on", True)

    if not data:
        return "Data tidak valid", 400

    pdf_bytes = generate_notepad.build_notepad_pdf(data)
    title = (data.get("title") or "Notepad").strip()
    slug = slugify(title)[:40] if title else "notepad"
    filename = f"Notepad_{slug}.pdf"
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )




@app.route("/favicon.ico", methods=["GET"])
def favicon():
    ico_path = os.path.join(resource_path("static"), "favicon.ico")
    if os.path.exists(ico_path):
        return send_file(ico_path, mimetype="image/vnd.microsoft.icon")
    return send_file(os.path.join(resource_path("static"), "logo_kemnaker.png"), mimetype="image/png")


@app.route("/sample-csv", methods=["GET"])
def download_sample_csv():
    csv_path = os.path.join(base_dir(), "sample_names.csv")
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True, download_name="sample_names.csv", mimetype="text/csv")
    flash("Sample CSV file not found.")
    return redirect(url_for("index"))


@app.route("/api/kemnaker-units", methods=["GET"])
@app.route("/kemnaker_data", methods=["GET"])
def api_kemnaker_units():
    import kemnaker_data
    force_refresh = request.args.get("refresh", "0") in ("1", "true", "True")
    data = kemnaker_data.get_kemnaker_data(force_refresh=force_refresh)
    resp = jsonify(data)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


import hashlib
import tempfile

if os.environ.get("VERCEL"):
    PHOTO_CACHE_DIR = os.path.join(tempfile.gettempdir(), "photo_cache")
elif is_frozen():
    PHOTO_CACHE_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "NameTableGenerator",
        "photo_cache"
    )
else:
    PHOTO_CACHE_DIR = os.path.join(base_dir(), "photo_cache")
os.makedirs(PHOTO_CACHE_DIR, exist_ok=True)

@app.route("/api/kemnaker-photo")
def proxy_kemnaker_photo():
    raw_url = request.args.get("url", "").strip()
    if not raw_url or not raw_url.startswith("https://portal.kemnaker.go.id/"):
        return ("Invalid URL", 400)
    
    # On Vercel or cloud environments where Kemnaker portal blocks datacenter IPs (403),
    # redirect client browser to fetch directly from portal.kemnaker.go.id
    if os.environ.get("VERCEL"):
        return redirect(raw_url, code=302)

    fname = hashlib.md5(raw_url.encode("utf-8")).hexdigest() + os.path.splitext(raw_url)[1]
    if not os.path.splitext(fname)[1]:
        fname += ".jpg"
    cache_file = os.path.join(PHOTO_CACHE_DIR, fname)
    
    if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
        return send_file(cache_file)
        
    try:
        import ssl, urllib.request
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(raw_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://portal.kemnaker.go.id/"
        })
        with urllib.request.urlopen(req, timeout=8, context=ctx) as res:
            content = res.read()
            with open(cache_file, "wb") as f:
                f.write(content)
        return send_file(cache_file)
    except Exception as e:
        return redirect(raw_url, code=302)


def _extract_card_options(form):
    """Extracts font, sizing, spacing, case, paper size, and custom asset options from request.form."""
    sides = form.get("sides", "2").strip()
    font_name_choice = form.get("font_name_choice", form.get("font_choice", "Montserrat")).strip()
    font_pos_choice = form.get("font_pos_choice", form.get("font_choice", "Montserrat")).strip()
    font_size_name = form.get("font_size_name", "auto").strip()
    font_size_pos = form.get("font_size_pos", "auto").strip()
    spacing_gap = form.get("spacing_gap", "40").strip()
    spacing_is_manual = form.get("spacing_is_manual", "0").strip()
    horizontal_offset = form.get("horizontal_offset", "0").strip()
    text_case = form.get("text_case", "uppercase").strip()
    paper_size = form.get("paper_size", "a4").strip()

    custom_bg_data = form.get("custom_bg_data", "").strip()
    custom_font_name_data = form.get("custom_font_name_data", form.get("custom_font_data", "")).strip()
    custom_font_name_filename = form.get("custom_font_name_filename", form.get("custom_font_name", "")).strip()
    custom_font_pos_data = form.get("custom_font_pos_data", "").strip()
    custom_font_pos_filename = form.get("custom_font_pos_filename", "").strip()

    return {
        "sides": sides,
        "font_name_choice": font_name_choice,
        "font_pos_choice": font_pos_choice,
        "font_size_name": font_size_name,
        "font_size_pos": font_size_pos,
        "spacing_gap": spacing_gap,
        "spacing_is_manual": spacing_is_manual,
        "horizontal_offset": horizontal_offset,
        "text_case": text_case,
        "paper_size": paper_size,
        "custom_bg_data": custom_bg_data,
        "custom_font_name_data": custom_font_name_data,
        "custom_font_name_filename": custom_font_name_filename,
        "custom_font_pos_data": custom_font_pos_data,
        "custom_font_pos_filename": custom_font_pos_filename,
    }


@app.route("/generate", methods=["POST"])
def generate_single():
    import kemnaker_data
    from generate import (
        format_bulk_name, clean_titles, clean_position_text,
        strip_trailing_punctuation, sanitize_text
    )
    from generate_html import build_pdf_with_fallback as build_pdf

    content_mode = request.form.get("content_mode", "both").strip()
    if content_mode not in ("both", "name_only", "position_only"):
        content_mode = "both"

    input_source = request.form.get("input_source", "tamu").strip().lower()
    raw_name = sanitize_text(request.form.get("name", ""), preserve_newlines=(content_mode == "name_only"))
    raw_position = sanitize_text(request.form.get("position", ""), preserve_newlines=True)

    opts = _extract_card_options(request.form)

    if input_source == "kemnaker":
        raw_position = kemnaker_data.expand_kemnaker_position(raw_position)
        cleaned_position = clean_position_text(raw_position)
        if content_mode == "name_only" and "\n" in raw_name:
            cleaned_name = "\n".join(clean_titles(part) for part in raw_name.splitlines() if part.strip())
        else:
            cleaned_name = format_bulk_name(raw_name, max_len=24, font=opts.get("font_name_choice"), font_size=opts.get("font_size_name"))
    else:
        # Manual Single Input (Tamu / Manual): preserve user's full name, titles, and position text verbatim
        cleaned_name = raw_name
        cleaned_position = raw_position

    if content_mode == "name_only":
        name = strip_trailing_punctuation(cleaned_name.strip())
        position = ""
        if not name:
            flash("Silakan isi nama terlebih dahulu.")
            return redirect(url_for("index"))
    elif content_mode == "position_only":
        name = ""
        position = strip_trailing_punctuation(cleaned_position.strip())
        if not position:
            flash("Silakan isi jabatan terlebih dahulu.")
            return redirect(url_for("index"))
    else:
        name = strip_trailing_punctuation(cleaned_name.strip())
        position = strip_trailing_punctuation(cleaned_position.strip())
        if not name or not position:
            flash("Silakan isi nama dan jabatan.")
            return redirect(url_for("index"))

    slug_base = name or position or "nametag"
    out_path = os.path.join(OUTPUT_DIR, f"{slugify(slug_base)}.pdf")
    build_pdf(
        name, position, out_path,
        content_mode=content_mode,
        clean_titles_flag=(input_source == "kemnaker"),
        **opts
    )

    return send_file(out_path, as_attachment=True,
                      download_name=f"{slugify(slug_base)}.pdf")


@app.route("/batch", methods=["POST"])
@app.route("/generate_batch", methods=["POST"])
def generate_batch():
    import kemnaker_data
    from generate import (
        split_name_and_position, format_bulk_name,
        clean_position_text, strip_trailing_punctuation, deduplicate_bulk_rows
    )
    from generate_html import build_pdf_multipage

    content_mode = request.form.get("content_mode", "both").strip()
    if content_mode not in ("both", "name_only", "position_only"):
        content_mode = "both"

    input_source = request.form.get("input_source", "tamu").strip().lower()
    bulk_text = request.form.get("bulk_data", "").strip()
    file = request.files.get("csv_file")

    opts = _extract_card_options(request.form)
    n_font = opts.get("font_name_choice")
    n_size = opts.get("font_size_name")

    rows = []

    # 1. Direct bulk textarea input (supports any delimiter, tabs, parentheses, etc.)
    if bulk_text:
        lines = [l for l in bulk_text.splitlines() if l.strip()]
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            if content_mode == "name_only":
                name_raw, _ = split_name_and_position(line_str)
                cand = (name_raw or line_str).strip()
                fmt = format_bulk_name(cand, max_len=24, font=n_font, font_size=n_size) if cand else ""
                fmt = strip_trailing_punctuation(fmt[:40].strip())
                if fmt:
                    rows.append({"name": fmt, "position": ""})
            elif content_mode == "position_only":
                _, pos_raw = split_name_and_position(line_str)
                cand = (pos_raw or line_str).strip()
                fmt = clean_position_text(cand)
                fmt = strip_trailing_punctuation(fmt[:128].strip())
                if fmt:
                    rows.append({"name": "", "position": fmt})
            else:
                name_raw, pos_raw = split_name_and_position(line_str)

                # Skip header line if pasted from table
                if name_raw.lower() in ("name", "nama", "nama lengkap", "nama pegawai", "nama pejabat") and pos_raw.lower() in ("position", "jabatan", "posisi", ""):
                    continue

                fmt_name = strip_trailing_punctuation(format_bulk_name(name_raw, max_len=24, font=n_font, font_size=n_size))
                pos_clean = strip_trailing_punctuation(clean_position_text(pos_raw)[:128])
                if fmt_name:
                    rows.append({"name": fmt_name, "position": pos_clean})

    # 2. Uploaded CSV / text file fallback
    elif file and file.filename != "":
        raw_text = file.stream.read().decode("utf-8-sig", errors="ignore")
        if not raw_text.strip():
            pass
        else:
            first_lines = [l for l in raw_text.splitlines() if l.strip()][:5]
            delim = ","
            semi_cnt = sum(l.count(";") for l in first_lines)
            comma_cnt = sum(l.count(",") for l in first_lines)
            tab_cnt = sum(l.count("\t") for l in first_lines)
            if tab_cnt > comma_cnt and tab_cnt > semi_cnt:
                delim = "\t"
            elif semi_cnt > comma_cnt:
                delim = ";"

            reader = csv.reader(io.StringIO(raw_text), delimiter=delim)
            all_rows = [r for r in reader if any(c.strip() for c in r)]
            
            if all_rows:
                h0 = [c.lower().strip() for c in all_rows[0]]
                name_idx = -1
                pos_idx = -1
                has_header = False
                for c_idx, h in enumerate(h0):
                    if h in ("nama", "name", "nama lengkap", "nama pegawai", "nama pejabat"):
                        name_idx = c_idx
                        has_header = True
                    elif h in ("jabatan", "position", "posisi"):
                        pos_idx = c_idx
                        has_header = True

                data_rows = all_rows[1:] if has_header else all_rows
                for row in data_rows:
                    if not row:
                        continue
                    if name_idx != -1 and pos_idx != -1:
                        name_raw = row[name_idx].strip() if name_idx < len(row) else ""
                        pos_raw = row[pos_idx].strip() if pos_idx < len(row) else ""
                    elif len(row) >= 3 and (re.match(r'^\(?\d+[\.\)\:\-\]]*$', row[0].strip()) or row[0].strip().lower() in ('no', 'nomor')):
                        name_raw = row[1].strip()
                        pos_raw = " - ".join(c.strip() for c in row[2:] if c.strip())
                    elif len(row) >= 2:
                        name_raw = row[0].strip()
                        pos_raw = " - ".join(c.strip() for c in row[1:] if c.strip())
                    elif len(row) == 1:
                        # Single column: use split_name_and_position
                        name_raw, pos_raw = split_name_and_position(row[0].strip())
                    else:
                        continue

                    name_raw = sanitize_text(name_raw)
                    pos_raw = sanitize_text(pos_raw)

                    if content_mode == "name_only":
                        fmt = strip_trailing_punctuation(format_bulk_name(name_raw, max_len=24, font=n_font, font_size=n_size)[:40].strip()) if name_raw else ""
                        if fmt:
                            rows.append({"name": fmt, "position": ""})
                    elif content_mode == "position_only":
                        cand = pos_raw or name_raw
                        fmt = strip_trailing_punctuation(clean_position_text(cand)[:128].strip()) if cand else ""
                        if fmt:
                            rows.append({"name": "", "position": fmt})
                    else:
                        fmt_name = strip_trailing_punctuation(format_bulk_name(name_raw, max_len=24, font=n_font, font_size=n_size))
                        pos_clean = strip_trailing_punctuation(clean_position_text(pos_raw)[:128])
                        if fmt_name:
                            rows.append({"name": fmt_name, "position": pos_clean})

    # Deduplicate rows across all bulk inputs
    rows = deduplicate_bulk_rows(rows, content_mode=content_mode, source="kemnaker")

    if not rows:
        flash("Tidak ada data yang valid.")
        return redirect(url_for("index"))

    out_path = os.path.join(OUTPUT_DIR, "nametags_bulk.pdf")
    build_pdf_multipage(
        rows, out_path,
        content_mode=content_mode,
        **opts
    )

    return send_file(out_path, as_attachment=True,
                      download_name="nametags_bulk.pdf", mimetype="application/pdf")


if __name__ == "__main__":
    from paths import is_frozen

    if is_frozen():
        # Packaged desktop build: no reloader (breaks inside a frozen
        # exe), no debug mode, and open the browser automatically since
        # there's no terminal for the user to click a link from.
        import threading
        import webbrowser

        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
        app.run(debug=False, use_reloader=False, host="127.0.0.1", port=5000)
    else:
        app.run(debug=True, host="0.0.0.0", port=5000)
