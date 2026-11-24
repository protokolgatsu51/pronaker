/*
 * Shared name-table layout engine.
 *
 * The SAME code renders:
 *   1) the live in-browser preview (index.html, called on every keystroke)
 *   2) the exact page that Playwright screenshots to PDF (card.html)
 * so what you see in the preview is guaranteed to be what you get in the PDF.
 *
 * Geometry constants were measured directly from the reference PDF you
 * supplied (pdfplumber text positions), not eyeballed.
 */

const CARD = {
  PAGE_W: 841.89,      // pt (Standard A4 width: 297mm = 841.89pt)
  PAGE_H: 372.72,      // pt
  CENTER_X: 420.95,    // pt - exact horizontal center (PAGE_W / 2 = 841.89 / 2)
  OPTICAL_CENTER_Y: 97.45,    // pt - exact optical vertical center of card content
  NAME_BASELINE_Y: 102.5,     // pt from bottom
  NAME_TO_POSITION_GAP: 40.0, // pt, baseline to baseline
  POSITION_LINE_GAP: 20.0,    // pt, baseline to baseline between wrapped lines
  MAX_TEXT_WIDTH: 625.0,      // pt, wrap width for the position text (safe from logo)
  NAME_BOX_WIDTH: 625.0,      // pt, centered name text box boundary
  MAX_NAME_WIDTH: 625.0,      // pt, maximum text width before auto-abbreviation
  NAME_FONT_SIZE: 45.86,      // pt
  POSITION_FONT_SIZE: 18.0,   // pt
  NAME_FONT_WEIGHT: 700,
  POSITION_FONT_WEIGHT: 700,
  FONT_FAMILY: '"Montserrat-Bold", Montserrat, sans-serif',
  NAME_FONT_FAMILY: '"Montserrat-Bold", Montserrat, sans-serif',
  POSITION_FONT_FAMILY: '"Montserrat-Bold", Montserrat, sans-serif',
  CUSTOM_NAME_FONT_SIZE: null,
  CUSTOM_POS_FONT_SIZE: null,
  TEXT_CASE: "uppercase",      // "uppercase", "capitalize", "lowercase"
  PAPER_SIZE: "a4",
  SIDES: 2,
  BG_URL: "",
  ASCENT_RATIO: 0.75,
  CONTENT_MODE: "both",
  HORIZONTAL_OFFSET: 0.0,
  MODE_60PT_FONT_SIZE: 60.0,
  MODE_60PT_MAX_CHARS: 36,
  MODE_60PT_SINGLE_BASELINE_Y: 86.0,
  MODE_60PT_LINE1_BASELINE_Y: 115.0,
  MODE_60PT_LINE2_BASELINE_Y: 57.0,
};

function setHorizontalOffset(offset) {
  CARD.HORIZONTAL_OFFSET = parseFloat(offset) || 0.0;
}

// Sanitizes tabs, NBSP, zero-width spaces, and control chars
function sanitizeText(text, preserveNewlines = false) {
  if (!text) return "";
  if (preserveNewlines) {
    return String(text)
      .replace(/[\t\v\f\u00a0\u200b\u200e\u200f\ufeff]+/g, " ")
      .split(/\r?\n/)
      .map(l => l.replace(/^[ ]+|[ ]+$/g, "").replace(/[ ]+/g, " "))
      .join("\n");
  }
  return String(text).replace(/[\t\r\n\v\f\u00a0\u200b\u200e\u200f\ufeff]+/g, " ").trim().replace(/\s+/g, " ");
}

// Applies uppercase, capitalize (title case), or lowercase
function applyTextCase(text, textCase = "uppercase") {
  if (!text) return "";
  const s = sanitizeText(text, true);
  if (textCase === "capitalize") {
    return s.toLowerCase().replace(/(?:^|[\s/\-\(\)])[a-z]/g, (m) => m.toUpperCase());
  } else if (textCase === "lowercase") {
    return s.toLowerCase();
  } else {
    return s.toUpperCase();
  }
}

// pt -> px, for canvas text measurement only (canvas always measures in css px)
function ptToPx(pt) {
  return pt * (96 / 72);
}

let _measureCanvas = null;
function measureTextWidthPt(text, weight, sizePt, fontFamily = null) {
  if (!_measureCanvas) _measureCanvas = document.createElement("canvas");
  const ctx = _measureCanvas.getContext("2d");
  const fam = fontFamily || (weight >= 600 ? CARD.NAME_FONT_FAMILY : CARD.POSITION_FONT_FAMILY) || CARD.FONT_FAMILY;
  ctx.font = `${weight} ${ptToPx(sizePt)}px ${fam}`;
  const widthPx = ctx.measureText(text).width;
  return widthPx / (96 / 72);
}

// Strips trailing punctuation (commas, semicolons, colons, dashes, etc.)
// Preserves trailing period if part of an academic degree abbreviation (e.g. M.T., Ph.D.)
function stripTrailingPunctuation(text) {
  if (!text) return "";
  const lines = String(text).split(/\r?\n/);
  const cleaned = lines.map(l => {
    let c = l.replace(/[\s,;:!?\-–—_/\t|*•·+~="\'\\`^]+$/, "").trim();
    if (!/\b[A-Za-z]\.$/.test(c)) {
      c = c.replace(/\.+$/, "").trim();
    }
    return c;
  });
  return cleaned.join("\n").trim();
}

// Expands Kemnaker abbreviations (Sekretaris Ditjen, Biro Humas, Barenbang, etc.)
function expandKemnakerPosition(pos) {
  if (!pos) return "";
  let s = String(pos).trim();
  s = stripTrailingPunctuation(s);

  // 1. Sesditjen / Sesitjen / Sesbadan prefixes
  s = s.replace(/\bSesditjen\b/gi, "Sekretaris Direktorat Jenderal");
  s = s.replace(/\bSesitjen\b/gi, "Sekretaris Inspektorat Jenderal");
  s = s.replace(/\bSesbadan\b/gi, "Sekretaris Badan");

  // 2. Specific Ditjen / Unit abbreviations
  s = s.replace(
    /\b(?:Sekretaris\s+)?(?:Ditjen|Direktorat Jenderal)\s+(?:Binapenta\s*&\s*PKK|Binapenta\s+dan\s+PKK|Binapenta)\b/gi,
    (m) => (/sekretaris/i.test(m) ? "Sekretaris " : "") +
           "Direktorat Jenderal Pembinaan Penempatan Tenaga Kerja dan Perluasan Kesempatan Kerja"
  );
  s = s.replace(
    /\b(?:Sekretaris\s+)?(?:Ditjen|Direktorat Jenderal)\s+(?:PHI\s*[-–—]\s*JSK|PHI\s*&\s*JSK|PHI\s+dan\s+JSK|PHI)\b/gi,
    (m) => (/sekretaris/i.test(m) ? "Sekretaris " : "") +
           "Direktorat Jenderal Pembinaan Hubungan Industrial dan Jaminan Sosial Tenaga Kerja"
  );
  s = s.replace(
    /\b(?:Sekretaris\s+)?(?:Ditjen|Direktorat Jenderal)\s+(?:Binalavotas|Binalattas)\b/gi,
    (m) => (/sekretaris/i.test(m) ? "Sekretaris " : "") +
           "Direktorat Jenderal Pembinaan Pelatihan Vokasi dan Produktivitas"
  );
  s = s.replace(
    /\b(?:Sekretaris\s+)?(?:Ditjen|Direktorat Jenderal)\s+(?:Binwasnaker\s*&\s*K3|Binwasnaker\s+dan\s+K3|Binwasnaker)\b/gi,
    (m) => (/sekretaris/i.test(m) ? "Sekretaris " : "") +
           "Direktorat Jenderal Pembinaan Pengawasan Ketenagakerjaan dan Keselamatan dan Kesehatan Kerja"
  );

  // 3. Barenbang
  s = s.replace(/\bSekretaris\s+Barenbang\b/gi, "Sekretaris Badan Perencanaan dan Pengembangan Ketenagakerjaan");
  s = s.replace(/\bKepala\s+Barenbang\b/gi, "Kepala Badan Perencanaan dan Pengembangan Ketenagakerjaan");

  // 4. Biro Humas -> Biro Hubungan Masyarakat
  s = s.replace(/\bBiro\s+Humas\b/gi, "Biro Hubungan Masyarakat");

  // 5. Standalone Ditjen / Setjen / Itjen
  s = s.replace(/\bDitjen\b/gi, "Direktorat Jenderal");
  s = s.replace(/\bSetjen\b/gi, "Sekretariat Jenderal");
  s = s.replace(/\bItjen\b/gi, "Inspektorat Jenderal");

  // 6. Normalize Menteri & Wakil Menteri
  if (s.toLowerCase() === "wakil menteri ketenagakerjaan") {
    s = "Wakil Menteri Ketenagakerjaan Republik Indonesia";
  } else if (s.toLowerCase() === "menteri ketenagakerjaan") {
    s = "Menteri Ketenagakerjaan Republik Indonesia";
  }

  s = s.replace(/\s+/g, " ").trim();
  return s;
}

// Word-wrap using the REAL font metrics (same font used for the PDF),
// 1) Supports user explicit Enter key for Single Generator (\n) to control Line 1 & Line 2
// 2) Uses balanced 2-line wrap for Bulk Generator to prevent 'jomplang' / orphaned words
// Max 128 characters, strictly max 2 lines.
function wrapPosition(text) {
  if (!text || typeof text !== "string") return [];
  let cleanText = stripTrailingPunctuation(text.trim());
  if (cleanText.length > 128) {
    cleanText = stripTrailingPunctuation(cleanText.substring(0, 128).trim());
  }
  if (!cleanText) return [];

  // 1. Explicit newline from Single Generator (Enter key)
  if (cleanText.includes("\n")) {
    const rawLines = cleanText.split(/\r?\n/)
      .map(l => stripTrailingPunctuation(l.trim()).replace(/\s+/g, " "))
      .filter(Boolean);
    if (rawLines.length === 1) {
      return [rawLines[0]];
    }
    if (rawLines.length >= 2) {
      const l1 = rawLines[0];
      const l2 = rawLines.slice(1).join(" ");
      return [l1, l2].slice(0, 2);
    }
  }

  // 2. Single continuous line (or Bulk Generator input)
  const singleLine = cleanText.replace(/\s+/g, " ");
  const activeCase = CARD.TEXT_CASE || "uppercase";
  const measuredSingle = applyTextCase(singleLine, activeCase);
  if (measureTextWidthPt(measuredSingle, CARD.POSITION_FONT_WEIGHT, CARD.POSITION_FONT_SIZE) <= CARD.MAX_TEXT_WIDTH) {
    return [singleLine];
  }

  // 2-line wrap: line 1 must fit and must always be longer than line 2 (w1 > w2)
  const words = singleLine.split(" ");
  if (words.length <= 1) {
    return [singleLine];
  }

  const TARGET_RATIO = 0.60;
  const trailingStopwords = new Set(['DAN', 'ATAU', 'PADA', 'DI', 'KE', 'DENGAN', 'UNTUK']);
  const candidates = [];

  for (let i = 1; i < words.length; i++) {
    const l1 = words.slice(0, i).join(" ");
    const l2 = words.slice(i).join(" ");
    const ml1 = applyTextCase(l1, activeCase);
    const ml2 = applyTextCase(l2, activeCase);
    const w1 = measureTextWidthPt(ml1, CARD.POSITION_FONT_WEIGHT, CARD.POSITION_FONT_SIZE);
    const w2 = measureTextWidthPt(ml2, CARD.POSITION_FONT_WEIGHT, CARD.POSITION_FONT_SIZE);

    if (w1 <= CARD.MAX_TEXT_WIDTH && w2 <= CARD.MAX_TEXT_WIDTH) {
      const totalW = w1 + w2;
      const ratio = totalW > 0 ? w1 / totalW : 0.5;
      const isTopHeavy = w1 > w2;
      const lastWordL1 = words[i - 1].toUpperCase();
      const trailingPenalty = trailingStopwords.has(lastWordL1) ? 0.15 : 0.0;

      let score, priority;
      if (isTopHeavy) {
        score = Math.abs(ratio - TARGET_RATIO) + trailingPenalty;
        priority = 0;
      } else {
        score = (0.55 - ratio) + 1.0 + trailingPenalty;
        priority = 1;
      }
      candidates.push({ priority, score, lines: [l1, l2] });
    }
  }

  if (candidates.length > 0) {
    candidates.sort((a, b) => a.priority - b.priority || a.score - b.score);
    return candidates[0].lines;
  }

  // Fallback to greedy wrap if no split fits both lines within max width
  const lines = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? current + " " + word : word;
    if (measureTextWidthPt(candidate, CARD.POSITION_FONT_WEIGHT, CARD.POSITION_FONT_SIZE) <= CARD.MAX_TEXT_WIDTH) {
      current = candidate;
    } else {
      if (current) lines.push(current);
      current = word;
      if (lines.length >= 2) break;
    }
  }
  if (current && lines.length < 2) {
    lines.push(current);
  }
  return lines.slice(0, 2);
}

// Word-wrap for Name Only mode:
// - Respects user's explicit Enter key breaks (\n) verbatim (up to 4 lines)
// - When continuous, measures with the active fontSize & fontFamily so shrinking font size allows single-line fit
function wrap60pt(text, maxChars = 128, fontSizePt = CARD.MODE_60PT_FONT_SIZE, fontFamily = null) {
  if (!text || typeof text !== "string") return [];
  let cleanText = stripTrailingPunctuation(text.trim());
  if (cleanText.length > maxChars) {
    cleanText = stripTrailingPunctuation(cleanText.substring(0, maxChars).trim());
  }
  if (!cleanText) return [];

  const sz = (fontSizePt && !isNaN(parseFloat(fontSizePt))) ? parseFloat(fontSizePt) : CARD.MODE_60PT_FONT_SIZE;
  const fam = fontFamily || CARD.NAME_FONT_FAMILY;

  // 1. Explicit newline (Enter key) — preserve user's exact lines per line break!
  if (cleanText.includes("\n")) {
    const rawLines = cleanText.split(/\r?\n/)
      .map(l => stripTrailingPunctuation(l.trim()).replace(/\s+/g, " "))
      .filter(Boolean);
    if (rawLines.length >= 1) {
      return rawLines.slice(0, 4);
    }
  }

  // 2. Single continuous line — measure using the ACTUAL chosen fontSize & fontFamily
  const singleLine = cleanText.replace(/\s+/g, " ");
  const widthPt = measureTextWidthPt(singleLine, CARD.NAME_FONT_WEIGHT, sz, fam);
  if (widthPt <= CARD.MAX_TEXT_WIDTH) {
    return [singleLine];
  }

  // 3. Balanced 2-line wrap measured at sz & fam
  const words = singleLine.split(" ").filter(Boolean);
  if (words.length <= 1) {
    return [singleLine];
  }

  let bestDiff = Infinity;
  let bestSplit = null;
  for (let i = 1; i < words.length; i++) {
    const l1 = words.slice(0, i).join(" ");
    const l2 = words.slice(i).join(" ");
    const w1 = measureTextWidthPt(l1, CARD.NAME_FONT_WEIGHT, sz, fam);
    const w2 = measureTextWidthPt(l2, CARD.NAME_FONT_WEIGHT, sz, fam);
    if (w1 <= CARD.MAX_TEXT_WIDTH && w2 <= CARD.MAX_TEXT_WIDTH) {
      const diff = Math.abs(w1 - w2);
      if (diff < bestDiff) {
        bestDiff = diff;
        bestSplit = [l1, l2];
      }
    }
  }

  if (bestSplit) {
    return bestSplit;
  }

  // 4. Greedy wrap (or balanced 2-line fallback if text scales down in layoutBlock)
  let current = "";
  const lines = [];
  for (const w of words) {
    const candidate = current ? current + " " + w : w;
    if (measureTextWidthPt(candidate, CARD.NAME_FONT_WEIGHT, sz, fam) <= CARD.MAX_TEXT_WIDTH) {
      current = candidate;
    } else {
      if (current) lines.push(current);
      current = w;
      if (lines.length >= 3) break;
    }
  }
  if (current && lines.length < 3) lines.push(current);
  if (lines.length === 0) return [singleLine];
  return lines.slice(0, 3);
}

// Dynamic layout for Position Only (Jabatan Saja) mode:
// - Respects explicit Enter key breaks (\n) verbatim (up to 4 lines) without re-splitting lines
// - Respects user's manual font size & chosen font family before deciding whether continuous text wraps
function layoutPositionOnly(text, maxChars = 128, fontFamily = null, customSizePt = null) {
  if (!text || typeof text !== "string") {
    return { lines: [], fontSize: 40, baselines: [] };
  }
  let cleanText = stripTrailingPunctuation(text.trim());
  if (cleanText.length > maxChars) {
    cleanText = stripTrailingPunctuation(cleanText.substring(0, maxChars).trim());
  }
  if (!cleanText) {
    return { lines: [], fontSize: 40, baselines: [] };
  }

  const weight = CARD.POSITION_FONT_WEIGHT || CARD.NAME_FONT_WEIGHT;
  const fam = fontFamily || CARD.POSITION_FONT_FAMILY;
  const maxW = CARD.MAX_TEXT_WIDTH;
  const hasCustom = customSizePt !== null && customSizePt !== undefined && customSizePt !== "auto" && !isNaN(parseFloat(customSizePt));
  const targetSize = hasCustom ? parseFloat(customSizePt) : null;

  function getBaselines(numLines, fontSize) {
    const gap = Math.max(fontSize * 1.25, fontSize + 4.0);
    if (numLines === 1) {
      return [86.0];
    } else if (numLines === 2) {
      return [86.0 + gap / 2.0, 86.0 - gap / 2.0];
    } else if (numLines === 3) {
      return [86.0 + gap, 86.0, 86.0 - gap];
    } else {
      const top = 86.0 + ((numLines - 1) * gap) / 2.0;
      return Array.from({ length: numLines }, (_, i) => top - i * gap);
    }
  }

  // 1. Explicit newlines entered by user (Enter key) — preserve lines per Enter break!
  if (cleanText.includes("\n")) {
    const rawLines = cleanText.split(/\r?\n/)
      .map(l => stripTrailingPunctuation(l.trim()).replace(/\s+/g, " "))
      .filter(Boolean);

    if (rawLines.length === 1) {
      cleanText = rawLines[0];
    } else if (rawLines.length >= 2) {
      const keptLines = rawLines.slice(0, 4);
      let s = hasCustom
        ? targetSize
        : (keptLines.length === 2 ? 46.0 : (keptLines.length === 3 ? 34.0 : 26.0));
      const minAuto = keptLines.length <= 2 ? 12.0 : 10.0;
      if (hasCustom) {
        let maxLineW = 0;
        keptLines.forEach(l => {
          const w = measureTextWidthPt(l, weight, s, fam);
          if (w > maxLineW) maxLineW = w;
        });
        if (maxLineW > maxW && maxW > 0) {
          s = Math.max(8.0, Math.floor(s * (maxW / maxLineW) * 10) / 10);
        }
      } else {
        while (s > minAuto) {
          if (keptLines.every(l => measureTextWidthPt(l, weight, s, fam) <= maxW)) {
            break;
          }
          s -= 1.0;
        }
      }
      return { lines: keptLines, fontSize: s, baselines: getBaselines(keptLines.length, s) };
    }
  }

  // 2. Continuous text (no explicit Enter breaks)
  const continuousText = cleanText.replace(/\s+/g, " ");
  const words = continuousText.split(" ").filter(Boolean);
  if (words.length === 0) {
    return { lines: [], fontSize: hasCustom ? targetSize : 40, baselines: [] };
  }

  // Helper to find balanced 2-line split at a specific font size
  function findBalanced2Lines(sz) {
    if (words.length < 2) return null;
    const TARGET_RATIO = 0.60;
    const trailingStopwords = new Set(['DAN', 'ATAU', 'PADA', 'DI', 'KE', 'DENGAN', 'UNTUK']);
    const candidates = [];
    for (let i = 1; i < words.length; i++) {
      const l1 = words.slice(0, i).join(" ");
      const l2 = words.slice(i).join(" ");
      const w1 = measureTextWidthPt(l1, weight, sz, fam);
      const w2 = measureTextWidthPt(l2, weight, sz, fam);
      if (w1 <= maxW && w2 <= maxW) {
        const totalW = w1 + w2;
        const ratio = totalW > 0 ? w1 / totalW : 0.5;
        const isTopHeavy = w1 > w2;
        const lastWordL1 = words[i - 1].toUpperCase();
        const trailingPenalty = trailingStopwords.has(lastWordL1) ? 0.15 : 0.0;

        let score, priority;
        if (isTopHeavy) {
          score = Math.abs(ratio - TARGET_RATIO) + trailingPenalty;
          priority = 0;
        } else {
          score = (0.55 - ratio) + 1.0 + trailingPenalty;
          priority = 1;
        }
        candidates.push({ priority, score, lines: [l1, l2] });
      }
    }
    if (candidates.length > 0) {
      candidates.sort((a, b) => a.priority - b.priority || a.score - b.score);
      return candidates[0].lines;
    }
    return null;
  }

  function findBalanced3Lines(sz) {
    if (words.length < 3) return null;
    let bestDiff = Infinity;
    let bestSplit = null;
    const n = words.length;
    for (let i = 1; i < n - 1; i++) {
      for (let j = i + 1; j < n; j++) {
        const l1 = words.slice(0, i).join(" ");
        const l2 = words.slice(i, j).join(" ");
        const l3 = words.slice(j).join(" ");
        const w1 = measureTextWidthPt(l1, weight, sz, fam);
        const w2 = measureTextWidthPt(l2, weight, sz, fam);
        const w3 = measureTextWidthPt(l3, weight, sz, fam);
        if (w1 <= maxW && w2 <= maxW && w3 <= maxW) {
          const diff = Math.max(w1, w2, w3) - Math.min(w1, w2, w3);
          if (diff < bestDiff) {
            bestDiff = diff;
            bestSplit = [l1, l2, l3];
          }
        }
      }
    }
    return bestSplit;
  }

  // If user chose an explicit manual font size, evaluate wrapping AT that font size first!
  if (hasCustom) {
    if (measureTextWidthPt(continuousText, weight, targetSize, fam) <= maxW) {
      return { lines: [continuousText], fontSize: targetSize, baselines: getBaselines(1, targetSize) };
    }
    const split2 = findBalanced2Lines(targetSize);
    if (split2) {
      return { lines: split2, fontSize: targetSize, baselines: getBaselines(2, targetSize) };
    }
    const split3 = findBalanced3Lines(targetSize);
    if (split3) {
      return { lines: split3, fontSize: targetSize, baselines: getBaselines(3, targetSize) };
    }
    // Greedy wrap at targetSize (will scale down in layoutBlock if any line still overflows)
    const gLines = [];
    let gCur = "";
    for (const w of words) {
      const cand = gCur ? gCur + " " + w : w;
      if (measureTextWidthPt(cand, weight, targetSize, fam) <= maxW) {
        gCur = cand;
      } else {
        if (gCur) gLines.push(gCur);
        gCur = w;
        if (gLines.length === 3) break;
      }
    }
    if (gCur && gLines.length < 4) gLines.push(gCur);
    if (gLines.length > 0) {
      return { lines: gLines, fontSize: targetSize, baselines: getBaselines(gLines.length, targetSize) };
    }
    return { lines: [continuousText], fontSize: targetSize, baselines: getBaselines(1, targetSize) };
  }

  // Auto mode: Step 2a: Check if fits on 1 line
  for (const s of [52, 48, 44, 40]) {
    if (measureTextWidthPt(continuousText, weight, s, fam) <= maxW) {
      return { lines: [continuousText], fontSize: s, baselines: [86.0] };
    }
  }

  // Auto mode: Step 2b: Try 2 lines
  for (const s of [44, 40, 36, 32, 30]) {
    const split2 = findBalanced2Lines(s);
    if (split2) {
      return { lines: split2, fontSize: s, baselines: getBaselines(2, s) };
    }
  }

  // Auto mode: Step 2c: Try 3 lines
  for (let s = 32; s >= 14; s -= 1) {
    const split3 = findBalanced3Lines(s);
    if (split3) {
      return { lines: split3, fontSize: s, baselines: getBaselines(3, s) };
    }
  }

  // Fallback greedy wrap up to 3 lines
  for (let s = 22; s >= 12; s -= 1) {
    const lines = [];
    let current = "";
    for (const w of words) {
      const candidate = current ? current + " " + w : w;
      if (measureTextWidthPt(candidate, weight, s, fam) <= maxW) {
        current = candidate;
      } else {
        if (current) lines.push(current);
        current = w;
        if (lines.length === 2) break;
      }
    }
    if (current) lines.push(current);
    if (lines.length <= 3 && lines.every(l => measureTextWidthPt(l, weight, s, fam) <= maxW)) {
      return { lines, fontSize: s, baselines: getBaselines(lines.length, s) };
    }
  }

  return { lines: [continuousText], fontSize: 16, baselines: [86.0] };
}

// Font metrics helper to support dynamic optical centering across various typography
function getFontMetrics(fontFamily) {
  const f = (fontFamily || "").toLowerCase();
  if (f.includes("times") || f.includes("garamond") || f.includes("georgia")) {
    return { ascentRatio: 0.69, descentRatio: 0.22 };
  }
  if (f.includes("myriad") || f.includes("arial") || f.includes("calibri")) {
    return { ascentRatio: 0.72, descentRatio: 0.24 };
  }
  if (f.includes("roboto") || f.includes("open sans")) {
    return { ascentRatio: 0.73, descentRatio: 0.23 };
  }
  if (f.includes("jakarta")) {
    return { ascentRatio: 0.74, descentRatio: 0.24 };
  }
  // Default (Montserrat & custom)
  return { ascentRatio: 0.75, descentRatio: 0.25 };
}

// Calculates aesthetically proportional spacing gap based on font sizes and font metrics.
// Calibrated to yield exactly 40.0 pt for standard Kemnaker fonts (45.86 pt and 18.0 pt Montserrat).
function calculateAutoSpacingGap(nameFontSize, posFontSize, nameFontFamily, posFontFamily) {
  const nMetrics = getFontMetrics(nameFontFamily);
  const pMetrics = getFontMetrics(posFontFamily);
  const nDescent = nMetrics.descentRatio * nameFontSize;
  const pAscent = pMetrics.ascentRatio * posFontSize;
  const visualGap = (nameFontSize + posFontSize) * 0.2354;
  return Math.round((nDescent + pAscent + visualGap) * 10) / 10;
}

// top offset (pt, from the top of the page) for a text box whose baseline
// should land at `baselineFromBottomPt`, given line-height:1.
function boxTopForBaseline(baselineFromBottomPt, fontSizePt, ascentRatio = null) {
  const ratio = (ascentRatio !== null && ascentRatio !== undefined) ? ascentRatio : CARD.ASCENT_RATIO;
  return CARD.PAGE_H - baselineFromBottomPt - ratio * fontSizePt;
}

const DEFAULT_PREVIEW_NAME = "TAMPILAN NAMA LENGKAP";
const DEFAULT_PREVIEW_POSITION = "TAMPILAN JABATAN ATAU POSISI";

function makeLine(text, {top, left, width, size, weight, opacity, fontFamily, centerX = null}) {
  const div = document.createElement("div");
  div.textContent = text;
  div.style.position = "absolute";
  if (centerX !== null && centerX !== undefined) {
    div.style.left = centerX + "pt";
    div.style.transform = "translateX(-50%)";
  } else {
    div.style.left = left + "pt";
    div.style.width = width + "pt";
  }
  div.style.top = top + "pt";
  div.style.fontFamily = fontFamily || CARD.FONT_FAMILY;
  div.style.fontWeight = weight;
  div.style.fontSize = size + "pt";
  div.style.lineHeight = "1";
  div.style.textAlign = "center";
  div.style.whiteSpace = "nowrap";
  div.style.color = "#111111";
  div.style.webkitFontSmoothing = "antialiased";
  div.style.textRendering = "geometricPrecision";
  if (opacity !== undefined && opacity !== null) {
    div.style.opacity = opacity;
  }
  return div;
}

function layoutBlock(container, name, positionLines, options = {}) {
  if (!container) return;
  container.innerHTML = "";

  const mode = options.mode || CARD.CONTENT_MODE || "both";
  const nameOpacity = options.nameOpacity !== undefined ? options.nameOpacity : 1.0;
  const positionOpacity = options.positionOpacity !== undefined ? options.positionOpacity : 1.0;
  const textCase = options.textCase || CARD.TEXT_CASE || "uppercase";
  const nameFontFamily = options.nameFontFamily || CARD.NAME_FONT_FAMILY || CARD.FONT_FAMILY;
  const posFontFamily = options.posFontFamily || CARD.POSITION_FONT_FAMILY || CARD.FONT_FAMILY;
  const customNameSize = options.nameFontSize || CARD.CUSTOM_NAME_FONT_SIZE;
  const customPosSize = options.posFontSize || CARD.CUSTOM_POS_FONT_SIZE;
  const horizontalOffset = options.horizontalOffset !== undefined
    ? parseFloat(options.horizontalOffset)
    : (CARD.HORIZONTAL_OFFSET || 0.0);
  const cx = CARD.CENTER_X + horizontalOffset;
  const opticalCenterY = CARD.OPTICAL_CENTER_Y || 97.45;
  const nameMetrics = getFontMetrics(nameFontFamily);
  const posMetrics = getFontMetrics(posFontFamily);

  // Only clean titles if explicitly requested (e.g. bulk import or official kemnaker dropdown)
  const cleanN = (options.cleanTitles && typeof cleanTitles === "function")
    ? cleanTitles(name)
    : (typeof sanitizeText === "function" ? sanitizeText(name, mode === "name_only") : (name || ""));
  const safeName = applyTextCase(cleanN, textCase);

  // Mode: Nama Saja (Dynamic optical vertical centering + manual line & spacing support)
  if (mode === "name_only") {
    if (!safeName) return;
    const targetNameSize = (customNameSize && customNameSize !== "auto") ? parseFloat(customNameSize) : CARD.MODE_60PT_FONT_SIZE;
    let fontSize = targetNameSize;
    const lines = wrap60pt(safeName, 128, targetNameSize, nameFontFamily);
    // Boundary protection: enforce safe margin (CARD.MAX_TEXT_WIDTH = 625 pt)
    lines.forEach(line => {
      const w = measureTextWidthPt(line, CARD.NAME_FONT_WEIGHT, fontSize, nameFontFamily);
      if (w > CARD.MAX_TEXT_WIDTH && CARD.MAX_TEXT_WIDTH > 0) {
        fontSize = Math.floor(fontSize * (CARD.MAX_TEXT_WIDTH / w) * 10) / 10;
      }
    });

    const nameAscent = nameMetrics.ascentRatio * fontSize;
    const nameDescent = nameMetrics.descentRatio * fontSize;
    const n = lines.length;
    const autoLineGap = Math.max(fontSize * 1.15, fontSize + 6.0);
    const hasManualSpacing = (options.isAutoSpacing === false && options.spacingGap !== undefined && options.spacingGap !== null && options.spacingGap !== "auto");
    const lineGap = hasManualSpacing ? parseFloat(options.spacingGap) : autoLineGap;
    const topBaseline = opticalCenterY + ((n - 1) * lineGap + nameDescent - nameAscent) / 2.0;

    for (let i = 0; i < n; i++) {
      const baseline = topBaseline - i * lineGap;
      const top = boxTopForBaseline(baseline, fontSize, nameMetrics.ascentRatio);
      container.appendChild(makeLine(lines[i], {
        top: top,
        left: cx - CARD.MAX_TEXT_WIDTH / 2,
        width: CARD.MAX_TEXT_WIDTH,
        centerX: cx,
        size: fontSize,
        weight: CARD.NAME_FONT_WEIGHT,
        opacity: nameOpacity,
        fontFamily: nameFontFamily,
      }));
    }
    return;
  }

  // Mode: Jabatan Saja (Dynamic optical vertical centering + manual line, size, & spacing support)
  if (mode === "position_only") {
    const rawPosText = options.rawPosition !== undefined
      ? options.rawPosition
      : (Array.isArray(positionLines) ? positionLines.join("\n") : (positionLines || name || ""));
    const safePos = applyTextCase(sanitizeText(rawPosText || "", true), textCase);
    if (!safePos) return;
    const { lines, fontSize } = layoutPositionOnly(safePos, 128, posFontFamily, customPosSize);
    let finalSize = (customPosSize && customPosSize !== "auto") ? parseFloat(customPosSize) : fontSize;
    // Boundary protection: enforce safe margin (CARD.MAX_TEXT_WIDTH = 625 pt)
    lines.forEach(line => {
      const w = measureTextWidthPt(line, CARD.POSITION_FONT_WEIGHT, finalSize, posFontFamily);
      if (w > CARD.MAX_TEXT_WIDTH && CARD.MAX_TEXT_WIDTH > 0) {
        finalSize = Math.floor(finalSize * (CARD.MAX_TEXT_WIDTH / w) * 10) / 10;
      }
    });

    const posAscent = posMetrics.ascentRatio * finalSize;
    const posDescent = posMetrics.descentRatio * finalSize;
    const n = lines.length;
    const autoLineGap = Math.max(finalSize * 1.25, finalSize + 4.0);
    const hasManualSpacing = (options.isAutoSpacing === false && options.spacingGap !== undefined && options.spacingGap !== null && options.spacingGap !== "auto");
    const lineGap = hasManualSpacing ? parseFloat(options.spacingGap) : autoLineGap;
    const topBaseline = opticalCenterY + ((n - 1) * lineGap + posDescent - posAscent) / 2.0;

    for (let i = 0; i < n; i++) {
      const baseline = topBaseline - i * lineGap;
      const top = boxTopForBaseline(baseline, finalSize, posMetrics.ascentRatio);
      container.appendChild(makeLine(lines[i], {
        top: top,
        left: cx - CARD.MAX_TEXT_WIDTH / 2,
        width: CARD.MAX_TEXT_WIDTH,
        centerX: cx,
        size: finalSize,
        weight: CARD.POSITION_FONT_WEIGHT,
        opacity: positionOpacity,
        fontFamily: posFontFamily,
      }));
    }
    return;
  }

  // Mode: Nama & Jabatan (Default standard layout with Dynamic Optical Centering)
  const safeLines = (Array.isArray(positionLines) ? positionLines : (positionLines ? [positionLines] : []))
    .map(l => applyTextCase(sanitizeText(l), textCase))
    .filter(Boolean)
    .slice(0, 2);
  const numPosLines = safeLines.length;

  // 1. Calculate actual font sizes (handling custom sizes and auto-fit boundary constraints)
  let nameFontSize = customNameSize && customNameSize !== "auto" ? parseFloat(customNameSize) : CARD.NAME_FONT_SIZE;
  if (safeName) {
    const measuredW = measureTextWidthPt(safeName, CARD.NAME_FONT_WEIGHT, nameFontSize, nameFontFamily);
    // Boundary protection: enforce safe margin (CARD.NAME_BOX_WIDTH = 625 pt) so text never touches Kemnaker/Indonesia Emas logos
    if (measuredW > CARD.NAME_BOX_WIDTH && CARD.NAME_BOX_WIDTH > 0) {
      nameFontSize = Math.floor(nameFontSize * (CARD.NAME_BOX_WIDTH / measuredW) * 10) / 10;
    }
  }

  let posFontSize = customPosSize && customPosSize !== "auto" ? parseFloat(customPosSize) : CARD.POSITION_FONT_SIZE;
  if (numPosLines > 0) {
    safeLines.forEach(line => {
      const measuredLineW = measureTextWidthPt(line, CARD.POSITION_FONT_WEIGHT, posFontSize, posFontFamily);
      if (measuredLineW > CARD.MAX_TEXT_WIDTH && CARD.MAX_TEXT_WIDTH > 0) {
        posFontSize = Math.floor(posFontSize * (CARD.MAX_TEXT_WIDTH / measuredLineW) * 10) / 10;
      }
    });
  }

  // 2. Determine effective spacing gap:
  // Proportional spacing calculated from actual font sizes and metrics unless manually overridden
  const autoGap = calculateAutoSpacingGap(nameFontSize, posFontSize, nameFontFamily, posFontFamily);
  let effectiveSpacingGap;
  if (options.isAutoSpacing || options.spacingGap === "auto") {
    effectiveSpacingGap = autoGap;
  } else if (options.spacingGap !== undefined && options.spacingGap !== null) {
    effectiveSpacingGap = parseFloat(options.spacingGap);
  } else {
    effectiveSpacingGap = autoGap;
  }

  // 3. Mathematical Dynamic Optical Vertical Centering:
  // Optical vertical center: OPTICAL_CENTER_Y = 97.45 pt
  // Ensures distance from top fold stripe to top of text equals distance from bottom stripe to bottom of text
  const posLineGap = CARD.POSITION_LINE_GAP || 20.0;
  const nameAscent = nameMetrics.ascentRatio * nameFontSize;
  const nameDescent = nameMetrics.descentRatio * nameFontSize;
  const posDescent = posMetrics.descentRatio * posFontSize;

  let dynamicNameBaselineY;
  if (numPosLines > 0) {
    dynamicNameBaselineY = opticalCenterY + (effectiveSpacingGap + ((numPosLines - 1) * posLineGap) + posDescent - nameAscent) / 2.0;
  } else {
    dynamicNameBaselineY = opticalCenterY - (nameAscent - nameDescent) / 2.0;
  }

  if (safeName) {
    const nameTop = boxTopForBaseline(dynamicNameBaselineY, nameFontSize, nameMetrics.ascentRatio);
    container.appendChild(makeLine(safeName, {
      top: nameTop,
      left: cx - CARD.NAME_BOX_WIDTH / 2,
      width: CARD.NAME_BOX_WIDTH,
      centerX: cx,
      size: nameFontSize,
      weight: CARD.NAME_FONT_WEIGHT,
      opacity: nameOpacity,
      fontFamily: nameFontFamily,
    }));
  }

  if (numPosLines > 0) {
    safeLines.forEach((formattedLine, i) => {
      const baseline = dynamicNameBaselineY - effectiveSpacingGap - i * posLineGap;
      container.appendChild(makeLine(formattedLine, {
        top: boxTopForBaseline(baseline, posFontSize, posMetrics.ascentRatio),
        left: cx - CARD.MAX_TEXT_WIDTH / 2,
        width: CARD.MAX_TEXT_WIDTH,
        centerX: cx,
        size: posFontSize,
        weight: CARD.POSITION_FONT_WEIGHT,
        opacity: positionOpacity,
        fontFamily: posFontFamily,
      }));
    });
  }
}

function renderCard(name, position, options = {}) {
  const mode = options.mode || CARD.CONTENT_MODE || "both";
  const normal = document.getElementById("block-normal");
  const flip = document.getElementById("block-flip");
  const bg = document.getElementById("bg");
  const activeBg = options.bgUrl || CARD.BG_URL;
  if (bg && activeBg) {
    bg.src = activeBg;
  }

  const rawName = stripTrailingPunctuation((name || "").toString().trim());
  const rawPos = stripTrailingPunctuation((position || "").toString().trim());

  const allowPlaceholder = options.allowPlaceholder !== false;
  const isNameEmpty = !rawName;
  const isPosEmpty = !rawPos;

  const activeCase = options.textCase || CARD.TEXT_CASE || "uppercase";
  const placeholderName = applyTextCase(DEFAULT_PREVIEW_NAME, activeCase);
  const placeholderPos = applyTextCase(DEFAULT_PREVIEW_POSITION, activeCase);

  let displayName = rawName;
  let displayPos = rawPos;
  let nameOpacity = 1.0;
  let positionOpacity = 1.0;

  if (mode === "name_only") {
    displayName = (isNameEmpty && allowPlaceholder) ? placeholderName : rawName;
    nameOpacity = (isNameEmpty && allowPlaceholder) ? 0.6 : 1.0;
    displayPos = "";
  } else if (mode === "position_only") {
    displayPos = (isPosEmpty && allowPlaceholder) ? placeholderPos : rawPos;
    positionOpacity = (isPosEmpty && allowPlaceholder) ? 0.6 : 1.0;
    displayName = "";
  } else {
    displayName = (isNameEmpty && allowPlaceholder) ? placeholderName : rawName;
    displayPos = (isPosEmpty && allowPlaceholder) ? placeholderPos : rawPos;
    nameOpacity = (isNameEmpty && allowPlaceholder) ? 0.6 : 1.0;
    positionOpacity = (isPosEmpty && allowPlaceholder) ? 0.6 : 1.0;
  }

  const positionLines = wrapPosition(displayPos);
  const horizontalOffset = options.horizontalOffset !== undefined
    ? parseFloat(options.horizontalOffset)
    : (CARD.HORIZONTAL_OFFSET || 0.0);
  const blockOpts = { ...options, nameOpacity, positionOpacity, mode, textCase: activeCase, rawPosition: displayPos, horizontalOffset };

  const activeSides = options.sides !== undefined ? options.sides : CARD.SIDES;

  if (normal) layoutBlock(normal, displayName, positionLines, blockOpts);
  if (flip) {
    if (activeSides === 1) {
      flip.style.display = "none";
    } else {
      flip.style.display = "block";
      layoutBlock(flip, displayName, positionLines, blockOpts);
    }
  }

  // Live Sheet Preview Support (when settings drawer/modal is present)
  const normalSheet = document.getElementById("block-normal-sheet");
  const flipSheet = document.getElementById("block-flip-sheet");
  const bgSheet = document.getElementById("bg-sheet");
  if (bgSheet && activeBg) {
    bgSheet.src = activeBg;
  }
  if (normalSheet) layoutBlock(normalSheet, displayName, positionLines, blockOpts);
  if (flipSheet) {
    if (activeSides === 1) {
      flipSheet.style.display = "none";
    } else {
      flipSheet.style.display = "block";
      layoutBlock(flipSheet, displayName, positionLines, blockOpts);
    }
  }
}

// ---------------------------------------------------------------------------
// Bulk Title Cleaner & Parser Utilities
// ---------------------------------------------------------------------------
const LEADING_LIST_PREFIX_PATTERN = /^\s*(?:\[\d{1,2}[\/\-\.]\d{1,2}(?:[\/\-\.]\d{2,4})?,?\s*\d{1,2}[\.:]\d{2}(?::\d{2})?(?:\s*[APap][Mm])?\]\s*[^:\n]{1,50}:\s*|\(?\d+[\.\)\:\-\]]*|\[?\d+\]|[-*•·–—>→+~▪▫◦■/\\|]+)\s*/;

const FRONT_TITLES_PATTERN = /^\s*(?:Prof(?:esor)?\.?|Dr\.?\s*\(\s*H\.?\s*C\.?\s*\)|\(\s*H\.?\s*C\.?\s*\)|H\.?\s*C\.?|Dr\.?\s+rer\.?\s*(?:nat|pol|oec|soc|medic|publ|sec|hort|for|techn)\.?|Dr\.?(?:\s*[-–]\s*|\s+)(?:Eng|Ing|Phil|Sc|Med|Agr|Tech(?:n)?|Jur|Theol|Pol|Paed|Oec|Soc|Biol|Chem|Phys|Math|Nat|Hum|Psi|Kom|Ed|Kn|Si|Ag|Pd)\.?|rer\.?\s*(?:nat|pol|oec|soc|medic|publ|sec|hort|for|techn)\.?|(?:Eng|Ing)\.|Drs\.?|Dra\.?|Drg\.?|Drh\.?|Dr\.?|Ir\.?|Apt\.?|Ns\.?|Gr\.?|Bdn\.?|K\.?\s*H\.?|KH\.?|Kiai\s+Haji|Kyai\s+Haji|T\.?\s*G\.?\s*K\.?\s*H\.?|T\.?\s*G\.?\s*H\.?|TGKH\.?|TGH\.?|Tgk\.?|Hjh\.?|Hj\.?|H\.|(?:\bH\b\.?)|Haji|Hajjah|Hajah|Ust(?:adz(?:ah)?)?\.?|Habib|Sayyid|Syarifah|Pdt\.?|Romo|Mgr\.?|Bpk\.?|Bapak|Ibu|Sdri?\.?|Saudara|Saudari|Plt\.?|Plh\.?|Pj\.?|Pjs\.?|Yth\.?|(?:Jenderal(?:\s+Besar)?|Let(?:nan)?\s+Jenderal|Letjen|May(?:or)?\s+Jenderal|Mayjen|Brig(?:adir)?\s+Jenderal|Brigjen|Laksamana(?:\s+(?:Madya|Muda|Pertama))?|Laksdya|Laksda|Laksma|Marsekal(?:\s+(?:Madya|Muda|Pertama))?|Marsdya|Marsda|Marsma|Kolonel|Let(?:nan)?\s+Kolonel|Letkol|Mayor|Kapten|Let(?:nan)?\s+(?:Satu|Dua)|Lettu|Letda|Komisaris\s+Jenderal|Komjen|Inspektur\s+Jenderal|Irjen|Kombes|AKBP|Kompol|AKP|Iptu|Ipda)(?:\s+(?:TNI(?:\s+(?:AD|AL|AU))?|Pol(?:ri)?\.?|Laut(?:\s*\([A-Za-z]+\))?|(?:Mar|Inf|Kav|Arm|Arh|Czi|Chb|Cpl|Ckm|Chk|Cpm|Cku|Cba|Sus|Tek|Kal|Adm|Kes|Pas|Lek|Pnb|Nav)\.?))?(?:\s+(?:\(\s*Purn\.?\s*\)|Purn\.?))?|TNI(?:\s+(?:AD|AL|AU))?(?:\s+(?:\(\s*Purn\.?\s*\)|Purn\.?))?|Polri(?:\s+(?:\(\s*Purn\.?\s*\)|Purn\.?))?|Pol\.(?:\s+(?:\(\s*Purn\.?\s*\)|Purn\.?))?|\(\s*Purn\.?\s*\)|Purn\.|(?:Mar|Inf|Kav|Arm|Arh|Czi|Chb|Cpl|Ckm|Chk|Cpm|Cku|Cba|Sus|Tek|Kal|Adm|Kes|Pas|Lek|Pnb|Nav)\.)(?:[\.\s\:\-\/–—]+|$)/i;

function isValidOfficialName(name) {
  if (!name) return false;
  const s = String(name).trim();
  if (!s) return false;
  if (!/[A-Za-z0-9]/.test(s)) return false;
  if (["kosong", "belum ada", "vacant", "nihil", "n/a", "none", "null", "plt", "plt.", "plh", "plh.", "pj", "pj.", "-", "–"].includes(s.toLowerCase())) return false;
  return true;
}

const TITLE_TOKEN_PATTERN = /^(?:[SMDA]\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*(?:\s*\([A-Za-z0-9\s\.\-]+\))?\.?|S\.?\s*Tr\.?(?:\.\s*[A-Za-z]+|[A-Za-z]+)*\.?|A\.?\s*Md\.?(?:\.\s*[A-Za-z]+|[A-Za-z]+)*\.?|D\.?\s*(?:III|IV|3|4)\.?|Sp\.\s*[A-Za-z]+(?:\s*\([A-Za-z0-9\s\.\-]+\)|-[A-Za-z0-9\-]+|(?:\.\s*[A-Za-z]+)*)*\.?|Subsp\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|Dipl\.?\s*-?\s*[A-Za-z]+\.?|Dr\.?\s*(?:Eng|Ing|Phil|Sc|Med|Agr|Tech(?:n)?|Jur|Theol|Pol|H\.?\s*C\.?)\.?|Ph\.?\s*D\.?|PhD\.?|M\.?\s*B\.?\s*A\.?|MBA\.?|M\.?\s*(?:Bus|Com|Sc|Eng|Ed|Fin|Phil|Arch|Tech|Law|Res|Des|Pub\.?\s*Pol|Int\.?\s*Rel)\.?|B\.?\s*(?:Sc|Eng|A|Com|Ed|Bus|Tech|Fin|Acc|Arch|Pharm|Psych|Phil|Law|B\.?A|I\.?T|C\.?A|S\.?)\.?(?:\s*\([A-Za-z]+\))?|LL\.?\s*[BM]\.?|LL[BM]\.?|Ed\.?\s*D\.?|EdD\.?|D\.?\s*Sc\.?|DSc\.?|D\.?\s*B\.?\s*A\.?|DBA\.?|D\.?\s*Eng\.?|DEng\.?|Psy\.?\s*D\.?|\(\s*H\.?\s*C\.?\s*\)|H\.?\s*C\.?|\(\s*Purn\.?\s*\)|Purn\.?|I\.?\s*P\.?\s*[UMP]\.?|IP[UMP]\.?|(?:ASEAN|Asean)\s+Eng\.?|P\.?\s*Eng\.?|C\.?\s*Eng\.?|A\.?\s*C\.?\s*P\.?\s*E\.?|ACPE\.?|C\.?\s*P\.?\s*E\.?|CPE\.?|Psikolog\.?|Kons\.?|Gr\.?|Apt\.?|Ns\.?|Bdn\.?|(?:SE|SH|ST|SP|SKom|SPd|SSos|SIP|SIKom|SKM|SKep|SGz|SPi|SPt|SHut|SAg|SFarm|SPsi|SSn|SKed|SStat|SAkt|SIK|SHum|SFils|STr\w*|AMd\w*)\.?|(?:MM|MH|MT|ME|MSi|MPd|MKes|MKom|MA|MSc|MEng|MP|MKn|MAP|MAg|MFarm|MPsi|MSn|MEcon|MARS|MPH|MPP|MPA|MKM|MIKom|MIP|MKP|MHut|MHum|MHan|MAk|MFils|MStat|MFin|MMgt|MTech|MPhil|BSc|BEng|BA|BBA|BCom|BEd)\.?|(?:FINASIM|FACS|FICS|FIHA|FACC|FESC|FACP|FRCS|MRCP|CMA|CPA|CIA|CHRP|CPHR|QIA|CBV|CPMA|CFA|CFP|QWP|FRM|PRM|CWM|RFP|PMP|CAPM|PRINCE2|CSM|CSPO|ITIL|TOGAF|CISA|CISM|CISSP|CGEIT|CRISC|CEH|OSCP|CIPM|CIPP|CDPSE|CRA|CRP|CRGP|CRMP|CRMO|CERG|CCRP|CSO|CGO|CGP|FCCA|ACCA|FCA|ACMA|CGMA|CIMA|SHRM-?S?CP|SPHR|GPHR|PHR|CAFM|BKP|CTA|ACPA|CA)\.?|(?:[A-Z]\.){3,6}|Ak\.?|Akt\.?|MM\.?PD\.?|\(K\)|Konsultan)$/i;

const BACK_TITLES_PATTERN = /(?:,\s*|\s+)(?:[SMDA]\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*(?:\s*\([A-Za-z0-9\s\.\-]+\))?\.?|S\.?\s*Tr\.?(?:\.\s*[A-Za-z]+|[A-Za-z]+)*\.?|A\.?\s*Md\.?(?:\.\s*[A-Za-z]+|[A-Za-z]+)*\.?|D\.?\s*(?:III|IV|3|4)|Sp\.\s*[A-Za-z]+(?:\s*\([A-Za-z0-9\s\.\-]+\)|-[A-Za-z0-9\-]+|(?:\.\s*[A-Za-z]+)*)*\.?|Subsp\.\s*[A-Za-z]+(?:\s*\([A-Za-z0-9\s\.\-]+\)|-[A-Za-z0-9\-]+|(?:\.\s*[A-Za-z]+)*)\.?|Dipl\.?\s*-?\s*[A-Za-z]+\.?|Dr\.?\s*(?:Eng|Ing|Phil|Sc|Med|Agr|Tech(?:n)?|Jur|Theol|Pol|H\.?\s*C\.?)\.?|Ph\.?\s*D\.?|PhD|M\.?\s*B\.?\s*A\.?|MBA|M\.?\s*(?:Bus|Com|Sc|Eng|Ed|Fin|Phil|Arch|Tech|Law|Res|Des|Pub\.?\s*Pol|Int\.?\s*Rel)\.?|B\.?\s*(?:Sc|Eng|A|Com|Ed|Bus|Tech|Fin|Acc|Arch|Pharm|Psych|Phil|Law|B\.?A|I\.?T|C\.?A|S\.?)\.?(?:\s*\([A-Za-z]+\))?|LL\.?\s*[BM]\.?|LL[BM]|Ed\.?\s*D\.?|EdD|D\.?\s*Sc\.?|DSc|D\.?\s*B\.?\s*A\.?|DBA|D\.?\s*Eng\.?|DEng|Psy\.?\s*D\.?|\(\s*H\.?\s*C\.?\s*\)|H\.?\s*C\.?|\(\s*Purn\.?\s*\)|Purn\.?|I\.?\s*P\.?\s*[UMP]\b\.?|IP[UMP]\b\.?|(?:ASEAN|Asean)\s+Eng\.?|P\.?\s*Eng\.?|C\.?\s*Eng\.?|A\.?\s*C\.?\s*P\.?\s*E|ACPE|C\.?\s*P\.?\s*E|CPE|Psikolog|Kons\.?|Gr\.?|Apt\.?|Ns\.?|Bdn\.?|(?:SE|SH|ST|SP|SKom|SPd|SSos|SIP|SIKom|SKM|SKep|SGz|SPi|SPt|SHut|SAg|SFarm|SPsi|SSn|SKed|SStat|SAkt|SIK|SHum|SFils|STr\w*|AMd\w*)\b|(?:MM|MH|MT|ME|MSi|MPd|MKes|MKM|MKom|MA|MSc|MEng|MP|MKn|MAP|MPA|MPP|MPH|MAg|MFarm|MPsi|MSn|MEcon|MARS|MIKom|MIP|MKP|MHut|MHum|MHan|MAk|MFils|MStat|MFin|MMgt|MTech|MPhil|BSc|BEng|BA|BBA|BCom|BEd)\b|FINASIM|FACS|FICS|FIHA|FACC|FESC|FACP|FRCS|MRCP|CMA|CPA|CIA|CHRP|CPHR|QIA|CBV|CPMA|CFA|CFP|QWP|FRM|PRM|CWM|RFP|PMP|CAPM|PRINCE2|CSM|CSPO|ITIL|TOGAF|CISA|CISM|CISSP|CGEIT|CRISC|CEH|OSCP|CIPM|CIPP|CDPSE|CRA|CRP|CRGP|CRMP|CRMO|CERG|CCRP|CSO|CGO|CGP|FCCA|ACCA|FCA|ACMA|CGMA|CIMA|SHRM-?S?CP|SPHR|GPHR|PHR|CAFM|Ak\.?|Akt\.?|CA\b|BKP|CTA|ACPA|MM\.?PD|(?:[A-Z]\.){3,8}(?![A-Za-z0-9])|H\.|Hj\.|Haji|Hajjah|Hajah|Hjh\.?)(?:\.+(?=$|[\s,\)\]\-;:/])|(?=$|[\s,\)\]\-;:/]))/gi;

function cleanTitles(name) {
  if (!name) return "";
  let s = sanitizeText(name);

  // Strip wrapping markdown emphasis / quotes (WhatsApp / copy-paste noise)
  s = s.replace(/^[*_~`"'“”‘’]+|[*_~`"'“”‘’]+$/g, "").replace(/[*_~`]+/g, " ").trim();

  // 1. Strip parenthesized religious/academic titles e.g. "(H.) " or "(Hj.) " or "(Dr.) " or "(H.C.) "
  s = s.replace(/^\s*\((?:H\.|Hj\.|Haji|Hajjah|Hajah|Hjh\.?|Dr\.?|Drs\.?|Dra\.?|H\.?\s*C\.?)\)\s*/i, "").trim();

  // 2. Strip leading numbering or bullet markers
  let prev = null;
  while (prev !== s) {
    prev = s;
    s = s.replace(LEADING_LIST_PREFIX_PATTERN, "").trim();
  }

  // 3. Strip front titles in a loop
  prev = null;
  while (prev !== s) {
    prev = s;
    s = s.replace(FRONT_TITLES_PATTERN, "").trim();
  }

  // 4. Strip back titles / academic degrees in a loop
  prev = null;
  while (prev !== s) {
    prev = s;
    s = s.replace(BACK_TITLES_PATTERN, "").trim();
  }

  // 4b. Strip parenthesized trailing titles/subspecialties e.g. "(K)", "(Konsultan)", "(Han)", "(H.C.)", "(Purn.)"
  s = s.replace(/\s*\((?:K|Konsultan|Purn\.?|Sp\.[A-Za-z]+|H\.?\s*C\.?|[A-Za-z0-9\.\s\-]+)\)\s*$/i, "").trim();

  // 5. Clean leftover punctuation at ends (preserving trailing period ONLY if part of a single initial e.g. 'R.', 'P.')
  s = s.replace(/^[,\.\s\-–—>·•\:\=\|\/]+/, "").trim();
  s = s.replace(/[\s,;:!?\-–—_/\t|*•·+~="\'\\`^]+$/, "").trim();
  if (!/\b[A-Za-z]\.$/.test(s)) {
    s = s.replace(/\.+$/, "").trim();
  }

  // 6. Clean trailing comma-separated degree abbreviations
  while (s.includes(",")) {
    const lastCommaIdx = s.lastIndexOf(",");
    const before = s.substring(0, lastCommaIdx).trim();
    const after = s.substring(lastCommaIdx + 1).trim();
    if (TITLE_TOKEN_PATTERN.test(after) || (after.length <= 14 && /^(?:[A-Z]\.(?:[A-Za-z0-9\.\-\s]*)|[A-Z]{2,6}|\([A-Za-z\.]+\)|Konsultan)$/.test(after))) {
      s = before;
    } else {
      break;
    }
  }

  s = s.replace(/^[,\.\s\-–—>·•\:\=\|\/]+/, "").trim();
  s = s.replace(/[\s,;:!?\-–—_/\t|*•·+~="\'\\`^]+$/, "").trim();
  if (!/\b[A-Za-z]\.$/.test(s)) {
    s = s.replace(/\.+$/, "").trim();
  }
  s = stripTrailingPunctuation(s);
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

function getNameTextWidthPt(text, fontSize, fontFamily) {
  if (!text) return 0;
  const upper = (typeof applyTextCase === "function" ? applyTextCase(text, "uppercase") : String(text).toUpperCase()).trim();
  const sz = (fontSize !== undefined && fontSize !== null && fontSize !== "auto")
    ? parseFloat(fontSize)
    : (typeof CARD !== "undefined" && (CARD.CUSTOM_NAME_FONT_SIZE || CARD.NAME_FONT_SIZE) ? (CARD.CUSTOM_NAME_FONT_SIZE || CARD.NAME_FONT_SIZE) : 45.86);
  const ff = fontFamily || (typeof CARD !== "undefined" && (CARD.NAME_FONT_FAMILY || CARD.FONT_FAMILY) ? (CARD.NAME_FONT_FAMILY || CARD.FONT_FAMILY) : "Montserrat");
  if (typeof measureTextWidthPt === "function") {
    try {
      const w = measureTextWidthPt(upper, (typeof CARD !== "undefined" && CARD.NAME_FONT_WEIGHT) ? CARD.NAME_FONT_WEIGHT : 700, sz, ff);
      if (w > 0) return w;
    } catch (e) {}
  }
  // Precise character-based fallback if canvas measurement is unavailable, scaled by font size
  const scaleFactor = sz / 45.86;
  let w = 0;
  for (const ch of upper) {
    if ("MW@#%".includes(ch)) w += 40.0;
    else if ("IJ.:,'!|()[]".includes(ch)) w += 13.0;
    else if ("QOGCDHNU".includes(ch)) w += 33.0;
    else if ("EFLSTZ".includes(ch)) w += 25.0;
    else if (ch === " ") w += 15.0;
    else w += 29.0;
  }
  return w * scaleFactor;
}

function fitsName(candidate, optionsOrMaxLen = 24, maxWidth = (typeof CARD !== "undefined" && (CARD.NAME_BOX_WIDTH || CARD.MAX_NAME_WIDTH)) ? (CARD.NAME_BOX_WIDTH || CARD.MAX_NAME_WIDTH) : 618.0) {
  if (!candidate) return true;
  const maxChars = (typeof optionsOrMaxLen === "object" && optionsOrMaxLen !== null && optionsOrMaxLen.maxLen)
    ? optionsOrMaxLen.maxLen
    : (typeof optionsOrMaxLen === "number" ? optionsOrMaxLen : 24);
  const maxW = (typeof optionsOrMaxLen === "object" && optionsOrMaxLen !== null && optionsOrMaxLen.maxWidth)
    ? optionsOrMaxLen.maxWidth
    : (typeof maxWidth === "number" ? maxWidth : 618.0);
  const fontSize = (typeof optionsOrMaxLen === "object" && optionsOrMaxLen !== null && optionsOrMaxLen.fontSize)
    ? optionsOrMaxLen.fontSize
    : undefined;
  const fontFamily = (typeof optionsOrMaxLen === "object" && optionsOrMaxLen !== null && optionsOrMaxLen.fontFamily)
    ? optionsOrMaxLen.fontFamily
    : undefined;

  if (candidate.length > maxChars) return false;
  if (getNameTextWidthPt(candidate, fontSize, fontFamily) > maxW) return false;
  return true;
}

function formatBulkName(rawName, optionsOrMaxLen = 24, maxWidth = (typeof CARD !== "undefined" && (CARD.NAME_BOX_WIDTH || CARD.MAX_NAME_WIDTH)) ? (CARD.NAME_BOX_WIDTH || CARD.MAX_NAME_WIDTH) : 618.0) {
  const cleaned = stripTrailingPunctuation(cleanTitles(rawName));
  if (!cleaned) return "";

  const maxChars = (typeof optionsOrMaxLen === "object" && optionsOrMaxLen !== null && optionsOrMaxLen.maxLen)
    ? optionsOrMaxLen.maxLen
    : (typeof optionsOrMaxLen === "number" ? optionsOrMaxLen : 24);
  const maxW = (typeof optionsOrMaxLen === "object" && optionsOrMaxLen !== null && optionsOrMaxLen.maxWidth)
    ? optionsOrMaxLen.maxWidth
    : (typeof maxWidth === "number" ? maxWidth : 618.0);
  const fontSize = (typeof optionsOrMaxLen === "object" && optionsOrMaxLen !== null && optionsOrMaxLen.fontSize)
    ? optionsOrMaxLen.fontSize
    : (typeof CARD !== "undefined" ? (CARD.CUSTOM_NAME_FONT_SIZE || CARD.NAME_FONT_SIZE || 45.86) : 45.86);
  const fontFamily = (typeof optionsOrMaxLen === "object" && optionsOrMaxLen !== null && optionsOrMaxLen.fontFamily)
    ? optionsOrMaxLen.fontFamily
    : (typeof CARD !== "undefined" ? (CARD.NAME_FONT_FAMILY || CARD.FONT_FAMILY || "Montserrat") : "Montserrat");

  function fits(cand) {
    if (!cand) return true;
    return getNameTextWidthPt(cand, fontSize, fontFamily) <= maxW;
  }

  // 1. If full cleaned name fits within maxW AND <= maxChars, return as is (e.g. 'Budi Santoso Wijaya')
  if (fits(cleaned) && cleaned.length <= maxChars) {
    return cleaned;
  }

  const words = cleaned.split(" ").filter(Boolean);
  if (words.length > 1) {
    // 2. Abbreviate last word if it fits (e.g. 'Muhammad Fauzan Ramadhan' -> 'Muhammad Fauzan R.', 'Nurul Aisyah Maharani Putri' -> 'Nurul Aisyah Maharani P.')
    const lastWord = words[words.length - 1];
    const initial = lastWord.charAt(0).toUpperCase() + ".";
    const lastCand = words.slice(0, -1).join(" ") + " " + initial;
    if (fits(lastCand)) {
      return lastCand;
    }

    // 3. Find longest prefix of full words + 1 initial, omitting all subsequent words (e.g. 'Arnando Jujur Pardamean Siregar' -> 'Arnando Jujur P.')
    for (let i = words.length - 2; i > 0; i--) {
      const cand = words.slice(0, i).join(" ") + " " + words[i].charAt(0).toUpperCase() + ".";
      if (fits(cand)) {
        return cand;
      }

      // If prefix has at least 2 full words and fits, prefer it over shrinking down to words[0] + initial!
      // (e.g. 'Faried Abdurrahman Nur Yuliono' -> 'Faried Abdurrahman' instead of 'Faried A.')
      if (i >= 2) {
        const candFull = words.slice(0, i).join(" ");
        if (fits(candFull)) {
          return candFull;
        }
      }
    }

    // 4. Fallback for i=1 (e.g. 'First W.')
    const candOneInit = words[0] + " " + words[1].charAt(0).toUpperCase() + ".";
    if (fits(candOneInit)) {
      return candOneInit;
    }
    if (fits(words[0])) {
      return words[0];
    }
    return words[0];
  }
  return stripTrailingPunctuation(cleaned.substring(0, 25).trim());
}

function cleanPositionText(pos) {
  if (!pos) return "";
  const lines = String(pos).split(/\r?\n/);
  const cleaned = lines.map(line => {
    let s = sanitizeText(line)
      .replace(/^[*_~`"'“”‘’]+|[*_~`"'“”‘’]+$/g, "")
      .replace(/[*_~`]+/g, " ")
      .replace(/^[\s\-–—>·•\:\=\|\/]+/, "")
      .trim();
    s = s.replace(/^(?:Jabatan|Posisi|Sebagai)\s*:\s*/i, "").trim();
    let prev = null;
    while (prev !== s) {
      prev = s;
      s = s.replace(/^\s*(?:[SMDA]\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|S\.?\s*Tr\.?(?:\.\s*[A-Za-z]+|[A-Za-z]+)*\.?|A\.?\s*Md\.?(?:\.\s*[A-Za-z]+|[A-Za-z]+)*\.?|Ph\.?\s*D\.?|PhD|M\.?\s*B\.?\s*A\.?|MBA|Sp\.\s*[A-Za-z]+|Subsp\.\s*[A-Za-z]+|M\.?M\.?|M\.?Si\.?|S\.?E\.?|S\.?H\.?|S\.?T\.?|S\.?Kom\.?|S\.?Pd\.?|S\.?Sos\.?|M\.?Kom\.?|M\.?H\.?|M\.?T\.?|M\.?Pd\.?|M\.?K\.?K\.?K\.?|M\.?K\.?M\.?|FINASIM|Ak\.?|Akt\.?|CA\b|MM\.PD|Psikolog|\(H\.?\s*C\.?\))(?:[,\s\:\-\/–—]+|$)/i, "").trim();
    }
    s = s.replace(/^[\s\-–—>·•\:\=\|\/]+/, "").trim();
    return stripTrailingPunctuation(s);
  }).filter(Boolean);
  return cleaned.join("\n");
}

function _isCommaDegreeSegment(seg) {
  if (!seg) return false;
  const s = seg.replace(/^[,\s]+|[,\s]+$/g, "").trim();
  if (!s) return false;
  if (TITLE_TOKEN_PATTERN.test(s)) return true;
  // Space-joined degrees inside a single comma segment e.g. "S.H. M.H." or "SE MM"
  const tokens = s.split(/\s+/).filter(Boolean);
  return tokens.length >= 1 && tokens.every(t => TITLE_TOKEN_PATTERN.test(t));
}

function _splitCommaNameAndPosition(str) {
  if (!str || !str.includes(",")) return null;
  const parts = str.split(",").map(p => p.trim()).filter(Boolean);
  if (parts.length < 2) return null;
  let splitIdx = 1;
  while (splitIdx < parts.length && _isCommaDegreeSegment(parts[splitIdx])) {
    splitIdx++;
  }
  if (splitIdx < parts.length) {
    return {
      name: stripTrailingPunctuation(parts.slice(0, splitIdx).join(", ")),
      position: parts.slice(splitIdx).join(", ").trim()
    };
  }
  return null;
}

function splitNameAndPosition(line) {
  if (!line) return { name: "", position: "" };
  line = String(line).trim();
  if (!line) return { name: "", position: "" };

  // Pre-clean WhatsApp timestamps / formatting & weird Unicode dashes
  line = line
    .replace(/^\s*\[\d{1,2}[\/\-\.]\d{1,2}(?:[\/\-\.]\d{2,4})?,?\s*\d{1,2}[\.:]\d{2}(?::\d{2})?(?:\s*[APap][Mm])?\]\s*[^:\n]{1,50}:\s*/, "")
    .replace(/[\u2010\u2011\u2012\u2212]/g, "-")
    .replace(/^[*_~`]+|[*_~`]+$/g, "")
    .trim();

  // Strip leading bullets / numbering first when followed by clean content (preserve tabs if TSV)
  if (!line.includes("\t")) {
    let prevL = null;
    while (prevL !== line) {
      prevL = line;
      line = line.replace(LEADING_LIST_PREFIX_PATTERN, "").trim();
    }
    line = line.replace(/[*_~`]+/g, " ").replace(/\s+/g, " ").trim();
  }
  if (!line) return { name: "", position: "" };

  // Check TSV (Excel copy-paste with tabs)
  if (line.includes("\t")) {
    const parts = line.split("\t").map(p => p.replace(/[*_~`]+/g, "").trim()).filter(Boolean);
    if (parts.length >= 3) {
      if (/^\(?\d+[\.\)\:\-\]]*$/.test(parts[0]) || /^(?:no|nomor)$/i.test(parts[0])) {
        return {
          name: stripTrailingPunctuation(parts[1]),
          position: parts.slice(2).join(" - ")
        };
      } else {
        return {
          name: stripTrailingPunctuation(parts[0]),
          position: parts.slice(1).join(" - ")
        };
      }
    } else if (parts.length === 2) {
      if (/^\(?\d+[\.\)\:\-\]]*$/.test(parts[0]) || /^(?:no|nomor)$/i.test(parts[0])) {
        return {
          name: stripTrailingPunctuation(parts[1]),
          position: ""
        };
      } else {
        return {
          name: stripTrailingPunctuation(parts[0]),
          position: parts[1]
        };
      }
    } else if (parts.length === 1) {
      return {
        name: stripTrailingPunctuation(parts[0]),
        position: ""
      };
    }
  }

  // Strip leading numbering again cleanly
  const numMatch = line.match(/^\(?\d+[\.\)\:\-\]\,\;]\s+(.*)$/);
  if (numMatch) {
    line = numMatch[1].trim();
  }

  // Check Semicolon delimiter (Standard Indonesian Excel CSV)
  if (line.includes(";")) {
    const parts = line.split(";").map(p => p.trim().replace(/^["']|["']$/g, "")).filter(Boolean);
    if (parts.length >= 2) {
      return {
        name: stripTrailingPunctuation(parts[0]),
        position: parts.slice(1).join(" - ")
      };
    } else if (parts.length === 1) {
      return {
        name: stripTrailingPunctuation(parts[0]),
        position: ""
      };
    }
  }

  line = sanitizeText(line);

  // 1. Parentheses / brackets at end: e.g. "Nama Pejabat (Jabatan)" OR "Nama, S.T., Koordinator PEP (Perencanaan, Evaluasi)"
  const parenMatch = line.match(/^(.*?)\s*[\(\[\{](.+?)[\)\]\}]\s*$/);
  if (parenMatch) {
    const beforeParen = parenMatch[1].trim();
    const insideParen = parenMatch[2].trim();
    const delims = ["|", ";", ":", " - ", " – ", " — ", " / ", "="];
    let foundDelim = null;
    for (const d of delims) {
      if (beforeParen.includes(d)) {
        foundDelim = d;
        break;
      }
    }
    if (foundDelim) {
      const idx = beforeParen.indexOf(foundDelim);
      const namePart = stripTrailingPunctuation(beforeParen.substring(0, idx).trim());
      const posPart = beforeParen.substring(idx + foundDelim.length).trim() + " (" + insideParen + ")";
      if (namePart && posPart) {
        return { name: namePart, position: posPart };
      }
    } else {
      const commaSplit = _splitCommaNameAndPosition(beforeParen);
      if (commaSplit && commaSplit.name && commaSplit.position) {
        return {
          name: commaSplit.name,
          position: commaSplit.position + " (" + insideParen + ")"
        };
      }
      // If insideParen itself is purely a degree/subspecialty like (H.C.) or (K), do not treat it as position
      if (!_isCommaDegreeSegment(insideParen)) {
        const namePart = stripTrailingPunctuation(beforeParen);
        const posPart = insideParen;
        if (namePart && posPart) {
          return { name: namePart, position: posPart };
        }
      }
    }
  }

  // 2. Explicit strong delimiters: Pipe, Semicolon, Colon, Dash with spaces, Slash with spaces, Equal
  const delims = ["|", ";", ":", " - ", " – ", " — ", " / ", "="];
  for (const d of delims) {
    if (line.includes(d)) {
      const idx = line.indexOf(d);
      return {
        name: stripTrailingPunctuation(line.substring(0, idx).trim()),
        position: line.substring(idx + d.length).trim()
      };
    }
  }

  // 3. Smart Comma check: skips trailing degree tokens left-to-right so positions with commas stay whole
  const commaRes = _splitCommaNameAndPosition(line);
  if (commaRes) {
    return commaRes;
  }

  // 4. Single dash (only with whitespace on at least one side so Dr.-Ing. or hyphenated names stay intact) or slash
  const dashWithSpaceMatch = line.match(/^(.*?)(?:\s+-|-\s+)(.+)$/);
  if (dashWithSpaceMatch) {
    const left = dashWithSpaceMatch[1].trim();
    const right = dashWithSpaceMatch[2].trim();
    if (left && right) {
      return { name: stripTrailingPunctuation(left), position: right };
    }
  }
  if (line.includes("/")) {
    const idx = line.indexOf("/");
    const left = line.substring(0, idx).trim();
    const right = line.substring(idx + 1).trim();
    if (left && right) {
      return { name: stripTrailingPunctuation(left), position: right };
    }
  }

  // 5. Check if line contains position indicators starting with PLT / Plt / Plh / Pj separated by space
  const pltMatch = line.match(/\s+(?:PLT\.?|Plt\.?|PLH\.?|Plh\.?|Pj\.?|PJ\.?)\s+/i);
  if (pltMatch) {
    const idx = pltMatch.index;
    const namePart = line.substring(0, idx).trim();
    const posPart = line.substring(idx).trim();
    if (namePart && posPart) {
      return { name: stripTrailingPunctuation(namePart), position: posPart };
    }
  }

  return { name: stripTrailingPunctuation(line), position: "" };
}

function setFontFamily(fontFamily) {
  CARD.FONT_FAMILY = fontFamily;
  CARD.NAME_FONT_FAMILY = fontFamily;
  CARD.POSITION_FONT_FAMILY = fontFamily;
}

function setNameFontFamily(fontFamily) {
  CARD.NAME_FONT_FAMILY = fontFamily;
}

function setPosFontFamily(fontFamily) {
  CARD.POSITION_FONT_FAMILY = fontFamily;
}

function setNameFontSize(size) {
  CARD.CUSTOM_NAME_FONT_SIZE = size && size !== "auto" ? parseFloat(size) : null;
}

function setPosFontSize(size) {
  CARD.CUSTOM_POS_FONT_SIZE = size && size !== "auto" ? parseFloat(size) : null;
}

function setSpacingGap(gap) {
  CARD.NAME_TO_POSITION_GAP = parseFloat(gap) || 40.0;
}

function setTextCase(textCase) {
  CARD.TEXT_CASE = textCase || "uppercase";
}

const PAPER_SIZE_DIMS = {
  a4: { w: 841.89, h: 372.72 },
  f4: { w: 935.43, h: 419.0 },
  letter: { w: 792.0, h: 360.0 },
  a3: { w: 1190.55, h: 532.0 },
};

function setPaperSize(paperSize) {
  const ps = String(paperSize || "a4").toLowerCase();
  CARD.PAPER_SIZE = ps;
  const dims = PAPER_SIZE_DIMS[ps] || PAPER_SIZE_DIMS.a4;
  const ratio = dims.w / 841.89;
  CARD.PAGE_W = dims.w;
  CARD.PAGE_H = dims.h;
  CARD.CENTER_X = dims.w / 2;
  CARD.NAME_BOX_WIDTH = 625.0 * ratio;
  CARD.MAX_NAME_WIDTH = 625.0 * ratio;
  CARD.MAX_TEXT_WIDTH = 625.0 * ratio;
}

function setCardSides(sides) {
  CARD.SIDES = parseInt(sides, 10) || 2;
}

function setBackgroundUrl(url) {
  CARD.BG_URL = url;
}

function setContentMode(mode) {
  CARD.CONTENT_MODE = mode || "both";
}

const GENERIC_ROLES = new Set([
  "peserta", "anggota", "panitia", "staf", "staff", "tamu", "undangan",
  "member", "participant", "committee", "guest", "delegasi", "delegate"
]);

function normalizeDedupKey(text) {
  if (!text) return "";
  return String(text).toLowerCase().replace(/[^a-z0-9]/g, "").trim();
}

function deduplicateBulkRows(rows, contentMode = "both", source = "kemnaker") {
  if (!rows || !rows.length) return [];
  if (source !== "kemnaker") return rows;
  const seenNames = new Set();
  const seenPositions = new Set();
  const seenPairs = new Set();
  const uniqueRows = [];

  for (const r of rows) {
    const name = (r.rawName || r.name || "").trim();
    const pos = (r.position || "").trim();

    const cleanedN = typeof cleanTitles === "function" ? cleanTitles(name) : name;
    const nk = normalizeDedupKey(cleanedN || name);
    const pk = normalizeDedupKey(pos);
    const pairK = nk + "||" + pk;

    if (contentMode === "name_only") {
      if (nk && seenNames.has(nk)) continue;
      if (nk) seenNames.add(nk);
      uniqueRows.push(r);
    } else if (contentMode === "position_only") {
      if (pk && seenPositions.has(pk)) continue;
      if (pk) seenPositions.add(pk);
      uniqueRows.push(r);
    } else {
      // mode 'both'
      let isDup = false;
      if (seenPairs.has(pairK)) {
        isDup = true;
      } else if (nk && seenNames.has(nk)) {
        isDup = true;
      } else if (pk && seenPositions.has(pk) && !GENERIC_ROLES.has(pk)) {
        isDup = true;
      }

      if (isDup) continue;

      if (nk) seenNames.add(nk);
      if (pk) seenPositions.add(pk);
      seenPairs.add(pairK);
      uniqueRows.push(r);
    }
  }

  return uniqueRows;
}

window.CARD = CARD;
window.renderCard = renderCard;
window.wrapPosition = wrapPosition;
window.wrap60pt = wrap60pt;
window.layoutBlock = layoutBlock;
window.cleanTitles = cleanTitles;
window.formatBulkName = formatBulkName;
window.getNameTextWidthPt = getNameTextWidthPt;
window.fitsName = fitsName;
window.splitNameAndPosition = splitNameAndPosition;
window.cleanPositionText = cleanPositionText;
window.stripTrailingPunctuation = stripTrailingPunctuation;
window.expandKemnakerPosition = expandKemnakerPosition;
window.deduplicateBulkRows = deduplicateBulkRows;
window.isValidOfficialName = isValidOfficialName;
window.sanitizeText = sanitizeText;
window.applyTextCase = applyTextCase;
window.setFontFamily = setFontFamily;
window.setNameFontFamily = setNameFontFamily;
window.setPosFontFamily = setPosFontFamily;
window.setNameFontSize = setNameFontSize;
window.setPosFontSize = setPosFontSize;
window.setSpacingGap = setSpacingGap;
window.setTextCase = setTextCase;
window.setPaperSize = setPaperSize;
window.setCardSides = setCardSides;
window.setHorizontalOffset = setHorizontalOffset;
window.setBackgroundUrl = setBackgroundUrl;
window.setContentMode = setContentMode;
window.DEFAULT_PREVIEW_NAME = DEFAULT_PREVIEW_NAME;
window.DEFAULT_PREVIEW_POSITION = DEFAULT_PREVIEW_POSITION;
window.getFontMetrics = getFontMetrics;
window.calculateAutoSpacingGap = calculateAutoSpacingGap;


