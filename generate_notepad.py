import os
import io
import re
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, white, HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------------------------------------------------------------------
# Font Registration (Arial with fallback to Helvetica)
# ---------------------------------------------------------------------------
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

_arial_path = "C:/Windows/Fonts/arial.ttf"
_arial_bold_path = "C:/Windows/Fonts/arialbd.ttf"
if os.path.exists(_arial_path):
    try:
        pdfmetrics.registerFont(TTFont("Arial", _arial_path))
        FONT_REGULAR = "Arial"
    except Exception:
        pass
if os.path.exists(_arial_bold_path):
    try:
        pdfmetrics.registerFont(TTFont("Arial-Bold", _arial_bold_path))
        FONT_BOLD = "Arial-Bold"
    except Exception:
        pass

MM_TO_PT = 72.0 / 25.4

# ---------------------------------------------------------------------------
# Colors extracted directly from Kemnaker DOCX / PDF examples:
# Title, Hari & Tanggal, Waktu: 0x1F3864 (Hex #1F3864) - Dark Navy Blue
# Subheaders, Names, Jabatan, Borders: 0x000000 - Pure Black
# ---------------------------------------------------------------------------
COLOR_NAVY = HexColor("#1F3864")
COLOR_BLACK = HexColor("#000000")
COLOR_WHITE = HexColor("#FFFFFF")

# ---------------------------------------------------------------------------
# Exact physical dimensions extracted from:
# - static/Contoh Notepad Besar.pdf: width=442.4pt (156.1mm), height=644.4pt (227.3mm)
# - static/Contoh Notepad Kecil (Kemnaker & Tamu).pdf: width=314.72pt (111.0mm), height=438.07pt (154.5mm)
# ---------------------------------------------------------------------------
BESAR_W = 442.40       # 15.61 cm
BESAR_H_FULL = 644.40  # 22.73 cm (full page printable area for 15 items)
BESAR_H_MIN = 438.07   # 15.45 cm (compact)

KECIL_W = 314.72       # 11.10 cm (110 mm standard)
KECIL_H = 438.07       # 15.45 cm (152.4 mm standard)


def draw_double_border(c, x, y, w, h):
    """
    Draws the exact Word double border:
    Outer line: 1.44pt thick black stroke.
    Gap: 2.16pt.
    Inner line: 0.72pt thick black stroke.
    """
    c.saveState()
    c.setStrokeColor(COLOR_BLACK)
    
    # Outer rectangle (1.44pt thick)
    c.setLineWidth(1.44)
    c.rect(x, y, w, h, stroke=1, fill=0)
    
    # Inner rectangle (0.72pt thick) with 2.16pt gap
    gap = 2.16
    c.setLineWidth(0.72)
    c.rect(x + gap, y + gap, w - (gap * 2), h - (gap * 2), stroke=1, fill=0)
    
    c.restoreState()


def wrap_text_lines(c, text, font_name, font_size, max_width):
    """Wraps text into lines that fit within max_width, respecting explicit newlines."""
    if not text:
        return []
    input_lines = str(text).splitlines()
    all_lines = []
    for raw_l in input_lines:
        words = raw_l.strip().split()
        if not words:
            continue
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            w = c.stringWidth(test_line, font_name, font_size)
            if w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    all_lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    all_lines.append(word)
                    current_line = []
        if current_line:
            all_lines.append(" ".join(current_line))
    return all_lines


def _prepare_sections(data, mode):
    """Build normalized (header, items, header_indent) tuples for a notepad mode."""
    sections = []
    if mode == "besar":
        pendamping = data.get("pendamping_list", [])
        peserta = data.get("peserta_list", [])
        if pendamping:
            sections.append(("Pendamping :", pendamping, 6.0))
        if peserta:
            peserta_label = data.get("peserta_label", "Peserta :")
            sections.append((peserta_label, peserta, 6.0))
    elif mode == "kecil_pendamping":
        pendamping = data.get("pendamping_list", [])
        sections.append(("Pendamping :", pendamping, 6.0))
    elif mode == "kecil_peserta":
        peserta = data.get("peserta_list", [])
        peserta_label = data.get("peserta_label", "")  # Empty in Contoh Tamu
        sections.append((peserta_label, peserta, 6.0))
    return sections


def _format_item_parts(item, sep):
    """Return (name_display, pos_body) with exact trailing period rules."""
    name = (item.get("name") if isinstance(item, dict) else str(item)).strip()
    pos = (item.get("position") if isinstance(item, dict) else "").strip()

    if sep == ",":
        name_display = (name + ",") if pos else name
        pos_body = f" {pos}" if pos else ""
    else:
        name_display = name
        pos_body = f" – {pos}" if pos else ""

    if pos_body and not pos_body.rstrip().endswith("."):
        pos_body = pos_body.rstrip() + "."
    elif not pos_body and name_display and not name_display.rstrip().endswith("."):
        name_display = name_display.rstrip() + "."

    return name_display, pos_body


def _split_first_and_rest_words(c, pos_body, rem_w, max_item_w, font_reg, item_fs, sep):
    """
    Split pos_body into (first_line_text, rest_lines) in STRICT word order.
    Stops appending to first_line_words as soon as any word exceeds rem_w
    so subsequent shorter words never jump ahead out of order.
    """
    words = pos_body.strip().split()
    first_line_words = []
    rest_words = []

    for wi, w in enumerate(words):
        candidate = " " + " ".join(first_line_words + [w])
        if c.stringWidth(candidate, font_reg, item_fs) <= rem_w:
            first_line_words.append(w)
        else:
            rest_words = words[wi:]
            break

    # Avoid leaving an orphan separator dash at the end of line 1
    if sep != "," and first_line_words == ["–"] and rest_words:
        first_line_words = []
        rest_words = words

    first_line_text = (" " + " ".join(first_line_words)) if first_line_words else ""
    rest_lines = wrap_text_lines(c, " ".join(rest_words), font_reg, item_fs, max_item_w) if rest_words else []
    return first_line_text, rest_lines


def _measure_sections_height(c, sections, sep, font_reg, font_bold, item_fs, item_line_h, wrapped_line_h, max_item_w, first_sec_drop=34.0, next_sec_drop=42.0, first_item_with_hdr=30.0, next_item_with_hdr=26.0):
    """Simulate total vertical drop needed from meta bottom to bottom of last item."""
    drop = 0.0
    for sec_idx, (sec_header, items, _) in enumerate(sections):
        if sec_header:
            drop += first_sec_drop if sec_idx == 0 else next_sec_drop
            first_item_drop = first_item_with_hdr if sec_idx == 0 else next_item_with_hdr
        else:
            drop += 34.6 if sec_idx == 0 else next_sec_drop
            first_item_drop = 0.0

        for idx, item in enumerate(items, 1):
            name_display, pos_body = _format_item_parts(item, sep)
            if idx == 1:
                drop += first_item_drop
            else:
                drop += item_line_h

            name_w = c.stringWidth(name_display, font_bold, item_fs)
            pos_w = c.stringWidth(pos_body, font_reg, item_fs)

            if (name_w + pos_w) > max_item_w:
                if name_w <= max_item_w:
                    rem_w = max_item_w - name_w
                    _, rest_lines = _split_first_and_rest_words(
                        c, pos_body, rem_w, max_item_w, font_reg, item_fs, sep
                    )
                    drop += len(rest_lines) * wrapped_line_h
                else:
                    name_lines = wrap_text_lines(c, name_display, font_bold, item_fs, max_item_w)
                    drop += max(0, len(name_lines) - 1) * wrapped_line_h
                    if pos_body:
                        pos_lines = wrap_text_lines(c, pos_body.strip(), font_reg, item_fs, max_item_w)
                        drop += len(pos_lines) * wrapped_line_h
    return drop


def draw_notepad_box(c, box_x, box_y, box_w, box_h, data, mode="besar"):
    """
    Renders one notepad box with 100% exact styling matching Contoh Notepad PDF:
    - Double border (1.44pt outer, 2.16pt gap, 0.72pt inner)
    - Center-aligned Judul in Navy Blue (#1F3864)
    - Solid horizontal divider line (0.72pt black) separating Judul from content
    - Hari & Tanggal and Waktu in Navy Blue (#1F3864) Arial 14pt with tab-aligned colons
    - Subheaders (Pendamping / Peserta) in Arial Regular 12pt Black
    - Numbered list items with Arial Bold 12pt Name, Regular Separator & Jabatan, ending with '.'
    - Precise hanging indents (number at +18.7pt, name & wrapped lines at +36.7pt)
    """
    c.saveState()
    
    # Fill white background
    c.setFillColor(COLOR_WHITE)
    c.rect(box_x, box_y, box_w, box_h, stroke=0, fill=1)
    
    # 1. Double Border
    draw_double_border(c, box_x, box_y, box_w, box_h)
    
    # Inner border box coordinates
    gap = 2.16
    inner_x = box_x + gap
    inner_y = box_y + gap
    inner_w = box_w - (gap * 2)
    inner_h = box_h - (gap * 2)
    
    font_reg = FONT_REGULAR
    font_bold = FONT_BOLD
    
    title_text = (data.get("title") or "").strip().upper()
    hari_tgl = (data.get("hari_tanggal") or "").strip()
    waktu = (data.get("waktu") or "").strip()
    default_sep = "," if str(mode).startswith("kecil") else "–"
    sep = data.get("separator", default_sep)
    use_numbering = data.get("use_numbering", True)
    
    # Top of content
    cur_y = inner_y + inner_h - 14.0
    
    # 2. Draw Judul (Center, Bold, Navy Blue #1F3864)
    if title_text:
        title_fs = 12.0 if mode == "besar" else 11.0
        # Title width fits inner width with 7pt padding on each side (inner_w - 14.0)
        title_lines = wrap_text_lines(c, title_text, font_bold, title_fs, inner_w - 14.0)
        line_h = 13.8 if mode == "besar" else 12.0
        
        c.setFillColor(COLOR_NAVY)
        c.setFont(font_bold, title_fs)
        # First title line baseline matches Word/PDF top margin (y=87.4 in Besar, 86.5-87.3 in Kecil)
        cur_y = inner_y + inner_h - 22.2
        for i, tl in enumerate(title_lines):
            if i > 0:
                cur_y -= line_h
            c.drawCentredString(inner_x + (inner_w / 2.0), cur_y, tl)
        
        # 3. Horizontal Divider Line under Judul (0.72pt solid black across inner box)
        cur_y -= 14.2  # Spacing before divider line (matches exact Word paragraph border)
        div_y = cur_y
        c.setStrokeColor(COLOR_BLACK)
        c.setLineWidth(0.72)
        c.line(inner_x, div_y, inner_x + inner_w, div_y)
    
    # 4. Draw Hari & Tanggal and Waktu (Navy Blue #1F3864, Arial Regular 14pt)
    meta_fs = 14.0
    label_x = inner_x + 45.1
    colon_x = inner_x + 92.0
    val_x = colon_x + 10.0
    
    c.setFillColor(COLOR_NAVY)
    meta_first_drop = 28.0 if title_text else 16.0  # One clean blank line below divider above Hari
    if hari_tgl:
        cur_y -= meta_first_drop
        c.setFont(font_reg, meta_fs)
        c.drawString(label_x, cur_y, "Hari")
        c.drawString(colon_x, cur_y, ":")
        c.drawString(val_x, cur_y, hari_tgl)
        if waktu:
            cur_y -= 18.5  # Exactly 18.5pt baseline to baseline
            c.setFont(font_reg, meta_fs)
            c.drawString(label_x, cur_y, "Waktu")
            c.drawString(colon_x, cur_y, ":")
            c.drawString(val_x, cur_y, waktu)
    elif waktu:
        cur_y -= meta_first_drop
        c.setFont(font_reg, meta_fs)
        c.drawString(label_x, cur_y, "Waktu")
        c.drawString(colon_x, cur_y, ":")
        c.drawString(val_x, cur_y, waktu)
    
    # 5. Prepare sections
    sections = _prepare_sections(data, mode)
    total_items = sum(len(items) for _, items, _ in sections)

    # Indentation matching Contoh PDF
    num_x = inner_x + 18.8
    text_x = inner_x + 36.8
    max_item_w = (inner_x + inner_w - 6.0) - text_x

    # Auto-fit scale table: preserves standard 12pt / 20.7pt unless wrapping or item count exceeds box height
    avail_list_h = max(40.0, (cur_y - (inner_y + 10.0)))
    scale_candidates = [
        (12.0, 20.7, 20.7, 34.0, 42.0, 30.0, 26.0),
        (11.0, 18.0, 18.0, 31.0, 36.0, 27.0, 23.0),
        (10.0, 16.0, 16.0, 28.0, 30.0, 24.0, 20.0),
        (9.5,  14.5, 14.5, 24.0, 24.0, 21.0, 18.0),
        (9.0,  13.2, 13.2, 22.0, 20.0, 19.0, 16.0),
        (8.5,  12.0, 12.0, 20.0, 18.0, 17.0, 14.5),
        (8.0,  11.0, 11.0, 18.0, 15.0, 15.0, 13.0),
        (7.5,  10.0, 10.0, 16.0, 13.0, 13.5, 11.5),
        (7.0,   9.2,  9.2, 14.0, 11.0, 12.0, 10.0),
        (6.5,   8.5,  8.5, 12.0,  9.5, 10.5,  9.0),
        (6.0,   7.8,  7.8, 10.5,  8.0,  9.0,  8.0),
        (5.5,   7.2,  7.2,  9.5,  7.0,  8.0,  7.0),
    ]
    start_idx = 0
    if mode == "besar":
        if total_items > 18:
            start_idx = 2
        elif total_items > 16:
            start_idx = 1
    else:
        if total_items > 9:
            start_idx = 2
        elif total_items > 7:
            start_idx = 1

    chosen = scale_candidates[-1]
    for cand in scale_candidates[start_idx:]:
        req_h = _measure_sections_height(
            c, sections, sep, font_reg, font_bold,
            cand[0], cand[1], cand[2], max_item_w,
            cand[3], cand[4], cand[5], cand[6]
        )
        if req_h <= avail_list_h:
            chosen = cand
            break

    item_fs, item_line_h, wrapped_line_h, first_sec_drop, next_sec_drop, first_item_with_hdr, next_item_with_hdr = chosen
    
    # 6. Render List Sections
    c.setFillColor(COLOR_BLACK)
    
    for sec_idx, (sec_header, items, header_indent) in enumerate(sections):
        if sec_header:
            cur_y -= first_sec_drop if sec_idx == 0 else next_sec_drop
            c.setFont(font_reg, item_fs)
            c.drawString(inner_x + header_indent, cur_y, sec_header)
            first_item_drop = first_item_with_hdr if sec_idx == 0 else next_item_with_hdr
        else:
            cur_y -= 34.6 if sec_idx == 0 else next_sec_drop
            first_item_drop = 0.0
        
        for idx, item in enumerate(items, 1):
            name_display, pos_body = _format_item_parts(item, sep)
            
            if idx == 1:
                if first_item_drop > 0:
                    cur_y -= first_item_drop
            else:
                cur_y -= item_line_h
            
            # Number (Arial Bold)
            if use_numbering:
                num_text = f"{idx}."
                c.setFont(font_bold, item_fs)
                c.drawString(num_x, cur_y, num_text)
            
            # Measure widths
            c.setFont(font_bold, item_fs)
            name_w = c.stringWidth(name_display, font_bold, item_fs)
            c.setFont(font_reg, item_fs)
            pos_w = c.stringWidth(pos_body, font_reg, item_fs)
            
            if (name_w + pos_w) <= max_item_w:
                # Single line
                c.setFont(font_bold, item_fs)
                c.drawString(text_x, cur_y, name_display)
                if pos_body:
                    c.setFont(font_reg, item_fs)
                    c.drawString(text_x + name_w, cur_y, pos_body)
            else:
                # Multi-line with strict word-order hanging indent
                c.setFont(font_bold, item_fs)
                if name_w <= max_item_w:
                    c.drawString(text_x, cur_y, name_display)
                    rem_w = max_item_w - name_w
                    first_line_text, wrap_lines = _split_first_and_rest_words(
                        c, pos_body, rem_w, max_item_w, font_reg, item_fs, sep
                    )
                    if first_line_text:
                        c.setFont(font_reg, item_fs)
                        c.drawString(text_x + name_w, cur_y, first_line_text)
                    for wl in wrap_lines:
                        cur_y -= wrapped_line_h
                        c.setFont(font_reg, item_fs)
                        c.drawString(text_x, cur_y, wl)
                else:
                    # Name itself is wider than max_item_w
                    name_lines = wrap_text_lines(c, name_display, font_bold, item_fs, max_item_w)
                    for n_idx, nl in enumerate(name_lines):
                        if n_idx > 0:
                            cur_y -= wrapped_line_h
                        c.setFont(font_bold, item_fs)
                        c.drawString(text_x, cur_y, nl)
                    if pos_body:
                        pos_lines = wrap_text_lines(c, pos_body.strip(), font_reg, item_fs, max_item_w)
                        for pl in pos_lines:
                            cur_y -= wrapped_line_h
                            c.setFont(font_reg, item_fs)
                            c.drawString(text_x, cur_y, pl)
    
    c.restoreState()


def build_notepad_pdf(data, output_path=None):
    """
    Main builder for Note Pad PDF matching Contoh Notepad PDF exactly.
    Supports:
    - 'besar': 1 A4 portrait page, width 442.4pt (15.61cm), height up to 644.4pt (22.73cm)
    - 'kecil' (pendamping only): 1 A4 portrait page, 314.72pt x 438.07pt (11.1cm x 15.45cm)
    - 'kecil' (peserta only): 1 A4 portrait page, 314.72pt x 438.07pt (11.1cm x 15.45cm)
    - 'kecil' (both - separate): 2 A4 portrait pages
    - 'kecil' (both - single_page): 1 A4 landscape page, 2 boxes side-by-side
    """
    notepad_type = data.get("notepad_type", "besar")
    kecil_mode = data.get("kecil_mode", "both")
    layout_both = data.get("layout_both", "single_page")
    
    buf = io.BytesIO() if output_path is None else None
    dest = output_path if output_path is not None else buf
    
    # A4 dimensions: 595.32pt x 841.92pt
    page_w = 595.32
    page_h = 841.92
    
    if notepad_type == "besar":
        c = canvas.Canvas(dest, pagesize=(page_w, page_h))
        c.setTitle("Note Pad Tools Kemnaker RI")

        # Keep outer Notepad Besar frame fixed at BESAR_W x BESAR_H_FULL (15.6 x 22.7 cm)
        box_h = BESAR_H_FULL
            
        box_x = 70.58  # Exact coordinate from Contoh Notepad Besar.pdf
        box_y = page_h - 72.0 - box_h  # 72.0pt (1 inch) top margin
        
        draw_notepad_box(c, box_x, box_y, BESAR_W, box_h, data, mode="besar")
        c.showPage()
        c.save()
        
    elif notepad_type == "kecil":
        if kecil_mode == "pendamping":
            c = canvas.Canvas(dest, pagesize=(page_w, page_h))
            c.setTitle("Note Pad Tools Kemnaker RI - Pendamping Kemnaker")
            box_x = 108.14  # Exact coordinate from Contoh Notepad Kecil (Kemnaker).pdf
            box_y = page_h - 72.0 - KECIL_H
            draw_notepad_box(c, box_x, box_y, KECIL_W, KECIL_H, data, mode="kecil_pendamping")
            c.showPage()
            c.save()
            
        elif kecil_mode == "peserta":
            c = canvas.Canvas(dest, pagesize=(page_w, page_h))
            c.setTitle("Note Pad Tools Kemnaker RI - Peserta Tamu")
            box_x = 108.14  # Exact coordinate from Contoh Notepad Kecil (Tamu).pdf
            box_y = page_h - 72.0 - KECIL_H
            draw_notepad_box(c, box_x, box_y, KECIL_W, KECIL_H, data, mode="kecil_peserta")
            c.showPage()
            c.save()
            
        else:  # both
            if layout_both == "single_page":
                # 1 Page A4 Landscape: 2 boxes side-by-side
                land_w, land_h = page_h, page_w  # 841.92 x 595.32
                c = canvas.Canvas(dest, pagesize=(land_w, land_h))
                c.setTitle("Note Pad Tools Kemnaker RI - Pendamping & Peserta")
                
                gap_boxes = 40.0
                total_boxes_w = (KECIL_W * 2) + gap_boxes
                margin_x = (land_w - total_boxes_w) / 2.0
                box_y = land_h - 72.0 - KECIL_H
                
                # Box 1 (Left): Pendamping
                draw_notepad_box(c, margin_x, box_y, KECIL_W, KECIL_H, data, mode="kecil_pendamping")
                # Box 2 (Right): Peserta
                draw_notepad_box(c, margin_x + KECIL_W + gap_boxes, box_y, KECIL_W, KECIL_H, data, mode="kecil_peserta")
                
                c.showPage()
                c.save()
            else:
                # 2 Pages A4 Portrait
                c = canvas.Canvas(dest, pagesize=(page_w, page_h))
                c.setTitle("Note Pad Tools Kemnaker RI - Pendamping & Peserta")
                box_x = 108.14
                box_y = page_h - 72.0 - KECIL_H
                
                # Page 1: Pendamping
                draw_notepad_box(c, box_x, box_y, KECIL_W, KECIL_H, data, mode="kecil_pendamping")
                c.showPage()
                
                # Page 2: Peserta
                draw_notepad_box(c, box_x, box_y, KECIL_W, KECIL_H, data, mode="kecil_peserta")
                c.showPage()
                c.save()

    if output_path is None:
        buf.seek(0)
        return buf.getvalue()
    return output_path
