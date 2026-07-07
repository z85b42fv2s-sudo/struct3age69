from pathlib import Path
import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
from datetime import datetime, timedelta
import logic
import ai_handler
import report_generator
import regulation_handler

import os
from dotenv import load_dotenv
import importlib
import stripe

# Configurazione pagina Streamlit: deve essere la prima chiamata `st.*`
st.set_page_config(
    page_title="Structure3Age",
    page_icon="🧱",
    layout="wide"
)

# Force clear Streamlit cache to reload modules
st.cache_resource.clear()


# Force reload regulation_handler to get latest code
importlib.reload(regulation_handler)

# Carica variabili d'ambiente dal file .env solo in locale (se presente)
try:
    load_dotenv(override=True)
except Exception:
    pass

USERS_FILE = "users.csv"
TRIAL_DAYS = 3
SUBSCRIPTION_PRICE = 9.90
STRIPE_PUBLIC_KEY = "mk_1ShT5mAHjVSlqjiBcdK8asiZ"
STRIPE_SECRET_KEY = "mk_1ShT6iAHjVSlqjiBN9zJb2tO"

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

# --- AUTENTICAZIONE UTENTE ---
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
user_row = load_users()[load_users()["email"].astype(str).str.lower() == username] if username else pd.DataFrame()
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

# --- SEZIONE 2: Vulnerabilità e Normativa ---
st.header("2. Valutazione Vulnerabilità e Normativa")
normativa, vulnerabilita = logic.get_vulnerabilities(anno_costruzione, materiale)

st.info(f"Normativa di riferimento probabile: **{normativa}**")
st.write("### Vulnerabilità Tipiche Attese:")
for v in vulnerabilita:
    st.write(f"- {v}")

# --- SEZIONE 3: Livello di Conoscenza (LC) ---
st.header("3. Livello di Conoscenza (LC)")
st.write("Seleziona i dati disponibili per la struttura:")

col_lc1, col_lc2, col_lc3 = st.columns(3)
with col_lc1:
    geom = st.checkbox("Geometria completa (Rilievo)")
with col_lc2:
    dettagli = st.checkbox("Dettagli costruttivi (Armature/Tessitura)")
with col_lc3:
    materiali = st.checkbox("Proprietà materiali (Prove in situ/Lab)")

lc, fc, suggerimenti = logic.calculate_knowledge_level(geom, dettagli, materiali)

st.metric("Livello di Conoscenza (LC)", lc)
st.metric("Fattore di Confidenza (FC)", fc)

if suggerimenti:
    st.warning("Per migliorare il Livello di Conoscenza:")
    for s in suggerimenti:
        st.write(f"- {s}")

# --- SEZIONE 4: Analisi Consigliata ---
st.header("4. Tipo di Analisi Consigliata")
regolarita_pianta = st.checkbox("Struttura Regolare in Pianta")
regolarita_altezza = st.checkbox("Struttura Regolare in Altezza")

analisi_consigliata = logic.recommend_analysis_type(materiale, regolarita_pianta, regolarita_altezza)
st.success(f"Metodo di Analisi Consigliato: **{analisi_consigliata}**")

# --- SEZIONE 5: Analisi AI delle Foto ---
# --- SEZIONE 5: Analisi AI delle Foto ---
st.header("5. Analisi AI delle Foto (Degrado e Fessurazioni)")
uploaded_files = st.file_uploader("Carica foto della struttura (viste d'insieme e dettagli)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

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
                    
                except Exception as e:
                    st.error(f"Errore durante l'analisi: {e}")

    # Check if analysis exists in session state
    if 'analysis_result' in st.session_state:
        descrizione = st.session_state['analysis_result']
        files_to_use = st.session_state.get('uploaded_files', uploaded_files)

        st.markdown("### 📋 Report Analisi AI")
        st.write(descrizione)

        st.markdown("---")
        with st.expander("🛠️ Suggerimenti di Intervento (NTC 2018)", expanded=True):
            st.info("Questa sezione contiene suggerimenti generati dall'AI basati sulle NTC 2018. Consultare sempre un ingegnere strutturista per il progetto esecutivo.")
            st.markdown("Vedi il punto **5. Suggerimenti di Intervento** nel report sopra per i dettagli specifici.")

        # --- COST ESTIMATION ---
        st.markdown("---")
        st.subheader("💰 Stima Parametrica Costi")
        if st.button("Calcola Stima Costi (Prezzari DEI/Regionali)"):
            with st.spinner("Calcolo stima parametrica in corso..."):
                try:
                    project_id = os.getenv("OPENAI_PROJECT")
                    stima_costi = ai_handler.estimate_intervention_costs(descrizione, api_key, project_id)
                    st.markdown(stima_costi)
                    st.warning("⚠️ NOTA: I prezzi sono puramente indicativi e riferiti a medie di mercato. Non sostituiscono un computo metrico estimativo professionale.")
                except Exception as e:
                    st.error(f"Errore nella stima: {e}")
        
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
            "lc": lc,
            "fc": fc
        }
        
        pdf_bytes = report_generator.generate_pdf(report_data, descrizione, files_to_use)
        
        st.download_button(
            label="📥 Scarica Report PDF",
            data=pdf_bytes,
            file_name="report_structural_3age.pdf",
            mime="application/pdf"
        )

# --- SEZIONE 6: Assistente Normativo ---
st.markdown("---")
st.header("6. 📚 Assistente Normativo (RAG)")
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
