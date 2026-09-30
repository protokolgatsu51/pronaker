"""
Path helpers shared by app.py / generate.py / generate_html.py.

When run normally (`python app.py`), bundled files (templates/, static/,
assets/, fonts/) sit next to this file. When frozen into a PyInstaller
onedir build, PyInstaller extracts/places them under sys._MEIPASS instead
-- this module hides that difference so the rest of the code doesn't need
to know which mode it's running in.
"""

import os
import sys
import tempfile


def is_frozen():
    return getattr(sys, "frozen", False)


def base_dir():
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts):
    return os.path.join(base_dir(), *parts)


def output_dir():
    """Where generated PDFs are written. Program Files (where a frozen
    app is normally installed) usually isn't writable without admin
    rights, so the packaged app writes to the user's own AppData
    folder instead; on Vercel it uses /tmp; the dev version keeps using
    ./output next to the code, same as before."""
    if is_frozen():
        d = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "NameTableGenerator", "output",
        )
    elif os.environ.get("VERCEL"):
        d = os.path.join(tempfile.gettempdir(), "output")
    else:
        d = os.path.join(base_dir(), "output")
    os.makedirs(d, exist_ok=True)
    return d


def slugify(text):
    keep = [ch if ch.isalnum() else "_" for ch in (text or "").strip()]
    slug = "".join(keep)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "nametag"
