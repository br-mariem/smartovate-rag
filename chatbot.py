"""
US 4.1 : Interface Chatbot Web
Interface Streamlit connectée à l'API backend FastAPI.
- Maintient l'historique de conversation pendant la session
- Affiche la réponse de l'IA ainsi que les liens vers les documents sources
"""

import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Smartovate RAG - Assistant Documentaire", page_icon="🔎")

st.title("🔎 Assistant Documentaire Smartovate")
st.caption("Posez une question sur la base de connaissances interne (procédures, retours d'expérience, fiches techniques).")

# --- Initialisation de l'historique de conversation (persiste pendant la session) ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Affichage de l'historique existant ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "sources" in message:
            with st.expander("📄 Sources utilisées"):
                for source in message["sources"]:
                    st.markdown(f"**{source['source_document']}** (pertinence : {source['score']:.2f})")
                    st.caption(source["text"][:250] + "...")

# --- Saisie d'une nouvelle question ---
question = st.chat_input("Posez votre question...")

if question:
    # Affiche immédiatement la question de l'utilisateur
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Appelle l'API backend et affiche la réponse
    with st.chat_message("assistant"):
        with st.spinner("Recherche dans la base documentaire et génération de la réponse..."):
            try:
                response = requests.post(
                    f"{API_URL}/ask",
                    json={"question": question},
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()

                answer = data["answer"]
                sources = data["sources"]

                st.markdown(answer)

                if sources:
                    with st.expander("📄 Sources utilisées"):
                        for source in sources:
                            st.markdown(f"**{source['source_document']}** (pertinence : {source['score']:.2f})")
                            st.caption(source["text"][:250] + "...")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                })

            except requests.exceptions.ConnectionError:
                error_msg = "⚠️ Impossible de contacter l'API backend. Vérifiez qu'elle est bien lancée (python main.py)."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            except Exception as e:
                error_msg = f"⚠️ Une erreur est survenue : {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# --- Bouton pour réinitialiser la conversation ---
with st.sidebar:
    st.header("Options")
    if st.button("🗑️ Nouvelle conversation"):
        st.session_state.messages = []
        st.rerun()