FROM python:3.11-slim

WORKDIR /app

# Installe les dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copie et installe les dépendances Python (couche mise en cache séparément du code)
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

# Copie le code de l'application
COPY main.py search.py generate.py chatbot.py start.sh ./
COPY .streamlit/ .streamlit/

RUN chmod +x start.sh

# Port exposé (Streamlit, accessible publiquement)
EXPOSE 8080

CMD ["bash", "start.sh"]