
import os
import time

from dotenv import load_dotenv
from google import genai

from retriever import retrieve_legal_chunks


# ==================================================
# GEMINI CONFIGURATION
# ==================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is missing. Check your .env file."
    )

client = genai.Client(api_key=API_KEY)

MODEL_NAME = "gemini-3.8-flash"


# ==================================================
# GEMINI RESPONSE WITH RETRY
# ==================================================

def generate_with_retry(prompt):

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

            return response.text.strip()

        except Exception as error:

            error_message = str(error).upper()

            temporary_errors = [
                "503",
                "UNAVAILABLE",
                "429",
                "RESOURCE_EXHAUSTED",
                "500",
                "502",
                "504",
                "DEADLINE_EXCEEDED"
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
                f"Gemini API error: {error}"
            ) from error


# ==================================================
# PREPARE LEGAL EVIDENCE
# ==================================================

def prepare_legal_evidence(passages):

    if not passages:
        return (
            "No relevant legal passages were retrieved. "
            "Do not invent legal citations."
        )

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

        evidence.append(
            f"""
LEGAL SOURCE {index}

Document: {document}
Section: {section}
Section Title: {section_title}
Rule: {rule}
PDF Pages: {pages}

Relevant Legal Text:
{text}
"""
        )

    if not evidence:
        return "No usable legal evidence was retrieved."

    return "\n\n".join(evidence)


# ==================================================
# LEGAL SOURCE REFERENCES
# ==================================================

def format_legal_source_references(passages):

    if not passages:
        return (
            "LEGAL SOURCE REFERENCES\n"
            "No verifiable legal source references "
            "were retrieved."
        )

    references = []
    seen = set()

    for passage in passages:

        if not isinstance(passage, dict):
            continue

        document = str(
            passage.get("document_title") or ""
        ).strip()

        section = str(
            passage.get("section_number") or ""
        ).strip()

        section_title = str(
            passage.get("section_title") or ""
        ).strip()

        rule = str(
            passage.get("rule_number") or ""
        ).strip()

        pages = str(
            passage.get("source_pages") or ""
        ).strip()

        if not any([document, section, rule, pages]):
            continue

        reference_key = (
            document,
            section,
            rule,
            pages
        )

        if reference_key in seen:
            continue

        seen.add(reference_key)

        lines = [
            document or "Legal Document"
        ]

        if section:

            section_text = f"Section {section}"

            if section_title:
                section_text += f" - {section_title}"

            lines.append(section_text)

        if rule:
            lines.append(f"Rule: {rule}")

        if pages:
            lines.append(f"PDF Page(s): {pages}")

        references.append(
            "- " + "\n  ".join(lines)
        )

    if not references:
        return (
            "LEGAL SOURCE REFERENCES\n"
            "Retrieved passages did not contain "
            "enough metadata to verify references."
        )

    return (
        "LEGAL SOURCE REFERENCES\n"
        "References retrieved from SATYA's legal documents:\n\n"
        + "\n\n".join(references)
        + "\n\nVerify the original legal document before "
        "relying on a particular provision."
    )


def add_legal_source_references(answer, passages):

    source_section = format_legal_source_references(
        passages
    )

    return (
        answer.strip()
        + "\n\n"
        + source_section
    )


# ==================================================
# 1. LEGAL ASSISTANT CHAT
# ==================================================

def generate_legal_answer(question):

    print(
        "\nSATYA Legal Assistant is searching documents..."
    )

    passages = retrieve_legal_chunks(
        question,
        top_k=10
    )

    evidence = prepare_legal_evidence(passages)

    prompt = f"""
You are SATYA AI, an Indian Consumer Legal Assistant.

Your main job is to help consumers understand their rights
and assess whether their facts may support a consumer case.

USER QUESTION:
{question}

RETRIEVED LEGAL DOCUMENTS:
{evidence}


IMPORTANT TASK:

You MUST clearly assess whether the user may file
a consumer complaint.

Do not give only a general explanation of consumer law.


MANDATORY RESPONSE FORMAT:


1. CAN YOU FILE A CONSUMER CASE?

Choose ONE assessment:

YES - The facts described appear to provide grounds
for a consumer complaint.

POSSIBLY - There may be grounds, but some important
facts need confirmation.

NOT ENOUGH INFORMATION - More information is needed
to assess the complaint.

UNLIKELY - The facts described do not currently show
sufficient grounds for a consumer complaint.

Explain the reason for your assessment.

Never guarantee that the case will succeed.


2. WHY?

Explain:

- What consumer problem occurred.
- Whether a defect, deficiency or unfair trade practice
  may be involved.
- Which facts support the assessment.
- What facts are still missing.


3. APPLICABLE LAWS

Mention relevant Acts, sections and rules.

For every provision explain:

- Act name.
- Section or Rule.
- What the provision means.
- Why it may apply to this case.

Use retrieved legal evidence.

Never invent sections, rules or judgments.


4. WHO CAN YOU FILE AGAINST?

Identify possible opposite parties:

- Seller.
- Manufacturer.
- Service provider.
- E-commerce marketplace, if legally applicable.

Explain that the responsibilities of sellers,
manufacturers and marketplaces may differ.

Do not automatically assume every party is liable.


5. WHAT EVIDENCE DO YOU NEED?

Provide a relevant checklist:

- Purchase invoice.
- Payment receipt.
- Order confirmation.
- Warranty details.
- Product photographs.
- Emails and messages.
- Customer-care complaint numbers.
- Written refusal of refund or replacement.
- Evidence of financial loss, where relevant.


6. WHAT SHOULD YOU DO NEXT?

Give practical steps:

1. Preserve all evidence.
2. Contact the seller in writing.
3. Contact the marketplace or service provider,
   where applicable.
4. Raise a grievance with the National Consumer Helpline.

National Consumer Helpline:
1915
https://consumerhelpline.gov.in

5. Consider filing before the appropriate
   Consumer Commission if appropriate.

Official e-Jagriti portal:
https://e-jagriti.gov.in

Do not claim that contacting the helpline is a mandatory
precondition to filing a consumer complaint.


7. POSSIBLE RELIEF

Explain possible remedies:

- Repair.
- Replacement.
- Refund.
- Compensation for proven loss or injury.
- Other relief legally available.

Explain the legal basis where supported by evidence.

Do not guarantee any remedy.


8. INFORMATION STILL REQUIRED

Ask at most TWO useful questions.

Do not ask for information the user has already provided.

Questions may concern:

- Purchase date.
- Seller identity.
- Amount paid.
- Whether the seller rejected the complaint.
- Remedy preferred by the consumer.


9. LEGAL DISCLAIMER

SATYA provides general legal information.
It does not guarantee legal outcomes and is not
a substitute for advice from a qualified lawyer.


RULES:

- Give a clear assessment at the beginning.
- Use simple English.
- Be practical and specific.
- Do not invent facts.
- Do not invent legal citations.
- Do not guarantee case success.
- Do not claim that a complaint has already been filed.
- Distinguish verified legal information from suggestions.

The application will append legal source references.
Do not fabricate source references.
"""

    print("\nGenerating Legal Assistant response...")

    answer = generate_with_retry(prompt)

    return add_legal_source_references(
        answer,
        passages
    )


# ==================================================
# 2. CASE FILING GUIDE
# ==================================================

def generate_case_guide_answer(
    question,
    conversation_history=None
):

    print(
        "\nSATYA Case Filing Guide is searching documents..."
    )

    passages = retrieve_legal_chunks(
        question,
        top_k=10
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
You are SATYA AI - INDIAN CONSUMER CASE FILING GUIDE.

Your task is to explain how a consumer can prepare
and file a consumer complaint in India.

Do not provide only generic consumer-law information.


USER PROBLEM:
{question}


PREVIOUS CONVERSATION:
{history_text if history_text else "No previous conversation."}


RETRIEVED LEGAL DOCUMENTS:
{evidence}


LEGAL ACCURACY RULES:

1. Use retrieved legal documents as the primary
   source of legal information.

2. Never invent Acts, sections, rules, judgments,
   PDF page numbers, fees or legal deadlines.

3. Explain each applicable legal provision.

4. For defective goods, examine Consumer Protection
   Act, 2019, Section 2(10), Section 35 and Section 39
   where supported by retrieved evidence.

5. For deficiency in service, examine Section 2(11)
   where the facts support it.

6. For online purchases, examine the Consumer Protection
   (E-Commerce) Rules, 2020 where applicable.

7. Explain seller and marketplace responsibilities
   separately.

8. Do not automatically declare the marketplace liable.

9. Product liability is not an automatic remedy for
   every defective product.

10. Do not guarantee refund, replacement or compensation.

11. Explain jurisdiction based on applicable pecuniary
    and territorial requirements without guessing thresholds.

12. Clearly distinguish verified legal information
    from practical suggestions.


MANDATORY RESPONSE FORMAT:

SATYA - CONSUMER CASE FILING GUIDE


1. UNDERSTANDING YOUR CASE

Explain what happened, the consumer dispute involved,
the parties involved and any missing information.


2. APPLICABLE ACTS AND LEGAL SECTIONS

For each relevant Act provide:

Act name:
Section or Rule:
What the law says:
Why it applies:
Source document:
PDF page, if available:

Consider relevant laws such as:

- Consumer Protection Act, 2019.
- Consumer Protection (E-Commerce) Rules, 2020.
- Sale of Goods Act, 1930.
- Indian Contract Act, 1872.

Include only relevant and supported provisions.


3. EVIDENCE AND DOCUMENTS REQUIRED

Give a numbered checklist and explain why each
document is useful.

Examples:

- Purchase invoice.
- Payment receipt.
- Order confirmation.
- Warranty card.
- Product photographs.
- Seller communications.
- Complaint reference numbers.
- Service-centre report.
- Written refusal of refund or replacement.


4. STEP-BY-STEP PROCEDURE TO FILE THE CASE

STEP 1:
Preserve the product and all evidence.

STEP 2:
Contact the seller in writing.

Explain what to write and what remedy to request.

STEP 3:
Contact the marketplace or company where relevant.

Explain the difference between seller and marketplace
responsibilities.

STEP 4:
Register a grievance with the National Consumer Helpline.

Telephone: 1915
Website: https://consumerhelpline.gov.in

Preserve the grievance reference number.

STEP 5:
Prepare a formal consumer complaint.

Explain what information to include.

STEP 6:
Identify the appropriate Consumer Commission.

Explain pecuniary and territorial jurisdiction.
Do not guess current thresholds.

STEP 7:
Visit the official e-Jagriti portal.

https://e-jagriti.gov.in

Explain the general online filing process.

STEP 8:
Prepare and upload the required documents.

STEP 9:
Submit the complaint and preserve the filing reference.

STEP 10:
Explain notices, responses and further proceedings.


5. RELIEF THE CONSUMER MAY REQUEST

Explain possible remedies:

- Repair.
- Replacement.
- Refund.
- Compensation.
- Other legally available relief.

Connect each remedy to applicable law where verified.


6. COMPLAINT PREPARATION

Explain how to prepare the complaint.

Include:

- Consumer name and address.
- Seller or company details.
- Purchase details.
- Facts and chronology.
- Legal grounds.
- Relief requested.
- Supporting document list.

Use [TO BE FILLED] for missing details.

Never invent personal information.


7. IMPORTANT WARNINGS

Explain:

- Preserve original evidence.
- Keep complaint reference numbers.
- Check the limitation period.
- Verify the correct Consumer Commission.
- Do not submit false information.
- Seek qualified legal advice when necessary.


8. NEXT QUESTIONS

Ask no more than TWO relevant unanswered questions.


9. LEGAL DISCLAIMER

SATYA provides general legal information.
It does not guarantee a legal outcome and is not
a substitute for advice from a qualified lawyer.


RESPONSE QUALITY:

- Use simple English.
- Use numbered steps.
- Explain exactly what the consumer should do.
- Connect laws to the user's actual problem.
- Avoid unnecessary legal jargon.
- Do not invent citations or page numbers.
- Do not use ## or ### Markdown heading symbols.
- Do not guarantee a legal outcome.

The application will append retrieved legal references.
Do not fabricate references.

Now generate the complete case filing guide.
"""

    print("\nGenerating Case Filing Guide...")

    answer = generate_with_retry(prompt)

    return add_legal_source_references(
        answer,
        passages
    )
