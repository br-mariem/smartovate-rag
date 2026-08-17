"""
US 1.2 : Découpage et Vectorisation (Chunking & Embedding)
- Lit les fichiers déjà extraits depuis S3 (dossier processed/)
- Découpe le texte en chunks de ~500-1000 tokens avec 10% d'overlap (LangChain)
- Génère un vecteur pour chaque chunk via Amazon Titan Embeddings (Bedrock)
- Gère le rate limiting avec retry + backoff exponentiel
- Sauvegarde chunks + vecteurs + métadonnées dans S3 (dossier embeddings/)
"""

import boto3
import os
import json
import time
import random
from datetime import datetime, timezone
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

load_dotenv()

REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
CHUNK_SIZE_TOKENS = 800       # cible entre 500 et 1000 tokens comme demandé
CHUNK_OVERLAP_TOKENS = 80     # 10% d'overlap
MAX_RETRIES = 5

s3 = boto3.client("s3", region_name=REGION)
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# Encodeur de tokens (compatible avec la plupart des LLM, sert juste à mesurer la longueur)
tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))


# Splitter LangChain : découpe récursivement (paragraphes -> phrases -> mots)
# en respectant une taille cible mesurée en tokens réels, pas en caractères.
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE_TOKENS,
    chunk_overlap=CHUNK_OVERLAP_TOKENS,
    length_function=count_tokens,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def list_processed_documents():
    """Liste tous les fichiers .json déjà extraits dans processed/."""
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix="processed/")
    if "Contents" not in response:
        return []
    return [obj["Key"] for obj in response["Contents"] if obj["Key"].endswith(".json")]


def get_embedding(text: str) -> list:
    """Appelle Titan Embeddings avec retry + backoff exponentiel en cas de rate limiting."""
    for attempt in range(MAX_RETRIES):
        try:
            body = json.dumps({"inputText": text})
            response = bedrock.invoke_model(
                modelId=EMBEDDING_MODEL_ID,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            return result["embedding"]
        except bedrock.exceptions.ThrottlingException:
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            print(f"    ⏳ Rate limit atteint, nouvelle tentative dans {wait_time:.1f}s...")
            time.sleep(wait_time)
        except Exception as e:
            print(f"    ❌ Erreur embedding : {e}")
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Échec de la génération d'embedding après plusieurs tentatives.")


def process_document(s3_key: str):
    """Découpe un document déjà extrait en chunks, génère les embeddings, sauvegarde le résultat."""
    filename = os.path.basename(s3_key)
    print(f"\n--- Chunking + Embedding : {filename} ---")

    obj = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
    data = json.loads(obj["Body"].read())

    source_file = data["source_file"]
    full_text = data["text"]

    chunks = text_splitter.split_text(full_text)
    print(f"  📄 {len(chunks)} chunk(s) généré(s) (taille cible ~{CHUNK_SIZE_TOKENS} tokens, overlap {CHUNK_OVERLAP_TOKENS})")

    chunk_records = []
    for i, chunk_text in enumerate(chunks):
        token_count = count_tokens(chunk_text)
        print(f"  🔹 Chunk {i+1}/{len(chunks)} ({token_count} tokens) — génération de l'embedding...")

        embedding_vector = get_embedding(chunk_text)

        chunk_records.append({
            "chunk_id": f"{os.path.splitext(source_file)[0]}_chunk_{i}",
            "source_document": source_file,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "token_count": token_count,
            "text": chunk_text,
            "embedding": embedding_vector,
            "embedding_dimension": len(embedding_vector),
            "embedding_model": EMBEDDING_MODEL_ID,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    output_filename = os.path.splitext(filename)[0] + "_embeddings.json"
    output_key = f"embeddings/{output_filename}"

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=json.dumps(chunk_records, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"  ✅ {len(chunk_records)} chunk(s) + embeddings sauvegardés dans S3 : {output_key}")


def main():
    print("=== US 1.2 : Découpage et Vectorisation ===")
    documents = list_processed_documents()

    if not documents:
        print("Aucun document trouvé dans processed/. Lancez d'abord extract_documents.py.")
        return

    print(f"{len(documents)} document(s) trouvé(s) dans processed/ :")
    for doc in documents:
        print(f"  - {doc}")

    for doc_key in documents:
        process_document(doc_key)

    print("\n=== Chunking + Embedding terminé ===")


if __name__ == "__main__":
    main()