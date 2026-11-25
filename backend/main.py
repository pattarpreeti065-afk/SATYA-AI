
import os
import time
import logging
from uuid import uuid4
from typing import Literal
from fastapi.responses import FileResponse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path
from pdf_generator import generate_complaint_pdf
from answer_generator import (
    generate_legal_answer,
    generate_case_guide_answer
)


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("SATYA")


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="SATYA Legal Assistant API",
    description="AI legal assistant, case filing guide and complaint PDF generator",
    version="2.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)


class GuideMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class GuideRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    history: list[GuideMessage] = Field(
        default_factory=list,
        max_length=8
    )


class ComplaintPDFRequest(BaseModel):
    complaint_text: str = Field(
        min_length=1,
        max_length=20000
    )

# --------------------------------------------------
# LEGAL DOCUMENT LIBRARY
# --------------------------------------------------

LEGAL_DOCUMENTS_DIR = (
    Path(__file__).resolve().parent
    / "documents"
    / "consumer_law"
)

LEGAL_DOCUMENTS = {
    "act-2019": "Consumer_Protection_Act_2019.pdf",
    "general-rules-2020": "Consumer_Protection_General_Rules_2020.pdf",
    "ecommerce-rules-2020": "Consumer_Protection_ECommerce_Rules_2020.pdf",
    "ecommerce-amendment-2021": "Consumer_Protection_ECommerce_Amendment_Rules_2021.pdf",
}


@app.get("/documents/{document_id}")
def get_legal_document(document_id: str):

    filename = LEGAL_DOCUMENTS.get(document_id)

    if not filename:
        raise HTTPException(
            status_code=404,
            detail="Legal document not found."
        )

    file_path = LEGAL_DOCUMENTS_DIR / filename

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="PDF file is missing."
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename
    )
# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Welcome to SATYA Legal Assistant API",
        "status": "running",
        "chatbots": [
            "Legal Assistant Chat",
            "AI Case Filing Guide"
        ],
        "features": [
            "Complaint PDF Generator"
        ]
    }


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "SATYA"
    }


# --------------------------------------------------
# ERROR HANDLING
# --------------------------------------------------

def handle_ai_error(error):
    import traceback

    logger.error("SATYA BACKEND ERROR")
    traceback.print_exc()

    error_message = str(error).upper()

    if "503" in error_message or "UNAVAILABLE" in error_message:
        raise HTTPException(
            status_code=503,
            detail="SATYA AI is temporarily busy. Please try again later."
        )

    if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message:
        raise HTTPException(
            status_code=429,
            detail="AI request limit reached. Please try again later."
        )

    raise HTTPException(
        status_code=500,
        detail=f"Unable to process your request: {str(error)[:500]}"
    )


# --------------------------------------------------
# LEGAL ASSISTANT
# --------------------------------------------------

@app.post("/ask")
def ask_question(request: QuestionRequest):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter a legal question."
        )

    start_time = time.perf_counter()

    logger.info("Legal Assistant request received")

    try:
        answer = generate_legal_answer(question)

        elapsed = time.perf_counter() - start_time

        logger.info(
            "Legal Assistant completed in %.2f seconds",
            elapsed
        )

        return {
            "success": True,
            "chatbot": "legal_assistant",
            "question": question,
            "answer": answer,
            "processing_time_seconds": round(elapsed, 2)
        }

    except Exception as error:
        handle_ai_error(error)


# --------------------------------------------------
# AI CASE FILING GUIDE
# --------------------------------------------------

@app.post("/guide")
def case_filing_guide(request: GuideRequest):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please describe your problem."
        )

    start_time = time.perf_counter()

    logger.info("Case Filing Guide request received")

    try:
        history = [
            message.model_dump()
            for message in request.history
        ]

        logger.info(
            "Conversation history messages: %d",
            len(history)
        )

        answer = generate_case_guide_answer(
            question,
            conversation_history=history
        )

        elapsed = time.perf_counter() - start_time

        logger.info(
            "Case Filing Guide completed in %.2f seconds",
            elapsed
        )

        return {
            "success": True,
            "chatbot": "case_filing_guide",
            "question": question,
            "answer": answer,
            "processing_time_seconds": round(elapsed, 2)
        }

    except Exception as error:
        handle_ai_error(error)


# --------------------------------------------------
# COMPLAINT PDF GENERATOR
# --------------------------------------------------

@app.post("/generate-pdf")
def generate_pdf(request: ComplaintPDFRequest):

    complaint_text = request.complaint_text.strip()

    if not complaint_text:
        raise HTTPException(
            status_code=400,
            detail="Complaint text cannot be empty."
        )

    try:
        base_folder = os.path.dirname(
            os.path.abspath(__file__)
        )

        output_folder = os.path.join(
            base_folder,
            "generated_pdfs"
        )

        os.makedirs(
            output_folder,
            exist_ok=True
        )

        filename = f"SATYA_Complaint_{uuid4().hex[:8]}.pdf"

        output_path = os.path.join(
            output_folder,
            filename
        )

        generate_complaint_pdf(
            complaint_text,
            output_path
        )

        if not os.path.exists(output_path):
            raise FileNotFoundError(
                "PDF file was not created."
            )

        logger.info("Complaint PDF generated: %s", filename)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=filename
        )

    except Exception as error:
        import traceback

        logger.error("SATYA PDF GENERATION ERROR")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {str(error)}"
        )
