"""Automated legal document ingestion pipeline for SATYA."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal_chunker import chunk_legal_document
from pdf_processor import OcrRunner, discover_pdfs, process_pdf_file

logger = logging.getLogger("satya.ingest")


def run_ingestion(
    input_dir: Path,
    output_dir: Path,
    metadata_file: Path,
    max_chunk_chars: int = 1800,
    ocr_engine: str = "auto",
    min_text_chars: int = 40,
) -> dict[str, Any]:
    """Run the end-to-end PDF extraction, OCR fallback, deduplication, and legal chunking pipeline."""
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)

    pdf_files = discover_pdfs(input_dir)
    if not pdf_files:
        logger.warning("No PDF files found inside %s", input_dir)

    ocr_runner = OcrRunner(preferred_engine=ocr_engine)
    seen_file_hashes: dict[str, str] = {}
    seen_content_hashes: dict[str, str] = {}
    used_output_stems: set[str] = set()

    documents_summary: list[dict[str, Any]] = []
    duplicates_report: list[dict[str, Any]] = []
    failures_report: list[dict[str, Any]] = []

    total_pages = 0
    total_scanned_pages = 0
    total_ocr_pages = 0
    total_chunks = 0
    processed_successfully = 0
    partial_failures = 0

    for pdf_path in pdf_files:
        logger.info("Ingesting: %s", pdf_path)
        extraction = process_pdf_file(
            pdf_path=pdf_path,
            seen_file_hashes=seen_file_hashes,
            seen_content_hashes=seen_content_hashes,
            ocr_runner=ocr_runner,
            min_text_chars_per_page=min_text_chars,
        )

        if extraction.status == "duplicate":
            dup_entry = {
                "file_name": extraction.file_name,
                "file_path": str(pdf_path),
                "duplicate_of": extraction.duplicate_of,
                "duplicate_type": extraction.duplicate_type,
                "file_hash": extraction.file_hash,
                "content_hash": extraction.content_hash,
                "warnings": extraction.warnings,
            }
            duplicates_report.append(dup_entry)
            logger.warning(
                "DUPLICATE skipped: %s (%s of %s)",
                extraction.file_name,
                extraction.duplicate_type,
                extraction.duplicate_of,
            )
            continue

        if extraction.status == "failed":
            fail_entry = {
                "file_name": extraction.file_name,
                "file_path": str(pdf_path),
                "file_hash": extraction.file_hash,
                "error_type": extraction.error_type,
                "error_message": extraction.error_message,
                "failed_pages": extraction.failed_pages,
                "warnings": extraction.warnings,
            }
            failures_report.append(fail_entry)
            logger.error(
                "EXTRACTION FAILED: %s [%s]: %s",
                extraction.file_name,
                extraction.error_type,
                extraction.error_message,
            )
            continue

        try:
            chunked = chunk_legal_document(extraction, max_chunk_chars=max_chunk_chars)
        except Exception as exc:
            logger.exception("Chunking failed for %s: %s", extraction.file_name, exc)
            failures_report.append(
                {
                    "file_name": extraction.file_name,
                    "file_path": str(pdf_path),
                    "file_hash": extraction.file_hash,
                    "error_type": f"ChunkingError:{type(exc).__name__}",
                    "error_message": str(exc),
                    "failed_pages": extraction.failed_pages,
                    "warnings": extraction.warnings,
                }
            )
            continue

        stem = extraction.doc_id
        if stem in used_output_stems:
            stem = f"{stem}_{extraction.file_hash[:8]}"
        used_output_stems.add(stem)
        doc_output_path = output_dir / f"{stem}.json"

        doc_payload = {
            "doc_id": extraction.doc_id,
            "document_name": extraction.file_name,
            "source_path": str(pdf_path),
            "document_title": chunked["document_title"],
            "doc_type": chunked["doc_type"],
            "citation": chunked["citation"],
            "file_size_bytes": extraction.file_size_bytes,
            "file_hash": extraction.file_hash,
            "content_hash": extraction.content_hash,
            "status": extraction.status,
            "extraction_method": extraction.extraction_method,
            "total_pages": extraction.total_pages,
            "scanned_pages": extraction.scanned_pages,
            "ocr_pages": extraction.ocr_pages,
            "failed_pages": extraction.failed_pages,
            "pdf_metadata": extraction.pdf_metadata,
            "heading_counts": chunked["heading_counts"],
            "detected_headings": chunked["detected_headings"],
            "total_chunks": chunked["total_chunks"],
            "warnings": extraction.warnings,
            "pages": [
                {
                    "page_number": p.page_number,
                    "extraction_method": p.extraction_method,
                    "is_scanned": p.is_scanned,
                    "image_count": p.image_count,
                    "text_char_count": p.text_char_count,
                    "margin_notes": p.margin_notes,
                    "cleaned_text": p.cleaned_text,
                    "error": p.error,
                    "warnings": p.warnings,
                }
                for p in extraction.pages
            ],
            "chunks": chunked["chunks"],
        }

        doc_output_path.write_text(
            json.dumps(doc_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        total_pages += extraction.total_pages
        total_scanned_pages += len(extraction.scanned_pages)
        total_ocr_pages += len(extraction.ocr_pages)
        total_chunks += chunked["total_chunks"]

        if extraction.status == "partial_failure":
            partial_failures += 1
            failures_report.append(
                {
                    "file_name": extraction.file_name,
                    "file_path": str(pdf_path),
                    "file_hash": extraction.file_hash,
                    "error_type": extraction.error_type,
                    "error_message": extraction.error_message,
                    "failed_pages": extraction.failed_pages,
                    "warnings": extraction.warnings,
                }
            )
            logger.warning(
                "PARTIAL EXTRACTION: %s failed on pages %s",
                extraction.file_name,
                extraction.failed_pages,
            )
        else:
            processed_successfully += 1

        documents_summary.append(
            {
                "doc_id": extraction.doc_id,
                "file_name": extraction.file_name,
                "file_path": str(pdf_path),
                "output_file": str(doc_output_path),
                "document_title": chunked["document_title"],
                "doc_type": chunked["doc_type"],
                "citation": chunked["citation"],
                "file_size_bytes": extraction.file_size_bytes,
                "file_hash": extraction.file_hash,
                "content_hash": extraction.content_hash,
                "status": extraction.status,
                "extraction_method": extraction.extraction_method,
                "total_pages": extraction.total_pages,
                "scanned_pages": extraction.scanned_pages,
                "ocr_pages": extraction.ocr_pages,
                "failed_pages": extraction.failed_pages,
                "heading_counts": chunked["heading_counts"],
                "total_chunks": chunked["total_chunks"],
                "warnings": extraction.warnings,
            }
        )

    metadata_payload = {
        "system": "SATYA Legal Document Ingestion System",
        "pipeline_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "max_chunk_chars": max_chunk_chars,
            "ocr_engine": ocr_engine,
            "min_text_chars": min_text_chars,
        },
        "summary": {
            "total_files_found": len(pdf_files),
            "processed_successfully": processed_successfully,
            "partial_failures": partial_failures,
            "duplicates_detected": len(duplicates_report),
            "failed_extractions": sum(
                1 for f in failures_report if f.get("error_type") != "PartialPageExtractionError"
            ),
            "total_pages": total_pages,
            "scanned_pages_detected": total_scanned_pages,
            "ocr_pages_processed": total_ocr_pages,
            "total_chunks": total_chunks,
        },
        "documents": documents_summary,
        "duplicates": duplicates_report,
        "failures": failures_report,
    }

    metadata_file.write_text(
        json.dumps(metadata_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return metadata_payload


def _print_report(report: dict[str, Any]) -> None:
    """Print a concise human-readable summary of the ingestion run."""
    s = report["summary"]
    print("\n=== SATYA Ingestion Summary ===")
    print(f"PDFs discovered      : {s['total_files_found']}")
    print(f"Processed cleanly    : {s['processed_successfully']}")
    print(f"Partial failures     : {s['partial_failures']}")
    print(f"Duplicates detected  : {s['duplicates_detected']}")
    print(f"Failed extractions   : {s['failed_extractions']}")
    print(f"Total pages / OCR    : {s['total_pages']} / {s['ocr_pages_processed']}")
    print(f"Total legal chunks   : {s['total_chunks']}")

    if report["documents"]:
        print("\n--- Extracted Documents ---")
        for d in report["documents"]:
            print(
                f"  - {d['file_name']} | type={d['doc_type']} | pages={d['total_pages']} "
                f"| method={d['extraction_method']} | chunks={d['total_chunks']} "
                f"| headings={d['heading_counts']}"
            )

    if report["duplicates"]:
        print("\n--- Duplicates Detected ---")
        for dup in report["duplicates"]:
            print(
                f"  - {dup['file_name']} ({dup['duplicate_type']} of {dup['duplicate_of']})"
            )

    if report["failures"]:
        print("\n--- Extraction Failures ---", file=sys.stderr)
        for fail in report["failures"]:
            print(
                f"  - {fail['file_name']} [{fail['error_type']}]: {fail['error_message']}",
                file=sys.stderr,
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SATYA Automated Legal Document Ingestion Pipeline"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("documents/consumer_law"),
        help="Directory containing input legal PDFs (default: documents/consumer_law)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("extracted_documents"),
        help="Directory to store extracted JSON files (default: extracted_documents)",
    )
    parser.add_argument(
        "--metadata-file",
        type=Path,
        default=Path("metadata.json"),
        help="Path for corpus-level metadata JSON (default: metadata.json)",
    )
    parser.add_argument(
        "--max-chunk-chars",
        type=int,
        default=1800,
        help="Maximum characters per legal chunk before splitting at sub-section/clause boundaries",
    )
    parser.add_argument(
        "--ocr-engine",
        choices=["auto", "windows_ocr", "tesseract", "rapidocr"],
        default="auto",
        help="OCR engine to use for scanned PDFs (default: auto)",
    )
    parser.add_argument(
        "--min-text-chars",
        type=int,
        default=40,
        help="Minimum alphanumeric characters per page before flagging as scanned (default: 40)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero code if any extraction failure or partial failure occurs",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        report = run_ingestion(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            metadata_file=args.metadata_file,
            max_chunk_chars=args.max_chunk_chars,
            ocr_engine=args.ocr_engine,
            min_text_chars=args.min_text_chars,
        )
    except Exception as exc:
        logger.error("Fatal ingestion error: %s", exc)
        return 2

    _print_report(report)

    if args.strict and report["failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
