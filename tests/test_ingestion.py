"""Tests for SATYA automated legal document ingestion pipeline."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pymupdf
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ingest  # noqa: E402


def _make_text_pdf(path: Path, pages_text: list[str], title: str | None = None) -> None:
    """Create a text-based PDF using PyMuPDF."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), text, fontsize=11)
    if title:
        doc.set_metadata({"title": title})
    doc.save(str(path))
    doc.close()


def test_consumer_law_corpus_ingestion(tmp_path: Path) -> None:
    """Verify full ingestion, OCR, headings, chunks, and page provenance on consumer_law/."""
    input_dir = PROJECT_ROOT / "documents" / "consumer_law"
    out_dir = tmp_path / "extracted_documents"
    meta_file = tmp_path / "metadata.json"

    report = ingest.run_ingestion(
        input_dir=input_dir,
        output_dir=out_dir,
        metadata_file=meta_file,
        max_chunk_chars=1800,
    )

    assert meta_file.exists()
    summary = report["summary"]
    assert summary["total_files_found"] == 4
    assert summary["processed_successfully"] == 4
    assert summary["partial_failures"] == 0
    assert summary["duplicates_detected"] == 0
    assert summary["failed_extractions"] == 0
    assert summary["ocr_pages_processed"] == 11

    by_name = {d["file_name"]: d for d in report["documents"]}

    # 1. Consumer Protection Act, 2019 (text-based)
    act_meta = by_name["Consumer_Protection_Act_2019.pdf"]
    assert act_meta["doc_type"] == "act"
    assert act_meta["extraction_method"] == "pymupdf_text"
    assert act_meta["total_pages"] == 40
    assert act_meta["heading_counts"]["CHAPTER"] == 8
    assert act_meta["heading_counts"]["SECTION"] == 107

    act_doc = json.loads(Path(act_meta["output_file"]).read_text(encoding="utf-8"))
    sec_ids = [
        h["identifier"]
        for h in act_doc["detected_headings"]
        if h["heading_type"] == "SECTION"
    ]
    assert sec_ids == [str(i) for i in range(1, 108)]

    sec2_chunks = [c for c in act_doc["chunks"] if c["section_number"] == "2"]
    assert len(sec2_chunks) > 1
    assert all(c["section_title"] == "Definitions." for c in sec2_chunks)
    assert all(c["chapter"] == "CHAPTER I" for c in sec2_chunks)

    # 2. E-Commerce Rules, 2020 (scanned -> OCR)
    ecom_meta = by_name["Consumer_Protection_ECommerce_Rules_2020.pdf"]
    assert ecom_meta["doc_type"] == "rules"
    assert ecom_meta["extraction_method"] == "ocr"
    assert ecom_meta["ocr_pages"] == list(range(1, 9))
    assert ecom_meta["heading_counts"]["RULE"] == 8
    assert "SECTION" not in ecom_meta["heading_counts"]

    ecom_doc = json.loads(Path(ecom_meta["output_file"]).read_text(encoding="utf-8"))
    rule4_chunks = [c for c in ecom_doc["chunks"] if c["rule_number"] == "4"]
    assert rule4_chunks
    assert "e-commerce entities" in (rule4_chunks[0]["rule_title"] or "").lower()

    # 3. General Rules, 2020 (scanned -> OCR)
    gen_meta = by_name["Consumer_Protection_General_Rules_2020.pdf"]
    assert gen_meta["doc_type"] == "rules"
    assert gen_meta["extraction_method"] == "ocr"
    assert gen_meta["ocr_pages"] == [1, 2, 3]
    assert gen_meta["heading_counts"]["RULE"] == 5

    gen_doc = json.loads(Path(gen_meta["output_file"]).read_text(encoding="utf-8"))
    rule5_chunks = [c for c in gen_doc["chunks"] if c["rule_number"] == "5"]
    assert rule5_chunks
    assert "invoice" in (rule5_chunks[0]["rule_title"] or "").lower()

    # 4. E-Commerce Amendment Rules, 2021 (bilingual text-based)
    amend_meta = by_name["Consumer_Protection_ECommerce_Amendment_Rules_2021.pdf"]
    assert amend_meta["doc_type"] == "amendment_rules"
    assert amend_meta["extraction_method"] == "pymupdf_text"
    assert "Consumer Protection (E-Commerce) (Amendment) Rules, 2021" in amend_meta["document_title"]

    amend_doc = json.loads(Path(amend_meta["output_file"]).read_text(encoding="utf-8"))
    en_rule_nums = {
        c["rule_number"]
        for c in amend_doc["chunks"]
        if c["rule_number"] and c["language"] == "en"
    }
    assert {"1", "2"}.issubset(en_rule_nums)

    # Global provenance invariants on every chunk
    for doc_entry in report["documents"]:
        doc_json = json.loads(Path(doc_entry["output_file"]).read_text(encoding="utf-8"))
        max_p = doc_json["total_pages"]
        for chunk in doc_json["chunks"]:
            assert chunk["document_name"] == doc_entry["file_name"]
            assert chunk["text"].strip()
            assert chunk["contextualized_text"].strip()
            assert chunk["source_pages"]
            assert chunk["source_pages"] == sorted(set(chunk["source_pages"]))
            assert 1 <= chunk["page_start"] <= chunk["page_end"] <= max_p
            assert chunk["heading_hierarchy"]


def test_duplicate_detection_exact_and_content(tmp_path: Path) -> None:
    """Verify exact-byte and content-based duplicate document detection."""
    in_dir = tmp_path / "docs"
    out_dir = tmp_path / "out"
    meta_file = tmp_path / "metadata.json"
    in_dir.mkdir()

    orig = in_dir / "act_a_original.pdf"
    _make_text_pdf(
        orig,
        [
            "THE SAMPLE CONSUMER ACT, 2025\nCHAPTER I\nPRELIMINARY\n"
            "1. (1) This Act may be called the Sample Consumer Act, 2025.\n"
            "(2) It extends to the whole of India."
        ],
        title="Original Metadata",
    )

    exact_dup = in_dir / "act_b_exact_copy.pdf"
    shutil.copyfile(orig, exact_dup)

    # Re-save with altered metadata so file bytes/hash differ while extracted text is identical
    content_dup = in_dir / "act_c_resaved.pdf"
    doc = pymupdf.open(str(orig))
    doc.set_metadata({"title": "Modified Metadata Copy", "author": "Test"})
    doc.save(str(content_dup))
    doc.close()

    report = ingest.run_ingestion(in_dir, out_dir, meta_file)
    assert report["summary"]["total_files_found"] == 3
    assert report["summary"]["processed_successfully"] == 1
    assert report["summary"]["duplicates_detected"] == 2

    dup_types = {d["file_name"]: d["duplicate_type"] for d in report["duplicates"]}
    assert dup_types["act_b_exact_copy.pdf"] == "exact_file"
    assert dup_types["act_c_resaved.pdf"] == "content_duplicate"


def test_failure_reporting_never_silent(tmp_path: Path) -> None:
    """Verify corrupt, empty, and encrypted PDFs are explicitly reported in failures and strict exit code."""
    in_dir = tmp_path / "docs"
    out_dir = tmp_path / "out"
    meta_file = tmp_path / "metadata.json"
    in_dir.mkdir()

    _make_text_pdf(
        in_dir / "valid_rules.pdf",
        ["The Sample Rules, 2025\n1. Short title.—(1) These rules may be called the Sample Rules, 2025."],
    )
    (in_dir / "corrupt.pdf").write_bytes(b"not a valid pdf header at all")
    (in_dir / "empty.pdf").write_bytes(b"")

    enc_doc = pymupdf.open()
    p = enc_doc.new_page()
    p.insert_text((72, 72), "Secret legal text")
    enc_doc.save(
        str(in_dir / "encrypted.pdf"),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner123",
        user_pw="user123",
    )
    enc_doc.close()

    exit_code = ingest.main(
        [
            "--input-dir",
            str(in_dir),
            "--output-dir",
            str(out_dir),
            "--metadata-file",
            str(meta_file),
            "--strict",
        ]
    )
    assert exit_code == 1

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["summary"]["processed_successfully"] == 1
    assert meta["summary"]["failed_extractions"] == 3

    failures_by_name = {f["file_name"]: f for f in meta["failures"]}
    assert set(failures_by_name.keys()) == {"corrupt.pdf", "empty.pdf", "encrypted.pdf"}
    assert failures_by_name["empty.pdf"]["error_type"] == "EmptyFileError"
    assert failures_by_name["encrypted.pdf"]["error_type"] == "EncryptedPDFError"
    assert failures_by_name["corrupt.pdf"]["error_message"]


def test_scanned_pdf_triggers_ocr(tmp_path: Path) -> None:
    """Verify an image-only PDF is automatically flagged as scanned and extracted via OCR."""
    in_dir = tmp_path / "docs"
    out_dir = tmp_path / "out"
    meta_file = tmp_path / "metadata.json"
    in_dir.mkdir()

    # Render a text page to PNG, then wrap the PNG inside a new image-only PDF
    tmp_doc = pymupdf.open()
    tp = tmp_doc.new_page(width=595, height=842)
    tp.insert_text(
        (72, 100),
        "The Test Consumer Rules, 2024\n\n"
        "1. Short title.—(1) These rules may be called the Test Consumer Rules, 2024.\n"
        "2. Definitions.—(1) In these rules, Act means the Consumer Protection Act, 2019.",
        fontsize=14,
    )
    png_bytes = tp.get_pixmap(dpi=200).tobytes("png")
    tmp_doc.close()

    scan_doc = pymupdf.open()
    sp = scan_doc.new_page(width=595, height=842)
    sp.insert_image(sp.rect, stream=png_bytes)
    scan_doc.save(str(in_dir / "scanned_rules.pdf"))
    scan_doc.close()

    report = ingest.run_ingestion(in_dir, out_dir, meta_file)
    assert report["summary"]["processed_successfully"] == 1
    assert report["summary"]["ocr_pages_processed"] == 1
    doc_meta = report["documents"][0]
    assert doc_meta["extraction_method"] == "ocr"
    assert doc_meta["scanned_pages"] == [1]

    doc_json = json.loads(Path(doc_meta["output_file"]).read_text(encoding="utf-8"))
    full_text = "\n".join(p["cleaned_text"] for p in doc_json["pages"])
    assert "Test Consumer Rules" in full_text
    assert "Consumer Protection Act" in full_text
