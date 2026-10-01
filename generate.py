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
BG_IMAGE = os.path.join(BASE_DIR, "assets", "bg_template.png")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")

# ---------------------------------------------------------------------------
# Page geometry -- measured from the reference PDF (832.08 x 372.72 pt),
# which corresponds exactly to the PSD canvas (3467 x 1553 px @ 0.24 pt/px).
# ---------------------------------------------------------------------------
PAGE_W = 832.08
PAGE_H = 372.72
CENTER_X = 482.6                 # horizontal center line both texts sit on
NAME_BASELINE_Y = 104.9          # baseline of the name, bottom-up coords
NAME_TO_POSITION_GAP = 45.0      # per spec: name -> position baseline gap
POSITION_LINE_GAP = 20.0         # per spec: gap between wrapped position lines
MAX_TEXT_WIDTH = 625.0           # available width before position text wraps
                                  # (calibrated so the reference example wraps
                                  # exactly like your sample PDF; re-tune if
                                  # you drop in a real Myriad Pro font file)

NAME_FONT_SIZE = 45.86
POSITION_FONT_SIZE = 18.0

# ---------------------------------------------------------------------------
# Fonts -- if you drop real Myriad Pro files into /fonts (see fonts/README.md)
# they are used automatically. Otherwise falls back to Helvetica, which is
# the closest built-in match and keeps every position/size/spacing exact.
# ---------------------------------------------------------------------------
NAME_FONT = "Helvetica-Bold"
POSITION_FONT = "Helvetica"

_bold_path = os.path.join(FONTS_DIR, "MyriadPro-Bold.ttf")
_bold_path_otf = os.path.join(FONTS_DIR, "MyriadPro-Bold.otf")
_reg_path = os.path.join(FONTS_DIR, "MyriadPro-Regular.ttf")
_reg_path_otf = os.path.join(FONTS_DIR, "MyriadPro-Regular.otf")

try:
    if os.path.exists(_bold_path) or os.path.exists(_bold_path_otf):
        p = _bold_path if os.path.exists(_bold_path) else _bold_path_otf
        pdfmetrics.registerFont(TTFont("MyriadPro-Bold", p))
        NAME_FONT = "MyriadPro-Bold"
    if os.path.exists(_reg_path) or os.path.exists(_reg_path_otf):
        p = _reg_path if os.path.exists(_reg_path) else _reg_path_otf
        pdfmetrics.registerFont(TTFont("MyriadPro-Regular", p))
        POSITION_FONT = "MyriadPro-Regular"
except Exception:  # pragma: no cover - defensive, keeps fallback usable
    # CFF/PostScript outlines are rejected by reportlab TTFont; Helvetica fallback is expected
    pass


# ---------------------------------------------------------------------------
# Bulk Title Cleaner & Parser Utilities
# ---------------------------------------------------------------------------
import re

LEADING_LIST_PREFIX_PATTERN = re.compile(
    r'^\s*(?:'
    r'\(?\d+[\.\)\:\-\]]*|'
    r'[-*•·–—>→+~▪▫◦■/\\|]+'
    r')\s*',
    re.UNICODE
)

FRONT_TITLES_PATTERN = re.compile(
    r'^\s*(?:(?:Plt\.?|PLT\.?|Plh\.?|PLH\.?|Pj\.?|PJ\.?)\s+)?'
    r'(?:'
    r'Prof\.?\s+Dr\.?\s+Ir\.?|Prof\.?\s+Dr\.?|Prof\.?\s+Ir\.?|Prof\.?|'
    r'Dr\.?\s+Ir\.?|Dr\.?\s+Dr\.?|Dr\.?\s+drg\.?|Dr\.?\s+dr\.?|'
    r'Drs\.?|Dra\.?|Drg\.?|Drh\.?|Ir\.?|Ns\.?|Apt\.?|'
    r'Dr\.?|dr\.?|drg\.?|drh\.?|apt\.?|'
    r'Bpk\.?|Bapak|Ibu|Sdr\.?|Sdri\.?|'
    r'K\.?\s*H\.?|Kiai\s+Haji|Kyai\s+Haji|'
    r'Hajjah|Hajah|Haji|Hjh\.?|Hj\.?|H\.|(?:\bH\b\.?)'
    r')(?:\.|\s+|$)',
    re.IGNORECASE
)

TITLE_TOKEN_PATTERN = re.compile(
    r'^(?:'
    r'[SMDA]\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|'
    r'Sp\.\s*[A-Za-z]+(?:\s*\([A-Za-z]+\)|-[A-Za-z0-9]+|(?:\.\s*[A-Za-z]+)*)\.?|'
    r'Subsp\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|'
    r'Ph\.?\s*D\.?|PhD|'
    r'M\.?\s*B\.?\s*A\.?|MBA|'
    r'M\.?\s*Bus\.?|'
    r'B\.?\s*[A-Z]\.?\s*(?:Sc|A)?\.?|'
    r'LL\.?\s*M\.?|LLM|'
    r'Ed\.?\s*D\.?|D\.?\s*Sc\.?|D\.?\s*B\.?\s*A\.?|'
    r'IP[UMP]\b\.?|'
    r'(?:ASEAN|Asean)\s+Eng\.?|'
    r'ACPE|CPE|'
    r'(?:SE|SH|ST|SKom|SPd|SSos|SIP|SIKom|SKM|SPi|SPt|SHut|SAg|SFarm|SPsi|SSn|SKed)\b|'
    r'(?:MM|MH|MT|ME|MSi|MPd|MKes|MKom|MA|MSc|MP|MKn|MAP|MAg|MFarm|MPsi|MSn|MEcon)\b|'
    r'FINASIM|FACS|FICS|'
    r'CMA|CPA|CIA|CHRP|CPHR|QIA|CBV|CPMA|'
    r'CFA|CFP|QWP|FRM|PMP|CAPM|'
    r'CISA|CISM|CISSP|CEH|'
    r'CRA|CRP|CRGP|CSO|CGO|CGP|'
    r'Ak\.?|Akt\.?|CA\b|BKP|CTA|ACPA|'
    r'MM\.PD'
    r')$',
    re.IGNORECASE
)

BACK_TITLES_PATTERN = re.compile(
    r'(?:,\s*|\s+)(?:'
    r'[SMDA]\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|'
    r'Sp\.\s*[A-Za-z]+(?:\s*\([A-Za-z]+\)|-[A-Za-z0-9]+|(?:\.\s*[A-Za-z]+)*)\.?|'
    r'Subsp\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|'
    r'Ph\.?\s*D\.?|PhD|'
    r'M\.?\s*B\.?\s*A\.?|MBA|'
    r'M\.?\s*Bus\.?|'
    r'B\.?\s*[A-Z]\.?\s*(?:Sc|A)?\.?|'
    r'LL\.?\s*M\.?|LLM|'
    r'Ed\.?\s*D\.?|D\.?\s*Sc\.?|D\.?\s*B\.?\s*A\.?|'
    r'IP[UMP]\b\.?|'
    r'(?:ASEAN|Asean)\s+Eng\.?|'
    r'ACPE|CPE|'
    r'(?:SE|SH|ST|SKom|SPd|SSos|SIP|SIKom|SKM|SPi|SPt|SHut|SAg|SFarm|SPsi|SSn|SKed)\b|'
    r'(?:MM|MH|MT|ME|MSi|MPd|MKes|MKom|MA|MSc|MP|MKn|MAP|MAg|MFarm|MPsi|MSn|MEcon)\b|'
    r'FINASIM|FACS|FICS|'
    r'CMA|CPA|CIA|CHRP|CPHR|QIA|CBV|CPMA|'
    r'CFA|CFP|QWP|FRM|PMP|CAPM|'
    r'CISA|CISM|CISSP|CEH|'
    r'CRA|CRP|CRGP|CSO|CGO|CGP|'
    r'Ak\.?|Akt\.?|CA\b|BKP|CTA|ACPA|'
    r'MM\.PD|'
    r'H\.|Hj\.|Haji|Hajjah|Hajah|Hjh\.?'
    r')\b\.?',
    re.IGNORECASE
)

def clean_titles(name):
    """Removes leading list numbers/bullets, front and back titles/degrees, including Haji/Hajjah."""
    if not name:
        return ""
    s = name.strip()

    # Strip parenthesized religious titles e.g. "(H.) " or "(Hj.) "
    s = re.sub(r'^\s*\((?:H\.|Hj\.|Haji|Hajjah|Hajah|Hjh\.?)\)\s*', '', s, flags=re.IGNORECASE).strip()

    # 1. Strip leading numbering or bullet markers (e.g. "1. ", "2) ", "- ", "> ", "· ", "• ")
    prev = None
    while prev != s:
        prev = s
        s = LEADING_LIST_PREFIX_PATTERN.sub('', s).strip()

    # 2. Strip front titles & religious titles (e.g. "Prof. ", "Dr. ", "H. ", "Hj. ", "K.H. ", etc.)
    prev = None
    while prev != s:
        prev = s
        s = FRONT_TITLES_PATTERN.sub('', s).strip()

    # 3. Strip back titles / academic degrees
    prev = None
    while prev != s:
        prev = s
        s = BACK_TITLES_PATTERN.sub('', s).strip()

    # 4. Clean leftover punctuation at ends and normalize internal spacing
    s = re.sub(r'^[,\.\s\-–—>·•\:\=\|\/]+|[,\.\s\-–—>·•\:\=\|\/]+$', '', s).strip()

    # 5. Clean any trailing comma or short unrecognized title abbreviations
    while ',' in s:
        before, after = s.rsplit(',', 1)
        after_trim = after.strip()
        if re.match(r'^(?:[A-Z0-9\.\s\-\(\)]+|\(K\)|Konsultan)$', after_trim, re.IGNORECASE) and len(after_trim) <= 12:
            s = before.strip()
        else:
            break

    s = re.sub(r'^[,\.\s\-–—>·•\:\=\|\/]+|[,\.\s\-–—>·•\:\=\|\/]+$', '', s).strip()
    s = strip_trailing_punctuation(s)
    s = re.sub(r'\s+', ' ', s)
    return s

def format_bulk_name(raw_name, max_len=24):
    """
    1. Removes all front and back titles.
    2. If length > max_len: abbreviates the last name (e.g. Firmansyah -> F.).
    3. If still > max_len: uses words from beginning as much as fits (max_len).
    """
    cleaned = strip_trailing_punctuation(clean_titles(raw_name))
    if not cleaned:
        return ""
    if len(cleaned) <= max_len:
        return cleaned

    words = cleaned.split()
    if len(words) > 1:
        # Abbreviate last name
        last_word = words[-1]
        initial = last_word[0].upper() + "."
        candidate = " ".join(words[:-1]) + " " + initial
        if len(candidate) <= max_len:
            return candidate

        # If still > max_len: take words from beginning as much as fits
        result = ""
        for i in range(len(words) - 1):
            next_cand = (result + " " + words[i]).strip()
            if len(next_cand) <= max_len:
                result = next_cand
            else:
                init_cand = (result + " " + words[i][0].upper() + ".").strip()
                if len(init_cand) <= max_len:
                    result = init_cand
                break
        if result and len(result) <= max_len:
            return result

    return strip_trailing_punctuation(cleaned[:max_len].strip())

def strip_trailing_punctuation(text):
    """Strips trailing punctuation (dots, commas, semicolons, colons, dashes, etc.)
    except closing parentheses and brackets ), ], }."""
    if not text:
        return ""
    lines = str(text).splitlines()
    cleaned = []
    for l in lines:
        c = re.sub(r'[\s.,;:!?\-–—_/\t|*•·+~="\'\\`^]+$', '', l).strip()
        cleaned.append(c)
    return "\n".join(cleaned).strip()

def clean_position_text(pos):
    if not pos:
        return ""
    s = re.sub(r'^[\s\-–—>·•\:\=\|\/]+', '', str(pos)).strip()
    return strip_trailing_punctuation(s)

def split_name_and_position(line):
    """
    Parses a single line into (name, position) using any punctuation
    including parentheses, tabs, colons, dashes, etc.
    """
    line = line.strip()
    if not line:
        return "", ""

    # 1. Check parentheses / brackets: e.g. "Nama Pejabat (Jabatan Lengkap)"
    # or "Nama - Jabatan (Keterangan)"
    m = re.match(r'^(.*?)\s*[\(\[\{](.+?)[\)\]\}]\s*$', line)
    if m:
        before_paren = m.group(1).strip()
        inside_paren = m.group(2).strip()
        delims = ['\t', '|', ';', ':', ' - ', ' – ', ' — ', '=']
        found_delim = None
        for d in delims:
            if d in before_paren:
                found_delim = d
                break
        if found_delim:
            parts = before_paren.split(found_delim, 1)
            name_part = strip_trailing_punctuation(parts[0].strip())
            pos_part = clean_position_text(parts[1].strip() + " (" + inside_paren + ")")
            if name_part and pos_part:
                return name_part, pos_part
        else:
            name_part = strip_trailing_punctuation(before_paren)
            pos_part = clean_position_text(inside_paren)
            if name_part and pos_part:
                return name_part, pos_part

    # 2. Check explicit strong delimiters
    delims = ['\t', '|', ';', ':', ' - ', ' – ', ' — ', ' / ', '=']
    for d in delims:
        if d in line:
            parts = line.split(d, 1)
            return strip_trailing_punctuation(parts[0].strip()), clean_position_text(parts[1])

    # 3. Check for comma: could separate degrees or name/position
    if ',' in line:
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if len(parts) >= 2:
            last_part = parts[-1]
            is_title = bool(TITLE_TOKEN_PATTERN.match(last_part))
            if not is_title:
                return strip_trailing_punctuation(", ".join(parts[:-1])), clean_position_text(last_part)

    # 4. Check for single dash or slash between words
    for d in ['-', '/']:
        if d in line:
            parts = line.split(d, 1)
            if parts[0].strip() and parts[1].strip():
                return strip_trailing_punctuation(parts[0].strip()), clean_position_text(parts[1])

    # 5. Check if line contains position indicators starting with PLT / Plt / Plh / Pj separated by space
    pos_match = re.search(r'\s+(?:PLT\.?|Plt\.?|PLH\.?|Plh\.?|Pj\.?|PJ\.?)\s+', line)
    if pos_match:
        name_part = line[:pos_match.start()].strip()
        pos_part = line[pos_match.start():].strip()
        if name_part and pos_part:
            return strip_trailing_punctuation(name_part), clean_position_text(pos_part)

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


def wrap_60pt(text, max_len=36, max_width=MAX_TEXT_WIDTH, font=NAME_FONT):
    clean_text = (text or "").strip()[:max_len].strip()
    if not clean_text:
        return []
    if "\n" in clean_text:
        lines = [l.strip().upper() for l in clean_text.splitlines() if l.strip()]
        if len(lines) == 1:
            return [lines[0]]
        return [lines[0], " ".join(lines[1:])][:2]

    single_line = " ".join(clean_text.split()).upper()
    try:
        w = pdfmetrics.stringWidth(single_line, font, 60.0)
    except Exception:
        w = len(single_line) * 32.0

    if w <= max_width:
        return [single_line]

    words = single_line.split()
    if len(words) <= 1:
        return [single_line]

    best_diff = float("inf")
    best_split = [single_line]
    for i in range(1, len(words)):
        l1 = " ".join(words[:i])
        l2 = " ".join(words[i:])
        try:
            w1 = pdfmetrics.stringWidth(l1, font, 60.0)
            w2 = pdfmetrics.stringWidth(l2, font, 60.0)
        except Exception:
            w1 = len(l1) * 32.0
            w2 = len(l2) * 32.0

        if w1 <= max_width and w2 <= max_width:
            diff = abs(w1 - w2)
            if diff < best_diff:
                best_diff = diff
                best_split = [l1, l2]

    if best_diff == float("inf"):
        lines = []
        cur = ""
        for w_word in words:
            cand = (cur + " " + w_word).strip() if cur else w_word
            try:
                cw = pdfmetrics.stringWidth(cand, font, 60.0)
            except Exception:
                cw = len(cand) * 32.0
            if cw <= max_width:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                cur = w_word
                if len(lines) >= 2:
                    break
        if cur and len(lines) < 2:
            lines.append(cur)
        return lines[:2]

    return best_split


def layout_position_only(text, font=NAME_FONT, max_width=MAX_TEXT_WIDTH, max_chars=128):
    """
    Dynamic 1-to-3 line layout & auto-font-reduction for Position Only mode.
    Handles explicit newlines (Enter key) as well as continuous titles up to max_chars.
    Returns (lines, font_size, baselines).
    """
    if not text:
        return [], 40.0, []
    clean_text = text.strip()[:max_chars].strip()
    if not clean_text:
        return [], 40.0, []

    def measure(t, sz):
        try:
            return pdfmetrics.stringWidth(t, font, sz)
        except Exception:
            return len(t) * sz * 0.55

    def get_baselines(num_lines, sz):
        gap = sz * 1.25
        if num_lines == 1:
            return [86.0]
        elif num_lines == 2:
            return [86.0 + gap / 2.0, 86.0 - gap / 2.0]
        else:
            return [86.0 + gap, 86.0, 86.0 - gap]

    # 1. Explicit newlines entered by user
    if "\n" in clean_text:
        raw_lines = [l.strip().upper() for l in clean_text.splitlines() if l.strip()]
        if len(raw_lines) == 1:
            clean_text = raw_lines[0]
        elif len(raw_lines) == 2:
            l1, l2 = raw_lines[0], raw_lines[1]
            s = 46.0
            while s >= 16.0:
                if measure(l1, s) <= max_width and measure(l2, s) <= max_width:
                    break
                s -= 1.0
            return [l1, l2], s, get_baselines(2, s)
        else:
            l1, l2, l3 = raw_lines[0], raw_lines[1], " ".join(raw_lines[2:])
            s = 34.0
            while s >= 14.0:
                if measure(l1, s) <= max_width and measure(l2, s) <= max_width and measure(l3, s) <= max_width:
                    break
                s -= 1.0
            return [l1, l2, l3], s, get_baselines(3, s)

    # 2. Continuous text
    upper = " ".join(clean_text.split()).upper()
    words = upper.split()
    if not words:
        return [], 40.0, []

    # 2a. Check if fits on 1 line
    for s in [52.0, 48.0, 44.0, 40.0]:
        if measure(upper, s) <= max_width:
            return [upper], s, [86.0]

    # 2b. Try 2 lines
    if len(words) >= 2:
        for s in [44.0, 40.0, 36.0, 32.0, 30.0]:
            TARGET_RATIO = 0.60
            trailing_stopwords = {'DAN', 'ATAU', 'PADA', 'DI', 'KE', 'DENGAN', 'UNTUK'}
            candidates = []
            for i in range(1, len(words)):
                l1 = " ".join(words[:i])
                l2 = " ".join(words[i:])
                w1 = measure(l1, s)
                w2 = measure(l2, s)
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
                return candidates[0][2], s, get_baselines(2, s)

    # 2c. Try 3 lines
    if len(words) >= 3:
        for s in range(32, 13, -1):
            s_float = float(s)
            best_diff = float("inf")
            best_split = None
            n = len(words)
            for i in range(1, n - 1):
                for j in range(i + 1, n):
                    l1 = " ".join(words[:i])
                    l2 = " ".join(words[i:j])
                    l3 = " ".join(words[j:])
                    w1 = measure(l1, s_float)
                    w2 = measure(l2, s_float)
                    w3 = measure(l3, s_float)
                    if w1 <= max_width and w2 <= max_width and w3 <= max_width:
                        diff = max(w1, w2, w3) - min(w1, w2, w3)
                        if diff < best_diff:
                            best_diff = diff
                            best_split = [l1, l2, l3]
            if best_split:
                return best_split, s_float, get_baselines(3, s_float)

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

    return [upper], 16.0, [86.0]


def _draw_block(c, name, position_lines, content_mode="both"):
    """Draws the text block using local coords where (0,0)
    behaves like the normal (bottom, right-side-up) orientation."""
    if content_mode == "name_only":
        safe_name = (name or "").strip().upper()
        if safe_name:
            lines = wrap_60pt(safe_name, 36, font=NAME_FONT)
            c.setFont(NAME_FONT, 60.0)
            if len(lines) == 1:
                c.drawCentredString(CENTER_X, 86.0, lines[0])
            elif len(lines) >= 2:
                c.drawCentredString(CENTER_X, 115.0, lines[0])
                c.drawCentredString(CENTER_X, 57.0, lines[1])
        return

    if content_mode == "position_only":
        pos_text = position_lines if isinstance(position_lines, str) else "\n".join(position_lines)
        safe_pos = (pos_text or name or "").strip()
        if safe_pos:
            lines, font_sz, baselines = layout_position_only(safe_pos, font=NAME_FONT, max_width=MAX_TEXT_WIDTH, max_chars=128)
            c.setFont(NAME_FONT, font_sz)
            for line, y in zip(lines, baselines):
                c.drawCentredString(CENTER_X, y, line)
        return

    # Default 'both' mode
    safe_name = name.upper()
    c.setFont(NAME_FONT, NAME_FONT_SIZE)
    c.drawCentredString(CENTER_X, NAME_BASELINE_Y, safe_name)

    c.setFont(POSITION_FONT, POSITION_FONT_SIZE)
    baseline = NAME_BASELINE_Y - NAME_TO_POSITION_GAP
    for line in position_lines[:2]:
        c.drawCentredString(CENTER_X, baseline, line.upper())
        baseline -= POSITION_LINE_GAP


def build_pdf(name, position, output_path, sides="2", content_mode="both", **kwargs):
    """Renders one name-table PDF (one page, one card) to output_path."""
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))

    bg = ImageReader(BG_IMAGE)
    c.drawImage(bg, 0, 0, width=PAGE_W, height=PAGE_H,
                preserveAspectRatio=False, mask="auto")

    position_lines = wrap_position(position)

    # Normal orientation (bottom half, right-side-up)
    c.saveState()
    _draw_block(c, name, position_lines, content_mode=content_mode)
    c.restoreState()

    # Flipped orientation (top half, rotated 180 degrees about page center)
    if str(sides) != "1":
        c.saveState()
        c.translate(PAGE_W, PAGE_H)
        c.rotate(180)
        _draw_block(c, name, position_lines, content_mode=content_mode)
        c.restoreState()

    c.showPage()
    c.save()
    return output_path


def build_pdf_multipage(rows, output_path, sides="2", content_mode="both", **kwargs):
    """Renders multiple cards into a single multi-page PDF (one card per page)."""
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
    bg = ImageReader(BG_IMAGE)
    for row in rows:
        if isinstance(row, dict):
            name = row.get("name", "")
            position = row.get("position", "")
        else:
            name, position = row[0], row[1]
        c.drawImage(bg, 0, 0, width=PAGE_W, height=PAGE_H,
                    preserveAspectRatio=False, mask="auto")
        position_lines = wrap_position(position)
        # Normal orientation (bottom half, right-side-up)
        c.saveState()
        _draw_block(c, name, position_lines, content_mode=content_mode)
        c.restoreState()
        # Flipped orientation (top half, rotated 180 degrees about page center)
        if str(sides) != "1":
            c.saveState()
            c.translate(PAGE_W, PAGE_H)
            c.rotate(180)
            _draw_block(c, name, position_lines, content_mode=content_mode)
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
