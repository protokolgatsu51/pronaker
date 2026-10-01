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
  PAGE_W: 832.08,      // pt
  PAGE_H: 372.72,      // pt
  CENTER_X: 482.6,      // pt - horizontal center line both texts sit on
  NAME_BASELINE_Y: 104.9,     // pt from bottom
  NAME_TO_POSITION_GAP: 45.0, // pt, baseline to baseline
  POSITION_LINE_GAP: 20.0,    // pt, baseline to baseline between wrapped lines
  MAX_TEXT_WIDTH: 610.0,      // pt, wrap width for the position text (real
                               // Myriad Pro metrics; calibrated so the
                               // reference example wraps exactly like your
                               // sample PDF)
  NAME_BOX_WIDTH: 668.0,      // pt, centered name text box boundary
  MAX_NAME_WIDTH: 668.0,      // pt, maximum text width before auto-abbreviation
  NAME_FONT_SIZE: 45.86,      // pt
  POSITION_FONT_SIZE: 18.0,   // pt
  NAME_FONT_WEIGHT: 700,
  POSITION_FONT_WEIGHT: 400,
  FONT_FAMILY: "MyriadPro, Arial, Helvetica, sans-serif",
  SIDES: 2,
  BG_URL: "",
  ASCENT_RATIO: 0.75,  // from the font's own hhea/OS2 metrics (750/1000)
  CONTENT_MODE: "both",
  MODE_60PT_FONT_SIZE: 60.0,
  MODE_60PT_MAX_CHARS: 36,
  MODE_60PT_SINGLE_BASELINE_Y: 86.0,
  MODE_60PT_LINE1_BASELINE_Y: 115.0,
  MODE_60PT_LINE2_BASELINE_Y: 57.0,
};

// pt -> px, for canvas text measurement only (canvas always measures in css px)
function ptToPx(pt) {
  return pt * (96 / 72);
}

let _measureCanvas = null;
function measureTextWidthPt(text, weight, sizePt) {
  if (!_measureCanvas) _measureCanvas = document.createElement("canvas");
  const ctx = _measureCanvas.getContext("2d");
  ctx.font = `${weight} ${ptToPx(sizePt)}px ${CARD.FONT_FAMILY}`;
  const widthPx = ctx.measureText(text).width;
  return widthPx / (96 / 72);
}

// Strips trailing punctuation (dots, commas, semicolons, colons, dashes, etc.)
// except closing parentheses and brackets ), ], }
function stripTrailingPunctuation(text) {
  if (!text) return "";
  const lines = String(text).split(/\r?\n/);
  const cleaned = lines.map(l => {
    return l.replace(/[\s.,;:!?\-–—_/\t|*•·+~="\'\\`^]+$/, "").trim();
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
      .map(l => stripTrailingPunctuation(l.trim()).replace(/\s+/g, " ").toUpperCase())
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
  const singleLine = cleanText.replace(/\s+/g, " ").toUpperCase();
  if (measureTextWidthPt(singleLine, CARD.POSITION_FONT_WEIGHT, CARD.POSITION_FONT_SIZE) <= CARD.MAX_TEXT_WIDTH) {
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
    const w1 = measureTextWidthPt(l1, CARD.POSITION_FONT_WEIGHT, CARD.POSITION_FONT_SIZE);
    const w2 = measureTextWidthPt(l2, CARD.POSITION_FONT_WEIGHT, CARD.POSITION_FONT_SIZE);

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

// Word-wrap for 60 pt Name Only / Position Only mode (max 36 chars, 1 or 2 lines)
function wrap60pt(text, maxChars = 36) {
  if (!text || typeof text !== "string") return [];
  let cleanText = stripTrailingPunctuation(text.trim());
  if (cleanText.length > maxChars) {
    cleanText = stripTrailingPunctuation(cleanText.substring(0, maxChars).trim());
  }
  if (!cleanText) return [];

  // 1. Explicit newline (Enter key)
  if (cleanText.includes("\n")) {
    const rawLines = cleanText.split(/\r?\n/)
      .map(l => stripTrailingPunctuation(l.trim()).replace(/\s+/g, " ").toUpperCase())
      .filter(Boolean);
    if (rawLines.length === 1) return [rawLines[0]];
    if (rawLines.length >= 2) {
      return [rawLines[0], rawLines.slice(1).join(" ")].slice(0, 2);
    }
  }

  // 2. Single continuous line
  const upper = cleanText.replace(/\s+/g, " ").toUpperCase();
  const widthPt = measureTextWidthPt(upper, CARD.NAME_FONT_WEIGHT, CARD.MODE_60PT_FONT_SIZE);
  if (widthPt <= CARD.MAX_TEXT_WIDTH) {
    return [upper];
  }

  // 3. Balanced 2-line wrap
  const words = upper.split(" ").filter(Boolean);
  if (words.length <= 1) {
    return [upper];
  }

  let bestDiff = Infinity;
  let bestSplit = [upper];
  for (let i = 1; i < words.length; i++) {
    const l1 = words.slice(0, i).join(" ");
    const l2 = words.slice(i).join(" ");
    const w1 = measureTextWidthPt(l1, CARD.NAME_FONT_WEIGHT, CARD.MODE_60PT_FONT_SIZE);
    const w2 = measureTextWidthPt(l2, CARD.NAME_FONT_WEIGHT, CARD.MODE_60PT_FONT_SIZE);
    if (w1 <= CARD.MAX_TEXT_WIDTH && w2 <= CARD.MAX_TEXT_WIDTH) {
      const diff = Math.abs(w1 - w2);
      if (diff < bestDiff) {
        bestDiff = diff;
        bestSplit = [l1, l2];
      }
    }
  }

  if (bestDiff === Infinity) {
    let current = "";
    const lines = [];
    for (const w of words) {
      const candidate = current ? current + " " + w : w;
      if (measureTextWidthPt(candidate, CARD.NAME_FONT_WEIGHT, CARD.MODE_60PT_FONT_SIZE) <= CARD.MAX_TEXT_WIDTH) {
        current = candidate;
      } else {
        if (current) lines.push(current);
        current = w;
        if (lines.length >= 2) break;
      }
    }
    if (current && lines.length < 2) lines.push(current);
    return lines.slice(0, 2);
  }

  return bestSplit;
}

// Dynamic 1-to-3 line layout & auto-font-reduction for Position Only (Jabatan Saja) mode
// Supports explicit newlines (Enter key) as well as automatic wrapping for long positions (up to 128 chars).
function layoutPositionOnly(text, maxChars = 128) {
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

  const weight = CARD.NAME_FONT_WEIGHT;
  const maxW = CARD.MAX_TEXT_WIDTH;

  function getBaselines(numLines, fontSize) {
    const gap = fontSize * 1.25;
    if (numLines === 1) {
      return [86.0];
    } else if (numLines === 2) {
      return [86.0 + gap / 2.0, 86.0 - gap / 2.0];
    } else {
      return [86.0 + gap, 86.0, 86.0 - gap];
    }
  }

  // 1. Explicit newlines entered by user (Enter key)
  if (cleanText.includes("\n")) {
    const rawLines = cleanText.split(/\r?\n/)
      .map(l => l.trim().replace(/\s+/g, " ").toUpperCase())
      .filter(Boolean);

    if (rawLines.length === 1) {
      cleanText = rawLines[0];
    } else if (rawLines.length === 2) {
      const l1 = rawLines[0];
      const l2 = rawLines[1];
      let s = 46.0;
      while (s >= 16.0) {
        if (measureTextWidthPt(l1, weight, s) <= maxW && measureTextWidthPt(l2, weight, s) <= maxW) {
          break;
        }
        s -= 1.0;
      }
      return { lines: [l1, l2], fontSize: s, baselines: getBaselines(2, s) };
    } else {
      const l1 = rawLines[0];
      const l2 = rawLines[1];
      const l3 = rawLines.slice(2).join(" ");
      let s = 34.0;
      while (s >= 14.0) {
        if (measureTextWidthPt(l1, weight, s) <= maxW &&
            measureTextWidthPt(l2, weight, s) <= maxW &&
            measureTextWidthPt(l3, weight, s) <= maxW) {
          break;
        }
        s -= 1.0;
      }
      return { lines: [l1, l2, l3], fontSize: s, baselines: getBaselines(3, s) };
    }
  }

  // 2. Continuous text
  const upper = cleanText.replace(/\s+/g, " ").toUpperCase();
  const words = upper.split(" ").filter(Boolean);
  if (words.length === 0) {
    return { lines: [], fontSize: 40, baselines: [] };
  }

  // Step 2a: Check if fits on 1 line
  for (const s of [52, 48, 44, 40]) {
    if (measureTextWidthPt(upper, weight, s) <= maxW) {
      return { lines: [upper], fontSize: s, baselines: [86.0] };
    }
  }

  // Step 2b: Try 2 lines
  if (words.length >= 2) {
    for (const s of [44, 40, 36, 32, 30]) {
      const TARGET_RATIO = 0.60;
      const trailingStopwords = new Set(['DAN', 'ATAU', 'PADA', 'DI', 'KE', 'DENGAN', 'UNTUK']);
      const candidates = [];
      for (let i = 1; i < words.length; i++) {
        const l1 = words.slice(0, i).join(" ");
        const l2 = words.slice(i).join(" ");
        const w1 = measureTextWidthPt(l1, weight, s);
        const w2 = measureTextWidthPt(l2, weight, s);
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
        return { lines: candidates[0].lines, fontSize: s, baselines: getBaselines(2, s) };
      }
    }
  }

  // Step 2c: Try 3 lines
  if (words.length >= 3) {
    for (let s = 32; s >= 14; s -= 1) {
      let bestDiff = Infinity;
      let bestSplit = null;
      const n = words.length;
      for (let i = 1; i < n - 1; i++) {
        for (let j = i + 1; j < n; j++) {
          const l1 = words.slice(0, i).join(" ");
          const l2 = words.slice(i, j).join(" ");
          const l3 = words.slice(j).join(" ");
          const w1 = measureTextWidthPt(l1, weight, s);
          const w2 = measureTextWidthPt(l2, weight, s);
          const w3 = measureTextWidthPt(l3, weight, s);
          if (w1 <= maxW && w2 <= maxW && w3 <= maxW) {
            const diff = Math.max(w1, w2, w3) - Math.min(w1, w2, w3);
            if (diff < bestDiff) {
              bestDiff = diff;
              bestSplit = [l1, l2, l3];
            }
          }
        }
      }
      if (bestSplit) {
        return { lines: bestSplit, fontSize: s, baselines: getBaselines(3, s) };
      }
    }
  }

  // Fallback greedy wrap up to 3 lines
  for (let s = 22; s >= 12; s -= 1) {
    const lines = [];
    let current = "";
    for (const w of words) {
      const candidate = current ? current + " " + w : w;
      if (measureTextWidthPt(candidate, weight, s) <= maxW) {
        current = candidate;
      } else {
        if (current) lines.push(current);
        current = w;
        if (lines.length === 2) break;
      }
    }
    if (current) lines.push(current);
    if (lines.length <= 3 && lines.every(l => measureTextWidthPt(l, weight, s) <= maxW)) {
      return { lines, fontSize: s, baselines: getBaselines(lines.length, s) };
    }
  }

  return { lines: [upper], fontSize: 16, baselines: [86.0] };
}

// top offset (pt, from the top of the page) for a text box whose baseline
// should land at `baselineFromBottomPt`, given line-height:1 (box height ==
// font-size exactly, since this font's ascent+|descent| == 1em with no gap).
function boxTopForBaseline(baselineFromBottomPt, fontSizePt) {
  return CARD.PAGE_H - baselineFromBottomPt - CARD.ASCENT_RATIO * fontSizePt;
}

const DEFAULT_PREVIEW_NAME = "TAMPILAN NAMA LENGKAP";
const DEFAULT_PREVIEW_POSITION = "TAMPILAN JABATAN ATAU POSISI";

function makeLine(text, {top, left, width, size, weight, opacity}) {
  const div = document.createElement("div");
  div.textContent = text;
  div.style.position = "absolute";
  div.style.left = left + "pt";
  div.style.top = top + "pt";
  div.style.width = width + "pt";
  div.style.fontFamily = CARD.FONT_FAMILY;
  div.style.fontWeight = weight;
  div.style.fontSize = size + "pt";
  div.style.lineHeight = "1";
  div.style.textAlign = "center";
  div.style.whiteSpace = "nowrap";
  div.style.color = "#111111";
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

  // Mode: Nama Saja (Font 60 pt, max 36 chars, centered)
  if (mode === "name_only") {
    const safeName = (name || "").toString().trim().toUpperCase();
    if (!safeName) return;
    const lines = wrap60pt(safeName, CARD.MODE_60PT_MAX_CHARS);
    if (lines.length === 1) {
      const top = boxTopForBaseline(CARD.MODE_60PT_SINGLE_BASELINE_Y, CARD.MODE_60PT_FONT_SIZE);
      container.appendChild(makeLine(lines[0], {
        top: top,
        left: CARD.CENTER_X - CARD.MAX_TEXT_WIDTH / 2,
        width: CARD.MAX_TEXT_WIDTH,
        size: CARD.MODE_60PT_FONT_SIZE,
        weight: CARD.NAME_FONT_WEIGHT,
        opacity: nameOpacity,
      }));
    } else if (lines.length >= 2) {
      const top1 = boxTopForBaseline(CARD.MODE_60PT_LINE1_BASELINE_Y, CARD.MODE_60PT_FONT_SIZE);
      const top2 = boxTopForBaseline(CARD.MODE_60PT_LINE2_BASELINE_Y, CARD.MODE_60PT_FONT_SIZE);
      container.appendChild(makeLine(lines[0], {
        top: top1,
        left: CARD.CENTER_X - CARD.MAX_TEXT_WIDTH / 2,
        width: CARD.MAX_TEXT_WIDTH,
        size: CARD.MODE_60PT_FONT_SIZE,
        weight: CARD.NAME_FONT_WEIGHT,
        opacity: nameOpacity,
      }));
      container.appendChild(makeLine(lines[1], {
        top: top2,
        left: CARD.CENTER_X - CARD.MAX_TEXT_WIDTH / 2,
        width: CARD.MAX_TEXT_WIDTH,
        size: CARD.MODE_60PT_FONT_SIZE,
        weight: CARD.NAME_FONT_WEIGHT,
        opacity: nameOpacity,
      }));
    }
    return;
  }

  // Mode: Jabatan Saja (Auto-scaled 1-3 lines up to 128 chars)
  if (mode === "position_only") {
    const rawPosText = options.rawPosition !== undefined
      ? options.rawPosition
      : (Array.isArray(positionLines) ? positionLines.join("\n") : (positionLines || name || ""));
    const safePos = (rawPosText || "").toString().trim();
    if (!safePos) return;
    const { lines, fontSize, baselines } = layoutPositionOnly(safePos, 128);
    for (let i = 0; i < lines.length; i++) {
      const top = boxTopForBaseline(baselines[i], fontSize);
      container.appendChild(makeLine(lines[i], {
        top: top,
        left: CARD.CENTER_X - CARD.MAX_TEXT_WIDTH / 2,
        width: CARD.MAX_TEXT_WIDTH,
        size: fontSize,
        weight: CARD.NAME_FONT_WEIGHT,
        opacity: positionOpacity,
      }));
    }
    return;
  }

  // Mode: Nama & Jabatan (Default standard layout)
  const safeName = (name || "").toString().trim().toUpperCase();
  if (safeName) {
    let fontSize = CARD.NAME_FONT_SIZE;
    const measuredW = typeof getNameTextWidthPt === "function"
      ? getNameTextWidthPt(safeName)
      : measureTextWidthPt(safeName, CARD.NAME_FONT_WEIGHT, fontSize);
    if (measuredW > CARD.NAME_BOX_WIDTH && CARD.NAME_BOX_WIDTH > 0) {
      fontSize = Math.floor(fontSize * (CARD.NAME_BOX_WIDTH / measuredW) * 10) / 10;
    }
    const nameTop = boxTopForBaseline(CARD.NAME_BASELINE_Y, fontSize);
    container.appendChild(makeLine(safeName, {
      top: nameTop,
      left: CARD.CENTER_X - CARD.NAME_BOX_WIDTH / 2,
      width: CARD.NAME_BOX_WIDTH,
      size: fontSize,
      weight: CARD.NAME_FONT_WEIGHT,
      opacity: nameOpacity,
    }));
  }

  if (Array.isArray(positionLines)) {
    const safeLines = positionLines.slice(0, 2);
    safeLines.forEach((line, i) => {
      const baseline = CARD.NAME_BASELINE_Y - CARD.NAME_TO_POSITION_GAP - i * CARD.POSITION_LINE_GAP;
      container.appendChild(makeLine(line, {
        top: boxTopForBaseline(baseline, CARD.POSITION_FONT_SIZE),
        left: CARD.CENTER_X - CARD.MAX_TEXT_WIDTH / 2,
        width: CARD.MAX_TEXT_WIDTH,
        size: CARD.POSITION_FONT_SIZE,
        weight: CARD.POSITION_FONT_WEIGHT,
        opacity: positionOpacity,
      }));
    });
  }
}

function renderCard(name, position, options = {}) {
  const mode = options.mode || CARD.CONTENT_MODE || "both";
  const normal = document.getElementById("block-normal");
  const flip = document.getElementById("block-flip");
  const bg = document.getElementById("bg");
  if (bg && CARD.BG_URL) {
    bg.src = CARD.BG_URL;
  }

  const rawName = stripTrailingPunctuation((name || "").toString().trim());
  const rawPos = stripTrailingPunctuation((position || "").toString().trim());

  const allowPlaceholder = options.allowPlaceholder !== false;
  const isNameEmpty = !rawName;
  const isPosEmpty = !rawPos;

  let displayName = rawName;
  let displayPos = rawPos;
  let nameOpacity = 1.0;
  let positionOpacity = 1.0;

  if (mode === "name_only") {
    displayName = (isNameEmpty && allowPlaceholder) ? DEFAULT_PREVIEW_NAME : rawName;
    nameOpacity = (isNameEmpty && allowPlaceholder) ? 0.6 : 1.0;
    displayPos = "";
  } else if (mode === "position_only") {
    displayPos = (isPosEmpty && allowPlaceholder) ? DEFAULT_PREVIEW_POSITION : rawPos;
    positionOpacity = (isPosEmpty && allowPlaceholder) ? 0.6 : 1.0;
    displayName = "";
  } else {
    displayName = (isNameEmpty && allowPlaceholder) ? DEFAULT_PREVIEW_NAME : rawName;
    displayPos = (isPosEmpty && allowPlaceholder) ? DEFAULT_PREVIEW_POSITION : rawPos;
    nameOpacity = (isNameEmpty && allowPlaceholder) ? 0.6 : 1.0;
    positionOpacity = (isPosEmpty && allowPlaceholder) ? 0.6 : 1.0;
  }

  const positionLines = wrapPosition(displayPos);
  const blockOpts = { nameOpacity, positionOpacity, mode, rawPosition: displayPos };

  if (normal) layoutBlock(normal, displayName, positionLines, blockOpts);
  if (flip) {
    if (CARD.SIDES === 1) {
      flip.style.display = "none";
    } else {
      flip.style.display = "block";
      layoutBlock(flip, displayName, positionLines, blockOpts);
    }
  }
}

// ---------------------------------------------------------------------------
// Bulk Title Cleaner & Parser Utilities
// ---------------------------------------------------------------------------
const LEADING_LIST_PREFIX_PATTERN = /^\s*(?:\(?\d+[\.\)\:\-\]]*|[-*•·–—>→+~▪▫◦■/\\|]+)\s*/;

const FRONT_TITLES_PATTERN = /^\s*(?:(?:Plt\.?|PLT\.?|Plh\.?|PLH\.?|Pj\.?|PJ\.?)\s+)?(?:Prof\.?\s+Dr\.?\s+Ir\.?|Prof\.?\s+Dr\.?|Prof\.?\s+Ir\.?|Prof\.?|Dr\.?\s+Ir\.?|Dr\.?\s+Dr\.?|Dr\.?\s+drg\.?|Dr\.?\s+dr\.?|Drs\.?|Dra\.?|Drg\.?|Drh\.?|Ir\.?|Ns\.?|Apt\.?|Dr\.?|dr\.?|drg\.?|drh\.?|apt\.?|Bpk\.?|Bapak|Ibu|Sdr\.?|Sdri\.?|K\.?\s*H\.?|Kiai\s+Haji|Kyai\s+Haji|Hajjah|Hajah|Haji|Hjh\.?|Hj\.?|H\.|(?:\bH\b\.?))(?:\.|\s+|$)/i;

function isValidOfficialName(name) {
  if (!name) return false;
  const s = String(name).trim();
  if (!s) return false;
  if (!/[A-Za-z0-9]/.test(s)) return false;
  if (["kosong", "belum ada", "vacant", "nihil", "n/a", "none", "null", "plt", "plt.", "plh", "plh.", "pj", "pj."].includes(s.toLowerCase())) return false;
  return true;
}

const TITLE_TOKEN_PATTERN = /^(?:[SMDA]\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|Sp\.\s*[A-Za-z]+(?:\s*\([A-Za-z]+\)|-[A-Za-z0-9]+|(?:\.\s*[A-Za-z]+)*)\.?|Subsp\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|Ph\.?\s*D\.?|PhD|M\.?\s*B\.?\s*A\.?|MBA|M\.?\s*Bus\.?|B\.?\s*[A-Z]\.?\s*(?:Sc|A)?\.?|LL\.?\s*M\.?|LLM|Ed\.?\s*D\.?|D\.?\s*Sc\.?|D\.?\s*B\.?\s*A\.?|IP[UMP]\b\.?|(?:ASEAN|Asean)\s+Eng\.?|ACPE|CPE|(?:SE|SH|ST|SKom|SPd|SSos|SIP|SIKom|SKM|SPi|SPt|SHut|SAg|SFarm|SPsi|SSn|SKed)\b|(?:MM|MH|MT|ME|MSi|MPd|MKes|MKom|MA|MSc|MP|MKn|MAP|MAg|MFarm|MPsi|MSn|MEcon)\b|FINASIM|FACS|FICS|CMA|CPA|CIA|CHRP|CPHR|QIA|CBV|CPMA|CFA|CFP|QWP|FRM|PMP|CAPM|CISA|CISM|CISSP|CEH|CRA|CRP|CRGP|CSO|CGO|CGP|Ak\.?|Akt\.?|CA\b|BKP|CTA|ACPA|MM\.PD)$/i;

const BACK_TITLES_PATTERN = /(?:,\s*|\s+)(?:[SMDA]\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|Sp\.\s*[A-Za-z]+(?:\s*\([A-Za-z]+\)|-[A-Za-z0-9]+|(?:\.\s*[A-Za-z]+)*)\.?|Subsp\.\s*[A-Za-z]+(?:\.\s*[A-Za-z]+)*\.?|Ph\.?\s*D\.?|PhD|M\.?\s*B\.?\s*A\.?|MBA|M\.?\s*Bus\.?|B\.?\s*[A-Z]\.?\s*(?:Sc|A)?\.?|LL\.?\s*M\.?|LLM|Ed\.?\s*D\.?|D\.?\s*Sc\.?|D\.?\s*B\.?\s*A\.?|IP[UMP]\b\.?|(?:ASEAN|Asean)\s+Eng\.?|ACPE|CPE|(?:SE|SH|ST|SKom|SPd|SSos|SIP|SIKom|SKM|SPi|SPt|SHut|SAg|SFarm|SPsi|SSn|SKed)\b|(?:MM|MH|MT|ME|MSi|MPd|MKes|MKom|MA|MSc|MP|MKn|MAP|MAg|MFarm|MPsi|MSn|MEcon)\b|FINASIM|FACS|FICS|CMA|CPA|CIA|CHRP|CPHR|QIA|CBV|CPMA|CFA|CFP|QWP|FRM|PMP|CAPM|CISA|CISM|CISSP|CEH|CRA|CRP|CRGP|CSO|CGO|CGP|Ak\.?|Akt\.?|CA\b|BKP|CTA|ACPA|MM\.PD|H\.|Hj\.|Haji|Hajjah|Hajah|Hjh\.?)\b\.?/gi;

function cleanTitles(name) {
  if (!name) return "";
  let s = name.trim();

  // Strip parenthesized religious titles e.g. "(H.) " or "(Hj.) "
  s = s.replace(/^\s*\((?:H\.|Hj\.|Haji|Hajjah|Hajah|Hjh\.?)\)\s*/i, "").trim();

  // 1. Strip leading numbering or bullet markers (e.g. "1. ", "2) ", "- ", "> ", "· ", "• ")
  let prev = null;
  while (prev !== s) {
    prev = s;
    s = s.replace(LEADING_LIST_PREFIX_PATTERN, "").trim();
  }

  // 2. Strip front titles & religious titles (e.g. "Prof. ", "Dr. ", "H. ", "Hj. ", "K.H. ", etc.)
  prev = null;
  while (prev !== s) {
    prev = s;
    s = s.replace(FRONT_TITLES_PATTERN, "").trim();
  }

  // 3. Strip back titles / academic degrees
  prev = null;
  while (prev !== s) {
    prev = s;
    s = s.replace(BACK_TITLES_PATTERN, "").trim();
  }

  // 4. Clean leftover punctuation at ends and normalize internal spacing
  s = s.replace(/^[,\.\s\-–—>·•\:\=\|\/]+|[,\.\s\-–—>·•\:\=\|\/]+$/, "").trim();

  // 5. Clean any trailing comma or short unrecognized title abbreviations
  while (s.includes(",")) {
    const lastCommaIdx = s.lastIndexOf(",");
    const before = s.substring(0, lastCommaIdx).trim();
    const after = s.substring(lastCommaIdx + 1).trim();
    if (/^(?:[A-Z0-9\.\s\-\(\)]+|\(K\)|Konsultan)$/i.test(after) && after.length <= 12) {
      s = before;
    } else {
      break;
    }
  }

  s = s.replace(/^[,\.\s\-–—>·•\:\=\|\/]+|[,\.\s\-–—>·•\:\=\|\/]+$/, "").trim();
  s = stripTrailingPunctuation(s);
  s = s.replace(/\s+/g, " ");
  return s;
}

function getNameTextWidthPt(text) {
  if (!text) return 0;
  const upper = String(text).trim().toUpperCase();
  if (typeof measureTextWidthPt === "function") {
    try {
      const w = measureTextWidthPt(upper, CARD.NAME_FONT_WEIGHT || 700, CARD.NAME_FONT_SIZE || 45.86);
      if (w > 0) return w;
    } catch (e) {}
  }
  // Precise character-based fallback if canvas measurement is unavailable
  let w = 0;
  for (const ch of upper) {
    if ("MW@#%".includes(ch)) w += 40.0;
    else if ("IJ.:,'!|()[]".includes(ch)) w += 13.0;
    else if ("QOGCDHNU".includes(ch)) w += 33.0;
    else if ("EFLSTZ".includes(ch)) w += 25.0;
    else if (ch === " ") w += 15.0;
    else w += 29.0;
  }
  return w;
}

function fitsName(candidate, maxLen = 24, maxWidth = (typeof CARD !== "undefined" && CARD.MAX_NAME_WIDTH) ? CARD.MAX_NAME_WIDTH : 668.0) {
  if (!candidate) return true;
  if (candidate.length > maxLen) return false;
  if (getNameTextWidthPt(candidate) > maxWidth) return false;
  return true;
}

function formatBulkName(rawName, maxLen = 24, maxWidth = (typeof CARD !== "undefined" && CARD.MAX_NAME_WIDTH) ? CARD.MAX_NAME_WIDTH : 668.0) {
  const cleaned = stripTrailingPunctuation(cleanTitles(rawName));
  if (!cleaned) return "";
  if (fitsName(cleaned, maxLen, maxWidth)) return cleaned;

  const words = cleaned.split(" ");
  if (words.length > 1) {
    // 1. Abbreviate last name: e.g. "Firmansyah" -> "F."
    const lastWord = words[words.length - 1];
    const initial = lastWord.charAt(0).toUpperCase() + ".";
    const candidate = words.slice(0, -1).join(" ") + " " + initial;
    if (fitsName(candidate, maxLen, maxWidth)) {
      return candidate;
    }

    // 2. If still > maxLen or > maxWidth: keep words from beginning as much as fits
    let result = "";
    for (let i = 0; i < words.length - 1; i++) {
      const nextCand = (result ? result + " " + words[i] : words[i]).trim();
      if (fitsName(nextCand + " " + initial, maxLen, maxWidth)) {
        result = nextCand;
      } else if (fitsName(nextCand, maxLen, maxWidth)) {
        result = nextCand;
      } else {
        const initCand = (result ? result + " " + words[i].charAt(0).toUpperCase() + "." : words[i].charAt(0).toUpperCase() + ".").trim();
        if (fitsName(initCand, maxLen, maxWidth)) {
          result = initCand;
        }
        break;
      }
    }
    if (result) {
      if (fitsName(result + " " + initial, maxLen, maxWidth)) {
        return result + " " + initial;
      }
      if (fitsName(result, maxLen, maxWidth)) {
        return result;
      }
    }
  }
  return stripTrailingPunctuation(cleaned.substring(0, maxLen).trim());
}

function cleanPositionText(pos) {
  if (!pos) return "";
  const s = pos.replace(/^[\s\-–—>·•\:\=\|\/]+/, "");
  return stripTrailingPunctuation(s);
}

function splitNameAndPosition(line) {
  line = (line || "").trim();
  if (!line) return { name: "", position: "" };

  // 1. Parentheses / brackets: e.g. "Nama Pejabat (Jabatan Lengkap)"
  // or "Nama - Jabatan (Keterangan)"
  const parenMatch = line.match(/^(.*?)\s*[\(\[\{](.+?)[\)\]\}]\s*$/);
  if (parenMatch) {
    const beforeParen = parenMatch[1].trim();
    const insideParen = parenMatch[2].trim();
    const delims = ["\t", "|", ";", ":", " - ", " – ", " — ", "="];
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
      const posPart = cleanPositionText(beforeParen.substring(idx + foundDelim.length).trim() + " (" + insideParen + ")");
      if (namePart && posPart) {
        return { name: namePart, position: posPart };
      }
    } else {
      const namePart = stripTrailingPunctuation(beforeParen);
      const posPart = cleanPositionText(insideParen);
      if (namePart && posPart) {
        return { name: namePart, position: posPart };
      }
    }
  }

  // 2. Explicit strong delimiters: Tab, Pipe, Semicolon, Colon, Dash with spaces, Slash with spaces, Equal
  const delims = ["\t", "|", ";", ":", " - ", " – ", " — ", " / ", "="];
  for (const d of delims) {
    if (line.includes(d)) {
      const idx = line.indexOf(d);
      return {
        name: stripTrailingPunctuation(line.substring(0, idx).trim()),
        position: cleanPositionText(line.substring(idx + d.length))
      };
    }
  }

  // 3. Comma check: could separate degrees or name/position
  if (line.includes(",")) {
    const parts = line.split(",").map(p => p.trim()).filter(Boolean);
    if (parts.length >= 2) {
      const lastPart = parts[parts.length - 1];
      const isTitle = TITLE_TOKEN_PATTERN.test(lastPart);
      if (!isTitle) {
        return {
          name: stripTrailingPunctuation(parts.slice(0, -1).join(", ")),
          position: cleanPositionText(lastPart)
        };
      }
    }
  }

  // 4. Single dash or slash between words
  for (const d of ["-", "/"]) {
    if (line.includes(d)) {
      const idx = line.indexOf(d);
      const left = line.substring(0, idx).trim();
      const right = cleanPositionText(line.substring(idx + 1));
      if (left && right) {
        return { name: stripTrailingPunctuation(left), position: right };
      }
    }
  }

  // 5. Check if line contains position indicators starting with PLT / Plt / Plh / Pj separated by space
  const pltMatch = line.match(/\s+(?:PLT\.?|Plt\.?|PLH\.?|Plh\.?|Pj\.?|PJ\.?)\s+/i);
  if (pltMatch) {
    const idx = pltMatch.index;
    const namePart = line.substring(0, idx).trim();
    const posPart = line.substring(idx).trim();
    if (namePart && posPart) {
      return { name: stripTrailingPunctuation(namePart), position: cleanPositionText(posPart) };
    }
  }

  return { name: stripTrailingPunctuation(line), position: "" };
}

function setFontFamily(fontFamily) {
  CARD.FONT_FAMILY = fontFamily;
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
    const name = (r.name || "").trim();
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
window.setFontFamily = setFontFamily;
window.setCardSides = setCardSides;
window.setBackgroundUrl = setBackgroundUrl;
window.setContentMode = setContentMode;
window.DEFAULT_PREVIEW_NAME = DEFAULT_PREVIEW_NAME;
window.DEFAULT_PREVIEW_POSITION = DEFAULT_PREVIEW_POSITION;

