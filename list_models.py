import boto3
from dotenv import load_dotenv
import os

load_dotenv()
region = os.getenv("AWS_REGION")

bedrock = boto3.client("bedrock", region_name=region)

print("=== Profils d'inférence disponibles ===")
try:
    response = bedrock.list_inference_profiles()
    for profile in response["inferenceProfileSummaries"]:
        if "claude" in profile["inferenceProfileId"].lower() or "haiku" in profile["inferenceProfileId"].lower():
            print(f"  - {profile['inferenceProfileId']}")
except Exception as e:
    print(f"Erreur : {e}")

print("\n=== Modèles Anthropic disponibles (foundation models) ===")
try:
    response = bedrock.list_foundation_models(byProvider="Anthropic")
    for model in response["modelSummaries"]:
        print(f"  - {model['modelId']}")
except Exception as e:
    print(f"Erreur : {e}")