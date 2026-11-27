"""PDF extraction, scanned-page detection, OCR fallback, and duplicate detection for SATYA."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pymupdf

logger = logging.getLogger("satya.pdf_processor")

# Patterns for Gazette running headers, footers, printer colophons, and KrutiDev legacy encoding noise.
RUNNING_HEADER_PATTERNS = [
    re.compile(r"^\s*(?:\d+\s+)?THE\s+GAZETTE\s+OF\s+INDIA\b.*$", re.IGNORECASE),
    re.compile(r"^\s*\[?PART\s+II[—\-–\s].*$", re.IGNORECASE),
    re.compile(r"^\s*SEC\.\s*1\]?\s*(?:THE\s+GAZETTE.*)?$", re.IGNORECASE),
    re.compile(r"^\s*(?:R\.\s*\d+\]?\s*)?CONSUMER\s+PROTECTION\s*\([^)]+\)\s*RULES,\s*\d{4}\s*(?:\[?R\.\s*\d+\]?)?\s*\d*\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d{1,3}\s+CONSUMER\s+PROTECTION\s*\([^)]+\)\s*RULES,\s*\d{4}\s*\[?R\.\s*\d+\]?\s*$", re.IGNORECASE),
    re.compile(r"^\s*R\.\s*\d+\]\s*$", re.IGNORECASE),
    re.compile(r"^\s*\[?\d{1,3}\]?\s*$"),
]

FOOTER_NOISE_PATTERNS = [
    re.compile(r"^\s*UPLOADED\s+BY\s+(?:THE\s+MANAGER|DTE\.?\s+OF\s+PRINTING)\b.*$", re.IGNORECASE),
    re.compile(r"^\s*AND\s+PUBLISHED\s+BY\s+THE\s+CONTROLLER\s+OF\s+PUBLICATIONS\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Digitally\s+signed\s+by\b.*$", re.IGNORECASE),
    re.compile(r"^\s*(?:MGIPMRND|CG-DL-E-|सी\.जी\.-डी\.एल\.|\d+\s+GI/\d{4}).*$", re.IGNORECASE),
    re.compile(r"^\s*Date:\s*\d{4}\.\d{2}\.\d{2}\b.*$", re.IGNORECASE),
    re.compile(r"^\s*\+05'?30'?\s*$"),
    re.compile(r"^\s*(?:BANSHI|DHAR|DUBEY|SURENDER|MAHADASAM)\s*$"),
    re.compile(r"^\s*xxxGID[HE]xxx\s*$", re.IGNORECASE),
]

KRUTIDEV_NOISE_PATTERNS = [
    re.compile(r"jftLVªh|vlk/kkj\.k|izkf/kdkj|vxLr|Jko\.k|ladyu|Hkkx\s+II"),
]

MARGIN_ACT_CITATION_RE = re.compile(r"^\d+\s+of\s+\d{4}\.?$", re.IGNORECASE)
OCR_LIST_ENUM_ONLY_RE = re.compile(r"^\([a-z0-9ivx]+\)$", re.IGNORECASE)


@dataclass
class PageExtraction:
    """Extracted text, layout lines, and provenance for a single PDF page."""

    page_number: int
    raw_text: str
    cleaned_text: str
    extraction_method: str
    is_scanned: bool
    image_count: int
    text_char_count: int
    margin_notes: list[dict[str, Any]] = field(default_factory=list)
    lines: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize page extraction to a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class DocumentExtraction:
    """Full extraction outcome for a single PDF file."""

    doc_id: str
    file_name: str
    file_path: str
    file_size_bytes: int
    file_hash: str
    content_hash: str | None
    status: str  # "success" | "partial_failure" | "duplicate" | "failed"
    duplicate_of: str | None = None
    duplicate_type: str | None = None
    total_pages: int = 0
    scanned_pages: list[int] = field(default_factory=list)
    ocr_pages: list[int] = field(default_factory=list)
    failed_pages: list[int] = field(default_factory=list)
    extraction_method: str = "none"
    pages: list[PageExtraction] = field(default_factory=list)
    full_text: str = ""
    pdf_metadata: dict[str, Any] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize document extraction to a JSON-friendly dictionary."""
        data = asdict(self)
        data["pages"] = [p.to_dict() for p in self.pages]
        return data


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hex digest of raw file bytes."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hex digest of normalized extracted text for duplicate detection."""
    normalized = re.sub(r"\s+", " ", text or "").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _is_noise_line(line: str, y0: float, y1: float, page_height: float) -> bool:
    """Return True if a line is a running Gazette header, footer colophon, or legacy font noise."""
    stripped = line.strip()
    if not stripped:
        return True

    for pat in KRUTIDEV_NOISE_PATTERNS:
        if pat.search(stripped):
            return True

    in_top_band = page_height > 0 and y1 <= page_height * 0.125
    in_bottom_band = page_height > 0 and y0 >= page_height * 0.84

    if in_top_band:
        for pat in RUNNING_HEADER_PATTERNS:
            if pat.match(stripped):
                return True

    if in_bottom_band:
        for pat in FOOTER_NOISE_PATTERNS:
            if pat.match(stripped):
                return True
        if re.match(r"^(?:\[\d{1,3}\]|\(\d{1,3}\)|\d{1,3})$", stripped):
            return True

    # Catch digital signature / printer colophons even slightly outside bottom band
    for pat in FOOTER_NOISE_PATTERNS:
        if pat.match(stripped):
            return True

    return False


def _normalize_text_line(text: str) -> str:
    """Normalize whitespace and zero-width artifacts inside a single line."""
    cleaned = text.replace("\u200d", "").replace("\u200c", "").replace("\xad", "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def _detect_page_scanned(page: pymupdf.Page, raw_text: str, min_text_chars: int = 40) -> tuple[bool, int, float]:
    """Determine whether a PDF page is scanned and needs OCR."""
    alnum_count = sum(ch.isalnum() for ch in raw_text)
    images = page.get_images(full=True)
    image_count = len(images)

    page_area = max(float(page.rect.width * page.rect.height), 1.0)
    max_img_coverage = 0.0
    for img in images:
        xref = img[0]
        try:
            for rect in page.get_image_rects(xref):
                coverage = (rect.width * rect.height) / page_area
                if coverage > max_img_coverage:
                    max_img_coverage = coverage
        except Exception:
            continue

    if alnum_count < min_text_chars and image_count > 0:
        return True, image_count, max_img_coverage
    if alnum_count < 100 and max_img_coverage >= 0.35:
        return True, image_count, max_img_coverage
    return False, image_count, max_img_coverage


def _detect_margin_columns(blocks: list[tuple[Any, ...]], page_width: float) -> bool:
    """Detect Indian Gazette Bare-Act two-margin layout (central body column + side notes)."""
    if page_width < 450:
        return False
    body_blocks = [b for b in blocks if b[6] == 0 and b[0] >= 110 and b[2] <= 485 and (b[2] - b[0]) > 120]
    side_blocks = [b for b in blocks if b[6] == 0 and (b[2] <= 108 or b[0] >= 482)]
    return len(body_blocks) >= 2 and len(side_blocks) >= 1


def _extract_pymupdf_page(page: pymupdf.Page, page_number: int) -> PageExtraction:
    """Extract cleaned text, layout lines, and margin notes from a text-based PDF page."""
    raw_text = page.get_text("text") or ""
    blocks = page.get_text("blocks") or []
    page_rect = page.rect
    page_width = float(page_rect.width)
    page_height = float(page_rect.height)
    has_margins = _detect_margin_columns(blocks, page_width)

    text_blocks = sorted(
        [b for b in blocks if b[6] == 0 and (b[4] or "").strip()],
        key=lambda b: (round(float(b[1]), 1), round(float(b[0]), 1)),
    )

    margin_notes: list[dict[str, Any]] = []
    body_lines: list[dict[str, Any]] = []

    for blk in text_blocks:
        x0, y0, x1, y1, blk_text = float(blk[0]), float(blk[1]), float(blk[2]), float(blk[3]), str(blk[4])
        if has_margins and (x1 <= 108.0 or x0 >= 482.0) and y1 > page_height * 0.10 and y0 < page_height * 0.90:
            note_text = _normalize_text_line(blk_text.replace("\n", " "))
            if note_text and not _is_noise_line(note_text, y0, y1, page_height):
                note_kind = "act_citation" if MARGIN_ACT_CITATION_RE.match(note_text) else "section_heading"
                margin_notes.append(
                    {
                        "y": round(y0, 2),
                        "x": round(x0, 2),
                        "side": "left" if x1 <= 108.0 else "right",
                        "kind": note_kind,
                        "text": note_text,
                    }
                )
            continue

        raw_lines = blk_text.splitlines()
        line_count = max(len(raw_lines), 1)
        line_h = (y1 - y0) / line_count
        for idx, raw_line in enumerate(raw_lines):
            ly0 = y0 + idx * line_h
            ly1 = ly0 + line_h
            cleaned_line = _normalize_text_line(raw_line)
            if not cleaned_line or _is_noise_line(cleaned_line, ly0, ly1, page_height):
                continue
            body_lines.append(
                {
                    "page_number": page_number,
                    "x": round(x0, 2),
                    "y": round(ly0, 2),
                    "text": cleaned_line,
                }
            )

    cleaned_text = "\n".join(item["text"] for item in body_lines)
    alnum_count = sum(ch.isalnum() for ch in cleaned_text)
    warnings: list[str] = []
    if alnum_count == 0:
        warnings.append("page_produced_no_meaningful_text")

    return PageExtraction(
        page_number=page_number,
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        extraction_method="pymupdf_text",
        is_scanned=False,
        image_count=len(page.get_images(full=True)),
        text_char_count=len(cleaned_text),
        margin_notes=margin_notes,
        lines=body_lines,
        warnings=warnings,
    )


def _reconstruct_lines_from_words(words: list[dict[str, Any]], img_width: int, img_height: int) -> list[dict[str, Any]]:
    """Cluster OCR word bounding boxes into reading-order horizontal lines."""
    if not words:
        return []

    heights = [float(w["h"]) for w in words if float(w.get("h", 0)) > 0]
    median_h = statistics.median(heights) if heights else 18.0
    y_tolerance = max(median_h * 0.58, 8.0)

    sorted_words = sorted(words, key=lambda w: (float(w["y"]) + float(w["h"]) / 2.0, float(w["x"])))
    line_groups: list[list[dict[str, Any]]] = []
    line_centers: list[float] = []

    for word in sorted_words:
        cy = float(word["y"]) + float(word["h"]) / 2.0
        placed = False
        for idx in range(len(line_groups) - 1, -1, -1):
            if abs(cy - line_centers[idx]) <= y_tolerance:
                line_groups[idx].append(word)
                line_centers[idx] = statistics.mean(
                    float(w["y"]) + float(w["h"]) / 2.0 for w in line_groups[idx]
                )
                placed = True
                break
        if not placed:
            line_groups.append([word])
            line_centers.append(cy)

    reconstructed: list[dict[str, Any]] = []
    for group in line_groups:
        group.sort(key=lambda w: float(w["x"]))
        joined = _normalize_text_line(" ".join(str(w["text"]) for w in group))
        if not joined:
            continue
        min_x = min(float(w["x"]) for w in group)
        min_y = min(float(w["y"]) for w in group)
        max_y = max(float(w["y"]) + float(w["h"]) for w in group)
        # Scale pixel coordinates to standard ~595x842 points for uniform filtering
        scale_y = 842.0 / max(float(img_height), 1.0)
        scale_x = 595.0 / max(float(img_width), 1.0)
        reconstructed.append(
            {
                "x": round(min_x * scale_x, 2),
                "y": round(min_y * scale_y, 2),
                "y1": round(max_y * scale_y, 2),
                "text": joined,
            }
        )

    # Merge stray list-marker-only lines like "(a)" if immediately adjacent in Y to next line
    merged: list[dict[str, Any]] = []
    i = 0
    while i < len(reconstructed):
        cur = reconstructed[i]
        if (
            OCR_LIST_ENUM_ONLY_RE.match(cur["text"])
            and i + 1 < len(reconstructed)
            and abs(reconstructed[i + 1]["y"] - cur["y"]) <= 18.0
            and cur["x"] < reconstructed[i + 1]["x"]
        ):
            nxt = reconstructed[i + 1]
            merged.append(
                {
                    "x": cur["x"],
                    "y": min(cur["y"], nxt["y"]),
                    "y1": max(cur["y1"], nxt["y1"]),
                    "text": f"{cur['text']} {nxt['text']}",
                }
            )
            i += 2
            continue
        merged.append(cur)
        i += 1
    return merged


class OcrRunner:
    """Pluggable OCR backend supporting RapidOCR, Tesseract, and Windows.Media.Ocr."""

    def __init__(self, preferred_engine: str = "auto", dpi: int = 250) -> None:
        self.preferred_engine = preferred_engine
        self.dpi = dpi
        self._resolved_engine: str | None = None
        self._rapidocr_instance: Any = None

    def resolve_engine(self) -> str:
        """Pick the best working OCR engine in the current environment."""
        if self._resolved_engine is not None:
            return self._resolved_engine

        if self.preferred_engine != "auto":
            candidates = [self.preferred_engine]
        elif sys.platform == "win32":
            candidates = ["windows_ocr", "tesseract", "rapidocr"]
        else:
            candidates = ["tesseract", "rapidocr"]

        errors: list[str] = []
        for candidate in candidates:
            if candidate == "rapidocr":
                try:
                    from rapidocr_onnxruntime import RapidOCR  # type: ignore

                    self._rapidocr_instance = RapidOCR()
                    self._resolved_engine = "rapidocr"
                    return self._resolved_engine
                except Exception as exc:
                    errors.append(f"rapidocr unavailable ({exc})")
            elif candidate == "tesseract":
                if shutil.which("tesseract"):
                    try:
                        import pytesseract  # type: ignore  # noqa: F401

                        self._resolved_engine = "tesseract"
                        return self._resolved_engine
                    except Exception as exc:
                        errors.append(f"tesseract unavailable ({exc})")
                else:
                    errors.append("tesseract binary not on PATH")
            elif candidate == "windows_ocr":
                if sys.platform == "win32" and shutil.which("powershell"):
                    self._resolved_engine = "windows_ocr"
                    return self._resolved_engine
                errors.append("windows_ocr requires Windows PowerShell")
            else:
                errors.append(f"unknown OCR engine: {candidate}")

        raise RuntimeError("No working OCR engine available: " + "; ".join(errors))

    def ocr_pages(self, doc: pymupdf.Document, page_numbers: list[int]) -> dict[int, dict[str, Any]]:
        """Run OCR on a list of 1-based page numbers and return per-page lines & raw text."""
        if not page_numbers:
            return {}
        engine = self.resolve_engine()
        logger.info("Running %s OCR on %d page(s): %s", engine, len(page_numbers), page_numbers)

        if engine == "windows_ocr":
            return self._run_windows_ocr_batch(doc, page_numbers)
        if engine == "tesseract":
            return self._run_tesseract_batch(doc, page_numbers)
        if engine == "rapidocr":
            return self._run_rapidocr_batch(doc, page_numbers)
        raise RuntimeError(f"Unsupported OCR engine: {engine}")

    def _run_rapidocr_batch(self, doc: pymupdf.Document, page_numbers: list[int]) -> dict[int, dict[str, Any]]:
        results: dict[int, dict[str, Any]] = {}
        for pno in page_numbers:
            page = doc[pno - 1]
            pix = page.get_pixmap(dpi=self.dpi)
            ocr_out, _ = self._rapidocr_instance(pix.tobytes("png"))
            words: list[dict[str, Any]] = []
            for item in ocr_out or []:
                box, text, _score = item
                xs = [pt[0] for pt in box]
                ys = [pt[1] for pt in box]
                words.append(
                    {
                        "text": text,
                        "x": min(xs),
                        "y": min(ys),
                        "w": max(xs) - min(xs),
                        "h": max(ys) - min(ys),
                    }
                )
            lines = _reconstruct_lines_from_words(words, pix.width, pix.height)
            results[pno] = {
                "engine": "rapidocr",
                "raw_text": "\n".join(l["text"] for l in lines),
                "lines": lines,
                "img_width": pix.width,
                "img_height": pix.height,
            }
        return results

    def _run_tesseract_batch(self, doc: pymupdf.Document, page_numbers: list[int]) -> dict[int, dict[str, Any]]:
        import io
        from PIL import Image
        import pytesseract  # type: ignore

        results: dict[int, dict[str, Any]] = {}
        for pno in page_numbers:
            page = doc[pno - 1]
            pix = page.get_pixmap(dpi=self.dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            words: list[dict[str, Any]] = []
            for i, txt in enumerate(data.get("text", [])):
                if txt and txt.strip():
                    words.append(
                        {
                            "text": txt.strip(),
                            "x": data["left"][i],
                            "y": data["top"][i],
                            "w": data["width"][i],
                            "h": data["height"][i],
                        }
                    )
            lines = _reconstruct_lines_from_words(words, pix.width, pix.height)
            results[pno] = {
                "engine": "tesseract",
                "raw_text": "\n".join(l["text"] for l in lines),
                "lines": lines,
                "img_width": pix.width,
                "img_height": pix.height,
            }
        return results

    def _run_windows_ocr_batch(self, doc: pymupdf.Document, page_numbers: list[int]) -> dict[int, dict[str, Any]]:
        """Render scanned pages to temp PNGs and run Windows.Media.Ocr in one PowerShell call."""
        ps_script = r"""
param([string]$InputJson, [string]$OutputJson)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[void][Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
[void][Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime]
[void][Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType=WindowsRuntime]
[void][Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

$ocr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $ocr) {
    $enLang = New-Object Windows.Globalization.Language("en-US")
    $ocr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($enLang)
}
if ($null -eq $ocr) {
    throw "Windows OCR engine could not be initialized for user profile or en-US language."
}

$items = Get-Content -Raw -Path $InputJson -Encoding UTF8 | ConvertFrom-Json
$output = @()
foreach ($item in $items) {
    $fs = [System.IO.File]::OpenRead($item.image_path)
    try {
        $stream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($fs)
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $ocrResult = Await ($ocr.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $words = @()
        foreach ($line in $ocrResult.Lines) {
            foreach ($word in $line.Words) {
                $r = $word.BoundingRect
                $words += [PSCustomObject]@{
                    text = $word.Text
                    x = [math]::Round($r.X, 2)
                    y = [math]::Round($r.Y, 2)
                    w = [math]::Round($r.Width, 2)
                    h = [math]::Round($r.Height, 2)
                }
            }
        }
        $output += [PSCustomObject]@{
            page_number = $item.page_number
            raw_text = $ocrResult.Text
            words = $words
        }
    } finally {
        $fs.Dispose()
    }
}
$output | ConvertTo-Json -Depth 5 | Set-Content -Path $OutputJson -Encoding UTF8
"""
        results: dict[int, dict[str, Any]] = {}
        with tempfile.TemporaryDirectory(prefix="satya_ocr_") as tmpdir:
            tmp = Path(tmpdir)
            manifest: list[dict[str, Any]] = []
            dimensions: dict[int, tuple[int, int]] = {}
            for pno in page_numbers:
                page = doc[pno - 1]
                pix = page.get_pixmap(dpi=self.dpi)
                img_path = tmp / f"page_{pno}.png"
                pix.save(str(img_path))
                manifest.append({"page_number": pno, "image_path": str(img_path)})
                dimensions[pno] = (pix.width, pix.height)

            input_json = tmp / "manifest.json"
            output_json = tmp / "ocr_output.json"
            ps_path = tmp / "run_ocr.ps1"
            input_json.write_text(json.dumps(manifest), encoding="utf-8")
            ps_path.write_text(ps_script, encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ps_path),
                    "-InputJson",
                    str(input_json),
                    "-OutputJson",
                    str(output_json),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Windows OCR failed (exit {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
                )

            raw_json = output_json.read_text(encoding="utf-8-sig")
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                parsed = [parsed]
            for entry in parsed:
                pno = int(entry["page_number"])
                img_w, img_h = dimensions[pno]
                words = entry.get("words") or []
                lines = _reconstruct_lines_from_words(words, img_w, img_h)
                results[pno] = {
                    "engine": "windows_ocr",
                    "raw_text": entry.get("raw_text") or "\n".join(l["text"] for l in lines),
                    "lines": lines,
                    "img_width": img_w,
                    "img_height": img_h,
                }
        return results


def _build_ocr_page_extraction(pno: int, ocr_payload: dict[str, Any], image_count: int) -> PageExtraction:
    """Filter headers/footers on OCR output and create a PageExtraction object."""
    raw_text = ocr_payload.get("raw_text", "")
    lines_out: list[dict[str, Any]] = []
    for item in ocr_payload.get("lines", []):
        txt = _normalize_text_line(item["text"])
        y0 = float(item.get("y", 0.0))
        y1 = float(item.get("y1", y0 + 12.0))
        if not txt or _is_noise_line(txt, y0, y1, 842.0):
            continue
        lines_out.append(
            {
                "page_number": pno,
                "x": float(item.get("x", 0.0)),
                "y": y0,
                "text": txt,
            }
        )

    cleaned_text = "\n".join(item["text"] for item in lines_out)
    warnings: list[str] = []
    if sum(ch.isalnum() for ch in cleaned_text) < 15:
        warnings.append("ocr_produced_minimal_text")

    return PageExtraction(
        page_number=pno,
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        extraction_method=f"ocr:{ocr_payload.get('engine', 'unknown')}",
        is_scanned=True,
        image_count=image_count,
        text_char_count=len(cleaned_text),
        margin_notes=[],
        lines=lines_out,
        warnings=warnings,
    )


def discover_pdfs(input_dir: Path) -> list[Path]:
    """Find every PDF inside input_dir (recursively) sorted deterministically."""
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {input_dir}")
    pdfs = [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"]
    return sorted(pdfs, key=lambda p: p.as_posix().lower())


def process_pdf_file(
    pdf_path: Path,
    seen_file_hashes: dict[str, str],
    seen_content_hashes: dict[str, str],
    ocr_runner: OcrRunner | None = None,
    min_text_chars_per_page: int = 40,
) -> DocumentExtraction:
    """Process a single PDF with duplicate detection, scanned-page OCR, and explicit error reporting."""
    file_name = pdf_path.name
    doc_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", pdf_path.stem).strip("_").lower() or "document"
    ocr_runner = ocr_runner or OcrRunner()

    if not pdf_path.exists():
        return DocumentExtraction(
            doc_id=doc_id,
            file_name=file_name,
            file_path=str(pdf_path),
            file_size_bytes=0,
            file_hash="",
            content_hash=None,
            status="failed",
            error_type="FileNotFoundError",
            error_message=f"PDF file not found: {pdf_path}",
        )

    file_size = pdf_path.stat().st_size
    if file_size == 0:
        return DocumentExtraction(
            doc_id=doc_id,
            file_name=file_name,
            file_path=str(pdf_path),
            file_size_bytes=0,
            file_hash="",
            content_hash=None,
            status="failed",
            error_type="EmptyFileError",
            error_message="PDF file is 0 bytes.",
        )

    try:
        file_hash = compute_file_hash(pdf_path)
    except OSError as exc:
        return DocumentExtraction(
            doc_id=doc_id,
            file_name=file_name,
            file_path=str(pdf_path),
            file_size_bytes=file_size,
            file_hash="",
            content_hash=None,
            status="failed",
            error_type=type(exc).__name__,
            error_message=f"Failed to read file bytes: {exc}",
        )

    if file_hash in seen_file_hashes:
        original = seen_file_hashes[file_hash]
        logger.warning("Exact duplicate PDF detected: %s duplicates %s", file_name, original)
        return DocumentExtraction(
            doc_id=doc_id,
            file_name=file_name,
            file_path=str(pdf_path),
            file_size_bytes=file_size,
            file_hash=file_hash,
            content_hash=None,
            status="duplicate",
            duplicate_of=original,
            duplicate_type="exact_file",
            warnings=[f"Exact SHA-256 duplicate of {original}"],
        )

    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as exc:
        logger.error("Failed to open PDF %s: %s", file_name, exc)
        return DocumentExtraction(
            doc_id=doc_id,
            file_name=file_name,
            file_path=str(pdf_path),
            file_size_bytes=file_size,
            file_hash=file_hash,
            content_hash=None,
            status="failed",
            error_type=type(exc).__name__,
            error_message=f"Corrupt or unreadable PDF: {exc}",
        )

    try:
        if doc.is_encrypted and doc.needs_pass:
            return DocumentExtraction(
                doc_id=doc_id,
                file_name=file_name,
                file_path=str(pdf_path),
                file_size_bytes=file_size,
                file_hash=file_hash,
                content_hash=None,
                status="failed",
                error_type="EncryptedPDFError",
                error_message="PDF is password-protected/encrypted and cannot be extracted without credentials.",
            )

        total_pages = len(doc)
        if total_pages == 0:
            return DocumentExtraction(
                doc_id=doc_id,
                file_name=file_name,
                file_path=str(pdf_path),
                file_size_bytes=file_size,
                file_hash=file_hash,
                content_hash=None,
                status="failed",
                total_pages=0,
                error_type="EmptyPDFError",
                error_message="PDF contains 0 pages.",
            )

        pdf_metadata = {k: v for k, v in (doc.metadata or {}).items() if v}
        page_results: dict[int, PageExtraction] = {}
        scanned_pages: list[int] = []
        scanned_image_counts: dict[int, int] = {}
        failed_pages: list[int] = []
        warnings: list[str] = []

        for idx in range(total_pages):
            pno = idx + 1
            try:
                page = doc[idx]
                raw_text = page.get_text("text") or ""
                is_scanned, img_count, _coverage = _detect_page_scanned(
                    page, raw_text, min_text_chars=min_text_chars_per_page
                )
                if is_scanned:
                    scanned_pages.append(pno)
                    scanned_image_counts[pno] = img_count
                else:
                    page_results[pno] = _extract_pymupdf_page(page, pno)
            except Exception as exc:
                logger.error("Error inspecting page %d of %s: %s", pno, file_name, exc)
                failed_pages.append(pno)
                page_results[pno] = PageExtraction(
                    page_number=pno,
                    raw_text="",
                    cleaned_text="",
                    extraction_method="failed",
                    is_scanned=False,
                    image_count=0,
                    text_char_count=0,
                    error=f"{type(exc).__name__}: {exc}",
                )

        ocr_pages: list[int] = []
        if scanned_pages:
            try:
                ocr_outputs = ocr_runner.ocr_pages(doc, scanned_pages)
                for pno in scanned_pages:
                    payload = ocr_outputs.get(pno)
                    if not payload:
                        failed_pages.append(pno)
                        page_results[pno] = PageExtraction(
                            page_number=pno,
                            raw_text="",
                            cleaned_text="",
                            extraction_method="failed",
                            is_scanned=True,
                            image_count=scanned_image_counts.get(pno, 0),
                            text_char_count=0,
                            error="OCR returned no result for scanned page.",
                        )
                    else:
                        pe = _build_ocr_page_extraction(pno, payload, scanned_image_counts.get(pno, 0))
                        page_results[pno] = pe
                        ocr_pages.append(pno)
            except Exception as exc:
                logger.error("OCR failed for %s (pages %s): %s", file_name, scanned_pages, exc)
                warnings.append(f"OCR failure on scanned pages {scanned_pages}: {exc}")
                for pno in scanned_pages:
                    failed_pages.append(pno)
                    page_results[pno] = PageExtraction(
                        page_number=pno,
                        raw_text="",
                        cleaned_text="",
                        extraction_method="failed",
                        is_scanned=True,
                        image_count=scanned_image_counts.get(pno, 0),
                        text_char_count=0,
                        error=f"OCRError: {exc}",
                    )
    finally:
        doc.close()

    ordered_pages = [page_results[i] for i in range(1, total_pages + 1)]
    full_text = "\n\n".join(p.cleaned_text for p in ordered_pages if p.cleaned_text.strip())
    failed_pages = sorted(set(failed_pages))

    if not full_text.strip():
        return DocumentExtraction(
            doc_id=doc_id,
            file_name=file_name,
            file_path=str(pdf_path),
            file_size_bytes=file_size,
            file_hash=file_hash,
            content_hash=None,
            status="failed",
            total_pages=total_pages,
            scanned_pages=scanned_pages,
            ocr_pages=ocr_pages,
            failed_pages=failed_pages or list(range(1, total_pages + 1)),
            extraction_method="failed",
            pages=ordered_pages,
            full_text="",
            pdf_metadata=pdf_metadata,
            error_type="NoExtractableTextError",
            error_message="Extraction yielded no readable text across all pages.",
            warnings=warnings,
        )

    content_hash = compute_content_hash(full_text)
    if content_hash in seen_content_hashes:
        original = seen_content_hashes[content_hash]
        logger.warning("Content-duplicate PDF detected: %s matches %s", file_name, original)
        return DocumentExtraction(
            doc_id=doc_id,
            file_name=file_name,
            file_path=str(pdf_path),
            file_size_bytes=file_size,
            file_hash=file_hash,
            content_hash=content_hash,
            status="duplicate",
            duplicate_of=original,
            duplicate_type="content_duplicate",
            total_pages=total_pages,
            scanned_pages=scanned_pages,
            ocr_pages=ocr_pages,
            failed_pages=failed_pages,
            extraction_method="duplicate_skipped",
            pdf_metadata=pdf_metadata,
            warnings=[f"Normalized text matches content of {original}"],
        )

    seen_file_hashes[file_hash] = file_name
    seen_content_hashes[content_hash] = file_name

    if ocr_pages and len(ocr_pages) == total_pages:
        overall_method = "ocr"
    elif ocr_pages:
        overall_method = "mixed"
    else:
        overall_method = "pymupdf_text"

    status = "partial_failure" if failed_pages else "success"
    error_type = "PartialPageExtractionError" if failed_pages else None
    error_message = (
        f"Failed to extract {len(failed_pages)} page(s): {failed_pages}" if failed_pages else None
    )

    return DocumentExtraction(
        doc_id=doc_id,
        file_name=file_name,
        file_path=str(pdf_path),
        file_size_bytes=file_size,
        file_hash=file_hash,
        content_hash=content_hash,
        status=status,
        total_pages=total_pages,
        scanned_pages=scanned_pages,
        ocr_pages=ocr_pages,
        failed_pages=failed_pages,
        extraction_method=overall_method,
        pages=ordered_pages,
        full_text=full_text,
        pdf_metadata=pdf_metadata,
        error_type=error_type,
        error_message=error_message,
        warnings=warnings,
    )
