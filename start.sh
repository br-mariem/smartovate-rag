#!/bin/bash
# Lance l'API FastAPI en arrière-plan (port interne 8000)
python main.py &

# Lance Streamlit au premier plan, exposé sur le port attendu par App Runner
streamlit run chatbot.py --server.port=${PORT:-8080} --server.address=0.0.0.0 --server.headless=true