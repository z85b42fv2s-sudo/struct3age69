from pathlib import Path
import hashlib
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logic
import ai_handler
import synthesis
import report_generator
import regulation_handler

import os
from dotenv import load_dotenv

# Configurazione pagina Streamlit: deve essere la prima chiamata `st.*`
st.set_page_config(
    page_title="Structure3Age",
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

USERS_FILE = "users.csv"
PROFESSIONALS_FILE = "professionisti.csv"
TRIAL_DAYS = 3
SUBSCRIPTION_PRICE = 9.90
STRIPE_PUBLIC_KEY = "mk_1ShT5mAHjVSlqjiBcdK8asiZ"
STRIPE_SECRET_KEY = "mk_1ShT6iAHjVSlqjiBN9zJb2tO"


@st.cache_data(ttl=15)
def load_users():
    try:
        df = pd.read_csv(USERS_FILE)
        required = ["email", "data_registrazione", "abbonato", "verified", "verification_code", "verification_expires"]
        if df.empty or not all(col in df.columns for col in required):
            emails = df["email"].tolist() if "email" in df.columns else []
            df = pd.DataFrame(columns=required)
            for e in emails:
                df = pd.concat([df, pd.DataFrame({"email": [e], "data_registrazione": [datetime.now().strftime("%Y-%m-%d")], "abbonato": [False], "verified": [False], "verification_code": [""], "verification_expires": [""]})], ignore_index=True)
            df.to_csv(USERS_FILE, index=False)
        for col in ["email", "data_registrazione", "verification_code", "verification_expires"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)
                df[col] = df[col].replace({"nan": "", "None": ""})
        if "verification_code" in df.columns:
            df["verification_code"] = df["verification_code"].apply(
                lambda value: value[:-2] if isinstance(value, str) and value.endswith(".0") and value[:-2].isdigit() else value
            )
        df["abbonato"] = df["abbonato"].apply(lambda value: str(value).strip().lower() in {"true", "1", "yes", "si"})
        if "verified" in df.columns:
            df["verified"] = df["verified"].apply(lambda value: str(value).strip().lower() in {"true", "1", "yes", "si"})
        return df
    except Exception:
        df = pd.DataFrame(columns=["email", "data_registrazione", "abbonato", "verified", "verification_code", "verification_expires"])
        df.to_csv(USERS_FILE, index=False)
        return df


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

    if st.button("Trova professionisti in zona", key="trova_professionisti_button"):
        if not localita_value.strip():
            st.warning("Inserisci CAP o Comune nella sezione dati generali.")
        else:
            risultati_prof = suggest_professionals(localita_value, categoria_prof)
            if risultati_prof.empty:
                st.warning("Nessun professionista trovato per i filtri selezionati.")
            else:
                st.success(f"Trovati {len(risultati_prof)} professionisti.")
                for _, row in risultati_prof.iterrows():
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
    st.title("Iscrizione e Prova Gratuita")
    st.write("Compila il modulo per iscriverti e iniziare la prova gratuita di 3 giorni. **Non serve inserire dati di pagamento per la prova gratuita!**")
    email = st.text_input("Email", "", key="signup_email")
    if st.button("Inizia la prova gratuita"):
        if not email or "@" not in email:
            st.error("Inserisci una email valida.")
        else:
            # Protezione: se per qualche motivo la funzione save_user non è disponibile
            # (ad esempio deploy non aggiornato), mostriamo un messaggio chiaro invece di sollevare NameError.
            if "save_user" in globals() and callable(globals().get("save_user")):
                save_user(email, abbonato=False)
            else:
                st.error("Servizio non pronto: riprova fra pochi secondi o aggiorna il deploy (Rerun).")
                return
            st.session_state.current_user_email = email.strip().lower()
            st.success("Prova gratuita attivata! Ora puoi usare subito la tua email dalla pagina principale.")
            st.info("Al termine della prova gratuita, ti verrà richiesto di abbonarti per continuare.")

    # Il pagamento Stripe viene mostrato solo DOPO la prova gratuita (gestito nella pagina principale)
    st.markdown("---")
    st.info("Dopo la prova gratuita, per continuare sarà necessario abbonarsi tramite Stripe. Nessun dato di pagamento richiesto ora per la prova gratuita.")

# --- NAVIGAZIONE PAGINE ---
# Mostro il selettore subito, ma rimando la chiamata della pagina
selected_page = st.sidebar.selectbox("Naviga", ["App principale", "Iscrizione e Pagamento"])

components.html(
    """
    <head>
        <meta name=\"google-site-verification\" content=\"D-2hzr1YwD7pGFy_0r30wH3TuUFqkSpmXooJbX0_RlI\" />
    </head>
    """,
    height=0
)

st.markdown("---")
st.header("Accesso rapido")
st.info("Se hai già un'email verificata, puoi accedere subito anche dalla pagina iniziale.")
accesso_email_rapido = st.text_input("Email per accesso rapido", placeholder="demo@demo.it", key="accesso_email_rapido")
if st.button("Accedi con email rapida", key="accesso_rapido_button"):
    email_norm = accesso_email_rapido.strip().lower()
    if not email_norm or "@" not in email_norm:
        st.warning("Inserisci una email valida.")
    else:
        utenti = load_users()
        user_row = utenti[utenti["email"].astype(str).str.lower() == email_norm]
        if not user_row.empty and bool(user_row.iloc[0].get("verified", False)):
            st.session_state.current_user_email = email_norm
            st.rerun()
        elif not user_row.empty:
            st.warning("Email presente ma non verificata. Completa la verifica OTP dalla sidebar.")
        else:
            st.warning("Email non trovata nel database utenti.")

st.markdown("---")
st.header("Professionisti Consigliati in Zona")
st.info("Indicazioni orientative: verifica sempre abilitazioni, referenze e preventivi prima di affidare incarichi.")
professionisti_localita = st.text_input("CAP o Comune per cercare professionisti", placeholder="Es. 20121 oppure Milano", key="professionisti_localita_public")
render_professionals_section(professionisti_localita)

# --- AUTENTICAZIONE UTENTE ---
@st.cache_data(ttl=15)
def load_users():
    try:
        df = pd.read_csv(USERS_FILE)
        # Ensure required columns exist; if not, recreate with full schema
        required = ["email", "data_registrazione", "abbonato", "verified", "verification_code", "verification_expires"]
        if df.empty or not all(col in df.columns for col in required):
            # preserve existing emails if present
            emails = df["email"].tolist() if "email" in df.columns else []
            df = pd.DataFrame(columns=required)
            for e in emails:
                df = pd.concat([df, pd.DataFrame({"email": [e], "data_registrazione": [datetime.now().strftime("%Y-%m-%d")], "abbonato": [False], "verified": [False], "verification_code": [""], "verification_expires": [""]})], ignore_index=True)
            df.to_csv(USERS_FILE, index=False)
        # normalize text columns so OTPs are never treated as numbers by pandas
        for col in ["email", "data_registrazione", "verification_code", "verification_expires"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)
                df[col] = df[col].replace({"nan": "", "None": ""})
        if "verification_code" in df.columns:
            df["verification_code"] = df["verification_code"].apply(
                lambda value: value[:-2] if isinstance(value, str) and value.endswith(".0") and value[:-2].isdigit() else value
            )
        # normalize boolean columns
        df["abbonato"] = df["abbonato"].apply(lambda value: str(value).strip().lower() in {"true", "1", "yes", "si"})
        if "verified" in df.columns:
            df["verified"] = df["verified"].apply(lambda value: str(value).strip().lower() in {"true", "1", "yes", "si"})
        return df
    except Exception:
        df = pd.DataFrame(columns=["email", "data_registrazione", "abbonato", "verified", "verification_code", "verification_expires"])
        df.to_csv(USERS_FILE, index=False)
        return df


def invalidate_users_cache():
    try:
        load_users.clear()
    except Exception:
        pass


@st.cache_data(ttl=300)
def load_professionals():
    try:
        df = pd.read_csv(PROFESSIONALS_FILE)
        required = ["nome", "categoria", "zona", "telefono", "sito", "note"]
        if not all(col in df.columns for col in required):
            return pd.DataFrame(columns=required)
        for col in required:
            df[col] = df[col].fillna("").astype(str)
        return df
    except Exception:
        return pd.DataFrame(columns=["nome", "categoria", "zona", "telefono", "sito", "note"])


def suggest_professionals(localita: str, categoria: str = ""):
    df = load_professionals()
    if df.empty:
        return df
    filtered = df
    if localita:
        localita_norm = localita.strip().lower()
        filtered = filtered[filtered["zona"].str.lower().str.contains(localita_norm, na=False)]
    if categoria and categoria != "Tutte":
        filtered = filtered[filtered["categoria"].str.lower() == categoria.strip().lower()]
    return filtered


def render_professionals_section(localita_value: str):
    categoria_prof = st.selectbox(
        "Tipo di professionista",
        ["Tutte", "Ingegnere Strutturista", "Impresa Edile", "Geologo", "Diagnostica Strutturale"],
        key="categoria_prof_select",
    )

    if st.button("Trova professionisti in zona", key="trova_professionisti_button"):
        if not localita_value.strip():
            st.warning("Inserisci CAP o Comune nella sezione dati generali.")
        else:
            risultati_prof = suggest_professionals(localita_value, categoria_prof)
            if risultati_prof.empty:
                st.warning("Nessun professionista trovato per i filtri selezionati.")
            else:
                st.success(f"Trovati {len(risultati_prof)} professionisti.")
                for _, row in risultati_prof.iterrows():
                    st.markdown(
                        f"**{row['nome']}**  \n"
                        f"Categoria: {row['categoria']}  \n"
                        f"Zona: {row['zona']}  \n"
                        f"Telefono: {row['telefono']}  \n"
                        f"Sito: {row['sito']}  \n"
                        f"Note: {row['note']}"
                    )

def save_user(email, abbonato=False, verified=False):
    df = load_users()
    email = email.strip().lower()
    now = datetime.now().strftime("%Y-%m-%d")
    if email in df["email"].astype(str).str.lower().values:
        idx = df[df["email"].astype(str).str.lower() == email].index[0]
        df.at[idx, "data_registrazione"] = now
        df.at[idx, "abbonato"] = abbonato
        # preserve verified unless explicitly True
        if verified:
            df.at[idx, "verified"] = True
    else:
        df = pd.concat([df, pd.DataFrame({"email": [email], "data_registrazione": [now], "abbonato": [abbonato], "verified": [verified], "verification_code": [""], "verification_expires": [""]})], ignore_index=True)
    df.to_csv(USERS_FILE, index=False)
    invalidate_users_cache()

def check_trial(email):
    df = load_users()
    email = email.strip().lower()
    user = df[df["email"].astype(str).str.lower() == email]
    if user.empty:
        return True, None
    reg_date = datetime.strptime(user.iloc[0]["data_registrazione"], "%Y-%m-%d")
    days_used = (datetime.now() - reg_date).days
    abbonato = user.iloc[0]["abbonato"]
    in_trial = days_used < TRIAL_DAYS
    return in_trial or abbonato, abbonato


# ------------------ OTP / Email helpers ------------------
import random
import smtplib
from email.message import EmailMessage

def get_secret(key):
    if hasattr(st, "secrets") and key in st.secrets:
        return st.secrets[key]
    return os.getenv(key)

def send_email_smtp(to_email: str, subject: str, body: str) -> bool:
    host = get_secret("SMTP_HOST")
    port = int(get_secret("SMTP_PORT") or 587)
    user = get_secret("SMTP_USER")
    password = get_secret("SMTP_PASSWORD")
    from_addr = get_secret("EMAIL_FROM")

    # fallback: test mode -> show code in sidebar
    if not all([host, port, user, password, from_addr]):
        st.sidebar.info(f"[TEST MODE] Email to {to_email}: {subject} -- {body}")
        return True

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as e:
        st.error("Errore invio email: " + str(e))
        return False


def generate_otp():
    return f"{random.randint(0, 999999):06d}"

def set_verification_code(email, minutes=10):
    # create or update user with a verification code and expiry
    df = load_users()
    email = email.strip().lower()
    now = datetime.now()
    expires = (now + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S")
    code = generate_otp()
    if email in df["email"].astype(str).str.lower().values:
        idx = df[df["email"].astype(str).str.lower() == email].index[0]
        df.at[idx, "verification_code"] = code
        df.at[idx, "verification_expires"] = expires
        df.at[idx, "verified"] = False
    else:
        df = pd.concat([df, pd.DataFrame({
            "email": [email],
            "data_registrazione": [now.strftime("%Y-%m-%d")],
            "abbonato": [False],
            "verified": [False],
            "verification_code": [code],
            "verification_expires": [expires]
        })], ignore_index=True)
    df.to_csv(USERS_FILE, index=False)
    invalidate_users_cache()
    return code, expires


def verify_otp(email, code):
    df = load_users()
    email = email.strip().lower()
    user = df[df["email"].astype(str).str.lower() == email]
    if user.empty:
        return False, "Email non trovata"
    stored = str(user.iloc[0]["verification_code"]).strip()
    expires = user.iloc[0]["verification_expires"]
    if not stored:
        return False, "Nessun codice inviato. Richiedi un nuovo codice."
    try:
        exp_dt = datetime.strptime(expires, "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return False, "Codice non valido. Richiedi nuovo codice."
    if datetime.now() > exp_dt:
        return False, "Codice scaduto. Richiedi un nuovo codice."
    if code.strip() != stored:
        return False, "Codice errato."
    # OK -> mark verified and clear code
    idx = df[df["email"].astype(str).str.lower() == email].index[0]
    df.at[idx, "verified"] = True
    df.at[idx, "verification_code"] = ""
    df.at[idx, "verification_expires"] = ""
    df.to_csv(USERS_FILE, index=False)
    invalidate_users_cache()
    return True, "Email verificata"

# ------------------ end OTP helpers ------------------

# Se l'utente ha selezionato la pagina di iscrizione, renderizza la pagina ORA
if 'selected_page' in globals() and selected_page == "Iscrizione e Pagamento":
    # Visualizza il file di verifica Google se presente e inietta il meta tag
    verification_file = Path("googlea850bad541d5794f.html")
    if verification_file.exists():
        with open(verification_file, "r", encoding="utf-8") as f:
            st.markdown(f.read(), unsafe_allow_html=True)
    st.sidebar.info("Usa la pagina principale per accedere o attivare la prova gratuita.")
    pagina_iscrizione_pagamento()
    st.stop()

# --- ACCESSO / PROVA GRATUITA ---
st.sidebar.markdown("---")
st.sidebar.header("📝 Accedi / Prova Gratuita")
st.sidebar.write("""
Accedi con la tua email oppure avvia subito la prova gratuita di 3 giorni senza carta.
""")

if "current_user_email" not in st.session_state:
    st.session_state.current_user_email = ""

email_input = st.sidebar.text_input("Email", value=st.session_state.current_user_email, placeholder="nome@dominio.it", key="sidebar_email")
col_login, col_trial = st.sidebar.columns(2)

if col_login.button("Accedi"):
    email_norm = email_input.strip().lower()
    if not email_norm or "@" not in email_norm:
        st.sidebar.error("Inserisci una email valida.")
    else:
        utenti = load_users()
        user_row = utenti[utenti["email"].astype(str).str.lower() == email_norm]
        if not user_row.empty and bool(user_row.iloc[0].get("verified", False)):
            st.session_state.current_user_email = email_norm
            st.rerun()
        elif not user_row.empty:
            st.sidebar.warning("Email presente ma non verificata. Richiedi il codice OTP e completa la verifica.")
        else:
            st.sidebar.error("Email non trovata. Usa 'Prova gratuita' per creare l'accesso e verificare l'email.")

if col_trial.button("Prova gratuita"):
    email_norm = email_input.strip().lower()
    if not email_norm or "@" not in email_norm:
        st.sidebar.error("Inserisci una email valida.")
    else:
        # Start OTP flow: generate code, save and send
        code, expires = set_verification_code(email_norm)
        subject = "Codice di verifica Structure3Age"
        body = f"Il tuo codice di verifica è: {code} (valido fino alle {expires})"
        sent = send_email_smtp(email_norm, subject, body)
        st.session_state['otp_last_sent'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if sent:
            st.sidebar.success("Codice di verifica inviato. Controlla la tua email (o la sidebar in test mode) e poi inserisci il codice per entrare.")
        else:
            st.sidebar.error("Errore invio codice. Riprova più tardi.")

if st.session_state.current_user_email:
    st.sidebar.success(f"Accesso attivo: {st.session_state.current_user_email}")
    if st.sidebar.button("Esci"):
        st.session_state.current_user_email = ""
        st.rerun()

# OTP verify input
otp_code = st.sidebar.text_input("Codice verifica (OTP)", key="otp_code")
if st.sidebar.button("Verifica codice"):
    email_norm = st.session_state.current_user_email or email_input.strip().lower()
    if not email_norm:
        st.sidebar.error("Inserisci l'email prima di verificare il codice.")
    else:
        ok, msg = verify_otp(email_norm, otp_code)
        if ok:
            st.sidebar.success(msg)
            st.session_state.current_user_email = email_norm
            st.rerun()
        else:
            st.sidebar.error(msg)

# Resend button (rate limited)
if st.sidebar.button("Reinvia codice"):
    email_norm = email_input.strip().lower()
    if not email_norm or "@" not in email_norm:
        st.sidebar.error("Inserisci una email valida.")
    else:
        last = st.session_state.get('otp_last_sent')
        if last:
            try:
                last_dt = datetime.strptime(last, "%Y-%m-%dT%H:%M:%S")
                if (datetime.now() - last_dt).total_seconds() < 60:
                    st.sidebar.error("Attendi prima di richiedere un nuovo codice (60s).")
                    st.stop()
            except Exception:
                pass
        code, expires = set_verification_code(email_norm)
        subject = "Codice di verifica Structure3Age"
        body = f"Il tuo codice di verifica è: {code} (valido fino alle {expires})"
        sent = send_email_smtp(email_norm, subject, body)
        st.session_state['otp_last_sent'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if sent:
            st.sidebar.success("Codice reinviato. Controlla la tua email (o la sidebar in test mode).")
        else:
            st.sidebar.error("Errore invio codice. Riprova più tardi.")

username = st.session_state.current_user_email.strip().lower()
users_df = load_users() if username else pd.DataFrame()
user_row = users_df[users_df["email"].astype(str).str.lower() == username] if username else pd.DataFrame()
authentication_status = bool(username) and not user_row.empty and bool(user_row.iloc[0].get("verified", False))

# Do NOT auto-create/save users here. Users are created explicitly via signup or
# when requesting a verification code (`set_verification_code`) so we avoid
# accidental registrations just by typing an email in the input.
if authentication_status:
    in_trial, abbonato = check_trial(username)
    reg_date = user_row.iloc[0]["data_registrazione"] if not user_row.empty else "-"
    abbo = user_row.iloc[0]["abbonato"] if not user_row.empty else False
    days_left = None
    if not user_row.empty:
        days_left = TRIAL_DAYS - (datetime.now() - datetime.strptime(reg_date, "%Y-%m-%d")).days

    if not abbonato and (days_left is not None and days_left <= 0):
        st.sidebar.markdown("---")
        st.sidebar.markdown("<a href='https://buy.stripe.com/test_6oU00i1DSaLZ9zK40R57W00' target='_blank'><button style='width:100%;background:#00c7b4;color:white;font-size:18px;padding:10px;border:none;border-radius:5px;'>Abbonati a €9,90/mese</button></a>", unsafe_allow_html=True)
        st.sidebar.info("La prova gratuita è finita: ora serve un abbonamento per continuare.")
    elif in_trial:
        st.sidebar.info(f"Prova gratuita attiva. Giorni rimanenti: {days_left if days_left is not None and days_left > 0 else 0}")
    else:
        st.sidebar.info("Abbonamento attivo.")

    st.sidebar.markdown("---")

else:
    st.info("Inserisci la tua email nella sidebar per accedere o attivare la prova gratuita.")
    st.stop()

if authentication_status:
    st.sidebar.markdown("---")
    st.sidebar.info(f"**DEBUG UTENTE**\nEmail: {username}\nRegistrato: {reg_date}\nAbbonato: {abbo}\nGiorni prova rimasti: {days_left if days_left is not None and days_left > 0 else 0}")
    st.sidebar.markdown("---")

    if abbonato:
        st.success("Abbonamento attivo! Puoi usare tutte le funzionalità.")
    elif in_trial:
        st.info(f"Benvenuto! Hai una prova gratuita attiva. Giorni rimanenti: {days_left if days_left is not None and days_left > 0 else 0}")
        st.success("Non serve inserire dati di pagamento per la prova gratuita.")
    else:
        st.error("Il periodo di prova gratuita è terminato. Abbonati per continuare a usare l'applicazione.")
        st.stop()

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
            st.image(file, caption=f"Foto {i+1}", use_column_width=True)
    
    if st.button("Analizza Foto con AI"):
        if not api_key:
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
                    
                    # Store in session state
                    st.session_state['analysis_result'] = descrizione
                    st.session_state['uploaded_files'] = uploaded_files
                    files_to_use = uploaded_files
                    
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
            with st.spinner("Calcolo stima parametrica in corso..."):
                try:
                    project_id = os.getenv("OPENAI_PROJECT")
                    source_text = interventi_ai or descrizione
                    stima_costi = ai_handler.estimate_intervention_costs(source_text, api_key, project_id)
                    st.markdown(stima_costi)
                    st.warning("⚠️ NOTA: I prezzi sono puramente indicativi e riferiti a medie di mercato. Non sostituiscono un computo metrico estimativo professionale.")
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
        final_synthesis = synthesis.generate_final_synthesis(dati_generali, vulnerabilita_attese, esito_visivo)
        st.session_state["final_synthesis"] = final_synthesis
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
    if not api_key:
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
                        
                        st.markdown("### 💡 Risposta dell'Assistente")
                        st.write(risposta)
                        
                        with st.expander("Vedi Fonti Utilizzate"):
                            for doc in relevant_docs:
                                st.markdown(f"**{doc['file']} (Pag. {doc['page']})**")
                                st.text(doc['text'][:300] + "...")

            except Exception as e:
                st.error(f"Errore: {e}")
