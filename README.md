# Smartovate RAG — Assistant Documentaire Interne

Système de Retrieval-Augmented Generation (RAG) permettant aux consultants de Smartovate Ltd. d'interroger en langage naturel une base documentaire interne (fiches techniques, procédures, retours d'expérience), plutôt que de chercher manuellement dans des documents dispersés.

## Aperçu

- **Domaines couverts** : Cloud/AWS, Développement, Data, Sécurité, DevOps/Infra
- **Corpus** : 53 documents (fiches techniques, procédures internes, retours d'expérience)
- **Anti-hallucination** : le système répond uniquement à partir du contenu indexé et signale explicitement quand une information n'est pas disponible

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│  Documents  │ ───► │  Pipeline    │ ───► │  Amazon         │
│  (S3 raw/)  │      │  d'ingestion │      │  OpenSearch     │
└─────────────┘      └──────────────┘      │  Serverless     │
                                            └────────┬────────┘
                                                     │
┌─────────────┐      ┌──────────────┐               │
│  Streamlit  │ ◄──► │   FastAPI    │ ◄─────────────┘
│  (frontend) │      │   (backend)  │      Amazon Bedrock
└─────────────┘      └──────────────┘      (Claude + Titan Embeddings)
```

### Pipeline d'ingestion (offline)

| Script | Rôle | Outils clés |
|---|---|---|
| `extract_documents.py` | Extraction du texte (PDF/DOCX/MD) en préservant la structure | `unstructured` (stratégie `hi_res` + Tesseract OCR) |
| `chunk_and_embed.py` | Découpage en chunks (~800 tokens, overlap 80) + vectorisation | `tiktoken`, Amazon Bedrock (Titan Embeddings V2) |
| `load_to_opensearch.py` | Indexation des chunks + vecteurs dans OpenSearch | `opensearch-py`, boto3 |

### Moteur RAG (runtime)

| Script | Rôle |
|---|---|
| `search.py` | Recherche sémantique Top-K dans OpenSearch à partir d'une question |
| `generate.py` | Génération de la réponse (Amazon Bedrock — Claude) à partir des chunks trouvés |
| `main.py` | API FastAPI exposant `/health` et `/ask`, orchestrant recherche + génération |
| `chatbot.py` | Interface Streamlit (thème sombre, historique multi-conversations) |

### Infrastructure (IaC)

- `infra/` : stack AWS CDK (Python) définissant la collection OpenSearch Serverless, les security policies (encryption, réseau, accès aux données), l'index k-NN, et un paramètre SSM exposant dynamiquement l'endpoint de la collection.

## Prérequis

- Python 3.11+
- Node.js (pour AWS CDK)
- Docker Desktop
- Un compte AWS avec les services suivants activés : S3, Bedrock, OpenSearch Serverless, IAM, SSM, ECR, ECS
- AWS CLI configuré (`aws configure`)

## Installation

```powershell
git clone https://github.com/br-mariem/smartovate-rag.git
cd smartovate-rag
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Déploiement de l'infrastructure

```powershell
cd infra
pip install aws-cdk-lib constructs
cdk deploy
```

Ceci crée la collection OpenSearch Serverless, l'index vectoriel, et publie l'endpoint dans SSM Parameter Store (`/smartovate-rag/opensearch-endpoint`), lu dynamiquement par les scripts applicatifs.

> **Coût** : pensez à faire `cdk destroy` entre deux sessions de travail pour libérer la facturation OpenSearch Serverless. Les données (documents source, embeddings) restent en sécurité dans S3.

## Alimenter le corpus

1. Déposez vos documents (PDF/DOCX/MD) dans le préfixe `raw/` du bucket S3
2. Lancez le pipeline d'ingestion dans l'ordre :

```powershell
python extract_documents.py
python chunk_and_embed.py
python load_to_opensearch.py
```

## Lancer l'application en local

Dans deux terminaux séparés :

```powershell
# Terminal 1 — Backend
python main.py

# Terminal 2 — Frontend
streamlit run chatbot.py
```

- API disponible sur `http://127.0.0.1:8000` (documentation interactive sur `/docs`)
- Interface sur `http://localhost:8501`

## Déploiement en production (ECS Express Mode)

```powershell
aws ecr get-login-password --region eu-north-1 | docker login --username AWS --password-stdin <votre-registry-ecr>
docker build -t smartovate-rag-app .
docker tag smartovate-rag-app:latest <votre-registry-ecr>/smartovate-rag-app:latest
docker push <votre-registry-ecr>/smartovate-rag-app:latest
```

Puis, dans la console ECS, mettez à jour le service Express Mode existant en cochant **"Forcer un nouveau déploiement"** (ou créez-en un nouveau si le service a été supprimé pour économiser les coûts entre sessions).

## Limites connues

- La recherche sémantique (Top-K) peut occasionnellement remonter des documents proches en vocabulaire mais hors sujet (ex: confusion entre "versioning S3" et "gestion de versions Git") — l'étape de génération filtre correctement ces faux positifs dans la réponse finale.
- Chaque document du corpus actuel tient dans un seul chunk (~500-700 tokens) ; le découpage multi-chunks avec overlap n'a pas encore été testé sur des documents plus longs.

## Structure du projet

```
smartovate-rag/
├── infra/                      # Infrastructure as Code (AWS CDK)
├── .streamlit/config.toml      # Thème de l'interface Streamlit
├── extract_documents.py        # US 1.1 — Extraction
├── chunk_and_embed.py          # US 1.2 — Chunking + Embeddings
├── load_to_opensearch.py       # US 2.2 — Indexation
├── search.py                   # US 3.1 — Recherche sémantique
├── generate.py                 # US 3.2 — Génération de réponse
├── main.py                     # US 4.2 — API FastAPI
├── chatbot.py                  # US 4.1 — Interface Streamlit
├── Dockerfile
├── requirements.txt / requirements-app.txt
└── start.sh
```

## Stack technique

- **Backend** : Python, FastAPI, LangChain (chunking)
- **IA** : Amazon Bedrock (Claude pour la génération, Titan Embeddings V2 pour la vectorisation)
- **Recherche vectorielle** : Amazon OpenSearch Serverless (k-NN, HNSW, cosine similarity)
- **Frontend** : Streamlit
- **Infrastructure** : AWS CDK (Python), Amazon ECS Express Mode, Amazon ECR
- **Stockage** : Amazon S3

---

*Projet réalisé dans le cadre d'un stage chez Smartovate Ltd.*
