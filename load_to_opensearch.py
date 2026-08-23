"""
US 2.2 : Indexation des documents vectorisés
- Lit tous les fichiers de chunks+embeddings depuis S3 (dossier embeddings/)
- Insère chaque chunk (vecteur + texte + métadonnées) dans l'index OpenSearch Serverless
- Logue le nombre de documents indexés avec succès et les éventuels échecs
"""

import boto3
import os
import json
from dotenv import load_dotenv
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

load_dotenv()

REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# --- Valeurs récupérées des Outputs de "cdk deploy" (US 2.1) ---
# Remplacez par vos propres valeurs si elles diffèrent

def get_collection_endpoint():
    """Récupère dynamiquement l'endpoint OpenSearch depuis SSM Parameter Store,
    en retirant le préfixe https:// car le client opensearch-py l'ajoute lui-même."""
    ssm = boto3.client("ssm", region_name="eu-north-1")
    response = ssm.get_parameter(Name="/smartovate-rag/opensearch-endpoint")
    endpoint = response["Parameter"]["Value"]
    return endpoint.replace("https://", "")

COLLECTION_ENDPOINT = get_collection_endpoint()

INDEX_NAME = "rag-chunks-index"

s3 = boto3.client("s3", region_name=REGION)

# --- Authentification IAM (SigV4) auprès d'OpenSearch Serverless ---
credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials, REGION, "aoss")  # "aoss" = service name pour OpenSearch Serverless

client = OpenSearch(
    hosts=[{"host": COLLECTION_ENDPOINT, "port": 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20,
)


def list_embedding_files():
    """Liste tous les fichiers de chunks/embeddings dans S3/embeddings/."""
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix="embeddings/")
    if "Contents" not in response:
        return []
    return [obj["Key"] for obj in response["Contents"] if obj["Key"].endswith(".json")]


def index_chunks(s3_key: str):
    """Charge un fichier de chunks depuis S3 et les insère un par un dans OpenSearch."""
    filename = os.path.basename(s3_key)
    print(f"\n--- Indexation : {filename} ---")

    obj = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
    chunk_records = json.loads(obj["Body"].read())

    success_count = 0
    failure_count = 0

    for record in chunk_records:
        document = {
            "embedding_vector": record["embedding"],
            "chunk_text": record["text"],
            "source_document": record["source_document"],
            "chunk_id": record["chunk_id"],
        }

        try:
            client.index(
                index=INDEX_NAME,
                body=document,
                # Note : OpenSearch Serverless ne supporte pas de spécifier l'ID à la création,
                # il est généré automatiquement. On garde chunk_id comme champ dans le document
                # pour pouvoir le retrouver/filtrer plus tard.
            )
            success_count += 1
            print(f"  ✅ {record['chunk_id']} indexé")
        except Exception as e:
            failure_count += 1
            print(f"  ❌ Échec pour {record['chunk_id']} : {e}")

    print(f"  Résumé : {success_count} succès, {failure_count} échec(s)")
    return success_count, failure_count


def main():
    print("=== US 2.2 : Indexation des documents vectorisés dans OpenSearch ===")
    files = list_embedding_files()

    if not files:
        print("Aucun fichier trouvé dans embeddings/. Lancez d'abord chunk_and_embed.py.")
        return

    print(f"{len(files)} fichier(s) trouvé(s) dans embeddings/ :")
    for f in files:
        print(f"  - {f}")

    total_success = 0
    total_failure = 0

    for file_key in files:
        s, f = index_chunks(file_key)
        total_success += s
        total_failure += f

    print(f"\n=== Indexation terminée : {total_success} succès, {total_failure} échec(s) au total ===")


if __name__ == "__main__":
    main()