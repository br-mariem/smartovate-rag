"""
US 3.2 : Génération de la réponse avec Amazon Bedrock
- Construit un prompt incluant la question + le contexte récupéré d'OpenSearch (US 3.1)
- Appelle Claude Haiku 4.5 via Bedrock pour générer la réponse
- La réponse cite explicitement les documents sources utilisés
- Anticipe le Bug 1 (hallucinations) : temperature=0 + instruction stricte de ne pas inventer
"""

import boto3
import os
import json
from dotenv import load_dotenv
from search import search_similar_chunks  # réutilise l'US 3.1 telle quelle

load_dotenv()

REGION = os.getenv("AWS_REGION")
GENERATION_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# --- Anticipation du Bug 1 (hallucinations) : instruction système stricte ---
SYSTEM_PROMPT = """Tu es un assistant interne pour les consultants de Smartovate Ltd.
Tu réponds aux questions UNIQUEMENT à partir des extraits de documents fournis en contexte.

Règles strictes :
- Si la réponse ne se trouve pas dans le contexte fourni, réponds exactement : "Je ne dispose pas de cette information dans la base documentaire."
- Ne jamais inventer, extrapoler, ou compléter avec des connaissances générales non présentes dans le contexte.
- Cite toujours le(s) document(s) source(s) utilisé(s) pour ta réponse, entre parenthèses à la fin des phrases concernées.
- Réponds en français, de façon claire et concise."""


def build_prompt(question: str, chunks: list) -> str:
    """Construit le prompt utilisateur avec la question et le contexte récupéré."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"[Extrait {i} - Source: {chunk['source_document']}]\n{chunk['text']}")

    context_text = "\n\n".join(context_parts)

    prompt = f"""Contexte documentaire :

{context_text}

---

Question du consultant : {question}

Réponds à la question en te basant uniquement sur le contexte ci-dessus."""

    return prompt


def generate_answer(question: str, chunks: list) -> str:
    """Appelle Claude avec le contexte pour générer une réponse sourcée."""
    user_prompt = build_prompt(question, chunks)

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "temperature": 0,  # anticipation Bug 1 : réduit les hallucinations
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_prompt}
        ]
    })

    response = bedrock.invoke_model(
        modelId=GENERATION_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def ask(question: str):
    """Pipeline RAG complet : retrieval (US 3.1) + génération (US 3.2)."""
    print(f"Question : {question}\n")

    print("🔍 Recherche des documents pertinents...")
    chunks = search_similar_chunks(question)

    if not chunks:
        print("Aucun document pertinent trouvé.")
        return

    print(f"   {len(chunks)} extrait(s) trouvé(s) :")
    for c in chunks:
        print(f"   - {c['source_document']} (score: {c['score']:.4f})")

    print("\n🤖 Génération de la réponse...\n")
    answer = generate_answer(question, chunks)

    print("=== Réponse ===")
    print(answer)


def main():
    print("=== US 3.2 : Moteur RAG complet (Retrieval + Génération) ===\n")

    # Question de test - à personnaliser
    test_question = "Comment configurer la dimensionnalité d'un index vectoriel OpenSearch ?"
    ask(test_question)

    # Test supplémentaire : une question SANS réponse dans les documents,
    # pour vérifier que Claude admet ne pas savoir plutôt que d'halluciner
    print("\n\n" + "=" * 60)
    print("Test anti-hallucination (question hors sujet) :")
    print("=" * 60 + "\n")
    ask("Quelle est la capitale de la France ?")


if __name__ == "__main__":
    main()