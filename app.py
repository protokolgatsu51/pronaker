"""
Simple web UI for the name-table generator.

Run:  python3 app.py
Then open http://localhost:5000
"""

import csv
import io
import os
import zipfile
from urllib.parse import parse_qs

from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify

import kemnaker_data
from generate_html import build_pdf_with_fallback as build_pdf
from generate_html import build_pdf_multipage
from paths import resource_path, output_dir, slugify, base_dir, is_frozen

app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)
app.secret_key = "dev-only-not-secret"  # fine for a local prototype

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
def index():
    return render_template("index.html")


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
def api_kemnaker_units():
    force_refresh = request.args.get("refresh", "0") in ("1", "true", "True")
    data = kemnaker_data.get_kemnaker_data(force_refresh=force_refresh)
    return jsonify(data)


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


from generate import (
    split_name_and_position, format_bulk_name, clean_titles,
    clean_position_text, strip_trailing_punctuation, deduplicate_bulk_rows
)

@app.route("/generate", methods=["POST"])
def generate_single():
    content_mode = request.form.get("content_mode", "both").strip()
    if content_mode not in ("both", "name_only", "position_only"):
        content_mode = "both"

    input_source = request.form.get("input_source", "tamu").strip().lower()
    raw_name = strip_trailing_punctuation(request.form.get("name", "").strip())
    raw_position = strip_trailing_punctuation(request.form.get("position", "").strip())

    if input_source == "kemnaker":
        raw_position = kemnaker_data.expand_kemnaker_position(raw_position)
        if content_mode == "name_only":
            name = strip_trailing_punctuation(clean_titles(raw_name)[:36].strip())
            if not kemnaker_data.is_valid_official_name(name):
                flash("Silakan pilih pejabat Kemnaker yang aktif.")
                return redirect(url_for("index"))
            position = ""
        elif content_mode == "position_only":
            name = ""
            position = strip_trailing_punctuation(clean_position_text(raw_position)[:128].strip())
            if not position:
                flash("Silakan pilih jabatan Kemnaker terlebih dahulu.")
                return redirect(url_for("index"))
        else:
            name = strip_trailing_punctuation(format_bulk_name(raw_name, 24))
            position = strip_trailing_punctuation(clean_position_text(raw_position)[:128])
            if not kemnaker_data.is_valid_official_name(name) or not position:
                flash("Silakan pilih jabatan dan pejabat Kemnaker yang aktif.")
                return redirect(url_for("index"))
    else:
        if content_mode == "name_only":
            name = strip_trailing_punctuation(raw_name[:36])
            position = ""
            if not name:
                flash("Silakan isi nama terlebih dahulu.")
                return redirect(url_for("index"))
        elif content_mode == "position_only":
            name = ""
            position = strip_trailing_punctuation(raw_position[:128])
            if not position:
                flash("Silakan isi jabatan terlebih dahulu.")
                return redirect(url_for("index"))
        else:
            name = strip_trailing_punctuation(raw_name[:24])
            position = strip_trailing_punctuation(raw_position[:128])
            if not name or not position:
                flash("Silakan isi nama dan jabatan.")
                return redirect(url_for("index"))

    sides = request.form.get("sides", "2").strip()
    font_choice = request.form.get("font_choice", "MyriadPro").strip()
    custom_bg_data = request.form.get("custom_bg_data", "").strip()
    custom_font_data = request.form.get("custom_font_data", "").strip()
    custom_font_name = request.form.get("custom_font_name", "").strip()

    slug_base = name or position or "nametag"
    out_path = os.path.join(OUTPUT_DIR, f"{slugify(slug_base)}.pdf")
    build_pdf(
        name, position, out_path,
        sides=sides,
        font_choice=font_choice,
        custom_bg_data=custom_bg_data,
        custom_font_data=custom_font_data,
        custom_font_name=custom_font_name,
        content_mode=content_mode,
    )

    return send_file(out_path, as_attachment=True,
                      download_name=f"{slugify(slug_base)}.pdf")


@app.route("/batch", methods=["POST"])
def generate_batch():
    content_mode = request.form.get("content_mode", "both").strip()
    if content_mode not in ("both", "name_only", "position_only"):
        content_mode = "both"

    bulk_text = request.form.get("bulk_data", "").strip()
    file = request.files.get("csv_file")

    sides = request.form.get("sides", "2").strip()
    font_choice = request.form.get("font_choice", "MyriadPro").strip()
    custom_bg_data = request.form.get("custom_bg_data", "").strip()
    custom_font_data = request.form.get("custom_font_data", "").strip()
    custom_font_name = request.form.get("custom_font_name", "").strip()

    rows = []

    # 1. Direct bulk textarea input (supports any delimiter, parentheses, tabs, colons, etc.)
    if bulk_text:
        lines = [l for l in bulk_text.splitlines() if l.strip()]
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            if content_mode == "name_only":
                name_raw, _ = split_name_and_position(line_str)
                cand = (name_raw or line_str).strip()
                fmt = clean_titles(cand) if cand else ""
                fmt = strip_trailing_punctuation(fmt[:36].strip())
                if fmt and kemnaker_data.is_valid_official_name(fmt):
                    rows.append({"name": fmt, "position": ""})
            elif content_mode == "position_only":
                _, pos_raw = split_name_and_position(line_str)
                cand = (pos_raw or line_str).strip()
                fmt = strip_trailing_punctuation(clean_position_text(cand)[:128].strip())
                if fmt:
                    rows.append({"name": "", "position": fmt})
            else:
                name_raw, pos_raw = split_name_and_position(line_str)

                # Skip header line if pasted from table
                if name_raw.lower() in ("name", "nama", "nama lengkap", "nama pegawai", "nama pejabat") and pos_raw.lower() in ("position", "jabatan", "posisi", ""):
                    continue

                if not kemnaker_data.is_valid_official_name(name_raw):
                    continue

                # Auto remove titles & abbreviate if > 24 chars
                fmt_name = strip_trailing_punctuation(format_bulk_name(name_raw, max_len=24))
                pos_clean = strip_trailing_punctuation(clean_position_text(pos_raw)[:128])

                if fmt_name and kemnaker_data.is_valid_official_name(fmt_name):
                    rows.append({"name": fmt_name, "position": pos_clean})

    # 2. Uploaded CSV / text file fallback
    elif file and file.filename != "":
        stream = io.StringIO(file.stream.read().decode("utf-8-sig", errors="ignore"))
        reader = csv.reader(stream)
        for i, row in enumerate(reader):
            if not row or len(row) < 1:
                continue
            # Skip header row if it contains 'name' or 'nama'
            if i == 0 and any(h.lower().strip() in ("name", "nama") for h in row):
                continue
            if content_mode == "name_only":
                name_raw = row[0].strip() if len(row) > 0 else ""
                fmt = strip_trailing_punctuation(clean_titles(name_raw)[:36].strip()) if name_raw else ""
                if fmt and kemnaker_data.is_valid_official_name(fmt):
                    rows.append({"name": fmt, "position": ""})
            elif content_mode == "position_only":
                pos_raw = row[1].strip() if len(row) > 1 and row[1].strip() else (row[0].strip() if len(row) > 0 else "")
                fmt = strip_trailing_punctuation(clean_position_text(pos_raw)[:128].strip()) if pos_raw else ""
                if fmt:
                    rows.append({"name": "", "position": fmt})
            else:
                name_raw = row[0].strip() if len(row) > 0 else ""
                pos_raw = row[1].strip() if len(row) > 1 else ""
                if not kemnaker_data.is_valid_official_name(name_raw):
                    continue
                fmt_name = strip_trailing_punctuation(format_bulk_name(name_raw, max_len=24))
                pos_clean = strip_trailing_punctuation(clean_position_text(pos_raw)[:128])
                if fmt_name and kemnaker_data.is_valid_official_name(fmt_name):
                    rows.append({"name": fmt_name, "position": pos_clean})

    # Deduplicate rows: hanya berlaku untuk Kemnaker! Untuk tamu biarkan sesuai input yang dimasukkan
    input_source = request.form.get("input_source", "tamu").strip().lower()
    if input_source == "kemnaker":
        rows = deduplicate_bulk_rows(rows, content_mode=content_mode, source="kemnaker")

    if not rows:
        flash("Tidak ada data yang valid.")
        return redirect(url_for("index"))

    out_path = os.path.join(OUTPUT_DIR, "nametags_bulk.pdf")
    build_pdf_multipage(
        rows, out_path,
        sides=sides,
        font_choice=font_choice,
        custom_bg_data=custom_bg_data,
        custom_font_data=custom_font_data,
        custom_font_name=custom_font_name,
        content_mode=content_mode,
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
