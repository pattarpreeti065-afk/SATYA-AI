"""Legal structure detection and context-preserving chunking for Indian statutes and rules."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from pdf_processor import DocumentExtraction

# Heading & structural patterns for Indian legislation (Acts, Rules, Notifications, Gazette PDFs)
ACT_TITLE_RE = re.compile(
    r"^(?:THE\s+)?[A-Z0-9\s,()\-&]+?\bACT,\s*\d{4}\b\.?$"
)
RULES_TITLE_RE = re.compile(
    r"^(?:The\s+)?[A-Za-z0-9\s,()\-&]+?\bRules,\s*\d{4}\b\.?\d*$",
    re.IGNORECASE,
)
CHAPTER_RE = re.compile(
    r"^CHAPTER\s+([IVXLCDM]+|\d+)\b(?:\s*[-—–:]\s*(.+))?$",
    re.IGNORECASE,
)
EXPLICIT_SECTION_RE = re.compile(
    r"^(?:SECTION|Section)\s+(\d+[A-Z]?)\s*(?:[:.—\-–]\s*(.*))?$"
)
EXPLICIT_RULE_RE = re.compile(
    r"^(?:RULE|Rule)\s+(\d+[A-Z]?)\s*(?:[:.—\-–]\s*(.*))?$"
)
EXPLICIT_SUBRULE_RE = re.compile(
    r"^(?:SUB-?RULE|Sub-?[Rr]ule)\s*\(?(\d+[A-Z]?)\)?\s*(?:[:.—\-–]\s*(.*))?$"
)
NUMBERED_PROVISION_RE = re.compile(
    r"^(\d{1,3}[A-Z]?)\.(?:\s+(.*))?$"
)
SUB_PROVISION_RE = re.compile(
    r"^(?:\d+\[)?\(([1-9]\d?|l)\)\s*(.*)$"
)
CLAUSE_RE = re.compile(
    r"^\(([a-z]{1,2}|[ivxlcdm]+|[A-Z])\)\s+(.+)$"
)
PROVISO_OR_EXPLANATION_RE = re.compile(
    r"^(?:Provided\s+(?:that|further\s+that|also\s+that)\b|Explanation\.?[—\-–]?)",
    re.IGNORECASE,
)
RULE_INLINE_TITLE_RE = re.compile(
    r"^([A-Z][^—]{2,150}?)\s*(?:\.?—|\.-)\s*(?:\d+\[)?(?:\(?(\d+|l)\)?\s*)?(.*)$"
)
FOOTNOTE_BODY_RE = re.compile(
    r"^(?:Ministry\s+of\s+|Subs\.?\s+by\b|Ins\.?\s+by\b|Omitted\s+by\b|G\.S\.R\.|S\.O\.|Published\s+in\b)",
    re.IGNORECASE,
)
TOC_LINE_RE = re.compile(r"\.{3,}\s*\d+\s*$")
DEVANAGARI_CHAR_RE = re.compile(r"[\u0900-\u097F]")


@dataclass
class DetectedHeading:
    """Represents a detected legal heading (ACT, CHAPTER, SECTION, RULE, SUB-RULE)."""

    heading_type: str  # ACT | CHAPTER | SECTION | RULE | SUB-RULE
    identifier: str
    title: str | None
    raw_text: str
    page_number: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LegalChunk:
    """Structured legal chunk with full structural metadata and source page provenance."""

    chunk_id: str
    chunk_index: int
    document_name: str
    document_title: str
    doc_type: str
    unit_type: str
    chapter: str | None
    chapter_title: str | None
    section_number: str | None
    section_title: str | None
    rule_number: str | None
    rule_title: str | None
    sub_section_numbers: list[str]
    sub_rule_numbers: list[str]
    paragraph_references: list[str]
    detected_headings: list[dict[str, Any]]
    heading_hierarchy: list[str]
    source_pages: list[int]
    page_start: int
    page_end: int
    page_spans: list[dict[str, Any]]
    extraction_method: str
    language: str
    char_count: int
    text: str
    contextualized_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _AnnotatedLine:
    """Internal representation of a line annotated with page and structural state."""

    page_number: int
    text: str
    language: str
    sub_num: str | None = None
    clause_ref: str | None = None
    paragraph_ref: str | None = None
    is_paragraph_start: bool = False


@dataclass
class _LegalUnit:
    """Logical section, rule, or front-matter unit before size-bounded splitting."""

    unit_type: str  # front_matter | table_of_contents | notification | section | rule
    chapter: str | None = None
    chapter_title: str | None = None
    section_number: str | None = None
    section_title: str | None = None
    rule_number: str | None = None
    rule_title: str | None = None
    language: str = "en"
    headings: list[DetectedHeading] = field(default_factory=list)
    lines: list[_AnnotatedLine] = field(default_factory=list)


def _detect_line_language(text: str) -> str:
    """Classify a line as 'hi' (Devanagari), 'en', or 'mixed'."""
    hi_chars = len(DEVANAGARI_CHAR_RE.findall(text))
    ascii_letters = sum(1 for c in text if "a" <= c.lower() <= "z")
    if hi_chars > 0 and ascii_letters > 10:
        return "mixed"
    if hi_chars > ascii_letters:
        return "hi"
    return "en"


def _infer_doc_metadata(doc: DocumentExtraction) -> dict[str, Any]:
    """Infer document title, doc_type (act/rules/amendment_rules), and citation."""
    first_pages_text = "\n".join(p.cleaned_text for p in doc.pages[:2])
    lines = [ln.strip() for ln in first_pages_text.splitlines() if ln.strip()]

    title = None
    doc_type = "legal_document"

    # Prefer explicit English title from the first two pages
    for idx, line in enumerate(lines[:40]):
        if ACT_TITLE_RE.match(line) and "GAZETTE" not in line.upper():
            title = line.rstrip(".")
            doc_type = "act"
            break
        if "Consurner" in line or "Consumer Protection" in line:
            # Handle multi-line title blocks like "The\nConsumer Protection (E-Commerce)\nRules, 2020"
            window = " ".join(lines[idx : min(idx + 3, len(lines))])
            window = re.sub(r"\s+", " ", window)
            window = window.replace("Consurner", "Consumer").replace("E-Conunerce", "E-Commerce")
            m_rules = re.search(
                r"((?:The\s+)?Consumer\s+Protection\s*(?:\([^)]+\))?\s*(?:\(Amendment\))?\s*Rules,\s*\d{4})",
                window,
                re.IGNORECASE,
            )
            if m_rules:
                title = m_rules.group(1)
                doc_type = "amendment_rules" if "amendment" in title.lower() else "rules"
                break

    if title is None:
        for line in lines:
            low = line.lower()
            if RULES_TITLE_RE.match(line) and "short title" not in low and "may be called" not in low:
                title = re.sub(r"\d+$", "", line.rstrip(".")).strip()
                doc_type = "amendment_rules" if "amendment" in title.lower() else "rules"
                break

    if title is None:
        # Check inline "called the ... Rules, YYYY" or "called the ... Act, YYYY"
        m_called = re.search(
            r"may\s+be\s+called\s+the\s+([A-Z][A-Za-z0-9\s()\-]+?(?:Act|Rules),\s*\d{4})",
            first_pages_text,
        )
        if m_called:
            title = re.sub(r"\s+", " ", m_called.group(1)).strip()
            if "rules" in title.lower():
                doc_type = "amendment_rules" if "amendment" in title.lower() else "rules"
            elif "act" in title.lower():
                doc_type = "act"

    if title is None:
        fname_lower = doc.file_name.lower()
        title = doc.file_name.rsplit(".", 1)[0].replace("_", " ")
        if "amendment" in fname_lower:
            doc_type = "amendment_rules"
        elif "rule" in fname_lower:
            doc_type = "rules"
        elif "act" in fname_lower:
            doc_type = "act"

    if "amendment" in first_pages_text.lower() and doc_type == "rules":
        if "amendment) rules" in first_pages_text.lower():
            doc_type = "amendment_rules"

    citation = None
    m_act_no = re.search(r"NO\.\s*\d+\s+OF\s+\d{4}", first_pages_text, re.IGNORECASE)
    m_gsr = re.search(r"G\.S\.R\.?\s*\d+\s*\(E\)", first_pages_text, re.IGNORECASE)
    if m_act_no:
        citation = re.sub(r"\s+", " ", m_act_no.group(0)).upper()
    elif m_gsr:
        citation = re.sub(r"\s+", " ", m_gsr.group(0)).upper()

    return {
        "document_title": title,
        "doc_type": doc_type,
        "citation": citation,
    }


def _is_toc_page(page_lines: list[dict[str, Any]]) -> bool:
    """Detect Table of Contents pages so TOC entries are not misparsed as rules/sections."""
    texts = [ln["text"].strip() for ln in page_lines if ln["text"].strip()]
    has_contents = any(t.upper() == "CONTENTS" for t in texts[:12])
    dot_leaders = sum(1 for t in texts if TOC_LINE_RE.search(t))
    return has_contents or dot_leaders >= 3


def _match_margin_heading(
    margin_notes: list[dict[str, Any]],
    line_y: float,
    used_indices: set[int],
) -> str | None:
    """Find the closest unused section-heading margin note aligned near line_y."""
    best_idx: int | None = None
    best_dist = 26.0
    for idx, note in enumerate(margin_notes):
        if idx in used_indices:
            continue
        if note.get("kind") != "section_heading":
            continue
        dist = abs(float(note["y"]) - line_y)
        if dist <= best_dist:
            best_dist = dist
            best_idx = idx
    if best_idx is not None:
        used_indices.add(best_idx)
        return str(margin_notes[best_idx]["text"])
    return None


def _is_likely_footnote(
    num_str: str,
    rest: str,
    line_y: float,
    seen_provisions: set[str],
    doc_type: str,
) -> bool:
    """Filter out page footnotes like '1. Ministry of Consumer Affairs...' or '2. Subs. by G.S.R...'."""
    if FOOTNOTE_BODY_RE.match(rest):
        return True
    if doc_type in {"rules", "amendment_rules"} and num_str in seen_provisions and line_y >= 560.0:
        return True
    return False


def _format_ref(
    doc_type: str,
    section_num: str | None,
    rule_num: str | None,
    sub_num: str | None,
    clause_ref: str | None,
) -> str | None:
    """Build a canonical Indian legal reference string like 'Sec. 2(47)(i)' or 'Rule 4(2)(a)'."""
    base = None
    if section_num:
        base = f"Sec. {section_num}"
    elif rule_num:
        base = f"Rule {rule_num}"
    if not base:
        return None
    if sub_num:
        base += f"({sub_num})"
    if clause_ref:
        base += f"({clause_ref})"
    return base


def _segment_into_units(doc: DocumentExtraction, meta: dict[str, Any]) -> tuple[list[_LegalUnit], list[DetectedHeading]]:
    """Parse extracted pages into structured legal units while detecting headings."""
    doc_type: str = meta["doc_type"]
    doc_title: str = meta["document_title"]

    all_headings: list[DetectedHeading] = [
        DetectedHeading(
            heading_type="ACT" if doc_type == "act" else "RULES",
            identifier=meta.get("citation") or doc_title,
            title=doc_title,
            raw_text=doc_title,
            page_number=1,
        )
    ]

    units: list[_LegalUnit] = []
    current_unit = _LegalUnit(unit_type="front_matter", language="en")
    current_chapter: str | None = None
    current_chapter_title: str | None = None
    current_sub_num: str | None = None
    current_clause_ref: str | None = None
    para_counter = 0

    seen_en_provisions: set[str] = set()
    seen_hi_provisions: set[str] = set()
    last_en_prov_int: int = 0
    in_hindi_section = False

    def flush_unit() -> None:
        nonlocal current_unit
        if current_unit.lines:
            units.append(current_unit)

    for page in doc.pages:
        pno = page.page_number
        if page.error and not page.lines:
            continue

        if _is_toc_page(page.lines):
            flush_unit()
            toc_unit = _LegalUnit(
                unit_type="table_of_contents",
                chapter=current_chapter,
                chapter_title=current_chapter_title,
                language=_detect_line_language(page.cleaned_text),
            )
            for ln in page.lines:
                toc_unit.lines.append(
                    _AnnotatedLine(
                        page_number=pno,
                        text=ln["text"],
                        language=_detect_line_language(ln["text"]),
                    )
                )
            units.append(toc_unit)
            current_unit = _LegalUnit(
                unit_type="front_matter",
                chapter=current_chapter,
                chapter_title=current_chapter_title,
            )
            continue

        used_margin_indices: set[int] = set()
        page_lines = page.lines
        idx = 0
        while idx < len(page_lines):
            ln = page_lines[idx]
            text = ln["text"].strip()
            line_y = float(ln.get("y", 0.0))
            lang = _detect_line_language(text)

            if lang == "hi":
                in_hindi_section = True
            elif lang == "en" and (
                "MINISTRY OF" in text.upper()
                or "NOTIFICATION" in text.upper()
                or text.upper().startswith("G.S.R.")
                or text.upper().startswith("THE CONSUMER")
                or text.upper().startswith("CHAPTER ")
            ):
                in_hindi_section = False

            # 1. Detect CHAPTER heading
            m_chap = CHAPTER_RE.match(text)
            if m_chap:
                chap_num = f"CHAPTER {m_chap.group(1).upper()}"
                chap_title = m_chap.group(2).strip() if m_chap.group(2) else None
                if not chap_title and idx + 1 < len(page_lines):
                    next_txt = page_lines[idx + 1]["text"].strip()
                    if (
                        not NUMBERED_PROVISION_RE.match(next_txt)
                        and not CHAPTER_RE.match(next_txt)
                        and len(next_txt) <= 80
                        and next_txt[0].isalpha()
                    ):
                        chap_title = next_txt
                        idx += 1
                current_chapter = chap_num
                current_chapter_title = chap_title
                h = DetectedHeading(
                    heading_type="CHAPTER",
                    identifier=chap_num,
                    title=chap_title,
                    raw_text=f"{chap_num} - {chap_title}" if chap_title else chap_num,
                    page_number=pno,
                )
                all_headings.append(h)
                # Keep chapter heading attached to the next section/rule if current unit is already populated
                flush_unit()
                current_unit = _LegalUnit(
                    unit_type="front_matter",
                    chapter=current_chapter,
                    chapter_title=current_chapter_title,
                    language=lang,
                    headings=[h],
                    lines=[_AnnotatedLine(page_number=pno, text=h.raw_text, language=lang)],
                )
                idx += 1
                continue

            # 2. Detect explicit SECTION / RULE / SUB-RULE keywords
            m_exp_sec = EXPLICIT_SECTION_RE.match(text)
            m_exp_rule = EXPLICIT_RULE_RE.match(text)
            m_exp_sub = EXPLICIT_SUBRULE_RE.match(text)

            if m_exp_sec or m_exp_rule:
                is_rule = bool(m_exp_rule)
                m_obj = m_exp_rule or m_exp_sec
                assert m_obj is not None
                prov_num = m_obj.group(1)
                rest = m_obj.group(2).strip()
                flush_unit()
                current_sub_num = None
                current_clause_ref = None
                para_counter = 1
                h = DetectedHeading(
                    heading_type="RULE" if is_rule else "SECTION",
                    identifier=prov_num,
                    title=rest[:100] if rest else None,
                    raw_text=text,
                    page_number=pno,
                )
                all_headings.append(h)
                current_unit = _LegalUnit(
                    unit_type="rule" if is_rule else "section",
                    chapter=current_chapter,
                    chapter_title=current_chapter_title,
                    section_number=None if is_rule else prov_num,
                    rule_number=prov_num if is_rule else None,
                    language=lang,
                    headings=[h],
                    lines=[
                        _AnnotatedLine(
                            page_number=pno,
                            text=text,
                            language=lang,
                            paragraph_ref=f"para_{para_counter}",
                            is_paragraph_start=True,
                        )
                    ],
                )
                idx += 1
                continue

            if m_exp_sub:
                sub_id = f"({m_exp_sub.group(1)})"
                current_sub_num = m_exp_sub.group(1)
                current_clause_ref = None
                para_counter += 1
                h = DetectedHeading(
                    heading_type="SUB-RULE",
                    identifier=sub_id,
                    title=None,
                    raw_text=text,
                    page_number=pno,
                )
                all_headings.append(h)
                current_unit.headings.append(h)
                ref = _format_ref(
                    doc_type,
                    current_unit.section_number,
                    current_unit.rule_number,
                    current_sub_num,
                    None,
                )
                current_unit.lines.append(
                    _AnnotatedLine(
                        page_number=pno,
                        text=text,
                        language=lang,
                        sub_num=current_sub_num,
                        paragraph_ref=ref or f"para_{para_counter}",
                        is_paragraph_start=True,
                    )
                )
                idx += 1
                continue

            # 3. Detect Bare-Act / Gazette numbered Section or Rule (e.g., "2. In this Act..." or "4. Duties...")
            m_prov = NUMBERED_PROVISION_RE.match(text)
            if m_prov and not text.startswith(("“", '"', "'")):
                prov_num_str = m_prov.group(1)
                rest = (m_prov.group(2) or "").strip()
                if not rest and idx + 1 < len(page_lines):
                    next_line_txt = page_lines[idx + 1]["text"].strip()
                    if next_line_txt:
                        rest = next_line_txt
                        text = f"{text} {next_line_txt}"
                        lang = _detect_line_language(next_line_txt)
                        idx += 1

                if not rest:
                    idx += 1
                    continue

                prov_int_match = re.match(r"^\d+", prov_num_str)
                prov_int = int(prov_int_match.group(0)) if prov_int_match else 0

                seen_set = seen_hi_provisions if in_hindi_section else seen_en_provisions
                is_footnote = _is_likely_footnote(prov_num_str, rest, line_y, seen_set, doc_type)

                # Guard against false mid-sentence wrapped numbers (e.g., "2 of 1974." or "2019.")
                looks_sequential = True
                if not in_hindi_section and doc_type == "act" and last_en_prov_int > 0:
                    if prov_int <= last_en_prov_int or prov_int > last_en_prov_int + 3:
                        looks_sequential = False

                if not is_footnote and looks_sequential and prov_int > 0:
                    seen_set.add(prov_num_str)
                    if not in_hindi_section:
                        last_en_prov_int = prov_int

                    is_rule = doc_type in {"rules", "amendment_rules"}
                    prov_title: str | None = None
                    sub_num_inline: str | None = None

                    if is_rule:
                        title_candidate = rest
                        if "—" not in rest and ".-" not in rest and idx + 1 < len(page_lines):
                            nxt_txt = page_lines[idx + 1]["text"].strip()
                            if "—" in nxt_txt or ".-" in nxt_txt:
                                title_candidate = f"{rest} {nxt_txt}"
                        m_rtitle = RULE_INLINE_TITLE_RE.match(title_candidate)
                        if m_rtitle and ("—" in title_candidate[:160] or ".-" in title_candidate[:160]):
                            prov_title = m_rtitle.group(1).strip().rstrip(".")
                            if m_rtitle.group(2):
                                raw_sub = m_rtitle.group(2)
                                sub_num_inline = "1" if raw_sub == "l" else raw_sub
                    else:
                        prov_title = _match_margin_heading(page.margin_notes, line_y, used_margin_indices)

                    # Check inline sub-section/sub-rule like "1. (1) This Act..." or "4. Duties...—2[(1)"
                    if sub_num_inline is None:
                        m_inline_sub = re.search(r"(?:^|[.—\-–]\s*(?:\d+\[)?)\((\d{1,2}|l)\)\s+", rest)
                        if m_inline_sub:
                            raw_sub = m_inline_sub.group(1)
                            sub_num_inline = "1" if raw_sub == "l" else raw_sub

                    # Preserve pending chapter header if current_unit only held chapter title
                    pending_chapter_lines: list[_AnnotatedLine] = []
                    pending_headings: list[DetectedHeading] = []
                    if (
                        current_unit.unit_type == "front_matter"
                        and current_unit.headings
                        and current_unit.headings[0].heading_type == "CHAPTER"
                        and len(current_unit.lines) <= 2
                    ):
                        pending_chapter_lines = list(current_unit.lines)
                        pending_headings = list(current_unit.headings)
                    else:
                        flush_unit()

                    current_sub_num = sub_num_inline
                    current_clause_ref = None
                    para_counter = 1

                    h_type = "RULE" if is_rule else "SECTION"
                    h_main = DetectedHeading(
                        heading_type=h_type,
                        identifier=prov_num_str,
                        title=prov_title,
                        raw_text=text,
                        page_number=pno,
                    )
                    all_headings.append(h_main)
                    unit_headings = pending_headings + [h_main]

                    if sub_num_inline:
                        h_sub = DetectedHeading(
                            heading_type="SUB-RULE" if is_rule else "SUB-SECTION",
                            identifier=f"({sub_num_inline})",
                            title=None,
                            raw_text=text,
                            page_number=pno,
                        )
                        all_headings.append(h_sub)
                        unit_headings.append(h_sub)

                    ref = _format_ref(
                        doc_type,
                        None if is_rule else prov_num_str,
                        prov_num_str if is_rule else None,
                        current_sub_num,
                        None,
                    )
                    ann_lines = pending_chapter_lines + [
                        _AnnotatedLine(
                            page_number=pno,
                            text=text,
                            language=lang,
                            sub_num=current_sub_num,
                            paragraph_ref=ref or f"para_{para_counter}",
                            is_paragraph_start=True,
                        )
                    ]
                    current_unit = _LegalUnit(
                        unit_type="rule" if is_rule else "section",
                        chapter=current_chapter,
                        chapter_title=current_chapter_title,
                        section_number=None if is_rule else prov_num_str,
                        section_title=None if is_rule else prov_title,
                        rule_number=prov_num_str if is_rule else None,
                        rule_title=prov_title if is_rule else None,
                        language=lang,
                        headings=unit_headings,
                        lines=ann_lines,
                    )
                    idx += 1
                    continue

            # 4. Detect sub-section / sub-rule inside active Section or Rule
            m_sub = SUB_PROVISION_RE.match(text)
            if m_sub and current_unit.unit_type in {"section", "rule"}:
                raw_sub = m_sub.group(1)
                # Normalize OCR '(l)' -> '(1)' only when it is the very first sub-provision
                if raw_sub == "l":
                    sub_val = "1" if current_sub_num is None else "l"
                else:
                    sub_val = raw_sub

                if sub_val != "l":
                    current_sub_num = sub_val
                    current_clause_ref = None
                    para_counter += 1
                    h_type = "SUB-RULE" if current_unit.unit_type == "rule" else "SUB-SECTION"
                    h_sub = DetectedHeading(
                        heading_type=h_type,
                        identifier=f"({sub_val})",
                        title=None,
                        raw_text=text,
                        page_number=pno,
                    )
                    all_headings.append(h_sub)
                    current_unit.headings.append(h_sub)
                    ref = _format_ref(
                        doc_type,
                        current_unit.section_number,
                        current_unit.rule_number,
                        current_sub_num,
                        None,
                    )
                    current_unit.lines.append(
                        _AnnotatedLine(
                            page_number=pno,
                            text=text,
                            language=lang,
                            sub_num=current_sub_num,
                            paragraph_ref=ref or f"para_{para_counter}",
                            is_paragraph_start=True,
                        )
                    )
                    idx += 1
                    continue

            # 5. Detect clauses (a), (b), (i), (ii) or Proviso/Explanation
            m_clause = CLAUSE_RE.match(text)
            if m_clause and current_unit.unit_type in {"section", "rule"}:
                current_clause_ref = m_clause.group(1)
                para_counter += 1
                ref = _format_ref(
                    doc_type,
                    current_unit.section_number,
                    current_unit.rule_number,
                    current_sub_num,
                    current_clause_ref,
                )
                current_unit.lines.append(
                    _AnnotatedLine(
                        page_number=pno,
                        text=text,
                        language=lang,
                        sub_num=current_sub_num,
                        clause_ref=current_clause_ref,
                        paragraph_ref=ref or f"para_{para_counter}",
                        is_paragraph_start=True,
                    )
                )
                idx += 1
                continue

            if PROVISO_OR_EXPLANATION_RE.match(text):
                para_counter += 1
                label = "Explanation" if text.lower().startswith("explanation") else "Proviso"
                base_ref = _format_ref(
                    doc_type,
                    current_unit.section_number,
                    current_unit.rule_number,
                    current_sub_num,
                    current_clause_ref,
                )
                pref = f"{base_ref} [{label}]" if base_ref else f"para_{para_counter} [{label}]"
                current_unit.lines.append(
                    _AnnotatedLine(
                        page_number=pno,
                        text=text,
                        language=lang,
                        sub_num=current_sub_num,
                        clause_ref=current_clause_ref,
                        paragraph_ref=pref,
                        is_paragraph_start=True,
                    )
                )
                idx += 1
                continue

            # 6. Handle transition from Hindi to English NOTIFICATION in bilingual docs
            if (
                current_unit.language == "hi"
                and lang == "en"
                and "MINISTRY OF" in text.upper()
            ):
                flush_unit()
                current_unit = _LegalUnit(
                    unit_type="notification",
                    chapter=current_chapter,
                    chapter_title=current_chapter_title,
                    language="en",
                )

            # Default: append continuation line to current unit
            current_unit.lines.append(
                _AnnotatedLine(
                    page_number=pno,
                    text=text,
                    language=lang,
                    sub_num=current_sub_num,
                    clause_ref=current_clause_ref,
                    paragraph_ref=_format_ref(
                        doc_type,
                        current_unit.section_number,
                        current_unit.rule_number,
                        current_sub_num,
                        current_clause_ref,
                    ),
                    is_paragraph_start=False,
                )
            )
            idx += 1

    flush_unit()
    return units, all_headings


def _build_heading_hierarchy(
    doc_title: str,
    unit: _LegalUnit,
    sub_nums: list[str],
) -> list[str]:
    """Construct a readable breadcrumb hierarchy for a legal chunk."""
    hierarchy = [f"DOCUMENT: {doc_title}"]
    if unit.chapter:
        chap_label = f"{unit.chapter} - {unit.chapter_title}" if unit.chapter_title else unit.chapter
        hierarchy.append(f"CHAPTER: {chap_label}")
    if unit.section_number:
        sec_label = (
            f"Section {unit.section_number} - {unit.section_title}"
            if unit.section_title
            else f"Section {unit.section_number}"
        )
        hierarchy.append(f"SECTION: {sec_label}")
    if unit.rule_number:
        rule_label = (
            f"Rule {unit.rule_number} - {unit.rule_title}"
            if unit.rule_title
            else f"Rule {unit.rule_number}"
        )
        hierarchy.append(f"RULE: {rule_label}")
    if sub_nums:
        prefix = "SUB-RULE" if unit.rule_number else "SUB-SECTION"
        hierarchy.append(f"{prefix}: {', '.join(sub_nums)}")
    return hierarchy


def _split_lines_preserving_boundaries(
    lines: list[_AnnotatedLine],
    max_chunk_chars: int,
) -> list[list[_AnnotatedLine]]:
    """Split oversized unit lines at sub-provision, then clause/paragraph, then line boundaries."""
    total_len = sum(len(l.text) + 1 for l in lines)
    if total_len <= max_chunk_chars:
        return [lines]

    # Step 1: Group by sub_num so sub-sections / sub-rules stay intact whenever possible
    sub_groups: list[list[_AnnotatedLine]] = []
    cur_group: list[_AnnotatedLine] = []
    cur_sub = lines[0].sub_num if lines else None
    for ln in lines:
        if ln.sub_num != cur_sub and cur_group:
            sub_groups.append(cur_group)
            cur_group = [ln]
            cur_sub = ln.sub_num
        else:
            cur_group.append(ln)
    if cur_group:
        sub_groups.append(cur_group)

    # Pack small sub-groups together up to max_chunk_chars, or split large sub-groups at paragraph boundaries
    chunks: list[list[_AnnotatedLine]] = []
    bucket: list[_AnnotatedLine] = []
    bucket_len = 0

    def flush_bucket() -> None:
        nonlocal bucket, bucket_len
        if bucket:
            chunks.append(bucket)
            bucket = []
            bucket_len = 0

    for grp in sub_groups:
        grp_len = sum(len(l.text) + 1 for l in grp)
        if grp_len <= max_chunk_chars:
            if bucket_len + grp_len > max_chunk_chars and bucket:
                flush_bucket()
            bucket.extend(grp)
            bucket_len += grp_len
        else:
            flush_bucket()
            # Split oversized sub-group at paragraph/clause boundaries
            para_groups: list[list[_AnnotatedLine]] = []
            p_cur: list[_AnnotatedLine] = []
            for ln in grp:
                if ln.is_paragraph_start and p_cur:
                    para_groups.append(p_cur)
                    p_cur = [ln]
                else:
                    p_cur.append(ln)
            if p_cur:
                para_groups.append(p_cur)

            p_bucket: list[_AnnotatedLine] = []
            p_len = 0
            for pgrp in para_groups:
                plen = sum(len(l.text) + 1 for l in pgrp)
                if plen <= max_chunk_chars:
                    if p_len + plen > max_chunk_chars and p_bucket:
                        chunks.append(p_bucket)
                        p_bucket = []
                        p_len = 0
                    p_bucket.extend(pgrp)
                    p_len += plen
                else:
                    if p_bucket:
                        chunks.append(p_bucket)
                        p_bucket = []
                        p_len = 0
                    # Final fallback: pack line by line without breaking words
                    l_bucket: list[_AnnotatedLine] = []
                    l_len = 0
                    for ln in pgrp:
                        llen = len(ln.text) + 1
                        if l_len + llen > max_chunk_chars and l_bucket:
                            chunks.append(l_bucket)
                            l_bucket = []
                            l_len = 0
                        l_bucket.append(ln)
                        l_len += llen
                    if l_bucket:
                        chunks.append(l_bucket)
            if p_bucket:
                chunks.append(p_bucket)

    flush_bucket()
    return chunks


def _emit_chunk(
    doc: DocumentExtraction,
    meta: dict[str, Any],
    unit: _LegalUnit,
    chunk_lines: list[_AnnotatedLine],
    chunk_index: int,
) -> LegalChunk:
    """Create a LegalChunk object with full provenance and heading hierarchy."""
    doc_title = meta["document_title"]
    doc_type = meta["doc_type"]
    text = "\n".join(l.text for l in chunk_lines).strip()

    source_pages = sorted({l.page_number for l in chunk_lines})
    page_spans: list[dict[str, Any]] = []
    for pno in source_pages:
        p_lines = [l.text for l in chunk_lines if l.page_number == pno]
        page_spans.append(
            {
                "page_number": pno,
                "line_count": len(p_lines),
                "first_line": p_lines[0][:120] if p_lines else "",
            }
        )

    sub_nums: list[str] = []
    for l in chunk_lines:
        if l.sub_num:
            formatted = f"({l.sub_num})"
            if formatted not in sub_nums:
                sub_nums.append(formatted)

    para_refs: list[str] = []
    for l in chunk_lines:
        if l.paragraph_ref and l.paragraph_ref not in para_refs:
            para_refs.append(l.paragraph_ref)

    langs = {l.language for l in chunk_lines}
    if len(langs) == 1:
        chunk_lang = next(iter(langs))
    else:
        chunk_lang = "mixed"

    hierarchy = _build_heading_hierarchy(doc_title, unit, sub_nums)
    context_prefix = " | ".join(hierarchy)
    contextualized_text = f"[{context_prefix}]\n{text}"

    # Filter unit headings to those relevant to pages or sub-provisions in this chunk
    chunk_headings = [
        h.to_dict()
        for h in unit.headings
        if h.heading_type in {"ACT", "RULES", "CHAPTER", "SECTION", "RULE"}
        or h.identifier in sub_nums
    ]

    return LegalChunk(
        chunk_id=f"{doc.doc_id}_chunk_{chunk_index:04d}",
        chunk_index=chunk_index,
        document_name=doc.file_name,
        document_title=doc_title,
        doc_type=doc_type,
        unit_type=unit.unit_type,
        chapter=unit.chapter,
        chapter_title=unit.chapter_title,
        section_number=unit.section_number,
        section_title=unit.section_title,
        rule_number=unit.rule_number,
        rule_title=unit.rule_title,
        sub_section_numbers=sub_nums if unit.section_number else [],
        sub_rule_numbers=sub_nums if unit.rule_number else [],
        paragraph_references=para_refs,
        detected_headings=chunk_headings,
        heading_hierarchy=hierarchy,
        source_pages=source_pages,
        page_start=source_pages[0],
        page_end=source_pages[-1],
        page_spans=page_spans,
        extraction_method=doc.extraction_method,
        language=chunk_lang,
        char_count=len(text),
        text=text,
        contextualized_text=contextualized_text,
    )


def chunk_legal_document(
    doc: DocumentExtraction,
    max_chunk_chars: int = 1800,
) -> dict[str, Any]:
    """Detect legal structure and split a DocumentExtraction into context-preserving chunks."""
    meta = _infer_doc_metadata(doc)
    units, all_headings = _segment_into_units(doc, meta)

    chunks: list[LegalChunk] = []
    chunk_idx = 0
    for unit in units:
        if not unit.lines:
            continue
        split_groups = _split_lines_preserving_boundaries(unit.lines, max_chunk_chars=max_chunk_chars)
        for grp in split_groups:
            chunks.append(_emit_chunk(doc, meta, unit, grp, chunk_idx))
            chunk_idx += 1

    heading_counts: dict[str, int] = {}
    for h in all_headings:
        heading_counts[h.heading_type] = heading_counts.get(h.heading_type, 0) + 1

    return {
        "document_title": meta["document_title"],
        "doc_type": meta["doc_type"],
        "citation": meta["citation"],
        "heading_counts": heading_counts,
        "detected_headings": [h.to_dict() for h in all_headings],
        "total_chunks": len(chunks),
        "chunks": [c.to_dict() for c in chunks],
    }
