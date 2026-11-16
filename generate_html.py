"""
PDF export engine that renders templates/card.html (the exact same markup
used for the live web preview) through headless Chromium via Playwright.

Why: reportlab can only embed TrueType (glyf) outlines, and the supplied
Myriad Pro webfont is CFF/PostScript-flavored (common for webfonts), which
reportlab's font embedder rejects. Chromium renders CFF fonts natively, and
using it also means the live preview and the generated PDF are pixel-for-pixel
the same renderer -- no separate "preview math" vs "PDF math" to keep in sync.

Falls back to generate.py's reportlab/Helvetica engine if Playwright or a
browser binary isn't available (see build_pdf_with_fallback).
"""

import os
import sys
import tempfile
from pathlib import Path

from paths import base_dir, is_frozen

def _safe_print_err(prefix, err):
    try:
        clean_err = str(err).encode("ascii", "replace").decode("ascii")
        print(f"{prefix}: {clean_err}")
    except Exception:
        pass

# Must happen before Playwright is imported anywhere (including lazily
# inside functions below), so set it at module load time. When frozen,
# the browser is bundled at <install dir>/ms-playwright instead of the
# usual per-user cache, so Playwright needs to be told where to look.
if is_frozen():
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(base_dir(), "ms-playwright")

from jinja2 import Environment, FileSystemLoader

BASE_DIR = base_dir()
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Program Files (a frozen app's usual home) isn't writable without admin
# rights, so temp HTML files go to the OS temp folder instead of next to
# the bundled code.
TEMP_DIR = tempfile.gettempdir()

PAGE_W_PT = 832.08
PAGE_H_PT = 372.72

_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


PAPER_PAGE_SIZES = {
    "a4": (832.08, 372.72),
    "f4": (935.43, 419.0),
    "letter": (792.0, 360.0),
    "a3": (1190.55, 532.0),
}

def _render_card_html(name, position, asset_prefix, sides="2",
                       font_name_choice="Montserrat", font_pos_choice="Montserrat",
                       font_size_name="auto", font_size_pos="auto",
                       spacing_gap="40", text_case="uppercase", paper_size="a4",
                       custom_bg_data="", custom_font_name_data="", custom_font_name_filename="",
                       custom_font_pos_data="", custom_font_pos_filename="",
                       content_mode="both", **kwargs):
    template = _env.get_template("card.html")
    # Backward compatibility
    if "font_choice" in kwargs and kwargs["font_choice"]:
        font_name_choice = kwargs["font_choice"]
        font_pos_choice = kwargs["font_choice"]
    if "custom_font_data" in kwargs and kwargs["custom_font_data"]:
        custom_font_name_data = kwargs["custom_font_data"]
    if "custom_font_name" in kwargs and kwargs["custom_font_name"]:
        custom_font_name_filename = kwargs["custom_font_name"]

    pw, ph = PAPER_PAGE_SIZES.get(str(paper_size).lower(), (PAGE_W_PT, PAGE_H_PT))
    return template.render(
        name=name,
        position=position,
        asset_prefix=asset_prefix,
        sides=str(sides),
        font_name_choice=font_name_choice,
        font_pos_choice=font_pos_choice,
        font_size_name=str(font_size_name),
        font_size_pos=str(font_size_pos),
        spacing_gap=str(spacing_gap),
        text_case=str(text_case),
        paper_size=str(paper_size),
        page_w_pt=pw,
        page_h_pt=ph,
        custom_bg_data=custom_bg_data,
        custom_font_name_data=custom_font_name_data,
        custom_font_name_filename=custom_font_name_filename,
        custom_font_pos_data=custom_font_pos_data,
        custom_font_pos_filename=custom_font_pos_filename,
        content_mode=content_mode,
    )


def _file_uri(path):
    """Path -> proper file:// URI."""
    return Path(path).resolve().as_uri()


def build_pdf(name, position, output_path, sides="2",
              font_name_choice="Montserrat", font_pos_choice="Montserrat",
              font_size_name="auto", font_size_pos="auto",
              spacing_gap="40", text_case="uppercase", paper_size="a4",
              custom_bg_data="", custom_font_name_data="", custom_font_name_filename="",
              custom_font_pos_data="", custom_font_pos_filename="",
              content_mode="both", **kwargs):
    """Render the card via headless Chromium and save it as a PDF."""
    from playwright.sync_api import sync_playwright

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    asset_prefix = _file_uri(STATIC_DIR) + "/"
    pw, ph = PAPER_PAGE_SIZES.get(str(paper_size).lower(), (PAGE_W_PT, PAGE_H_PT))

    html = _render_card_html(
        name, position, asset_prefix,
        sides=sides,
        font_name_choice=font_name_choice,
        font_pos_choice=font_pos_choice,
        font_size_name=font_size_name,
        font_size_pos=font_size_pos,
        spacing_gap=spacing_gap,
        text_case=text_case,
        paper_size=paper_size,
        custom_bg_data=custom_bg_data,
        custom_font_name_data=custom_font_name_data,
        custom_font_name_filename=custom_font_name_filename,
        custom_font_pos_data=custom_font_pos_data,
        custom_font_pos_filename=custom_font_pos_filename,
        content_mode=content_mode,
        **kwargs
    )

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                      dir=TEMP_DIR, encoding="utf-8") as f:
        f.write(html)
        tmp_path = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1110, "height": 497})
            page.goto(_file_uri(tmp_path))
            page.wait_for_function("window.__rendered === true", timeout=12000)
            page.pdf(
                path=output_path,
                width=f"{pw/72}in",
                height=f"{ph/72}in",
                prefer_css_page_size=True,
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            browser.close()
    finally:
        os.remove(tmp_path)

    return output_path


def build_pdf_with_fallback(name, position, output_path, sides="2",
                            font_name_choice="MyriadPro", font_pos_choice="MyriadPro",
                            font_size_name="auto", font_size_pos="auto",
                            spacing_gap="40", text_case="uppercase", paper_size="a4",
                            custom_bg_data="", custom_font_name_data="", custom_font_name_filename="",
                            custom_font_pos_data="", custom_font_pos_filename="",
                            content_mode="both", **kwargs):
    """Try the exact-font Playwright engine; fall back to reportlab if Playwright is unavailable."""
    # Normalize kwargs for fallback
    fb_kwargs = {
        "sides": sides,
        "content_mode": content_mode,
        "name_font": font_name_choice,
        "pos_font": font_pos_choice,
        "name_size": font_size_name,
        "pos_size": font_size_pos,
        "spacing_gap": spacing_gap,
        "text_case": text_case,
        "paper_size": paper_size,
        "custom_bg_data": custom_bg_data,
    }
    if os.environ.get("VERCEL"):
        import generate as fallback
        return fallback.build_pdf(name, position, output_path, **fb_kwargs)

    try:
        return build_pdf(
            name, position, output_path,
            sides=sides,
            font_name_choice=font_name_choice,
            font_pos_choice=font_pos_choice,
            font_size_name=font_size_name,
            font_size_pos=font_size_pos,
            spacing_gap=spacing_gap,
            text_case=text_case,
            paper_size=paper_size,
            custom_bg_data=custom_bg_data,
            custom_font_name_data=custom_font_name_data,
            custom_font_name_filename=custom_font_name_filename,
            custom_font_pos_data=custom_font_pos_data,
            custom_font_pos_filename=custom_font_pos_filename,
            content_mode=content_mode,
            **kwargs
        )
    except Exception as e:
        _safe_print_err("[generate_html] Playwright render failed, falling back to reportlab", e)
        import generate as fallback
        return fallback.build_pdf(name, position, output_path, **fb_kwargs)


def _render_cards_multipage_html(cards, asset_prefix, sides="2",
                                font_name_choice="Montserrat", font_pos_choice="Montserrat",
                                font_size_name="auto", font_size_pos="auto",
                                spacing_gap="40", text_case="uppercase", paper_size="a4",
                                custom_bg_data="", custom_font_name_data="", custom_font_name_filename="",
                                custom_font_pos_data="", custom_font_pos_filename="",
                                content_mode="both", **kwargs):
    template = _env.get_template("cards_multipage.html")
    if "font_choice" in kwargs and kwargs["font_choice"]:
        font_name_choice = kwargs["font_choice"]
        font_pos_choice = kwargs["font_choice"]
    if "custom_font_data" in kwargs and kwargs["custom_font_data"]:
        custom_font_name_data = kwargs["custom_font_data"]
    if "custom_font_name" in kwargs and kwargs["custom_font_name"]:
        custom_font_name_filename = kwargs["custom_font_name"]

    pw, ph = PAPER_PAGE_SIZES.get(str(paper_size).lower(), (PAGE_W_PT, PAGE_H_PT))
    return template.render(
        cards=cards,
        asset_prefix=asset_prefix,
        sides=str(sides),
        font_name_choice=font_name_choice,
        font_pos_choice=font_pos_choice,
        font_size_name=str(font_size_name),
        font_size_pos=str(font_size_pos),
        spacing_gap=str(spacing_gap),
        text_case=str(text_case),
        paper_size=str(paper_size),
        page_w_pt=pw,
        page_h_pt=ph,
        custom_bg_data=custom_bg_data,
        custom_font_name_data=custom_font_name_data,
        custom_font_name_filename=custom_font_name_filename,
        custom_font_pos_data=custom_font_pos_data,
        custom_font_pos_filename=custom_font_pos_filename,
        content_mode=content_mode,
    )


def build_pdf_multipage(rows, output_path, sides="2",
                        font_name_choice="Montserrat", font_pos_choice="Montserrat",
                        font_size_name="auto", font_size_pos="auto",
                        spacing_gap="40", text_case="uppercase", paper_size="a4",
                        custom_bg_data="", custom_font_name_data="", custom_font_name_filename="",
                        custom_font_pos_data="", custom_font_pos_filename="",
                        content_mode="both", **kwargs):
    """Render multiple cards into a single multi-page PDF via Chromium."""
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    cards = []
    for r in rows:
        if isinstance(r, dict):
            cards.append({"name": r.get("name", ""), "position": r.get("position", "")})
        else:
            cards.append({"name": r[0], "position": r[1]})

    if not cards:
        raise ValueError("No cards to render")

    fb_kwargs = {
        "sides": sides,
        "content_mode": content_mode,
        "name_font": font_name_choice,
        "pos_font": font_pos_choice,
        "name_size": font_size_name,
        "pos_size": font_size_pos,
        "spacing_gap": spacing_gap,
        "text_case": text_case,
        "paper_size": paper_size,
        "custom_bg_data": custom_bg_data,
    }

    if os.environ.get("VERCEL"):
        import generate as fallback
        return fallback.build_pdf_multipage(cards, output_path, **fb_kwargs)

    try:
        from playwright.sync_api import sync_playwright

        asset_prefix = _file_uri(STATIC_DIR) + "/"
        pw, ph = PAPER_PAGE_SIZES.get(str(paper_size).lower(), (PAGE_W_PT, PAGE_H_PT))
        html = _render_cards_multipage_html(
            cards, asset_prefix,
            sides=sides,
            font_name_choice=font_name_choice,
            font_pos_choice=font_pos_choice,
            font_size_name=font_size_name,
            font_size_pos=font_size_pos,
            spacing_gap=spacing_gap,
            text_case=text_case,
            paper_size=paper_size,
            custom_bg_data=custom_bg_data,
            custom_font_name_data=custom_font_name_data,
            custom_font_name_filename=custom_font_name_filename,
            custom_font_pos_data=custom_font_pos_data,
            custom_font_pos_filename=custom_font_pos_filename,
            content_mode=content_mode,
            **kwargs
        )

        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                          dir=TEMP_DIR, encoding="utf-8") as f:
            f.write(html)
            tmp_path = f.name

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1110, "height": 497})
                page.goto(_file_uri(tmp_path))
                page.wait_for_function("window.__rendered === true", timeout=20000)
                page.pdf(
                    path=output_path,
                    width=f"{pw/72}in",
                    height=f"{ph/72}in",
                    prefer_css_page_size=True,
                    print_background=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                )
                browser.close()
        finally:
            os.remove(tmp_path)

        return output_path
    except Exception as e:
        _safe_print_err("[generate_html] Playwright multipage render failed, falling back to reportlab", e)
        import generate as fallback
        return fallback.build_pdf_multipage(cards, output_path, **fb_kwargs)


def build_pdf_batch(rows, outdir):
    """rows: list of (name, position, output_path). Reuses a single
    Chromium instance across all rows -- much faster than launching a
    fresh browser per card for bulk/CSV generation. Falls back to the
    reportlab engine entirely if Playwright isn't available."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        import generate as fallback
        return [fallback.build_pdf(n, p, out) for n, p, out in rows]

    asset_prefix = _file_uri(STATIC_DIR) + "/"
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1110, "height": 497})
            for name, position, output_path in rows:
                html = _render_card_html(name, position, asset_prefix)
                with tempfile.NamedTemporaryFile("w", suffix=".html",
                                                  delete=False, dir=TEMP_DIR,
                                                  encoding="utf-8") as f:
                    f.write(html)
                    tmp_path = f.name
                try:
                    page.goto(_file_uri(tmp_path))
                    page.wait_for_function("window.__rendered === true", timeout=12000)
                    page.pdf(
                        path=output_path,
                        width=f"{PAGE_W_PT/72}in",
                        height=f"{PAGE_H_PT/72}in",
                        prefer_css_page_size=True,
                        print_background=True,
                        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                    )
                    results.append(output_path)
                finally:
                    os.remove(tmp_path)
            browser.close()
    except Exception as e:
        _safe_print_err("[generate_html] Batch Playwright render failed partway, falling back to reportlab", e)
        import generate as fallback
        done = set(results)
        for name, position, output_path in rows:
            if output_path not in done:
                fallback.build_pdf(name, position, output_path)
                results.append(output_path)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("position")
    from paths import output_dir
    parser.add_argument("--out", default=os.path.join(output_dir(), "test.pdf"))
    args = parser.parse_args()

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    build_pdf(args.name, args.position, args.out)
    print(f"Generated {args.out}")
