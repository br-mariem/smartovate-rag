import boto3
import json
from dotenv import load_dotenv
import os

# Charge les variables du fichier .env
load_dotenv()

region = os.getenv("AWS_REGION")
bucket_name = os.getenv("S3_BUCKET_NAME")

print("=== Test 1 : Connexion S3 ===")
try:
    s3 = boto3.client("s3", region_name=region)
    response = s3.list_objects_v2(Bucket=bucket_name)
    print(f"✅ Connexion S3 réussie. Bucket '{bucket_name}' accessible.")
    if "Contents" in response:
        for obj in response["Contents"]:
            print(f"  - {obj['Key']}")
    else:
        print("  (bucket vide ou aucun fichier à la racine)")
except Exception as e:
    print(f"❌ Erreur S3 : {e}")

print("\n=== Test 2 : Connexion Bedrock (Claude) ===")
try:
    bedrock = boto3.client("bedrock-runtime", region_name=region)
    
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "Réponds juste 'Bonjour, la connexion fonctionne !' et rien d'autre."}
        ]
    })
    
    response = bedrock.invoke_model(
        modelId="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        body=body,
        contentType="application/json",
        accept="application/json"
    )
    
    result = json.loads(response["body"].read())
    print(f"✅ Réponse de Claude : {result['content'][0]['text']}")
except Exception as e:
    print(f"❌ Erreur Bedrock : {e}")

print("\n=== Test 3 : Connexion Bedrock (Titan Embeddings) ===")
try:
    body = json.dumps({"inputText": "Ceci est un test d'embedding."})
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=body,
        contentType="application/json",
        accept="application/json"
    )
    result = json.loads(response["body"].read())
    embedding = result["embedding"]
    print(f"✅ Embedding généré avec succès. Dimension du vecteur : {len(embedding)}")
except Exception as e:
    print(f"❌ Erreur Titan Embeddings : {e}")