"""
US 4.1 : Interface Chatbot Web — Assistant Documentaire Smartovate
Interface Streamlit connectée à l'API backend FastAPI.
- Thème futuriste (fond sombre, accents néon)
- Historique multi-conversations persistant (fichier local chat_history.json)
- Bouton "Nouveau chat" pour démarrer une conversation vierge
- Affiche la réponse de l'IA ainsi que les sources documentaires utilisées
"""

import streamlit as st
import requests
import json
import os
import uuid
from datetime import datetime

API_URL = "http://127.0.0.1:8000"
HISTORY_FILE = "chat_history.json"

st.set_page_config(
    page_title="Smartovate RAG - Assistant Documentaire",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# STYLE — Thème futuriste (fond sombre, accents néon cyan/violet)
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
}

/* Titre principal avec effet néon (accent visuel, le thème sombre de base
   est géré par .streamlit/config.toml) */
h1 {
    background: linear-gradient(90deg, #00e5ff 0%, #7c5cff 50%, #ff5cf1 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 700 !important;
    text-shadow: 0 0 30px rgba(0, 229, 255, 0.25);
}

/* Bulles de chat utilisateur */
[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
    background: linear-gradient(135deg, rgba(124, 92, 255, 0.15) 0%, rgba(0, 229, 255, 0.08) 100%);
    border: 1px solid rgba(124, 92, 255, 0.35);
    border-radius: 14px;
    padding: 4px 8px;
}

/* Bulles de chat assistant */
[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
    background: rgba(0, 229, 255, 0.06);
    border: 1px solid rgba(0, 229, 255, 0.25);
    border-radius: 14px;
    padding: 4px 8px;
    box-shadow: 0 0 20px rgba(0, 229, 255, 0.06);
}

/* Bouton "Nouveau chat" mis en avant avec un dégradé plein */
.new-chat-btn button {
    background: linear-gradient(90deg, #00e5ff 0%, #7c5cff 100%) !important;
    color: #05070c !important;
    font-weight: 700 !important;
    border: none !important;
}
.new-chat-btn button:hover {
    box-shadow: 0 0 20px rgba(0, 229, 255, 0.55) !important;
}

/* Entrée active dans l'historique */
.history-item-active button {
    border: 1px solid rgba(124, 92, 255, 0.6) !important;
    color: #ffffff !important;
}

/* Séparateur et libellés de la sidebar */
.sidebar-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,229,255,0.3), transparent);
    margin: 14px 0;
}
.sidebar-section-label {
    color: #5a6b8c;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    margin: 6px 0 4px 4px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# PERSISTANCE — Historique multi-conversations (fichier local)
# ============================================================
def load_history():
    """Charge toutes les conversations sauvegardées depuis le disque."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_history(history):
    """Sauvegarde toutes les conversations sur le disque."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def create_new_conversation():
    """Crée une nouvelle conversation vide et l'active.
    Supprime d'abord toute conversation vide existante (non envoyée) pour éviter
    l'accumulation d'entrées 'Nouvelle conversation' vides dans l'historique."""
    empty_ids = [cid for cid, c in st.session_state.all_chats.items() if not c["messages"]]
    for cid in empty_ids:
        del st.session_state.all_chats[cid]

    new_id = str(uuid.uuid4())
    st.session_state.all_chats[new_id] = {
        "title": "Nouvelle conversation",
        "created_at": datetime.now().isoformat(),
        "messages": [],
    }
    st.session_state.current_chat_id = new_id
    save_history(st.session_state.all_chats)


def get_conversation_title(messages):
    """Génère un titre court à partir de la première question posée."""
    for m in messages:
        if m["role"] == "user":
            title = m["content"].strip()
            return title[:45] + ("..." if len(title) > 45 else "")
    return "Nouvelle conversation"


# --- Initialisation de l'état de session ---
if "all_chats" not in st.session_state:
    st.session_state.all_chats = load_history()
    # Nettoyage : retire les conversations vides résiduelles (ex: anciens bugs, clics multiples)
    empty_ids = [cid for cid, c in st.session_state.all_chats.items() if not c["messages"]]
    for cid in empty_ids:
        del st.session_state.all_chats[cid]
    if empty_ids:
        save_history(st.session_state.all_chats)

if "current_chat_id" not in st.session_state or st.session_state.current_chat_id not in st.session_state.all_chats:
    if st.session_state.all_chats:
        # Reprend la conversation la plus récente
        most_recent_id = max(
            st.session_state.all_chats,
            key=lambda cid: st.session_state.all_chats[cid]["created_at"],
        )
        st.session_state.current_chat_id = most_recent_id
    else:
        create_new_conversation()


# ============================================================
# SIDEBAR — Historique des chats + bouton nouveau chat
# ============================================================
with st.sidebar:
    st.markdown("### 🔎 Smartovate RAG")

    st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
    if st.button("＋  Nouveau chat", use_container_width=True):
        create_new_conversation()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-label">Historique</div>', unsafe_allow_html=True)

    # Trie les conversations de la plus récente à la plus ancienne
    sorted_chat_ids = sorted(
        st.session_state.all_chats,
        key=lambda cid: st.session_state.all_chats[cid]["created_at"],
        reverse=True,
    )

    if not sorted_chat_ids:
        st.caption("Aucune conversation pour le moment.")

    for chat_id in sorted_chat_ids:
        chat = st.session_state.all_chats[chat_id]
        title = get_conversation_title(chat["messages"]) if chat["messages"] else "Nouvelle conversation"
        is_active = chat_id == st.session_state.current_chat_id
        css_class = "history-item-active" if is_active else "history-item"

        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
            if st.button(f"💬 {title}", key=f"select_{chat_id}", use_container_width=True):
                st.session_state.current_chat_id = chat_id
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
            delete_clicked = st.button("🗑️", key=f"delete_{chat_id}", help="Supprimer cette conversation")
            st.markdown('</div>', unsafe_allow_html=True)
            if delete_clicked:
                del st.session_state.all_chats[chat_id]
                save_history(st.session_state.all_chats)
                if chat_id == st.session_state.current_chat_id:
                    if st.session_state.all_chats:
                        st.session_state.current_chat_id = sorted(
                            st.session_state.all_chats,
                            key=lambda cid: st.session_state.all_chats[cid]["created_at"],
                            reverse=True,
                        )[0]
                    else:
                        create_new_conversation()
                st.rerun()

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.caption("Assistant documentaire interne — Smartovate Ltd.")


# ============================================================
# ZONE PRINCIPALE — Conversation active
# ============================================================
current_chat = st.session_state.all_chats[st.session_state.current_chat_id]

st.title("🔎 Assistant Documentaire Smartovate")
st.caption("Posez une question sur la base de connaissances interne (procédures, retours d'expérience, fiches techniques).")

# --- Affichage de l'historique de la conversation active ---
for message in current_chat["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("sources"):
            with st.expander("📄 Sources utilisées"):
                for source in message["sources"]:
                    st.markdown(f"**{source['source_document']}** (pertinence : {source['score']:.2f})")
                    st.caption(source["text"][:250] + "...")

# --- Saisie d'une nouvelle question ---
question = st.chat_input("Posez votre question...")

if question:
    current_chat["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

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

                current_chat["messages"].append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                })

            except requests.exceptions.ConnectionError:
                error_msg = "⚠️ Impossible de contacter l'API backend. Vérifiez qu'elle est bien lancée (python main.py)."
                st.error(error_msg)
                current_chat["messages"].append({"role": "assistant", "content": error_msg})
            except Exception as e:
                error_msg = f"⚠️ Une erreur est survenue : {str(e)}"
                st.error(error_msg)
                current_chat["messages"].append({"role": "assistant", "content": error_msg})

    # Sauvegarde après chaque échange
    save_history(st.session_state.all_chats)
    st.rerun()