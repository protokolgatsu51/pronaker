"""
Nametag / name-table PDF generator.

Reproduces the KEMNAKER name-table design (NAME_TABLE_TEMPLATE.psd) with the
name printed twice on one card: once right-side-up (bottom half) and once
rotated 180 degrees (top half), so the card is readable from both sides of
a table -- matching the reference PDF you supplied.

All geometry below (page size, baselines, spacing, centering) was measured
directly from your reference PDF
(DIREKTUR_JENDERAL_..._KESEHATAN_KERJA.pdf) using pdfplumber, so it is exact,
not eyeballed.
"""

import os
import textwrap
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from paths import base_dir, output_dir as _output_dir, slugify

BASE_DIR = base_dir()
BG_IMAGE = os.path.join(BASE_DIR, "static", "template_background_new.png")
if not os.path.exists(BG_IMAGE):
    BG_IMAGE = os.path.join(BASE_DIR, "assets", "template_background_new.png")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")
if not os.path.exists(FONTS_DIR):
    FONTS_DIR = os.path.join(BASE_DIR, "static", "fonts")

# ---------------------------------------------------------------------------
# Page geometry -- Standard A4 (297 x 210 mm landscape, 841.89 x 372.72 pt),
# centered layout safe from Kemnaker & Indonesia Emas logos.
# ---------------------------------------------------------------------------
PAGE_W = 841.89
PAGE_H = 372.72
CENTER_X = 420.95                 # exact horizontal center line (PAGE_W / 2)
NAME_BASELINE_Y = 102.5          # baseline of the name, bottom-up coords
NAME_TO_POSITION_GAP = 40.0      # per spec: name -> position baseline gap
POSITION_LINE_GAP = 20.0         # per spec: gap between wrapped position lines
MAX_TEXT_WIDTH = 625.0           # available width before position text wraps (safe from logo)
MAX_NAME_WIDTH = 625.0           # available width before name text must be abbreviated
NAME_BOX_WIDTH = 625.0           # centered name text box boundary

NAME_FONT_SIZE = 45.86
POSITION_FONT_SIZE = 18.0

# ---------------------------------------------------------------------------
# Fonts -- Montserrat is the default font, loaded from fonts/Montserrat-*.ttf.
# Myriad Pro and other fonts are registered if available, with Helvetica fallback.
# ---------------------------------------------------------------------------
NAME_FONT = "Helvetica-Bold"
POSITION_FONT = "Helvetica-Bold"

_montserrat_bold = os.path.join(FONTS_DIR, "Montserrat-Bold.ttf")
if not os.path.exists(_montserrat_bold):
    _montserrat_bold = os.path.join(BASE_DIR, "static", "fonts", "Montserrat-Bold.ttf")

_montserrat_reg = os.path.join(FONTS_DIR, "Montserrat-Regular.ttf")
if not os.path.exists(_montserrat_reg):
    _montserrat_reg = os.path.join(BASE_DIR, "static", "fonts", "Montserrat-Regular.ttf")

_bold_path = os.path.join(FONTS_DIR, "MyriadPro-Bold.ttf")
_bold_path_otf = os.path.join(FONTS_DIR, "MyriadPro-Bold.otf")
_reg_path = os.path.join(FONTS_DIR, "MyriadPro-Regular.ttf")
_reg_path_otf = os.path.join(FONTS_DIR, "MyriadPro-Regular.otf")

try:
    if os.path.exists(_montserrat_bold):
        pdfmetrics.registerFont(TTFont("Montserrat-Bold", _montserrat_bold))
        NAME_FONT = "Montserrat-Bold"
        POSITION_FONT = "Montserrat-Bold"
    if os.path.exists(_montserrat_reg):
        pdfmetrics.registerFont(TTFont("Montserrat-Regular", _montserrat_reg))
except Exception:
    pass

try:
    if os.path.exists(_bold_path) or os.path.exists(_bold_path_otf):
        p = _bold_path if os.path.exists(_bold_path) else _bold_path_otf
        pdfmetrics.registerFont(TTFont("MyriadPro-Bold", p))
    if os.path.exists(_reg_path) or os.path.exists(_reg_path_otf):
        p = _reg_path if os.path.exists(_reg_path) else _reg_path_otf
        pdfmetrics.registerFont(TTFont("MyriadPro-Regular", p))
except Exception:  # pragma: no cover - defensive, keeps fallback usable
    # CFF/PostScript outlines are rejected by reportlab TTFont; Helvetica fallback is expected
    pass


# ---------------------------------------------------------------------------
# Bulk Title Cleaner & Parser Utilities
# ---------------------------------------------------------------------------
import re

def sanitize_text(text, preserve_newlines=False):
    """Replaces tabs, non-breaking spaces, zero-width spaces, and control chars with regular space."""
    if not text:
        return ""
    if preserve_newlines:
        lines = str(text).splitlines()
        cleaned = []
        for line in lines:
            cl = re.sub(r'[\t\v\f\u00a0\u200b\u200e\u200f\ufeff]+', ' ', str(line)).strip()
            cl = re.sub(r'[ ]+', ' ', cl)
            cleaned.append(cl)
        return "\n".join(cleaned)
    s = re.sub(r'[\t\r\n\v\f\u00a0\u200b\u200e\u200f\ufeff]+', ' ', str(text)).strip()
    return re.sub(r'\s+', ' ', s)

def apply_text_case(text, text_case="uppercase"):
    """Applies uppercase, capitalize (title case), or lowercase."""
    if not text:
        return ""
    s = sanitize_text(text, preserve_newlines=True)
    if text_case == "capitalize":
        # Capitalize each word, preserving separators
        return re.sub(r'(?:^|[\s/\-\(\)])[a-z]', lambda m: m.group(0).upper(), s.lower())
    elif text_case == "lowercase":
        return s.lower()
    else:
        return s.upper()

LEADING_LIST_PREFIX_PATTERN = re.compile(
    r'^\s*(?:'
    r'\(?\d+[\.\)\:\-\]]*|'
    r'[-*•·–—>→+~▪▫◦■/\\|]+'
    r')\s*',
    re.UNICODE
)

FRONT_TITLES_PATTERN = re.compile(
    r'^\s*(?:'
    r'Prof(?:esor)?\.?|'
    r'Drs\.?|Dra\.?|Drg\.?|Drh\.?|Dr\.?|'
    r'Ir\.?|Apt\.?|Ns\.?|'
    r'K\.?\s*H\.?|KH\.?|Kiai\s+Haji|Kyai\s+Haji|'
    r'Hjh\.?|Hj\.?|H\.|(?:\bH\b\.?)|Haji|Hajjah|Hajah|'
    r'Ust(?:adz)?\.?|Habib|Sayyid|'
    r'Bpk\.?|Bapak|Ibu|Sdri?\.?|Saudara|Saudari|'
    r'Plt\.?|Plh\.?|Pj\.?|'
    r'Jenderal|Letjen|Mayjen|Brigjen|Kolonel|Letkol|Mayor|Kapten|Lettu|Letda|'
    r'Irjen(?:\s+Pol)?\.?|Brigjen(?:\s+Pol)?\.?|Kombes(?:\s+Pol)?\.?|AKBP|Kompol|AKP|Iptu|Ipda'
    r')(?:[\.\s\:\-\/–—]+|$)',
    re.IGNORECASE
)

TITLE_TOKEN_PATTERN = re.compile(
    r'^(?:'
    r'[SMDA]\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|'
    r'Sp\.\s*[A-Za-z]+(?:\s*\([A-Za-z]+\)|-[A-Za-z0-9]+|(?:\.\s*[A-Za-z]+)*)\.?|'
    r'Subsp\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|'
    r'Ph\.?\s*D\.?|PhD\.?|'
    r'M\.?\s*B\.?\s*A\.?|MBA\.?|'
    r'M\.?\s*(?:Bus|Com|Sc|Eng|Ed|Fin|Phil|Arch|Tech|Law|Res|Des|Pub\.?\s*Pol|Int\.?\s*Rel)\.?|'
    r'B\.?\s*[A-Z]\.?\s*(?:Sc|A)?\.?|'
    r'LL\.?\s*M\.?|LLM|'
    r'Ed\.?\s*D\.?|D\.?\s*Sc\.?|D\.?\s*B\.?\s*A\.?|'
    r'I\.?\s*P\.?\s*[UMP]\b\.?|IP[UMP]\.?|'
    r'(?:ASEAN|Asean)\s+Eng\.?|'
    r'A\.?\s*C\.?\s*P\.?\s*E\.?|ACPE\.?|C\.?\s*P\.?\s*E\.?|CPE\.?|'
    r'(?:SE|SH|ST|SKom|SPd|SSos|SIP|SIKom|SKM|SPi|SPt|SHut|SAg|SFarm|SPsi|SSn|SKed|SStat|SAkt|SIK|SHum|SFils|STr\w*|AMd\w*)\b\.?|'
    r'(?:MM|MH|MT|ME|MSi|MPd|MKes|MKM|MKom|MA|MSc|MEng|MP|MKn|MAP|MPA|MPP|MPH|MAg|MFarm|MPsi|MSn|MEcon|MARS|MFin|MMgt|MTech|MPhil|BSc|BEng|BA|BBA|BCom|BEd)\b\.?|'
    r'FINASIM|FACS|FICS|'
    r'CMA|CPA|CIA|CHRP|CPHR|QIA|CBV|CPMA|'
    r'CFA|CFP|QWP|FRM|PMP|CAPM|'
    r'CISA|CISM|CISSP|CEH|'
    r'CRA|CRP|CRGP|CSO|CGO|CGP|'
    r'Ak\.?|Akt\.?|CA\b\.?|BKP\.?|CTA\.?|ACPA\.?|FCCA\.?|ACCA\.?|CHRP\.?|CPHR\.?|PMP\.?|CFA\.?|CFP\.?|CPA\.?|CMA\.?|CIA\.?|CISA\.?|CISM\.?|CISSP\.?|QWP\.?|FRM\.?|'
    r'MM\.PD'
    r')$',
    re.IGNORECASE
)

BACK_TITLES_PATTERN = re.compile(
    r'(?:,\s*|\s+)(?:'
    r'[SMDA]\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*(?:\s*\([A-Za-z0-9\s\.\-]+\))?\.?|'
    r'Sp\.\s*[A-Za-z]+(?:\s*\([A-Za-z0-9\s\.\-]+\)|-[A-Za-z0-9]+|(?:\.\s*[A-Za-z]+)*)\.?|'
    r'Subsp\.\s*[A-Za-z]+(?:\s*\([A-Za-z0-9\s\.\-]+\)|-[A-Za-z0-9]+|(?:\.\s*[A-Za-z]+)*)\.?|'
    r'Ph\.?\s*D\.?|PhD\.?|'
    r'M\.?\s*B\.?\s*A\.?|MBA\.?|'
    r'M\.?\s*(?:Bus|Com|Sc|Eng|Ed|Fin|Phil|Arch|Tech|Law|Res|Des|Pub\.?\s*Pol|Int\.?\s*Rel)\.?|'
    r'B\.?\s*[A-Z]\.?\s*(?:Sc|A)?\.?|'
    r'LL\.?\s*M\.?|LLM|'
    r'Ed\.?\s*D\.?|D\.?\s*Sc\.?|D\.?\s*B\.?\s*A\.?|'
    r'I\.?\s*P\.?\s*[UMP]\b\.?|IP[UMP]\.?|'
    r'(?:ASEAN|Asean)\s+Eng\.?|'
    r'A\.?\s*C\.?\s*P\.?\s*E\.?|ACPE\.?|C\.?\s*P\.?\s*E\.?|CPE\.?|'
    r'(?:SE|SH|ST|SKom|SPd|SSos|SIP|SIKom|SKM|SPi|SPt|SHut|SAg|SFarm|SPsi|SSn|SKed|SStat|SAkt|SIK|SHum|SFils|STr\w*|AMd\w*)\b\.?|'
    r'(?:MM|MH|MT|ME|MSi|MPd|MKes|MKM|MKom|MA|MSc|MEng|MP|MKn|MAP|MPA|MPP|MPH|MAg|MFarm|MPsi|MSn|MEcon|MARS|MFin|MMgt|MTech|MPhil|BSc|BEng|BA|BBA|BCom|BEd)\b\.?|'
    r'FINASIM|FACS|FICS|'
    r'CMA|CPA|CIA|CHRP|CPHR|QIA|CBV|CPMA|'
    r'CFA|CFP|QWP|FRM|PMP|CAPM|'
    r'CISA|CISM|CISSP|CEH|'
    r'CRA|CRP|CRGP|CSO|CGO|CGP|'
    r'Ak\.?|Akt\.?|CA\b\.?|BKP\.?|CTA\.?|ACPA\.?|FCCA\.?|ACCA\.?|CHRP\.?|CPHR\.?|PMP\.?|CFA\.?|CFP\.?|CPA\.?|CMA\.?|CIA\.?|CISA\.?|CISM\.?|CISSP\.?|QWP\.?|FRM\.?|'
    r'MM\.PD|'
    r'(?:[A-Z]\.){3,8}(?![A-Za-z0-9])|H\.|Hj\.|Haji|Hajjah|Hajah|Hjh\.?'
    r')(?:\.+(?=$|[\s,\)\]\-;:/])|(?=$|[\s,\)\]\-;:/]))',
    re.IGNORECASE
)

def clean_titles(name):
    """Thoroughly removes leading tabs, bullets/numbering, front titles (Dr, Drs, Dra, H, Hj, etc.), and back degrees."""
    if not name:
        return ""
    # 0. Sanitize tabs, NBSP, zero-width spaces, and control chars
    s = sanitize_text(name)

    # 1. Strip parenthesized religious/academic titles e.g. "(H.) " or "(Hj.) " or "(Dr.) "
    s = re.sub(r'^\s*\((?:H\.|Hj\.|Haji|Hajjah|Hajah|Hjh\.?|Dr\.?|Drs\.?|Dra\.?)\)\s*', '', s, flags=re.IGNORECASE).strip()

    # 2. Strip leading numbering or bullet markers (e.g. "1. ", "2) ", "- ", "> ", "· ", "• ")
    prev = None
    while prev != s:
        prev = s
        s = LEADING_LIST_PREFIX_PATTERN.sub('', s).strip()

    # 3. Strip front titles & religious titles (e.g. "Prof. ", "Dr. ", "Drs. ", "H. ", "Hj. ", "K.H. ", etc.)
    prev = None
    while prev != s:
        prev = s
        s = FRONT_TITLES_PATTERN.sub('', s).strip()

    # 4. Strip back titles / academic degrees
    prev = None
    while prev != s:
        prev = s
        s = BACK_TITLES_PATTERN.sub('', s).strip()

    # 4b. Strip parenthesized trailing titles/subspecialties e.g. "(K)", "(Konsultan)", "(Han)"
    s = re.sub(r'\s*\((?:K|Konsultan|Sp\.[A-Za-z]+|[A-Za-z0-9\.\s\-]+)\)\s*$', '', s, flags=re.IGNORECASE).strip()

    # 5. Clean leftover punctuation at ends (preserving trailing period ONLY if part of a single initial e.g. 'R.', 'P.')
    s = re.sub(r'^[,\.\s\-–—>·•\:\=\|\/]+', '', s).strip()
    s = re.sub(r'[\s,;:!?\-–—_/\t|*•·+~="\'\\`^]+$', '', s).strip()
    if not re.search(r'\b[A-Za-z]\.$', s):
        s = re.sub(r'\.+$', '', s).strip()

    # 6. Clean any trailing comma or short unrecognized title abbreviations
    while ',' in s:
        before, after = s.rsplit(',', 1)
        after_trim = after.strip()
        if re.match(r'^(?:[A-Za-z0-9\.\s\-\(\)]+|\(K\)|Konsultan)$', after_trim, re.IGNORECASE) and len(after_trim) <= 15:
            s = before.strip()
        else:
            break

    s = re.sub(r'^[,\.\s\-–—>·•\:\=\|\/]+', '', s).strip()
    s = re.sub(r'[\s,;:!?\-–—_/\t|*•·+~="\'\\`^]+$', '', s).strip()
    if not re.search(r'\b[A-Za-z]\.$', s):
        s = re.sub(r'\.+$', '', s).strip()
    s = strip_trailing_punctuation(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def get_name_text_width_pt(text, font=None, font_size=None):
    if not text:
        return 0.0
    upper = str(text).strip().upper()
    f = font or NAME_FONT
    sz = float(font_size) if font_size and str(font_size).lower() != "auto" else NAME_FONT_SIZE
    try:
        return pdfmetrics.stringWidth(upper, f, sz)
    except Exception:
        scale = sz / NAME_FONT_SIZE
        w = 0.0
        for ch in upper:
            if ch in "MW@#%":
                w += 40.0
            elif ch in "IJ.:,'!|()[]":
                w += 13.0
            elif ch in "QOGCDHNU":
                w += 33.0
            elif ch in "EFLSTZ":
                w += 25.0
            elif ch == " ":
                w += 15.0
            else:
                w += 29.0
        return w * scale

def fits_name(text, max_len=24, max_width=MAX_NAME_WIDTH, font=None, font_size=None):
    if not text:
        return True
    if len(text) > max_len:
        return False
    if get_name_text_width_pt(text, font=font, font_size=font_size) > max_width:
        return False
    return True

def format_bulk_name(raw_name, max_len=24, max_width=MAX_NAME_WIDTH, font=None, font_size=None):
    """
    1. Removes all front and back academic titles.
    2. Uses target font and font size (default NAME_FONT_SIZE = 45.86 pt) to check if the name
       fits safely within max_width (CARD.NAME_BOX_WIDTH = 618.0 pt).
    3. If full cleaned name fits within max_width and <= 24 chars, returns it.
    4. If it exceeds max_width or 24 chars, abbreviates with AT MOST ONE initial ending with period '.'
       (e.g. 'Muhammad Fauzan Ramadhan' -> 'Muhammad Fauzan R.', 'Arnando Jujur P.'),
       so that the name fits comfortably at the locked font size without per-card font shrinking.
    """
    cleaned = strip_trailing_punctuation(clean_titles(raw_name))
    if not cleaned:
        return ""

    sz = float(font_size) if font_size and str(font_size).lower() != "auto" else NAME_FONT_SIZE
    f = _resolve_reportlab_font(font, is_bold=True) if font else NAME_FONT

    def fits(cand):
        if not cand:
            return True
        w = get_name_text_width_pt(cand.upper(), font=f, font_size=sz)
        return w <= max_width

    if fits(cleaned) and len(cleaned) <= max_len:
        return cleaned

    words = cleaned.split()
    if len(words) > 1:
        # 1. Abbreviate last word if it fits (e.g. 'Muhammad Fauzan Ramadhan' -> 'Muhammad Fauzan R.')
        last_cand = " ".join(words[:-1]) + " " + words[-1][0].upper() + "."
        if fits(last_cand):
            return last_cand

        # 2. Find longest prefix of full words + 1 initial, omitting all subsequent words (e.g. 'Arnando Jujur Pardamean Siregar' -> 'Arnando Jujur P.')
        for i in range(len(words) - 2, 0, -1):
            cand = " ".join(words[:i]) + " " + words[i][0].upper() + "."
            if fits(cand):
                return cand

            # If prefix has at least 2 full words and fits, prefer it over shrinking to words[0] + initial!
            # (e.g. 'Faried Abdurrahman Nur Yuliono' -> 'Faried Abdurrahman' instead of 'Faried A.')
            if i >= 2:
                cand_full = " ".join(words[:i])
                if fits(cand_full):
                    return cand_full

        # 3. Fallback for i=1 (e.g. 'First W.')
        cand_one_init = words[0] + " " + words[1][0].upper() + "."
        if fits(cand_one_init):
            return cand_one_init
        if fits(words[0]):
            return words[0]
        return words[0]

    return strip_trailing_punctuation(cleaned[:25].strip())


def strip_trailing_punctuation(text):
    """Strips trailing punctuation (commas, semicolons, colons, dashes, etc.)
    Preserves trailing period if part of an academic degree abbreviation (e.g. M.T., Ph.D.)."""
    if not text:
        return ""
    lines = str(text).splitlines()
    cleaned = []
    for l in lines:
        c = re.sub(r'[\s,;:!?\-–—_/\t|*•·+~="\'\\`^]+$', '', l).strip()
        if not re.search(r'\b[A-Za-z]\.$', c):
            c = re.sub(r'\.+$', '', c).strip()
        cleaned.append(c)
    return "\n".join(cleaned).strip()

def clean_position_text(pos):
    if not pos:
        return ""
    lines = str(pos).splitlines()
    cleaned_lines = []
    for line in lines:
        s = sanitize_text(line, preserve_newlines=False)
        s = re.sub(r'^[\s\-–—>·•\:\=\|\/]+', '', s).strip()
        prev = None
        while prev != s:
            prev = s
            s = re.sub(r'^\s*(?:[SMDA]\.[A-Za-z]+(?:\.[A-Za-z]+)*\.?|Ph\.?D\.?|PhD|M\.?B\.?A\.?|MBA|Sp\.[A-Za-z]+|Subsp\.[A-Za-z]+|M\.?M\.?|M\.?Si\.?|S\.?E\.?|S\.?H\.?|S\.?T\.?|S\.?Kom\.?|S\.?Pd\.?|S\.?Sos\.?|M\.?Kom\.?|M\.?H\.?|M\.?T\.?|M\.?Pd\.?|FINASIM|Ak\.?|Akt\.?|CA\b|MM\.PD)(?:[,\s\:\-\/–—]+|$)', '', s, flags=re.IGNORECASE).strip()
        s = re.sub(r'^[\s\-–—>·•\:\=\|\/]+', '', s).strip()
        s = strip_trailing_punctuation(s)
        if s:
            cleaned_lines.append(s)
    return "\n".join(cleaned_lines)

def split_name_and_position(line):
    """
    Parses a single line into (name, position) using any punctuation
    including parentheses, tabs, colons, dashes, etc.
    Intelligently handles copy-pasted multi-column rows from Excel/Sheets.
    """
    if not line:
        return "", ""
    line = str(line).strip()
    if not line:
        return "", ""

    # Check TSV (Excel copy-paste with tabs)
    if '\t' in line:
        parts = [p.strip() for p in line.split('\t') if p.strip()]
        if len(parts) >= 3:
            if re.match(r'^\(?\d+[\.\)\:\-\]]*$', parts[0]) or parts[0].lower() in ('no', 'nomor'):
                return strip_trailing_punctuation(parts[1]), ' - '.join(parts[2:])
            else:
                return strip_trailing_punctuation(parts[0]), ' - '.join(parts[1:])
        elif len(parts) == 2:
            if re.match(r'^\(?\d+[\.\)\:\-\]]*$', parts[0]) or parts[0].lower() in ('no', 'nomor'):
                return strip_trailing_punctuation(parts[1]), ""
            else:
                return strip_trailing_punctuation(parts[0]), parts[1]
        elif len(parts) == 1:
            return strip_trailing_punctuation(parts[0]), ""

    # Strip leading numbering: e.g. "1. ", "1, ", "1) ", "1 - ", "1; "
    num_match = re.match(r'^\(?\d+[\.\)\:\-\]\,\;]\s+(.*)$', line)
    if num_match:
        line = num_match.group(1).strip()

    # Check Semicolon delimiter (Standard Indonesian Excel CSV)
    if ';' in line:
        parts = [p.strip().strip('"\'') for p in line.split(';') if p.strip()]
        if len(parts) >= 2:
            return strip_trailing_punctuation(parts[0]), ' - '.join(parts[1:])
        elif len(parts) == 1:
            return strip_trailing_punctuation(parts[0]), ""

    line = sanitize_text(line)

    # 1. Check parentheses / brackets: e.g. "Nama Pejabat (Jabatan Lengkap)"
    # or "Nama - Jabatan (Keterangan)"
    m = re.match(r'^(.*?)\s*[\(\[\{](.+?)[\)\]\}]\s*$', line)
    if m:
        before_paren = m.group(1).strip()
        inside_paren = m.group(2).strip()
        delims = ['|', ';', ':', ' - ', ' – ', ' — ', '=']
        found_delim = None
        for d in delims:
            if d in before_paren:
                found_delim = d
                break
        if found_delim:
            parts = before_paren.split(found_delim, 1)
            name_part = strip_trailing_punctuation(parts[0].strip())
            pos_part = parts[1].strip() + " (" + inside_paren + ")"
            if name_part and pos_part:
                return name_part, pos_part
        else:
            name_part = strip_trailing_punctuation(before_paren)
            pos_part = inside_paren
            if name_part and pos_part:
                return name_part, pos_part

    # 2. Check explicit strong delimiters
    delims = ['|', ';', ':', ' - ', ' – ', ' — ', ' / ', '=']
    for d in delims:
        if d in line:
            parts = line.split(d, 1)
            return strip_trailing_punctuation(parts[0].strip()), parts[1].strip()

    # 3. Check for comma: could separate degrees or name/position
    if ',' in line:
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if len(parts) >= 2:
            last_part = parts[-1]
            is_title = bool(TITLE_TOKEN_PATTERN.match(last_part))
            if not is_title:
                return strip_trailing_punctuation(", ".join(parts[:-1])), last_part

    # 4. Check for single dash or slash between words
    for d in ['-', '/']:
        if d in line:
            parts = line.split(d, 1)
            if parts[0].strip() and parts[1].strip():
                return strip_trailing_punctuation(parts[0].strip()), parts[1].strip()

    # 5. Check if line contains position indicators starting with PLT / Plt / Plh / Pj separated by space
    pos_match = re.search(r'\s+(?:PLT\.?|Plt\.?|PLH\.?|Plh\.?|Pj\.?|PJ\.?)\s+', line)
    if pos_match:
        name_part = line[:pos_match.start()].strip()
        pos_part = line[pos_match.start():].strip()
        if name_part and pos_part:
            return strip_trailing_punctuation(name_part), pos_part

    return strip_trailing_punctuation(line), ""


GENERIC_ROLES = {
    "peserta", "anggota", "panitia", "staf", "staff", "tamu", "undangan",
    "member", "participant", "committee", "guest", "delegasi", "delegate"
}

def normalize_dedup_key(text):
    if not text:
        return ""
    s = re.sub(r'[^a-zA-Z0-9]', '', str(text).lower())
    return s.strip()

def deduplicate_bulk_rows(rows, content_mode="both", source="kemnaker"):
    """
    Deduplicates bulk rows:
    - Only applies to Kemnaker mode (source == 'kemnaker').
    - For Tamu (source == 'tamu'), all rows are preserved as entered by the user.
    """
    if not rows:
        return []
    if source != "kemnaker":
        return list(rows)

    seen_names = set()
    seen_positions = set()
    seen_pairs = set()
    unique_rows = []

    for r in rows:
        name = (r.get("name") or "").strip()
        pos = (r.get("position") or "").strip()

        cleaned_n = clean_titles(name) if name else ""
        nk = normalize_dedup_key(cleaned_n or name)
        pk = normalize_dedup_key(pos)
        pair_k = (nk, pk)

        if content_mode == "name_only":
            if nk and nk in seen_names:
                continue
            if nk:
                seen_names.add(nk)
            unique_rows.append(r)

        elif content_mode == "position_only":
            if pk and pk in seen_positions:
                continue
            if pk:
                seen_positions.add(pk)
            unique_rows.append(r)

        else:
            # Mode 'both'
            is_dup = False
            if pair_k in seen_pairs:
                is_dup = True
            elif nk and nk in seen_names:
                is_dup = True
            elif pk and pk in seen_positions and pk not in GENERIC_ROLES:
                is_dup = True

            if is_dup:
                continue

            if nk:
                seen_names.add(nk)
            if pk:
                seen_positions.add(pk)
            seen_pairs.add(pair_k)
            unique_rows.append(r)

    return unique_rows


def wrap_position(position, font=POSITION_FONT, size=POSITION_FONT_SIZE,
                   max_width=MAX_TEXT_WIDTH):
    """Word-wrap position text with support for:
    1) User explicit Enter key in single generator (\n) to control Line 1 & Line 2
    2) Balanced 2-line wrap in bulk generator to prevent 'jomplang' / orphaned words.
    Max 128 characters, strictly max 2 lines (never enters line 3)."""
    if not position:
        return []
    clean_text = strip_trailing_punctuation(position.strip())[:128]
    clean_text = strip_trailing_punctuation(clean_text)
    if not clean_text:
        return []

    # 1. Explicit newline from Single Generator (Enter key)
    if "\n" in clean_text:
        raw_lines = [strip_trailing_punctuation(l.strip()).upper() for l in clean_text.splitlines() if strip_trailing_punctuation(l.strip())]
        if len(raw_lines) == 1:
            return [raw_lines[0]]
        if len(raw_lines) >= 2:
            l1 = " ".join(raw_lines[0].split())
            l2 = " ".join(" ".join(raw_lines[1:]).split())
            return [l1, l2][:2]

    # 2. Single continuous line (or Bulk Generator input)
    single_line = " ".join(clean_text.split()).upper()
    if pdfmetrics.stringWidth(single_line, font, size) <= max_width:
        return [single_line]

    words = single_line.split()
    if len(words) <= 1:
        return [single_line]

    # 2-line wrap: line 1 must fit and must always be longer than line 2 (w1 > w2)
    TARGET_RATIO = 0.60
    trailing_stopwords = {'DAN', 'ATAU', 'PADA', 'DI', 'KE', 'DENGAN', 'UNTUK'}
    candidates = []
    for i in range(1, len(words)):
        l1 = " ".join(words[:i])
        l2 = " ".join(words[i:])
        w1 = pdfmetrics.stringWidth(l1, font, size)
        w2 = pdfmetrics.stringWidth(l2, font, size)
        if w1 <= max_width and w2 <= max_width:
            total_w = w1 + w2
            ratio = w1 / total_w if total_w > 0 else 0.5
            is_top_heavy = (w1 > w2)
            last_word_l1 = words[i - 1].upper()
            trailing_penalty = 0.15 if last_word_l1 in trailing_stopwords else 0.0

            if is_top_heavy:
                score = abs(ratio - TARGET_RATIO) + trailing_penalty
                priority = 0
            else:
                score = (0.55 - ratio) + 1.0 + trailing_penalty
                priority = 1

            candidates.append((priority, score, [l1, l2]))

    if candidates:
        candidates.sort(key=lambda x: (x[0], x[1]))
        return candidates[0][2]

    # Fallback to greedy
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= 2:
                break
    if current and len(lines) < 2:
        lines.append(current)
    return lines[:2]


def wrap_60pt(text, max_len=128, max_width=MAX_TEXT_WIDTH, font=NAME_FONT, font_size=60.0):
    clean_text = strip_trailing_punctuation((text or "").strip())
    if len(clean_text) > max_len:
        clean_text = strip_trailing_punctuation(clean_text[:max_len].strip())
    if not clean_text:
        return []

    sz = float(font_size) if font_size else 60.0

    # 1. Explicit newline (Enter key) — preserve user's exact lines verbatim (up to 4 lines)
    if "\n" in clean_text:
        lines = [strip_trailing_punctuation(l.strip()) for l in clean_text.splitlines() if strip_trailing_punctuation(l.strip())]
        lines = [" ".join(l.split()) for l in lines if l]
        if lines:
            return lines[:4]

    # 2. Single continuous line — measure using the ACTUAL chosen font_size & font
    single_line = " ".join(clean_text.split())
    try:
        w = pdfmetrics.stringWidth(single_line, font, sz)
    except Exception:
        w = len(single_line) * sz * 0.55

    if w <= max_width:
        return [single_line]

    words = single_line.split()
    if len(words) <= 1:
        return [single_line]

    best_diff = float("inf")
    best_split = None
    for i in range(1, len(words)):
        l1 = " ".join(words[:i])
        l2 = " ".join(words[i:])
        try:
            w1 = pdfmetrics.stringWidth(l1, font, sz)
            w2 = pdfmetrics.stringWidth(l2, font, sz)
        except Exception:
            w1 = len(l1) * sz * 0.55
            w2 = len(l2) * sz * 0.55

        if w1 <= max_width and w2 <= max_width:
            diff = abs(w1 - w2)
            if diff < best_diff:
                best_diff = diff
                best_split = [l1, l2]

    if best_split:
        return best_split

    lines = []
    cur = ""
    for w_word in words:
        cand = (cur + " " + w_word).strip() if cur else w_word
        try:
            cw = pdfmetrics.stringWidth(cand, font, sz)
        except Exception:
            cw = len(cand) * sz * 0.55
        if cw <= max_width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w_word
            if len(lines) >= 3:
                break
    if cur and len(lines) < 3:
        lines.append(cur)
    return lines[:3] if lines else [single_line]


def layout_position_only(text, font=NAME_FONT, max_width=MAX_TEXT_WIDTH, max_chars=128, custom_size=None):
    """
    Dynamic 1-to-4 line layout & auto-font-reduction for Position Only mode.
    - Preserves explicit newlines (Enter key) verbatim without re-splitting lines
    - Respects user's manual custom_size before deciding whether continuous text wraps
    Returns (lines, font_size, baselines).
    """
    if not text:
        return [], 40.0, []
    clean_text = strip_trailing_punctuation(text.strip())
    if len(clean_text) > max_chars:
        clean_text = strip_trailing_punctuation(clean_text[:max_chars].strip())
    if not clean_text:
        return [], 40.0, []

    has_custom = custom_size is not None and str(custom_size).lower() != "auto"
    target_size = float(custom_size) if has_custom else None

    def measure(t, sz):
        try:
            return pdfmetrics.stringWidth(t, font, sz)
        except Exception:
            return len(t) * sz * 0.55

    def get_baselines(num_lines, sz):
        gap = max(sz * 1.25, sz + 4.0)
        if num_lines == 1:
            return [86.0]
        elif num_lines == 2:
            return [86.0 + gap / 2.0, 86.0 - gap / 2.0]
        elif num_lines == 3:
            return [86.0 + gap, 86.0, 86.0 - gap]
        else:
            top = 86.0 + ((num_lines - 1) * gap) / 2.0
            return [top - i * gap for i in range(num_lines)]

    # 1. Explicit newlines entered by user — preserve lines per Enter break!
    if "\n" in clean_text:
        raw_lines = [strip_trailing_punctuation(l.strip()) for l in clean_text.splitlines() if strip_trailing_punctuation(l.strip())]
        raw_lines = [" ".join(l.split()) for l in raw_lines if l]
        if len(raw_lines) == 1:
            clean_text = raw_lines[0]
        elif len(raw_lines) >= 2:
            kept_lines = raw_lines[:4]
            if has_custom:
                s = target_size
                max_lw = max((measure(l, s) for l in kept_lines), default=0.0)
                if max_lw > max_width and max_width > 0:
                    s = max(8.0, s * (max_width / max_lw))
            else:
                s = 46.0 if len(kept_lines) == 2 else (34.0 if len(kept_lines) == 3 else 26.0)
                min_auto = 12.0 if len(kept_lines) <= 2 else 10.0
                while s > min_auto:
                    if all(measure(l, s) <= max_width for l in kept_lines):
                        break
                    s -= 1.0
            return kept_lines, s, get_baselines(len(kept_lines), s)

    # 2. Continuous text
    continuous = " ".join(clean_text.split())
    words = continuous.split()
    if not words:
        return [], (target_size if has_custom else 40.0), []

    def find_balanced_2_lines(sz):
        if len(words) < 2:
            return None
        TARGET_RATIO = 0.60
        trailing_stopwords = {'DAN', 'ATAU', 'PADA', 'DI', 'KE', 'DENGAN', 'UNTUK'}
        candidates = []
        for i in range(1, len(words)):
            l1 = " ".join(words[:i])
            l2 = " ".join(words[i:])
            w1 = measure(l1, sz)
            w2 = measure(l2, sz)
            if w1 <= max_width and w2 <= max_width:
                total_w = w1 + w2
                ratio = w1 / total_w if total_w > 0 else 0.5
                is_top_heavy = (w1 > w2)
                last_word_l1 = words[i - 1].upper()
                trailing_penalty = 0.15 if last_word_l1 in trailing_stopwords else 0.0

                if is_top_heavy:
                    score = abs(ratio - TARGET_RATIO) + trailing_penalty
                    priority = 0
                else:
                    score = (0.55 - ratio) + 1.0 + trailing_penalty
                    priority = 1

                candidates.append((priority, score, [l1, l2]))
        if candidates:
            candidates.sort(key=lambda x: (x[0], x[1]))
            return candidates[0][2]
        return None

    def find_balanced_3_lines(sz):
        if len(words) < 3:
            return None
        best_diff = float("inf")
        best_split = None
        n = len(words)
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                l1 = " ".join(words[:i])
                l2 = " ".join(words[i:j])
                l3 = " ".join(words[j:])
                w1 = measure(l1, sz)
                w2 = measure(l2, sz)
                w3 = measure(l3, sz)
                if w1 <= max_width and w2 <= max_width and w3 <= max_width:
                    diff = max(w1, w2, w3) - min(w1, w2, w3)
                    if diff < best_diff:
                        best_diff = diff
                        best_split = [l1, l2, l3]
        return best_split

    # Custom size set by user: check 1 line / 2 lines / 3 lines at target_size first!
    if has_custom:
        if measure(continuous, target_size) <= max_width:
            return [continuous], target_size, get_baselines(1, target_size)
        split2 = find_balanced_2_lines(target_size)
        if split2:
            return split2, target_size, get_baselines(2, target_size)
        split3 = find_balanced_3_lines(target_size)
        if split3:
            return split3, target_size, get_baselines(3, target_size)
        g_lines, g_cur = [], ""
        for w in words:
            cand = (g_cur + " " + w).strip() if g_cur else w
            if measure(cand, target_size) <= max_width:
                g_cur = cand
            else:
                if g_cur:
                    g_lines.append(g_cur)
                g_cur = w
                if len(g_lines) == 3:
                    break
        if g_cur and len(g_lines) < 4:
            g_lines.append(g_cur)
        if g_lines:
            return g_lines, target_size, get_baselines(len(g_lines), target_size)
        return [continuous], target_size, get_baselines(1, target_size)

    # Auto mode: 2a. Check if fits on 1 line
    for s in [52.0, 48.0, 44.0, 40.0]:
        if measure(continuous, s) <= max_width:
            return [continuous], s, [86.0]

    # Auto mode: 2b. Try 2 lines
    for s in [44.0, 40.0, 36.0, 32.0, 30.0]:
        split2 = find_balanced_2_lines(s)
        if split2:
            return split2, s, get_baselines(2, s)

    # Auto mode: 2c. Try 3 lines
    for s in range(32, 13, -1):
        s_float = float(s)
        split3 = find_balanced_3_lines(s_float)
        if split3:
            return split3, s_float, get_baselines(3, s_float)

    # Fallback greedy wrap up to 3 lines
    for s in range(22, 11, -1):
        s_float = float(s)
        lines, cur = [], ""
        for w in words:
            cand = (cur + " " + w).strip() if cur else w
            if measure(cand, s_float) <= max_width:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                cur = w
                if len(lines) == 2:
                    break
        if cur:
            lines.append(cur)
        if len(lines) <= 3 and all(measure(l, s_float) <= max_width for l in lines):
            return lines, s_float, get_baselines(len(lines), s_float)

    return [continuous], 16.0, [86.0]


PAGE_SIZES = {
    "a4": (PAGE_W, PAGE_H),         # Standard Kemnaker (841.89 x 372.72 pt)
    "f4": (935.43, 419.0),          # F4 / Folio (330 x 215 mm)
    "letter": (792.0, 360.0),       # Letter / Kuarto (279 x 216 mm)
    "a3": (1190.55, 532.0),         # A3 (420 x 297 mm)
}

def _resolve_reportlab_font(choice, is_bold=False):
    if not choice:
        return NAME_FONT if is_bold else POSITION_FONT
    ch = str(choice).lower().strip()
    if "montserrat" in ch:
        if "regular" in ch:
            return "Montserrat-Regular"
        return "Montserrat-Bold"
    if "myriad" in ch:
        try:
            target = "MyriadPro-Bold" if is_bold else "MyriadPro-Regular"
            pdfmetrics.getFont(target)
            return target
        except Exception:
            return "Helvetica-Bold" if is_bold else "Helvetica"
    if any(k in ch for k in ("times", "garamond", "georgia", "serif")):
        return "Times-Bold" if is_bold else "Times-Roman"
    if "courier" in ch or "mono" in ch:
        return "Courier-Bold" if is_bold else "Courier"
    try:
        pdfmetrics.getFont(choice)
        return choice
    except Exception:
        pass
    return NAME_FONT if is_bold else POSITION_FONT

def _draw_block(c, name, position_lines, content_mode="both",
                name_font=None, pos_font=None,
                name_size=None, pos_size=None,
                spacing_gap=None, spacing_is_manual=False, text_case="uppercase",
                center_x=None, max_name_width=None, max_text_width=None,
                clean_titles_flag=False, horizontal_offset=0.0):
    """Draws the text block using local coords where (0,0)
    behaves like the normal (bottom, right-side-up) orientation."""
    n_font = _resolve_reportlab_font(name_font, is_bold=True)
    p_font = _resolve_reportlab_font(pos_font, is_bold=(content_mode == "position_only"))
    n_size = float(name_size) if name_size and str(name_size).lower() != "auto" else NAME_FONT_SIZE
    p_size = float(pos_size) if pos_size and str(pos_size).lower() != "auto" else POSITION_FONT_SIZE
    gap = float(spacing_gap) if spacing_gap else NAME_TO_POSITION_GAP
    is_manual_gap = str(spacing_is_manual).lower() in ("1", "true", "yes")
    cx = (center_x if center_x is not None else CENTER_X) + float(horizontal_offset or 0.0)
    mw = max_name_width if max_name_width is not None else MAX_NAME_WIDTH
    tw = max_text_width if max_text_width is not None else MAX_TEXT_WIDTH

    # Only clean academic/religious titles if clean_titles_flag is True (bulk/kemnaker mode)
    if clean_titles_flag and name:
        if content_mode == "name_only" and "\n" in str(name):
            clean_n = "\n".join(clean_titles(part) for part in str(name).splitlines() if part.strip())
        else:
            clean_n = clean_titles(name)
    else:
        clean_n = sanitize_text(name, preserve_newlines=(content_mode == "name_only")) if name else ""
    safe_name = apply_text_case(clean_n, text_case)

    optical_center_y = 97.45

    if content_mode == "name_only":
        if safe_name:
            sz = 60.0 if not name_size or str(name_size).lower() == "auto" else n_size
            lines = wrap_60pt(safe_name, 128, max_width=tw, font=n_font, font_size=sz)
            for l in lines:
                w_l = get_name_text_width_pt(l, n_font, sz)
                if w_l > tw and tw > 0:
                    sz = sz * (tw / w_l)
            c.setFont(n_font, sz)
            n = len(lines)
            line_gap = gap if is_manual_gap else max(sz * 1.15, sz + 6.0)
            name_ascent = 0.75 * sz
            name_descent = 0.25 * sz
            top_baseline = optical_center_y + ((n - 1) * line_gap + name_descent - name_ascent) / 2.0
            for idx, line_txt in enumerate(lines):
                baseline = top_baseline - idx * line_gap
                c.drawCentredString(cx, baseline, line_txt)
        return

    if content_mode == "position_only":
        pos_text = position_lines if isinstance(position_lines, str) else "\n".join(position_lines)
        safe_pos = sanitize_text(pos_text or name or "", preserve_newlines=True)
        safe_pos = apply_text_case(safe_pos, text_case)
        if safe_pos:
            custom_p = p_size if (pos_size and str(pos_size).lower() != "auto") else None
            lines, sz, _ = layout_position_only(safe_pos, font=p_font, max_width=tw, max_chars=128, custom_size=custom_p)
            for l in lines:
                w_l = get_name_text_width_pt(l, p_font, sz)
                if w_l > tw and tw > 0:
                    sz = sz * (tw / w_l)
            c.setFont(p_font, sz)
            n = len(lines)
            line_gap = gap if is_manual_gap else max(sz * 1.25, sz + 4.0)
            pos_ascent = 0.75 * sz
            pos_descent = 0.25 * sz
            top_baseline = optical_center_y + ((n - 1) * line_gap + pos_descent - pos_ascent) / 2.0
            for idx, line_txt in enumerate(lines):
                baseline = top_baseline - idx * line_gap
                c.drawCentredString(cx, baseline, line_txt)
        return

    # Default 'both' mode
    safe_lines = [apply_text_case(sanitize_text(l), text_case) for l in (position_lines or []) if sanitize_text(l)]
    safe_lines = safe_lines[:2]
    num_pos_lines = len(safe_lines)

    # Dynamic optical centering calculation
    font_sz = n_size
    if safe_name:
        w = get_name_text_width_pt(safe_name, n_font, font_sz)
        if w > mw and mw > 0:
            font_sz = font_sz * (mw / w)

    actual_p_size = p_size
    if num_pos_lines > 0:
        for c_line in safe_lines:
            w_p = get_name_text_width_pt(c_line, p_font, actual_p_size)
            if w_p > tw and tw > 0:
                actual_p_size = actual_p_size * (tw / w_p)

    name_ascent = 0.75 * font_sz
    name_descent = 0.25 * font_sz
    pos_descent = 0.25 * actual_p_size

    if num_pos_lines > 0:
        dynamic_name_baseline_y = optical_center_y + (gap + ((num_pos_lines - 1) * POSITION_LINE_GAP) + pos_descent - name_ascent) / 2.0
    else:
        dynamic_name_baseline_y = optical_center_y - (name_ascent - name_descent) / 2.0

    if safe_name:
        c.setFont(n_font, font_sz)
        c.drawCentredString(cx, dynamic_name_baseline_y, safe_name)

    if num_pos_lines > 0:
        c.setFont(p_font, actual_p_size)
        baseline = dynamic_name_baseline_y - gap
        for c_line in safe_lines:
            c.drawCentredString(cx, baseline, c_line)
            baseline -= POSITION_LINE_GAP


def build_pdf(name, position, output_path, sides="2", content_mode="both",
              name_font=None, pos_font=None, name_size=None, pos_size=None,
              spacing_gap=None, text_case="uppercase", paper_size="a4",
              custom_bg_data="", clean_titles_flag=False, horizontal_offset=0.0, **kwargs):
    """Renders one name-table PDF (one page, one card) to output_path."""
    page_w, page_h = PAGE_SIZES.get(str(paper_size).lower(), (PAGE_W, PAGE_H))
    c = canvas.Canvas(output_path, pagesize=(page_w, page_h))

    bg = ImageReader(BG_IMAGE)
    c.drawImage(bg, 0, 0, width=page_w, height=page_h,
                preserveAspectRatio=False, mask="auto")

    position_lines = [position] if content_mode == "position_only" else wrap_position(position)

    scale_ratio = page_w / PAGE_W
    draw_kwargs = {
        "content_mode": content_mode,
        "name_font": name_font,
        "pos_font": pos_font,
        "name_size": name_size,
        "pos_size": pos_size,
        "spacing_gap": spacing_gap,
        "spacing_is_manual": kwargs.get("spacing_is_manual", False),
        "text_case": text_case,
        "center_x": CENTER_X * scale_ratio,
        "max_name_width": MAX_NAME_WIDTH * scale_ratio,
        "max_text_width": MAX_TEXT_WIDTH * scale_ratio,
        "clean_titles_flag": clean_titles_flag,
        "horizontal_offset": float(kwargs.get("horizontal_offset", horizontal_offset) or 0.0) * scale_ratio,
    }

    # Normal orientation (bottom half, right-side-up)
    c.saveState()
    _draw_block(c, name, position_lines, **draw_kwargs)
    c.restoreState()

    # Flipped orientation (top half, rotated 180 degrees about page center)
    if str(sides) != "1":
        c.saveState()
        c.translate(page_w, page_h)
        c.rotate(180)
        _draw_block(c, name, position_lines, **draw_kwargs)
        c.restoreState()

    c.showPage()
    c.save()
    return output_path


def build_pdf_multipage(rows, output_path, sides="2", content_mode="both",
                        name_font=None, pos_font=None, name_size=None, pos_size=None,
                        spacing_gap=None, text_case="uppercase", paper_size="a4",
                        custom_bg_data="", **kwargs):
    """Renders multiple cards into a single multi-page PDF (one card per page)."""
    if isinstance(output_path, (str, bytes, os.PathLike)):
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
    page_w, page_h = PAGE_SIZES.get(str(paper_size).lower(), (PAGE_W, PAGE_H))
    c = canvas.Canvas(output_path, pagesize=(page_w, page_h))
    bg = ImageReader(BG_IMAGE)

    scale_ratio = page_w / PAGE_W
    draw_kwargs = {
        "content_mode": content_mode,
        "name_font": name_font,
        "pos_font": pos_font,
        "name_size": name_size,
        "pos_size": pos_size,
        "spacing_gap": spacing_gap,
        "spacing_is_manual": kwargs.get("spacing_is_manual", False),
        "text_case": text_case,
        "center_x": CENTER_X * scale_ratio,
        "max_name_width": MAX_NAME_WIDTH * scale_ratio,
        "max_text_width": MAX_TEXT_WIDTH * scale_ratio,
        "clean_titles_flag": kwargs.get("clean_titles_flag", False),
        "horizontal_offset": float(kwargs.get("horizontal_offset", 0.0) or 0.0) * scale_ratio,
    }

    for row in rows:
        if isinstance(row, dict):
            name = row.get("name", "")
            position = row.get("position", "")
        else:
            name, position = row[0], row[1]
        c.drawImage(bg, 0, 0, width=page_w, height=page_h,
                    preserveAspectRatio=False, mask="auto")
        position_lines = [position] if content_mode == "position_only" else wrap_position(position)
        # Normal orientation (bottom half, right-side-up)
        c.saveState()
        _draw_block(c, name, position_lines, **draw_kwargs)
        c.restoreState()
        # Flipped orientation (top half, rotated 180 degrees about page center)
        if str(sides) != "1":
            c.saveState()
            c.translate(page_w, page_h)
            c.rotate(180)
            _draw_block(c, name, position_lines, **draw_kwargs)
            c.restoreState()
        c.showPage()
    c.save()
    return output_path


if __name__ == "__main__":
    import argparse
    import csv

    parser = argparse.ArgumentParser(description="Generate name-table PDFs.")
    parser.add_argument("name", nargs="?", help="Full name")
    parser.add_argument("position", nargs="?", help="Position / job title")
    parser.add_argument("--csv", help="CSV file with 'name,position' columns "
                                       "for batch generation")
    parser.add_argument("--outdir", default=_output_dir(),
                         help="Output directory (default: ./output)")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    if args.csv:
        with open(args.csv, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row["name"].strip()
                position = row["position"].strip()
                out = os.path.join(args.outdir, f"{slugify(name)}.pdf")
                build_pdf(name, position, out)
                print(f"Generated {out}")
                count += 1
            print(f"\nDone. {count} PDF(s) written to {args.outdir}")
    elif args.name and args.position:
        out = os.path.join(args.outdir, f"{slugify(args.name)}.pdf")
        build_pdf(args.name, args.position, out)
        print(f"Generated {out}")
    else:
        parser.print_help()
