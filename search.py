"""
US 3.1 : Recherche sémantique (Retrieval)
- Convertit la question de l'utilisateur en vecteur (Titan Embeddings)
- Envoie une requête k-NN à OpenSearch (Top-K = 5)
- Retourne les textes des chunks les plus proches + leurs sources
"""

import boto3
import os
import json
from dotenv import load_dotenv
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

load_dotenv()

REGION = os.getenv("AWS_REGION")
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"

# --- Mêmes valeurs que dans load_to_opensearch.py (Outputs de cdk deploy) ---
COLLECTION_ENDPOINT = "gpeln5w6xfclawqxb625.eu-north-1.aoss.amazonaws.com"
INDEX_NAME = "rag-chunks-index"
TOP_K = 5

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials, REGION, "aoss")

client = OpenSearch(
    hosts=[{"host": COLLECTION_ENDPOINT, "port": 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20,
)


def embed_question(question: str) -> list:
    """Transforme la question en vecteur avec le même modèle que les chunks (Titan V2)."""
    body = json.dumps({"inputText": question})
    response = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def search_similar_chunks(question: str, top_k: int = TOP_K) -> list:
    """Recherche les top_k chunks les plus proches sémantiquement de la question."""
    question_vector = embed_question(question)

    query = {
        "size": top_k,
        "query": {
            "knn": {
                "embedding_vector": {
                    "vector": question_vector,
                    "k": top_k,
                }
            }
        },
        "_source": ["chunk_text", "source_document", "chunk_id"],  # on ne renvoie pas le vecteur, inutile ici
    }

    response = client.search(index=INDEX_NAME, body=query)
    hits = response["hits"]["hits"]

    results = []
    for hit in hits:
        results.append({
            "score": hit["_score"],
            "chunk_id": hit["_source"]["chunk_id"],
            "source_document": hit["_source"]["source_document"],
            "text": hit["_source"]["chunk_text"],
        })
    return results


def main():
    print("=== US 3.1 : Recherche sémantique ===\n")

    # Question de test - à personnaliser selon vos documents
    test_question = "Comment configurer la dimensionnalité d'un index vectoriel OpenSearch ?"
    print(f"Question : {test_question}\n")

    results = search_similar_chunks(test_question)

    print(f"{len(results)} résultat(s) trouvé(s) :\n")
    for i, r in enumerate(results, 1):
        print(f"--- Résultat {i} (score: {r['score']:.4f}) ---")
        print(f"Source : {r['source_document']}")
        print(f"Extrait : {r['text'][:200]}...")
        print()


if __name__ == "__main__":
    main()