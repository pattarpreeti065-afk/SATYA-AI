
import os
import json
import numpy as np
import faiss

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load API key from .env
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Check your .env file.")

# Gemini configuration
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768

# File paths
INDEX_PATH = "vector_store/legal_index.faiss"
CHUNKS_PATH = "vector_store/legal_chunks.json"

# Initialize Gemini
client = genai.Client(api_key=API_KEY)


def load_legal_database():
    """Load FAISS index and legal chunk metadata."""

    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError(f"FAISS index not found: {INDEX_PATH}")

    if not os.path.exists(CHUNKS_PATH):
        raise FileNotFoundError(f"Chunk metadata not found: {CHUNKS_PATH}")

    index = faiss.read_index(INDEX_PATH)

    with open(CHUNKS_PATH, "r", encoding="utf-8") as file:
        chunks = json.load(file)

    if index.ntotal != len(chunks):
        raise ValueError("FAISS index and chunk metadata counts do not match.")

    return index, chunks


def create_query_embedding(question):
    """Convert a user question into a Gemini query embedding."""

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=question,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBEDDING_DIMENSION
        )
    )

    vector = np.array(
        [response.embeddings[0].values],
        dtype=np.float32
    )

    faiss.normalize_L2(vector)

    return vector


def retrieve_legal_chunks(question, top_k=5):
    """Find the most relevant legal passages."""

    if not question or not question.strip():
        return []

    index, chunks = load_legal_database()

    query_vector = create_query_embedding(question)

    scores, indices = index.search(query_vector, min(top_k, len(chunks)))

    results = []

    for score, chunk_index in zip(scores[0], indices[0]):

        if chunk_index < 0:
            continue

        chunk = chunks[int(chunk_index)]

        result = {
            "score": float(score),
            "document_name": chunk.get("document_name"),
            "document_title": chunk.get("document_title"),
            "unit_type": chunk.get("unit_type"),
            "chapter": chunk.get("chapter"),
            "chapter_title": chunk.get("chapter_title"),
            "section_number": chunk.get("section_number"),
            "section_title": chunk.get("section_title"),
            "rule_number": chunk.get("rule_number"),
            "rule_title": chunk.get("rule_title"),
            "sub_section_numbers": chunk.get("sub_section_numbers", []),
            "sub_rule_numbers": chunk.get("sub_rule_numbers", []),
            "paragraph_references": chunk.get("paragraph_references", []),
            "source_pages": chunk.get("source_pages", []),
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
            "text": chunk.get("text", ""),
            "contextualized_text": chunk.get("contextualized_text", "")
        }

        results.append(result)

    return results


def main():
    print("\nSATYA - Legal Search Engine")
    print("-" * 40)

    question = input("\nEnter your legal question: ").strip()

    if not question:
        print("Please enter a question.")
        return

    print("\nSearching legal documents...")

    try:
        results = retrieve_legal_chunks(question, top_k=5)

        if not results:
            print("\nNo relevant passages found.")
            return

        print(f"\nFound {len(results)} relevant passages:\n")

        for number, result in enumerate(results, start=1):
            print("=" * 60)
            print(f"RESULT {number}")
            print(f"Similarity score: {result['score']:.4f}")
            print(f"Document: {result['document_title'] or result['document_name']}")

            if result["section_number"]:
                print(
                    f"Section: {result['section_number']} "
                    f"{result['section_title'] or ''}"
                )

            if result["rule_number"]:
                print(
                    f"Rule: {result['rule_number']} "
                    f"{result['rule_title'] or ''}"
                )

            print(f"PDF pages: {result['source_pages']}")
            print("\nLegal text:")
            print(result["text"][:2000])

    except Exception as error:
        print(f"\nSearch failed: {error}")


if __name__ == "__main__":
    main()
