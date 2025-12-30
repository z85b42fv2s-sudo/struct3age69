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

# Force clear Streamlit cache to reload modules
st.cache_resource.clear()


# Force reload regulation_handler to get latest code
importlib.reload(regulation_handler)

# --- PAGINA ISCRIZIONE E PAGAMENTO STRIPE ---
def pagina_iscrizione_pagamento():
    st.title("Iscrizione e Pagamento")
    st.write("Compila il modulo per iscriverti e iniziare la prova gratuita di 3 giorni. Nessun pagamento richiesto ora.")
    email = st.text_input("Email", "")
    if st.button("Inizia la prova gratuita"):
        if not email or "@" not in email:
            st.error("Inserisci una email valida.")
        else:
            save_user(email, abbonato=False)
            st.success("Prova gratuita attivata! Puoi accedere con la tua email dalla pagina principale.")
            st.info("Al termine della prova gratuita, ti verrà richiesto di abbonarti per continuare.")

    st.markdown("---")
    st.write("Se hai già terminato la prova gratuita o vuoi abbonarti subito:")
    if st.button("Abbonati ora con Stripe"):
        if not email or "@" not in email:
            st.error("Inserisci una email valida.")
        else:
            try:
                stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    customer_email=email,
                    line_items=[{
                        "price_data": {
                            "currency": "eur",
                            "product_data": {"name": "Abbonamento Structural 3age"},
                            "unit_amount": int(9.90 * 100),
                            "recurring": {"interval": "month"}
                        },
                        "quantity": 1
                    }],
                    mode="subscription",
                    success_url=os.getenv("SUCCESS_URL", "https://google.com"),
                    cancel_url=os.getenv("CANCEL_URL", "https://google.com")
                )
                st.success("Verrai reindirizzato al pagamento...")
                st.markdown(f"<a href='{session.url}' target='_blank'><button style='width:100%;background:#00c7b4;color:white;font-size:18px;padding:10px;border:none;border-radius:5px;'>Vai a Stripe</button></a>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Errore nella creazione della sessione Stripe: {e}")

# --- NAVIGAZIONE PAGINE ---
pagina = st.sidebar.selectbox("Naviga", ["App principale", "Iscrizione e Pagamento"])
if pagina == "Iscrizione e Pagamento":
    pagina_iscrizione_pagamento()
    st.stop()


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

st.set_page_config(page_title="Structural 3age", layout="wide")

# --- AUTENTICAZIONE UTENTE ---
def load_users():
    try:
        df = pd.read_csv(USERS_FILE)
        # Se il file è vuoto o non ha le colonne giuste, ricrea l'intestazione
        if df.empty or not all(col in df.columns for col in ["email", "data_registrazione", "abbonato"]):
            df = pd.DataFrame(columns=["email", "data_registrazione", "abbonato"])
            df.to_csv(USERS_FILE, index=False)
        return df
    except Exception:
        df = pd.DataFrame(columns=["email", "data_registrazione", "abbonato"])
        df.to_csv(USERS_FILE, index=False)
        return df

def save_user(email, abbonato=False):
    df = load_users()
    if email not in df["email"].values:
        now = datetime.now().strftime("%Y-%m-%d")
        df = pd.concat([df, pd.DataFrame({"email": [email], "data_registrazione": [now], "abbonato": [abbonato]})], ignore_index=True)
        df.to_csv(USERS_FILE, index=False)

def check_trial(email):
    df = load_users()
    user = df[df["email"] == email]
    if user.empty:
        return True, None
    reg_date = datetime.strptime(user.iloc[0]["data_registrazione"], "%Y-%m-%d")
    days_used = (datetime.now() - reg_date).days
    abbonato = user.iloc[0]["abbonato"]
    in_trial = days_used < TRIAL_DAYS
    return in_trial or abbonato, abbonato

# Configurazione utenti demo
credentials = {
    "usernames": {
        "demo@demo.it": {
            "email": "demo@demo.it",
            "name": "Demo User",
            # Hash generata per la password 'demo123'
            "password": "$2b$12$6EQF.P8dAampjj/hnxqI0OwUJOaExqqdVxyHoEg215SJmv37Z/yp6"
        }
    }
}

authenticator = stauth.Authenticate(
    credentials,
    "struct3age69_cookie",
    "struct3age69_key",
    cookie_expiry_days=7
)


# La funzione login restituisce None se location è diverso da 'unrendered'.

name, authentication_status, username = authenticator.login(location="sidebar")

# --- SEZIONE ISCRIZIONE/ABBONAMENTO PUBBLICA ---
st.sidebar.markdown("---")
st.sidebar.header("📝 Iscriviti / Abbonati")
st.sidebar.write("""
Accedi a tutte le funzionalità avanzate dell'app con l'abbonamento mensile. Dopo la prova gratuita, potrai continuare solo se abbonato.
""")
st.sidebar.markdown("""
<a href='https://buy.stripe.com/test_6oU00i1DSaLZ9zK40R57W00' target='_blank'><button style='width:100%;background:#00c7b4;color:white;font-size:18px;padding:10px;border:none;border-radius:5px;'>Abbonati a €9,90/mese</button></a>
""", unsafe_allow_html=True)
st.sidebar.info("Hai già un account? Effettua il login nella sezione sopra.")

st.sidebar.markdown("---")

if authentication_status:
    save_user(username)
    in_trial, abbonato = check_trial(username)
    if not in_trial:
        st.error(f"Il periodo di prova gratuita è terminato. Abbonati per continuare a usare l'applicazione.")
        st.info("Clicca qui sotto per abbonarti:")
        st.markdown(f"<a href='https://buy.stripe.com/test_6oU00i1DSaLZ9zK40R57W00' target='_blank'><button>Abbonati a €9,90/mese</button></a>", unsafe_allow_html=True)
        st.stop()
    elif not abbonato:
        days_left = TRIAL_DAYS - (datetime.now() - datetime.strptime(load_users()[load_users()["email"] == username].iloc[0]["data_registrazione"], "%Y-%m-%d")).days
        st.info(f"Periodo di prova attivo. Giorni rimanenti: {days_left}")
elif authentication_status is False:
    st.error("Username/password errati")
    st.stop()
elif authentication_status is None:
    st.warning("Inserisci username e password")
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
