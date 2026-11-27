
import os
import json
import glob
import time

import numpy as np
import faiss
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load API key from .env
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found. Add it to the .env file."
    )

client = genai.Client(api_key=API_KEY)

# Configuration
EMBEDDING_MODEL = "gemini-embedding-001"
DIMENSIONS = 768
BATCH_SIZE = 16

DATA_FOLDER = "extracted_documents"
OUTPUT_FOLDER = "vector_store"


def load_legal_chunks():
    all_chunks = []

    files = glob.glob(
        os.path.join(DATA_FOLDER, "*.json")
    )

    if not files:
        raise FileNotFoundError(
            "No JSON files found in extracted_documents."
        )

    for file_path in files:
        print(f"Reading: {os.path.basename(file_path)}")

        with open(file_path, "r", encoding="utf-8") as file:
            document = json.load(file)

        for chunk in document.get("chunks", []):
            text = chunk.get("contextualized_text") or chunk.get("text", "")

            if not text.strip():
                continue

            if chunk.get("unit_type") == "front_matter":
                continue

            saved_chunk = chunk.copy()
            saved_chunk["embedding_text"] = text
            all_chunks.append(saved_chunk)

    return all_chunks



def create_embeddings(chunks):
    vectors = []

    texts = [
        chunk["embedding_text"]
        for chunk in chunks
    ]

    total = len(texts)

    for start in range(0, total, BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]

        print(
            f"Embedding {start + 1} to "
            f"{min(start + BATCH_SIZE, total)} of {total}"
        )

        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=DIMENSIONS
            )
        )

        for item in response.embeddings:
            vectors.append(item.values)

        if start + BATCH_SIZE < total:
            print("Waiting 12 seconds...")
            time.sleep(12)

    vectors = np.array(vectors, dtype="float32")
    faiss.normalize_L2(vectors)

    return vectors

def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print("Loading legal documents...")
    chunks = load_legal_chunks()

    print(f"Total legal chunks: {len(chunks)}")

    if not chunks:
        raise ValueError("No legal chunks available.")

    print("\nGenerating Gemini embeddings...")
    vectors = create_embeddings(chunks)

    print("\nCreating FAISS index...")
    index = faiss.IndexFlatIP(DIMENSIONS)
    index.add(vectors)

    index_path = os.path.join(
        OUTPUT_FOLDER,
        "legal_index.faiss"
    )

    chunks_path = os.path.join(
        OUTPUT_FOLDER,
        "legal_chunks.json"
    )

    faiss.write_index(index, index_path)

    with open(chunks_path, "w", encoding="utf-8") as file:
        json.dump(
            chunks,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("\nSUCCESS!")
    print(f"Indexed chunks: {index.ntotal}")
    print(f"FAISS index: {index_path}")
    print(f"Chunk metadata: {chunks_path}")


if __name__ == "__main__":
    main()
