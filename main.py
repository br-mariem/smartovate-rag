"""
API Backend FastAPI - Orchestration du flux RAG
Expose le moteur RAG (recherche + génération) via une API HTTP,
que le frontend Streamlit viendra consommer.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from search import search_similar_chunks
from generate import generate_answer

app = FastAPI(
    title="Smartovate RAG API",
    description="API du système RAG interne - recherche et génération de réponses sourcées",
    version="1.0.0",
)

# Autorise le frontend Streamlit (local, autre port) à appeler cette API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # simplifié pour ce PoC de dev ; à restreindre en production
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


class SourceChunk(BaseModel):
    source_document: str
    score: float
    text: str


class AnswerResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceChunk]


@app.get("/health")
def health_check():
    """Endpoint de vérification de santé de l'API (US 4.2 - critère d'acceptation)."""
    return {"status": "ok"}


@app.post("/ask", response_model=AnswerResponse)
def ask_question(request: QuestionRequest):
    """
    Pipeline RAG complet : recherche sémantique (US 3.1) + génération (US 3.2).
    Reçoit une question, retourne une réponse sourcée avec les extraits utilisés.
    """
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide.")

    try:
        chunks = search_similar_chunks(request.question)
        answer_text = generate_answer(request.question, chunks)

        sources = [
            SourceChunk(
                source_document=c["source_document"],
                score=c["score"],
                text=c["text"][:300],  # extrait tronqué pour l'affichage
            )
            for c in chunks
        ]

        return AnswerResponse(
            question=request.question,
            answer=answer_text,
            sources=sources,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement : {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)