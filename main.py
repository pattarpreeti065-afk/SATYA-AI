
import logging
import re
from pathlib import Path
from uuid import uuid4
from typing import Literal

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from answer_generator import (
    generate_legal_answer,
    generate_case_guide_answer
)

from pdf_generator import generate_complaint_pdf


# =========================================================
# CONFIGURATION
# =========================================================

APP_VERSION = "4.0.0"

BASE_DIR = Path(__file__).resolve().parent

DOCUMENTS_DIR = BASE_DIR / "documents" / "consumer_law"

PDF_DIR = BASE_DIR / "generated_pdfs"

PDF_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGE_SIZE = 10 * 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("SATYA")


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="SATYA AI",
    description="Indian Consumer Legal Assistant",
    version=APP_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# =========================================================
# REQUEST MODELS
# =========================================================

class QuestionRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=5000
    )


class GuideMessage(BaseModel):
    role: Literal["user", "assistant"]

    content: str = Field(
        ...,
        min_length=1,
        max_length=2000
    )


class GuideRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=5000
    )

    history: list[GuideMessage] = Field(
        default_factory=list,
        max_length=8
    )


class ComplaintPDFRequest(BaseModel):
    complaint_text: str = Field(
        ...,
        min_length=1,
        max_length=20000
    )


# =========================================================
# CONSUMER CASE FILING ASSESSMENT
# =========================================================

def assess_consumer_case(question: str) -> dict:
    """
    Gives a preliminary rule-based assessment.

    This works even when Gemini is unavailable.
    It does not determine whether a case will succeed.
    """

    text = question.lower()

    purchase_words = [
        "purchased",
        "purchase",
        "bought",
        "ordered",
        "order",
        "customer",
        "consumer",
        "paid",
        "payment",
        "product",
        "service"
    ]

    problem_words = [
        "defective",
        "damaged",
        "broken",
        "faulty",
        "not working",
        "poor quality",
        "wrong product",
        "fake product",
        "refund",
        "replacement",
        "refusing",
        "refused",
        "not delivered",
        "delivery",
        "fraud",
        "cheated",
        "overcharged",
        "deficiency",
        "harassment",
        "warranty",
        "guarantee",
        "cancelled",
        "canceled"
    ]

    refusal_words = [
        "refusing",
        "refused",
        "rejected",
        "not responding",
        "no response",
        "denied",
        "not helping",
        "not refunding",
        "not replacing"
    ]

    has_purchase = any(
        word in text for word in purchase_words
    )

    has_problem = any(
        word in text for word in problem_words
    )

    has_refusal = any(
        word in text for word in refusal_words
    )

    if has_purchase and has_problem:

        if has_refusal:

            status = "POSSIBLY — YES, YOU MAY HAVE GROUNDS TO FILE"

            explanation = (
                "You describe a purchase or consumer transaction, "
                "a problem with the product or service, and a refusal "
                "or failure to resolve it. These facts may support "
                "a consumer complaint under the Consumer Protection "
                "Act, 2019. The evidence, applicable legal requirements "
                "and circumstances must still be checked."
            )

        else:

            status = "POSSIBLY — YOU MAY HAVE GROUNDS TO FILE"

            explanation = (
                "You describe a consumer transaction and a possible "
                "problem with the product or service. This may support "
                "a consumer complaint, but more information is needed "
                "about the seller's response and the evidence available."
            )

        return {
            "status": status,
            "explanation": explanation,
            "can_file": "POSSIBLY"
        }

    if has_problem:

        return {
            "status": "NEED MORE INFORMATION",
            "explanation": (
                "You have described a possible consumer problem, "
                "but the purchase or service details are not clear. "
                "More information is needed before assessing whether "
                "you may file a consumer complaint."
            ),
            "can_file": "NEED MORE INFORMATION"
        }

    return {
        "status": "NEED MORE INFORMATION",
        "explanation": (
            "Please explain what you purchased or what service "
            "you received, what went wrong, and how the seller "
            "or service provider responded."
        ),
        "can_file": "NEED MORE INFORMATION"
    }


# =========================================================
# LEGAL ASSISTANT FALLBACK
# =========================================================

def legal_assistant_fallback(question: str) -> str:
    """
    Provides a useful response if Gemini is unavailable.
    """

    assessment = assess_consumer_case(question)

    answer = f"""
SATYA LEGAL ASSISTANT

1. CAN YOU FILE A CONSUMER CASE?

{assessment["status"]}

{assessment["explanation"]}

2. WHY?

A consumer complaint may be possible where the facts
show a defect in goods, deficiency in service or another
legally recognised consumer dispute.

For your situation, the important points are:

- What product or service you purchased.
- What problem occurred.
- Whether you contacted the seller.
- Whether the seller refused or failed to resolve it.
- What evidence you have.

3. APPLICABLE LAW

Consumer Protection Act, 2019:

- Section 2(10): Defines defect in goods.
- Section 2(11): Defines deficiency in service.
- Section 35: Provides for filing a consumer complaint.
- Section 39: Describes orders that a Consumer Commission
  may pass, subject to the facts and legal requirements.

These provisions are potentially relevant. Their application
must be checked against the complete facts and current law.

4. WHO MAY BE RESPONSIBLE?

Depending on the transaction, the possible opposite party
may include the seller, manufacturer or service provider.

An e-commerce marketplace is not automatically liable
just because the purchase happened on its platform.

5. EVIDENCE TO COLLECT

- Purchase invoice.
- Payment receipt.
- Order confirmation.
- Warranty documents.
- Product photographs or videos.
- Emails and messages with the seller.
- Customer-care complaint numbers.
- Written refusal of refund or replacement.

6. WHAT SHOULD YOU DO NEXT?

Step 1: Preserve the product and all purchase records.

Step 2: Send a written complaint to the seller requesting
an appropriate remedy.

Step 3: Contact the marketplace or service provider
where applicable.

Step 4: You may raise a grievance with the National
Consumer Helpline.

Telephone: 1915
Website: https://consumerhelpline.gov.in

Step 5: If appropriate, consider filing before the
competent Consumer Commission.

Official filing portal:
https://e-jagriti.gov.in

7. POSSIBLE RELIEF

Depending on the evidence and legal requirements,
you may request repair, replacement, refund or
other legally available relief.

A Consumer Commission decides what relief is justified.

8. PLEASE CONFIRM

1. When did you purchase the product or service?
2. Do you have an invoice or written proof that
   the seller refused your refund or replacement?

IMPORTANT:

This is general legal information, not a guarantee
that a complaint will succeed. Check the applicable
limitation period and jurisdiction requirements.

Note: The live AI service was unavailable, so this
preliminary assessment was generated using SATYA's
offline rules. It is not a complete legal review.
"""

    return answer.strip()


# =========================================================
# CASE FILING GUIDE FALLBACK
# =========================================================

def case_guide_fallback(question: str) -> str:

    assessment = assess_consumer_case(question)

    return f"""
SATYA - CONSUMER CASE FILING GUIDE

1. UNDERSTANDING YOUR CASE

Your question:
{question}

Preliminary filing assessment:
{assessment["status"]}

{assessment["explanation"]}


2. APPLICABLE ACTS AND LEGAL SECTIONS

Consumer Protection Act, 2019

Section 2(10):
Defines defect in goods.

Section 2(11):
Defines deficiency in service.

Section 35:
Provides for filing a consumer complaint.

Section 39:
Describes possible orders and remedies of a Consumer Commission.

These provisions are potentially relevant. Their exact
application depends on your facts and the applicable law.


3. EVIDENCE AND DOCUMENTS REQUIRED

1. Purchase invoice.
2. Payment receipt.
3. Order confirmation.
4. Warranty card.
5. Product photographs or videos.
6. Emails and messages with the seller.
7. Customer-care complaint numbers.
8. Written refusal of refund or replacement.
9. Service-centre report, if available.


4. STEP-BY-STEP PROCEDURE

STEP 1: Preserve all evidence and the product.

STEP 2: Contact the seller in writing. Clearly explain
the problem and request an appropriate remedy.

STEP 3: Contact the marketplace or platform where
applicable. Keep its response.

STEP 4: You may raise a grievance with the
National Consumer Helpline.

Telephone: 1915
Website: https://consumerhelpline.gov.in

STEP 5: Prepare a consumer complaint with the purchase
details, facts, legal grounds and requested relief.

STEP 6: Identify the appropriate Consumer Commission.
Check current pecuniary and territorial jurisdiction.

STEP 7: Visit the official e-Jagriti portal:
https://e-jagriti.gov.in

STEP 8: Follow the current filing instructions and
prepare the required documents.

STEP 9: Submit the complaint and save the filing reference.

STEP 10: Monitor notices and follow the Commission's
instructions during the proceedings.


5. POSSIBLE RELIEF

Depending on the facts, you may request repair,
replacement, refund or other relief legally available
under Section 39 of the Consumer Protection Act, 2019.


6. COMPLAINT PREPARATION

Consumer name: [TO BE FILLED]
Consumer address: [TO BE FILLED]
Seller details: [TO BE FILLED]
Purchase date: [TO BE FILLED]
Order number: [TO BE FILLED]
Amount paid: [TO BE FILLED]
Problem: [TO BE FILLED]
Relief requested: [TO BE FILLED]


7. IMPORTANT WARNINGS

- Keep original evidence safe.
- Check the limitation period.
- Verify the correct Consumer Commission.
- Keep all filing and grievance reference numbers.
- Do not submit false information.


8. NEXT QUESTIONS

1. What was the date of purchase?
2. Have you already complained to the seller in writing?


9. LEGAL DISCLAIMER

This is general legal information and not a guarantee
of a legal outcome or a substitute for qualified legal advice.

The live AI service was unavailable. This guide uses
a basic offline response and has not verified your
individual case against the legal document database.
"""


# =========================================================
# IMAGE VALIDATION
# =========================================================

def validate_image(filename: str, content: bytes):

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty."
        )

    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image must be smaller than 10 MB."
        )

    valid_signatures = {
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".jpeg": content.startswith(b"\xff\xd8\xff"),
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".webp": (
            content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        )
    }

    extension = Path(filename).suffix.lower()

    if extension not in valid_signatures:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG, PNG and WEBP images are supported."
        )

    if not valid_signatures[extension]:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file does not match its image extension."
        )


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {
        "success": True,
        "service": "SATYA AI",
        "version": APP_VERSION,
        "message": "Indian Consumer Legal Assistant is running."
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "service": "SATYA",
        "version": APP_VERSION,
        "legal_assessment": True
    }


# =========================================================
# LEGAL ASSISTANT CHAT
# =========================================================

@app.post("/ask")
def ask_legal_question(request: QuestionRequest):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter a question."
        )

    logger.info("Legal Assistant question received.")

    assessment = assess_consumer_case(question)

    try:

        logger.info("Calling Gemini Legal Assistant.")

        ai_answer = generate_legal_answer(question)

        if not ai_answer or not ai_answer.strip():
            raise RuntimeError("Empty AI response.")

        # Always put the case-filing assessment first.
        answer = f"""
CAN YOU FILE A CONSUMER CASE?

{assessment["status"]}

{assessment["explanation"]}

The assessment above is preliminary and based on
the facts provided. It is not a guarantee of success.

--------------------------------------------------

{ai_answer}
"""

        fallback = False

    except Exception as error:

        logger.exception(
            "Legal Assistant AI failed: %s",
            error
        )

        answer = legal_assistant_fallback(question)

        fallback = True

    return {
        "success": True,
        "chatbot": "legal_assistant",
        "question": question,
        "answer": answer,
        "can_file_assessment": assessment["can_file"],
        "fallback": fallback
    }


# =========================================================
# CASE FILING GUIDE
# =========================================================

@app.post("/guide")
def case_filing_guide(request: GuideRequest):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter your consumer case details."
        )

    history = [
        message.model_dump()
        for message in request.history
    ]

    assessment = assess_consumer_case(question)

    try:

        logger.info("Calling Gemini Case Filing Guide.")

        ai_answer = generate_case_guide_answer(
            question,
            conversation_history=history
        )

        if not ai_answer or not ai_answer.strip():
            raise RuntimeError("Empty guide response.")

        answer = f"""
PRELIMINARY CASE FILING ASSESSMENT

{assessment["status"]}

{assessment["explanation"]}

--------------------------------------------------

{ai_answer}
"""

        fallback = False

    except Exception as error:

        logger.exception(
            "Case Filing Guide AI failed: %s",
            error
        )

        answer = case_guide_fallback(question)

        fallback = True

    return {
        "success": True,
        "chatbot": "case_filing_guide",
        "question": question,
        "answer": answer,
        "can_file_assessment": assessment["can_file"],
        "fallback": fallback
    }


# =========================================================
# NOTICE ANALYSIS
# =========================================================

@app.post("/analyze-notice")
async def analyze_notice(
    file: UploadFile = File(...)
):

    filename = file.filename or "uploaded_notice"

    content = await file.read()

    validate_image(filename, content)

    logger.info(
        "Notice image uploaded: %s",
        filename
    )

    # This endpoint validates the image but does not
    # perform OCR or extract the notice contents.

    return {
        "success": True,
        "feature": "notice_analysis",
        "filename": filename,
        "answer": (
            "Your notice image was uploaded successfully. "
            "However, SATYA's current offline notice-upload "
            "handler does not yet read or analyze the contents. "
            "Please do not treat this upload as a completed "
            "legal notice analysis."
        ),
        "message": "Image validated successfully. Content analysis is not available in this handler."
    }


# =========================================================
# GENERATE COMPLAINT PDF
# =========================================================

@app.post("/generate-pdf")
def generate_pdf(request: ComplaintPDFRequest):

    complaint_text = request.complaint_text.strip()

    if not complaint_text:
        raise HTTPException(
            status_code=400,
            detail="Complaint text cannot be empty."
        )

    filename = (
        f"SATYA_Complaint_{uuid4().hex[:8]}.pdf"
    )

    output_path = PDF_DIR / filename

    try:

        generate_complaint_pdf(
            complaint_text,
            str(output_path)
        )

        if not output_path.exists():
            raise RuntimeError(
                "PDF generator did not create the file."
            )

        logger.info(
            "Complaint PDF generated: %s",
            filename
        )

        return FileResponse(
            path=str(output_path),
            media_type="application/pdf",
            filename=filename
        )

    except Exception as error:

        logger.exception(
            "PDF generation failed: %s",
            error
        )

        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {error}"
        )


# =========================================================
# LEGAL DOCUMENT ACCESS
# =========================================================

@app.get("/documents/{document_id}")
def get_document(document_id: str):

    # Prevent directory traversal.
    if (
        not document_id
        or Path(document_id).name != document_id
        or ".." in document_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid document ID."
        )

    if not DOCUMENTS_DIR.exists():
        raise HTTPException(
            status_code=404,
            detail="Legal documents directory not found."
        )

    matches = list(
        DOCUMENTS_DIR.rglob(document_id)
    )

    if not matches:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    file_path = matches[0]

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    return FileResponse(
        path=str(file_path),
        filename=file_path.name
    )


# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
def startup_event():

    logger.info(
        "SATYA AI backend started. Version: %s",
        APP_VERSION
    )

    logger.info(
        "Legal case filing assessment is enabled."
    )

    logger.info(
        "Documents directory: %s",
        DOCUMENTS_DIR
    )
