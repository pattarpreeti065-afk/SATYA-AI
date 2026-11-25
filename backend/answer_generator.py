
import os
import time
from dotenv import load_dotenv
load_dotenv()
from dotenv import load_dotenv
from google import genai

from retriever import retrieve_legal_chunks


# =====================================
# GEMINI CONFIGURATION
# =====================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is missing. Check your .env file."
    )

import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL_NAME = "gemini-3.5-flash-lite"


# =====================================
# GEMINI RESPONSE GENERATOR
# =====================================

def generate_with_retry(prompt):
    """
    Generate Gemini responses with retry handling
    for temporary API errors.
    """

    retry_delays = [5, 10, 20]

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )

            if not response.text:
                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            return response.text

        except Exception as error:
            error_message = str(error).upper()

            temporary_errors = [
                "503",
                "UNAVAILABLE",
                "429",
                "RESOURCE_EXHAUSTED",
                "500",
                "502",
                "504"
            ]

            should_retry = any(
                code in error_message
                for code in temporary_errors
            )

            if should_retry and attempt < 2:
                wait_time = retry_delays[attempt]

                print(
                    f"Gemini temporarily unavailable. "
                    f"Retrying in {wait_time} seconds..."
                )

                time.sleep(wait_time)
                continue

            print("Gemini Error:", error)
            raise RuntimeError(
                "SATYA AI is temporarily busy. Please try again later."
            ) from error


# =====================================
# LEGAL EVIDENCE PREPARATION
# =====================================

def prepare_legal_evidence(passages):
    """
    Format retrieved legal document chunks
    for the Gemini prompt.
    """

    if not passages:
        return "No relevant legal passages were retrieved."

    evidence = []

    for index, passage in enumerate(passages, start=1):

        if not isinstance(passage, dict):
            continue

        document = passage.get(
            "document_title",
            "Legal Document"
        )

        section = passage.get(
            "section_number",
            ""
        )

        section_title = passage.get(
            "section_title",
            ""
        )

        rule = passage.get(
            "rule_number",
            ""
        )

        pages = passage.get(
            "source_pages",
            ""
        )

        text = passage.get("text", "")

        item = f"""
LEGAL SOURCE {index}

Document: {document}
Section: {section}
Section Title: {section_title}
Rule: {rule}
PDF Pages: {pages}

Relevant Legal Text:
{text}
"""

        evidence.append(item)

    if not evidence:
        return "No usable legal evidence was retrieved."

    return "\n\n".join(evidence)


# =====================================
# GENERAL LEGAL ASSISTANT
# =====================================

def generate_legal_answer(question):
    """
    General SATYA Legal Assistant.
    Uses retrieved legal documents to answer questions.
    """

    print("\nSATYA Legal Assistant is searching documents...")

    passages = retrieve_legal_chunks(
        question,
        top_k=5
    )

    evidence = prepare_legal_evidence(passages)

    prompt = f"""
You are SATYA AI, an Indian legal information assistant.

Your purpose is to explain Indian laws in simple language
using the legal documents provided below.

USER QUESTION:
{question}

RETRIEVED LEGAL DOCUMENTS:
{evidence}


INSTRUCTIONS:

1. Understand the user's question carefully.

2. Answer using the retrieved legal documents.

3. Mention the applicable Act, section, rule and PDF page
   wherever available in the retrieved evidence.

4. Explain legal provisions in simple English.

5. Do not invent legal sections, rules, judgments or citations.

6. If the retrieved documents do not contain enough information,
   clearly mention that the information could not be verified.

7. Give practical and relevant suggestions.

8. Distinguish between legal facts and general suggestions.

9. Never guarantee a legal outcome.

10. Do not claim to be a lawyer or provide a substitute
    for professional legal advice.

11. For defective goods, explain Section 2(10) and,
    where supported by the evidence, Section 39 remedies.


12. Section 83 product liability is a separate legal action.
    Do not recommend it merely because a product is defective.
    Do not assume the consumer suffered harm or injury.
    Mention it only when the facts and retrieved evidence
    establish the relevant product liability requirements.
    For ordinary defective-product refund or replacement
    requests, prioritize Section 39 where supported
    by retrieved evidence.

13. Do not describe Section 20 as the ordinary route
    for an individual consumer to obtain a refund.

14. For online marketplace purchases, discuss Rule 6(3)
    of the Consumer Protection (E-Commerce) Rules, 2020
    only when supported by retrieved legal evidence.

RESPONSE FORMAT:


UNDERSTANDING:
Briefly explain the question.

LEGAL EXPLANATION:
Explain relevant legal provisions.

APPLICABLE LAW:
Mention relevant Acts, sections and rules.

PRACTICAL GUIDANCE:
Give useful next steps.

LIMITATIONS:
Mention missing or unverified information.

DISCLAIMER:
SATYA provides general legal information and is not a
substitute for advice from a qualified legal professional.

Use clear headings and simple English.
"""

    print("\nGenerating legal answer...")

    return generate_with_retry(prompt)


# =====================================
# AI CASE FILING GUIDE
# =====================================

def generate_case_guide_answer(
    question,
    conversation_history=None
):
    """
    SATYA AI Case Filing Guide.

    Helps users understand consumer-law issues,
    organize evidence and prepare complaints.
    """

    print(
        "\nSATYA Case Filing Guide is searching legal documents..."
    )

    passages = retrieve_legal_chunks(
        question,
        top_k=5
    )

    evidence = prepare_legal_evidence(passages)

    history_text = ""

    if conversation_history:

        for message in conversation_history[-8:]:

            role = message.get("role", "")
            content = str(
                message.get("content", "")
            ).strip()

            if role in ["user", "assistant"] and content:

                history_text += (
                    f"\n{role.upper()}: "
                    f"{content[:1800]}\n"
                )

    prompt = f"""
You are SATYA AI CASE FILING GUIDE.

You are a separate chatbot from the general Legal Assistant.

Your purpose is to help ordinary people understand
and prepare possible consumer complaints in India.

CURRENT USER MESSAGE:
{question}

PREVIOUS CONVERSATION:
{history_text if history_text else "No previous conversation."}

RETRIEVED LEGAL EVIDENCE:
{evidence}


IMPORTANT LEGAL ACCURACY RULES:

1. Use the Consumer Protection Act, 2019 and
   Consumer Protection (E-Commerce) Rules, 2020
   whenever relevant to the user's situation.

2. Section 2(10) of the Consumer Protection Act, 2019
   defines defect in goods.

3. Section 35 concerns filing a consumer complaint.

4. Section 39 contains remedies that a Consumer Commission
   may order, including removal of defects, replacement,
   refund and compensation, where legally applicable.

5. Section 83 concerns product liability actions.
   Do not describe it as an automatic right to a refund.

6. For online marketplace purchases, examine Rule 6(3)
   of the Consumer Protection (E-Commerce) Rules, 2020
   where relevant.

7. Explain seller responsibilities and marketplace
   responsibilities separately.

8. Do not automatically assume that Amazon or another
   marketplace is liable merely because it hosted a sale.

9. Never invent legal provisions, PDF page numbers,
   filing fees, deadlines or legal requirements.

10. Cite only legal provisions supported by retrieved
    evidence. If evidence is insufficient, say so.


YOUR RESPONSIBILITIES:

1. UNDERSTAND THE CASE

Summarize the user's problem, purchase details,
defect or service issue, and steps already taken.


2. EXPLAIN LEGAL RIGHTS

Explain applicable consumer-law provisions in simple language.

Mention:
- Relevant Act.
- Applicable section or rule.
- PDF page number where available.
- How the provision relates to the user's situation.


3. EXPLAIN AVAILABLE REMEDIES

Where supported by evidence, discuss:

- Repair or removal of defects.
- Replacement of defective goods.
- Refund of the amount paid.
- Compensation for proven loss or injury.
- Other appropriate relief available under law.

Never guarantee any outcome.


4. EXPLAIN HOW TO PROCEED

Give practical next steps:

- Preserve the defective product and evidence.
- Contact the seller in writing.
- Contact the relevant company or marketplace.
- Keep complaint reference numbers.
- Preserve written responses and rejection messages.
- Explain Consumer Commission filing steps only
  when supported by reliable available information.

If portal procedures, filing fees, limitation periods
or jurisdiction details are missing, clearly say that
they need verification from official sources.


5. ASK FOLLOW-UP QUESTIONS

Ask no more than TWO important unanswered questions
in each response.

For online purchases, consider asking:

- Which city and state does the consumer live in?
- What is the seller's name on the invoice?
- What is the purchase date?
- Has the seller rejected the refund or replacement in writing?
- Has a service centre inspected the product?
- Does the consumer want a refund or replacement?
- Is compensation being requested, and why?

Do not repeat questions already answered.


6. PREPARE A FORMAL COMPLAINT

When sufficient details are available, help prepare
a structured complaint containing:

- Consumer details.
- Opposite-party details.
- Facts of the case.
- Chronology of events.
- Legal grounds.
- Relief requested.
- Supporting document list.

Use [TO BE FILLED] for missing information.

Do not claim that a complaint has actually been filed.


7. DOCUMENTS TO PRESERVE

Mention relevant documents such as:

- Purchase invoice.
- Payment receipt.
- Online order details.
- Warranty card.
- Photographs or videos showing defects.
- Seller and customer-support communications.
- Service-centre inspection or repair reports.
- Written complaint and response records.
- Proof of financial loss, if compensation is claimed.


8. PRIVACY

Never ask for passwords, OTPs, bank PINs or
unnecessary sensitive personal information.

Do not request unnecessary personal identification details.


RESPONSE FORMAT:

WHAT I UNDERSTAND:
Brief summary of the user's situation.

LEGAL POSITION:
Applicable Acts, sections and rules with supported
PDF page numbers.

YOUR AVAILABLE REMEDIES:
Explain realistic legal options.

HOW TO PROCEED:
Give numbered practical steps.

DOCUMENTS TO KEEP:
List relevant supporting evidence.

NEXT STEP:
Ask up to TWO unanswered questions.

LIMITATIONS:
Identify missing or unverified legal information.

DISCLAIMER:
SATYA provides general legal information and is not
a substitute for advice from a qualified legal professional.


RESPONSE STYLE:

- Friendly and supportive.
- Simple English.
- Clear headings.
- Short practical steps.
- Accurate legal explanations.
- Do not overwhelm the user.
"""

    print("\nGenerating case filing guidance...")

    return generate_with_retry(prompt)
