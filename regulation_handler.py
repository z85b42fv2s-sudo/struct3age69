import os
from pypdf import PdfReader
import streamlit as st
from openai import OpenAI

import json

@st.cache_resource
def load_regulation_text(normativa_dir):
    """
    Legge tutti i PDF nella cartella normativa e ne estrae il testo.
    Usa una cache JSON per velocizzare i caricamenti successivi.
    """
    documents = []
    if not os.path.exists(normativa_dir):
        return documents

    cache_file = os.path.join(normativa_dir, "regulation_cache.json")
    
    # Try to load from cache
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Errore lettura cache: {e}")

    # If no cache, parse PDFs
    files = [f for f in os.listdir(normativa_dir) if f.lower().endswith('.pdf')]
    
    for filename in files:
        filepath = os.path.join(normativa_dir, filename)
        try:
            reader = PdfReader(filepath)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    documents.append({
                        'file': filename,
                        'page': i + 1,
                        'text': text
                    })
        except Exception as e:
            print(f"Errore lettura {filename}: {e}")
            
    # Save to cache
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(documents, f, ensure_ascii=False)
    except Exception as e:
        print(f"Errore salvataggio cache: {e}")

    return documents

def retrieve_relevant_context(query, documents, top_k=25):
    """
    Cerca i documenti più rilevanti per la query usando una ricerca per parole chiave migliorata.
    """
    stop_words = {"il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "a", "da", "in", "con", "su", "per", "tra", "fra", "che", "e", "o", "ma", "se", "perché", "come", "dove", "chi", "quale", "quali", "è", "sono", "hanno", "non", "del", "della", "dei", "delle", "al", "allo", "alla", "ai", "agli", "alle", "dal", "dallo", "dalla", "dai", "dagli", "dalle", "nel", "nello", "nella", "nei", "negli", "nelle", "sul", "sullo", "sulla", "sui", "sugli", "sulle"}
    
    query_words = [w for w in query.lower().split() if w not in stop_words and len(w) > 2]
    scored_docs = []

    for doc in documents:
        text_lower = doc['text'].lower()
        unique_matches = 0
        total_matches = 0
        
        for word in query_words:
            count = text_lower.count(word)
            if count > 0:
                unique_matches += 1
                total_matches += count
        
        # Score = (Unique Matches * 10) + Total Matches
        # Questo premia le pagine che contengono PIÙ parole diverse della query
        score = (unique_matches * 10) + total_matches
        
        if score > 0:
            scored_docs.append((score, doc))

    # Ordina per score decrescente
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    
    # Prendi i top_k
    return [doc for score, doc in scored_docs[:top_k]]

def ask_regulation_assistant(query, context_docs, api_key, project_id=None):
    """
    Invia la domanda e il contesto a OpenAI.
    """
    client = OpenAI(api_key=api_key, project=project_id)

    # Costruisci il contesto come stringa
    context_text = ""
    for doc in context_docs:
        context_text += f"\n--- Documento: {doc['file']} (Pag. {doc['page']}) ---\n{doc['text']}\n"

    prompt = f"""
    Sei un assistente esperto sulle Norme Tecniche per le Costruzioni (NTC 2018) e relativa Circolare.
    Rispondi alla domanda dell'utente basandoti ESCLUSIVAMENTE sui seguenti estratti normativi forniti.
    
    IMPORTANTE: 
    1. Se la domanda riguarda "quando è possibile" o "requisiti per", fornisci TUTTI i criteri, limiti e condizioni presenti nei documenti (es. limiti di altezza, periodo, accelerazione, regolarità, ecc.).
    2. Se la domanda riguarda regole generali (es. "passo staffe fuori zona critica"), fornisci TUTTE le casistiche presenti (travi, pilastri, pali, ecc.), anche se non menzionate esplicitamente.
    3. Organizza la risposta in modo strutturato con elenchi puntati o numerati.
    4. Cita sempre la fonte (Documento e Pagina) per ogni informazione.
    
    Se la risposta non è presente nei documenti, dillo chiaramente.

    CONTESTO NORMATIVO:
    {context_text}

    DOMANDA UTENTE:
    {query}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Errore nella chiamata API: {str(e)}"
