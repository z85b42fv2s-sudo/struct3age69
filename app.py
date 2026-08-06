from pathlib import Path
import hashlib
import streamlit as st
import pandas as pd
from datetime import datetime
import logic
import ai_handler
import synthesis
import report_generator
import regulation_handler

import os
from dotenv import load_dotenv

# Configurazione pagina Streamlit: deve essere la prima chiamata `st.*`
st.set_page_config(
    page_title="Structure3Age | Analisi strutturale e report AI",
    page_icon="🧱",
    layout="wide"
)

# In produzione evitiamo di invalidare cache/reload ad ogni rerun
# (impatta molto i tempi di avvio).

# Carica variabili d'ambiente dal file .env solo in locale (se presente)
try:
    load_dotenv(override=True)
except Exception:
    pass

APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "").strip()
APP_CONTACT_EMAIL = os.getenv("APP_CONTACT_EMAIL", "fabrizio.marrone.ing@gmail.com").strip()

USERS_FILE = "users.csv"
PROFESSIONALS_FILE = "professionisti.csv"
USER_USAGE_LIMIT = 6
TRIAL_DAYS = 3
SUBSCRIPTION_PRICE = 9.90
STRIPE_PUBLIC_KEY = "mk_1ShT5mAHjVSlqjiBcdK8asiZ"
STRIPE_SECRET_KEY = "mk_1ShT6iAHjVSlqjiBN9zJb2tO"


@st.cache_data(ttl=15)
def load_users():
    required = [
        "email",
        "password_hash",
        "created_at",
        "credits_total",
        "credits_left",
        "last_login",
        "abbonato",
        "verified",
    ]
    try:
        df = pd.read_csv(USERS_FILE)
        if df.empty:
            df = pd.DataFrame(columns=required)
        else:
            for col in required:
                if col not in df.columns:
                    if col in {"credits_total", "credits_left"}:
                        df[col] = USER_USAGE_LIMIT
                    elif col in {"abbonato", "verified"}:
                        df[col] = False
                    else:
                        df[col] = ""

        for col in ["email", "password_hash", "created_at", "last_login"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)
                df[col] = df[col].replace({"nan": "", "None": ""})

        for col in ["credits_total", "credits_left"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(USER_USAGE_LIMIT).astype(int)

        df["abbonato"] = df["abbonato"].apply(lambda value: str(value).strip().lower() in {"true", "1", "yes", "si"})
        df["verified"] = df["verified"].apply(lambda value: str(value).strip().lower() in {"true", "1", "yes", "si"})

        # Persist the migrated schema so future runs are consistent.
        df.to_csv(USERS_FILE, index=False)
        return df
    except Exception:
        df = pd.DataFrame(columns=required)
        df.to_csv(USERS_FILE, index=False)
        return df


def invalidate_users_cache():
    try:
        load_users.clear()
    except Exception:
        pass


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def find_user_row(email: str):
    users_df = load_users()
    email_norm = email.strip().lower()
    user_row = users_df[users_df["email"].astype(str).str.lower() == email_norm]
    if user_row.empty:
        return users_df, None, None
    return users_df, user_row.index[0], user_row.iloc[0]


def register_user(email: str, password: str):
    email_norm = email.strip().lower()
    if not email_norm or "@" not in email_norm:
        return False, "Inserisci una email valida."
    if not password or len(password) < 6:
        return False, "La password deve avere almeno 6 caratteri."

    users_df, idx, user = find_user_row(email_norm)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    password_hash = hash_password(password)

    if user is not None:
        existing_hash = str(user.get("password_hash", "")).strip()
        if existing_hash:
            return False, "Email già registrata. Accedi con la tua password."

        users_df.at[idx, "password_hash"] = password_hash
        users_df.at[idx, "created_at"] = now if not str(user.get("created_at", "")).strip() else str(user.get("created_at", ""))
        users_df.at[idx, "credits_total"] = USER_USAGE_LIMIT
        users_df.at[idx, "credits_left"] = USER_USAGE_LIMIT
        users_df.at[idx, "last_login"] = now
    else:
        new_row = {
            "email": email_norm,
            "password_hash": password_hash,
            "created_at": now,
            "credits_total": USER_USAGE_LIMIT,
            "credits_left": USER_USAGE_LIMIT,
            "last_login": now,
            "abbonato": False,
            "verified": True,
        }
        users_df = pd.concat([users_df, pd.DataFrame([new_row])], ignore_index=True)

    users_df.to_csv(USERS_FILE, index=False)
    invalidate_users_cache()
    return True, "Account creato con successo."


def authenticate_user(email: str, password: str):
    email_norm = email.strip().lower()
    if not email_norm or "@" not in email_norm:
        return False, "Inserisci una email valida."
    if not password:
        return False, "Inserisci la password."

    users_df, idx, user = find_user_row(email_norm)
    if user is None:
        return False, "Email non trovata. Registrati prima."

    stored_hash = str(user.get("password_hash", "")).strip()
    if not stored_hash:
        return False, "Account senza password: registralo di nuovo con la password scelta."

    if hash_password(password) != stored_hash:
        return False, "Password errata."

    users_df.at[idx, "last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    users_df.to_csv(USERS_FILE, index=False)
    invalidate_users_cache()
    return True, "Accesso effettuato."


def get_user_credit_status(email: str):
    email_norm = email.strip().lower()
    if email_norm == "demo@demo.it":
        return 999999, 999999
    _, _, user = find_user_row(email)
    if user is None:
        return 0, USER_USAGE_LIMIT
    return int(user.get("credits_left", USER_USAGE_LIMIT)), int(user.get("credits_total", USER_USAGE_LIMIT))


def consume_ai_credit(email: str, amount: int = 1):
    email_norm = email.strip().lower()
    if email_norm == "demo@demo.it":
        return True, 999999
    users_df, idx, user = find_user_row(email)
    if user is None:
        return False, 0

    remaining = int(user.get("credits_left", USER_USAGE_LIMIT))
    if remaining < amount:
        return False, remaining

    remaining -= amount
    users_df.at[idx, "credits_left"] = remaining
    users_df.to_csv(USERS_FILE, index=False)
    invalidate_users_cache()
    return True, remaining


def render_auth_panel(ui, key_prefix: str = "sidebar"):
    ui.markdown("### Accedi o registrati")
    ui.write("Crea un account con email e password. Non serve alcun codice di conferma.")

    with ui.form(f"{key_prefix}_login_form"):
        login_email = ui.text_input("Email", placeholder="nome@dominio.it", key=f"{key_prefix}_login_email")
        login_password = ui.text_input("Password", type="password", key=f"{key_prefix}_login_password")
        login_submit = st.form_submit_button("Accedi")
        if login_submit:
            ok, msg = authenticate_user(login_email, login_password)
            if ok:
                st.session_state.current_user_email = login_email.strip().lower()
                st.session_state["current_user_credits"] = get_user_credit_status(login_email)[0]
                ui.success(msg)
                st.rerun()
            else:
                ui.error(msg)

    with ui.form(f"{key_prefix}_register_form"):
        register_email = ui.text_input("Email per registrazione", placeholder="nome@dominio.it", key=f"{key_prefix}_register_email")
        register_password = ui.text_input("Scegli password", type="password", key=f"{key_prefix}_register_password")
        register_password_confirm = ui.text_input("Conferma password", type="password", key=f"{key_prefix}_register_password_confirm")
        register_submit = st.form_submit_button("Crea account")
        if register_submit:
            if register_password != register_password_confirm:
                ui.error("Le password non coincidono.")
            else:
                ok, msg = register_user(register_email, register_password)
                if ok:
                    st.session_state.current_user_email = register_email.strip().lower()
                    st.session_state["current_user_credits"] = get_user_credit_status(register_email)[0]
                    ui.success(msg)
                    st.rerun()
                else:
                    ui.error(msg)


@st.cache_data(ttl=300)
def load_professionals():
    try:
        df = pd.read_csv(PROFESSIONALS_FILE)
        required = ["nome", "categoria", "zona", "telefono", "sito", "note"]
        if not all(col in df.columns for col in required):
            return pd.DataFrame(columns=required)
        for col in required:
            df[col] = df[col].fillna("").astype(str)
        if "sempre_visibile" not in df.columns:
            df["sempre_visibile"] = False
        df["sempre_visibile"] = df["sempre_visibile"].apply(lambda value: str(value).strip().lower() in {"true", "1", "yes", "si"})
        return df
    except Exception:
        return pd.DataFrame(columns=["nome", "categoria", "zona", "telefono", "sito", "note", "sempre_visibile"])


def suggest_professionals(localita: str, categoria: str = ""):
    df = load_professionals()
    if df.empty:
        return df
    df = df.copy()
    always_visible = df[df["sempre_visibile"]]
    normal_df = df[~df["sempre_visibile"]].copy()

    if categoria and categoria != "Tutte":
        normal_df = normal_df[normal_df["categoria"].str.lower() == categoria.strip().lower()]

    if localita:
        localita_norm = localita.strip().lower()
        normal_df = normal_df[normal_df["zona"].str.lower().str.contains(localita_norm, na=False)]

    filtered = pd.concat([normal_df, always_visible], ignore_index=True)
    if filtered.empty:
        return filtered

    filtered = filtered.drop_duplicates(subset=["nome", "telefono", "sito", "zona"])
    return filtered


def render_professionals_section(localita_value: str):
    categoria_prof = st.selectbox(
        "Tipo di professionista",
        ["Tutte", "Ingegnere Strutturista", "Studio Tecnico Ingegneristico", "Impresa Edile", "Geologo", "Diagnostica Strutturale"],
        key="categoria_prof_select",
    )

    all_professionals = load_professionals()
    featured_professionals = all_professionals[all_professionals["sempre_visibile"]] if not all_professionals.empty else pd.DataFrame()

    if not featured_professionals.empty:
        st.markdown("### ⭐ Uffici in evidenza")
        for _, row in featured_professionals.iterrows():
            sito = row.get("sito", "").strip() or "—"
            telefono = row.get("telefono", "").strip() or "—"
            note = row.get("note", "").strip() or "—"
            categoria = row.get("categoria", "").strip() or "—"
            zona = row.get("zona", "").strip() or "—"

            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(135deg, rgba(14,116,144,0.14), rgba(15,23,42,0.96));
                    border: 1px solid rgba(56,189,248,0.4);
                    border-radius: 18px;
                    padding: 18px 20px;
                    margin: 0 0 16px 0;
                    box-shadow: 0 10px 25px rgba(15,23,42,0.18);
                    color: #F8FAFC;
                ">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;">
                        <div>
                            <div style="font-size:20px;font-weight:800;letter-spacing:0.2px;">{row['nome']}</div>
                            <div style="margin-top:6px;font-size:13px;color:#BAE6FD;">{categoria}</div>
                        </div>
                        <div style="background:rgba(56,189,248,0.18);color:#7DD3FC;padding:6px 12px;border-radius:999px;font-size:12px;font-weight:700;">
                            Sempre visibile
                        </div>
                    </div>
                    <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                        <div style="background:rgba(255,255,255,0.05);padding:10px 12px;border-radius:12px;">
                            <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;">Zona operativa</div>
                            <div style="font-size:14px;margin-top:2px;">{zona}</div>
                        </div>
                        <div style="background:rgba(255,255,255,0.05);padding:10px 12px;border-radius:12px;">
                            <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;">Telefono</div>
                            <div style="font-size:14px;margin-top:2px;">{telefono}</div>
                        </div>
                        <div style="background:rgba(255,255,255,0.05);padding:10px 12px;border-radius:12px;">
                            <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;">Sito web</div>
                            <div style="font-size:14px;margin-top:2px;">{sito}</div>
                        </div>
                        <div style="background:rgba(255,255,255,0.05);padding:10px 12px;border-radius:12px;">
                            <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;">Note</div>
                            <div style="font-size:14px;margin-top:2px;">{note}</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if st.button("Trova professionisti in zona", key="trova_professionisti_button"):
        risultati_prof = suggest_professionals(localita_value, categoria_prof)
        non_featured = risultati_prof[~risultati_prof["sempre_visibile"]] if not risultati_prof.empty else risultati_prof

        if non_featured.empty:
            st.info("Nessun risultato locale aggiuntivo trovato. Gli uffici in evidenza restano visibili sopra.")
        else:
            st.success(f"Trovati {len(non_featured)} professionisti locali.")
            for _, row in non_featured.iterrows():
                sito = row.get("sito", "").strip() or "—"
                telefono = row.get("telefono", "").strip() or "—"
                note = row.get("note", "").strip() or "—"
                categoria = row.get("categoria", "").strip() or "—"
                zona = row.get("zona", "").strip() or "—"

                st.markdown(
                    f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(15,23,42,0.96), rgba(30,41,59,0.96));
                        border: 1px solid rgba(148,163,184,0.35);
                        border-radius: 18px;
                        padding: 18px 20px;
                        margin: 0 0 16px 0;
                        box-shadow: 0 10px 25px rgba(15,23,42,0.18);
                        color: #F8FAFC;
                    ">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;">
                            <div>
                                <div style="font-size:20px;font-weight:800;letter-spacing:0.2px;">{row['nome']}</div>
                                <div style="margin-top:6px;font-size:13px;color:#CBD5E1;">{categoria}</div>
                            </div>
                            <div style="background:rgba(34,197,94,0.15);color:#86EFAC;padding:6px 12px;border-radius:999px;font-size:12px;font-weight:700;">
                                Presenza locale
                            </div>
                        </div>
                        <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                            <div style="background:rgba(255,255,255,0.05);padding:10px 12px;border-radius:12px;">
                                <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;">Zona operativa</div>
                                <div style="font-size:14px;margin-top:2px;">{zona}</div>
                            </div>
                            <div style="background:rgba(255,255,255,0.05);padding:10px 12px;border-radius:12px;">
                                <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;">Telefono</div>
                                <div style="font-size:14px;margin-top:2px;">{telefono}</div>
                            </div>
                            <div style="background:rgba(255,255,255,0.05);padding:10px 12px;border-radius:12px;">
                                <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;">Sito web</div>
                                <div style="font-size:14px;margin-top:2px;">{sito}</div>
                            </div>
                            <div style="background:rgba(255,255,255,0.05);padding:10px 12px;border-radius:12px;">
                                <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;">Note</div>
                                <div style="font-size:14px;margin-top:2px;">{note}</div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def compute_uploaded_files_hash(uploaded_files):
    hasher = hashlib.sha256()
    for uploaded_file in uploaded_files or []:
        try:
            hasher.update(uploaded_file.name.encode("utf-8"))
            hasher.update(uploaded_file.getvalue())
        except Exception:
            continue
    return hasher.hexdigest()

# Meta tag Google Search Console (iniettato con component)
import streamlit.components.v1 as components

# --- PAGINA ISCRIZIONE E PAGAMENTO STRIPE ---
def pagina_iscrizione_pagamento():
    st.title("Registrazione e Accesso")
    st.write("Crea un account con email e password. Ogni account ha 6 utilizzi AI iniziali.")
    render_auth_panel(st, key_prefix="page")
    st.markdown("---")
    st.info("Ogni richiesta AI consuma un credito del tuo account. Quando i crediti finiscono, puoi richiederne l'aumento manualmente.")

# --- NAVIGAZIONE PAGINE ---
# Mostro il selettore subito, ma rimando la chiamata della pagina
selected_page = st.sidebar.selectbox("Naviga", ["App principale", "Registrazione / Accesso"])

components.html(
    """
    <head>
        <meta name=\"google-site-verification\" content=\"D-2hzr1YwD7pGFy_0r30wH3TuUFqkSpmXooJbX0_RlI\" />
    </head>
    """,
    height=0
)

st.markdown(
    """
    # Structure3Age
    Piattaforma per pre-screening strutturale, analisi visiva delle foto, sintesi finale del quadro tecnico e supporto normativo sulle NTC 2018.

    ## Cosa fa il servizio
    - Acquisisce i dati generali della struttura
    - Elabora le vulnerabilità attese in base a materiale, anno e contesto territoriale
    - Analizza le immagini della struttura con AI
    - Produce una sintesi finale e un report PDF scaricabile

    ## Ambito di utilizzo
    Servizio pensato per aiutare tecnici, committenti e studi professionali a raccogliere un primo quadro delle criticità strutturali prima di un sopralluogo approfondito.
    """
)

if APP_PUBLIC_URL:
    st.caption(f"Sito pubblico: {APP_PUBLIC_URL}")

st.caption(f"Contatti: {APP_CONTACT_EMAIL}")

st.markdown("---")
st.header("Accesso rapido")
st.info("Usa il pannello laterale per accedere o registrarti con email e password. Ogni account ha 6 crediti AI iniziali.")

st.markdown("---")
st.header("Professionisti Consigliati in Zona")
st.info("Indicazioni orientative: verifica sempre abilitazioni, referenze e preventivi prima di affidare incarichi.")
professionisti_localita = st.text_input("CAP o Comune per cercare professionisti", placeholder="Es. 20121 oppure Milano", key="professionisti_localita_public")
render_professionals_section(professionisti_localita)

# Se l'utente ha selezionato la pagina di registrazione, mostra solo il pannello dedicato
if 'selected_page' in globals() and selected_page == "Registrazione / Accesso":
    verification_file = Path("googlea850bad541d5794f.html")
    if verification_file.exists():
        with open(verification_file, "r", encoding="utf-8") as f:
            st.markdown(f.read(), unsafe_allow_html=True)
    pagina_iscrizione_pagamento()
    st.stop()

# --- ACCESSO / REGISTRAZIONE ---
st.sidebar.markdown("---")

if "current_user_email" not in st.session_state:
    st.session_state.current_user_email = ""

render_auth_panel(st.sidebar, key_prefix="sidebar")

username = st.session_state.current_user_email.strip().lower()
users_df = load_users() if username else pd.DataFrame()
user_row = users_df[users_df["email"].astype(str).str.lower() == username] if username else pd.DataFrame()
authentication_status = bool(username) and not user_row.empty and bool(str(user_row.iloc[0].get("password_hash", "")).strip())

if not authentication_status:
    st.info("Accedi o crea un account con email e password per continuare.")
    st.stop()

current_credits, total_credits = get_user_credit_status(username)
st.sidebar.success(f"Accesso attivo: {username}")
credit_label = "∞" if username == "demo@demo.it" else f"{current_credits}/{total_credits}"
st.sidebar.info(f"Crediti AI residui: {credit_label}")
if current_credits <= 0:
    st.sidebar.error("Crediti AI esauriti. Richiedi un reset o un upgrade manuale.")

if st.sidebar.button("Esci"):
    st.session_state.current_user_email = ""
    st.session_state.pop("current_user_credits", None)
    st.rerun()

st.title("Structural 3age - Analisi Condizione Strutture")





# Usa solo la variabile d'ambiente/secrets per la chiave OpenAI
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.sidebar.warning("Chiave OpenAI non trovata. Contatta l'amministratore.")
st.session_state["openai_api_key"] = api_key
st.session_state["openai_project"] = os.getenv("OPENAI_PROJECT")

# --- SEZIONE 1: Dati Generali ---
st.header("1. Dati Generali della Struttura")
col1, col2 = st.columns(2)

with col1:
    materiale = st.selectbox("Materiale Strutturale", ["Cemento Armato", "Muratura"])
    anno_costruzione = st.number_input("Anno di Costruzione", min_value=1800, max_value=2025, value=1970)
    zona_sismica = st.selectbox("Zona Sismica (1=Alta, 4=Bassa)", [1, 2, 3, 4])

with col2:
    tipo_terreno = st.selectbox("Categoria Sottosuolo (NTC 2018)", ["A", "B", "C", "D", "E"])
    categoria_topografica = st.selectbox("Categoria Topografica", ["T1", "T2", "T3", "T4"])
    localita_input = st.text_input("CAP o Comune", placeholder="Es. 20121 oppure Milano")

# --- SEZIONE 2: Vulnerabilità e Normativa ---
st.header("2. Valutazione Vulnerabilità e Normativa")
normativa, vulnerabilita = logic.get_vulnerabilities(anno_costruzione, materiale)

st.info(f"Normativa di riferimento probabile: **{normativa}**")
st.write("### Vulnerabilità Tipiche Attese:")
for v in vulnerabilita:
    st.write(f"- {v}")

# --- SEZIONE 4: Analisi AI delle Foto ---
st.header("4. Analisi AI delle Foto (Degrado e Fessurazioni)")
uploaded_files = st.file_uploader("Carica foto della struttura (viste d'insieme e dettagli)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

dati_generali = {
    "materiale": materiale,
    "anno": anno_costruzione,
    "zona_sismica": zona_sismica,
    "terreno": tipo_terreno,
    "topografia": categoria_topografica,
    "comune_cap": localita_input,
}

vulnerabilita_attese = {
    "normativa_probabile": normativa,
    "vulnerabilita_attese": vulnerabilita,
    "fonte": "logic.py",
}

files_to_use = st.session_state.get("uploaded_files", uploaded_files or [])
descrizione = st.session_state.get("analysis_result", "")

if uploaded_files:
    # Display uploaded images in a grid
    cols = st.columns(min(len(uploaded_files), 3))
    for i, file in enumerate(uploaded_files):
        with cols[i % 3]:
            st.image(file, caption=f"Foto {i+1}", use_container_width=True)
    
    if st.button("Analizza Foto con AI"):
        current_credits, _ = get_user_credit_status(username)
        if current_credits <= 0:
            st.error("Crediti AI esauriti. Non puoi avviare nuove analisi.")
        elif not api_key:
            st.error("Inserisci la chiave API di OpenAI nella sidebar per procedere.")
        else:
            with st.spinner("Analisi approfondita in corso (Stati Limite, Meccanismi, Interventi)..."):
                try:
                    project_id = os.getenv("OPENAI_PROJECT")
                    
                    # Prepare context info
                    context_info = {
                        "materiale": materiale,
                        "anno": anno_costruzione,
                        "zona_sismica": zona_sismica,
                        "terreno": tipo_terreno,
                        "normativa": normativa
                    }
                    
                    # Pass the list of files and context directly
                    descrizione = ai_handler.analyze_structure_image(uploaded_files, api_key, project_id, context_info)
                    if str(descrizione).startswith("Errore"):
                        st.error(descrizione)
                    else:
                        # Store in session state
                        st.session_state['analysis_result'] = descrizione
                        st.session_state['uploaded_files'] = uploaded_files
                        files_to_use = uploaded_files
                        success, remaining = consume_ai_credit(username)
                        if success:
                            st.session_state["current_user_credits"] = remaining
                    
                except Exception as e:
                    st.error(f"Errore durante l'analisi: {e}")

    # Check if analysis exists in session state
    if 'analysis_result' in st.session_state:
        descrizione = st.session_state['analysis_result']
        files_to_use = st.session_state.get('uploaded_files', uploaded_files)
        interventi_ai = ai_handler.extract_intervention_section(descrizione)

        st.markdown("### 📋 Report Analisi AI")
        st.write(descrizione)

        st.markdown("---")
        st.subheader("🛠️ Interventi Consigliati")
        if interventi_ai:
            st.markdown(interventi_ai)
        else:
            st.warning("La sezione interventi non è stata trovata nel testo AI generato.")
        st.info("Interventi estratti direttamente dalla risposta AI. Consultare sempre un ingegnere strutturista per il progetto esecutivo.")

        # --- COST ESTIMATION ---
        st.markdown("---")
        st.subheader("💰 Stima Parametrica Costi")
        if st.button("Calcola Stima Costi (Prezzari DEI/Regionali)"):
            current_credits, _ = get_user_credit_status(username)
            if current_credits <= 0:
                st.error("Crediti AI esauriti. Non puoi calcolare nuove stime.")
            if not api_key:
                st.error("Chiave API OpenAI non configurata.")
            else:
                with st.spinner("Calcolo stima parametrica in corso..."):
                    try:
                        project_id = os.getenv("OPENAI_PROJECT")
                        source_text = interventi_ai or descrizione
                        stima_costi = ai_handler.estimate_intervention_costs(source_text, api_key, project_id)
                        if str(stima_costi).startswith("Errore"):
                            st.error(stima_costi)
                        else:
                            st.markdown(stima_costi)
                            st.warning("⚠️ NOTA: I prezzi sono puramente indicativi e riferiti a medie di mercato. Non sostituiscono un computo metrico estimativo professionale.")
                            success, remaining = consume_ai_credit(username)
                            if success:
                                st.session_state["current_user_credits"] = remaining
                    except Exception as e:
                        st.error(f"Errore nella stima: {e}")

st.markdown("---")
st.subheader("3. Sintesi Finale / Report")
st.info("Questa sezione incrocia i dati generali, le vulnerabilità attese e l'analisi visiva AI in un'unica sintesi coerente.")

esito_visivo = {
    "presenza_foto": bool(files_to_use),
    "foto_hash": compute_uploaded_files_hash(files_to_use),
    "analisi_visiva_disponibile": bool(descrizione),
    "analisi_visiva": descrizione if descrizione else "Nessuna analisi visiva disponibile: sintesi basata solo su dati regolamentari.",
    "openai_ready": bool(api_key),
    "openai_project_presente": bool(os.getenv("OPENAI_PROJECT")),
}

if st.button("Genera / Aggiorna sintesi finale", key="genera_sintesi_finale_button"):
    try:
        current_credits, _ = get_user_credit_status(username)
        if current_credits <= 0:
            st.error("Crediti AI esauriti. Non puoi generare nuove sintesi.")
        elif not api_key:
            st.error("Chiave API OpenAI non configurata.")
        else:
            final_synthesis = synthesis.generate_final_synthesis(dati_generali, vulnerabilita_attese, esito_visivo)
            if str(final_synthesis.get("quadro_sintetico", "")).startswith("Sintesi finale non disponibile"):
                st.error(final_synthesis.get("quadro_sintetico", "Sintesi finale non disponibile."))
            else:
                st.session_state["final_synthesis"] = final_synthesis
                success, remaining = consume_ai_credit(username)
                if success:
                    st.session_state["current_user_credits"] = remaining
    except Exception as e:
        st.error(f"Errore nella generazione della sintesi finale: {e}")

final_synthesis = st.session_state.get("final_synthesis")

if final_synthesis:
    st.markdown("### 🧩 Quadro sintetico")
    st.write(final_synthesis.get("quadro_sintetico", ""))

    st.markdown("### 🔎 Vulnerabilità attese vs riscontrate")
    tabella_vulnerabilita = final_synthesis.get("tabella_vulnerabilita", [])
    if tabella_vulnerabilita:
        st.table(pd.DataFrame(tabella_vulnerabilita))
    else:
        st.info("Nessuna tabella vulnerabilità disponibile nella sintesi finale.")

    st.markdown("### ⚠️ Indizio di attenzione complessivo")
    st.write(final_synthesis.get("indizio_attenzione", "media").upper())
    st.write(final_synthesis.get("motivazione_indizio", ""))

    st.markdown("### ✅ Prossimi passi consigliati")
    for passo in final_synthesis.get("prossimi_passi", []):
        st.write(f"- {passo}")

    st.caption(final_synthesis.get("disclaimer", ""))
else:
    st.warning("Premi il pulsante per generare la sintesi finale automatizzata.")

# --- PDF GENERATION ---
st.markdown("---")
st.subheader("📄 Scarica Report")

report_data = {
    "materiale": materiale,
    "anno": anno_costruzione,
    "zona_sismica": zona_sismica,
    "terreno": tipo_terreno,
    "topografia": categoria_topografica,
    "normativa": normativa,
    "localita": localita_input,
}

pdf_bytes = report_generator.generate_pdf(report_data, descrizione, files_to_use, final_synthesis, interventi_ai)

st.download_button(
    label="📥 Scarica Report PDF",
    data=pdf_bytes,
    file_name="report_structural_3age.pdf",
    mime="application/pdf",
)

# --- SEZIONE 5: Assistente Normativo ---
st.markdown("---")
st.header("5. 📚 Assistente Normativo (RAG)")
st.info("Fai una domanda sulle NTC 2018 o sui documenti caricati. L'AI cercherà la risposta nei PDF.")

question = st.text_input("Domanda (es. 'Quali sono i limiti per i nodi non confinati?')")

if st.button("Chiedi all'Assistente"):
    current_credits, _ = get_user_credit_status(username)
    if current_credits <= 0:
        st.error("Crediti AI esauriti. Non puoi fare nuove domande all'assistente.")
    elif not api_key:
        st.error("Inserisci la chiave API per continuare.")
    elif not question:
        st.warning("Scrivi una domanda prima di procedere.")
    else:
        with st.spinner("Ricerca nei documenti normativi in corso..."):
            try:
                normativa_dir = os.path.join(os.getcwd(), "normativa")
                # Load documents (cached)
                docs = regulation_handler.load_regulation_text(normativa_dir)
                
                if not docs:
                    st.error("Nessun documento trovato nella cartella 'normativa'.")
                else:
                    # Retrieve context
                    relevant_docs = regulation_handler.retrieve_relevant_context(question, docs)
                    
                    if not relevant_docs:
                        st.warning("Nessun contenuto rilevante trovato nei documenti per questa domanda.")
                    else:
                        # Ask AI
                        project_id = os.getenv("OPENAI_PROJECT")
                        risposta = regulation_handler.ask_regulation_assistant(question, relevant_docs, api_key, project_id)
                        if str(risposta).startswith("Errore"):
                            st.error(risposta)
                        else:
                            st.markdown("### 💡 Risposta dell'Assistente")
                            st.write(risposta)
                            success, remaining = consume_ai_credit(username)
                            if success:
                                st.session_state["current_user_credits"] = remaining
                        
                        with st.expander("Vedi Fonti Utilizzate"):
                            for doc in relevant_docs:
                                st.markdown(f"**{doc['file']} (Pag. {doc['page']})**")
                                st.text(doc['text'][:300] + "...")

            except Exception as e:
                st.error(f"Errore: {e}")
