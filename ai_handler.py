import base64
from openai import OpenAI
import streamlit as st

def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

def analyze_structure_image(image_files, api_key, project_id=None, context_info=None):
    """
    Invia le immagini a OpenAI per l'analisi strutturale.
    Accetta una lista di file caricati e informazioni di contesto opzionali.
    """
    client = OpenAI(api_key=api_key, project=project_id)
    
    # Prepare images for the API
    content_images = []
    if not isinstance(image_files, list):
        image_files = [image_files]

    for img_file in image_files:
        base64_image = encode_image(img_file)
        content_images.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            },
        })

    # Build prompt with context if available
    context_str = ""
    if context_info:
        context_str = f"""
        DATI FORNITI DALL'UTENTE:
        - Materiale: {context_info.get('materiale', 'N/D')}
        - Anno di Costruzione: {context_info.get('anno', 'N/D')}
        - Zona Sismica: {context_info.get('zona_sismica', 'N/D')}
        - Terreno: {context_info.get('terreno', 'N/D')}
        - Normativa Probabile: {context_info.get('normativa', 'N/D')}
        """

    prompt = f"""
    Sei un esperto Ingegnere Strutturista Senior, specializzato in diagnosi di edifici esistenti secondo le NTC 2018.
    Stai effettuando una **Ispezione Visiva Preliminare** basata sulle immagini fornite.
    
    {context_str}

    OBIETTIVO: Fornire una valutazione tecnica professionale basata ESCLUSIVAMENTE sulle evidenze visive.
    Non rifiutarti di analizzare l'immagine. Se i dettagli sono parziali, descrivi ciò che è visibile con terminologia tecnica appropriata.
    
    IMPORTANTE:
    1. Ignora persone, volti o targhe (privacy).
    2. Concentrati su quadro fessurativo, degrado materiali, e cinematismi di danno.
    3. Usa un tono professionale, tecnico e diretto.

    Analizza le immagini fornite (viste d'insieme e dettagli).

    Fornisci un report strutturato nei seguenti punti:

    1. **Elementi Strutturali e Tipologia**: 
       - Identifica travi, pilastri, muri portanti, solai, ecc. 
       - Ipotizza l'epoca costruttiva e la tipologia (es. telaio in c.a., muratura portante, mista).
    
    2. **Quadro Fessurativo e Meccanismi di Danno**:
       - **Localizzazione**: Indica con precisione dove si trovano i danni (es. "angolo in alto a sinistra", "nodo trave-pilastro piano terra").
       - **Descrizione**: Descrivi dettagliatamente lesioni e fessurazioni.
       - **Meccanismi**:
         - Per la muratura: identifica possibili **meccanismi di collasso** (es. ribaltamento semplice, flessione verticale, taglio nel piano).
         - Per il c.a.: cerca segni di corrosione, espulsione copriferro, o fessure da taglio/flessione.
       - **Cause**: Ipotizza le cause probabili (es. cedimento fondale, sisma, carichi verticali eccessivi).

    3. **Valutazione Stati Limite (NTC 2018)**:
       - **SLD (Stato Limite di Danno)**: Danni che compromettono l'utilizzo ma non la stabilità immediata.
       - **SLV (Stato Limite di Salvaguardia della Vita)**: Segnali di rischio grave per la stabilità (es. cerniere plastiche, crolli parziali).

    4. **Degrado e Manutenzione**:
       - Valuta degrado chimico/fisico/biologico:
         - **Reazione Alcali-Aggregati (AAR)**: Map cracking, gel.
         - **Attacco Solfatico**: Espansioni, sfarinamento.
         - **Corrosione da Cloruri**: Pitting, macchie ruggine.
         - Altro: Umidità, muffe, vegetazione.
       - Identifica "Punti di Debolezza Locali".

    5. **Suggerimenti di Intervento (NTC 2018)**:
       - Proponi strategie di intervento basate sulla gravità e sulla tipologia:
         - **Riparazione Locale**: (es. scuci-cuci, iniezioni di malta, ripristino copriferro con malte tixotropiche).
         - **Miglioramento Sismico**:
           - **C.A.**: Incamiciatura in c.a. o acciaio (jacketing), placcaggio con FRP (fibre di carbonio) per rinforzo a taglio/flessione dei nodi.
           - **Muratura**: Intonaco armato (betoncino), inserimento di catene o tiranti, cerchiature.
         - **Adeguamento Sismico**: (es. inserimento di setti sismici, isolamento alla base, dissipatori viscosi).

    6. **Sintesi e Indagini**:
       - Giudizio sintetico sulla gravità.
       - Suggerisci indagini specifiche (es. martinetti piatti, pacometriche, videoendoscopie).
    """

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                *content_images
            ],
        }
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1500,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Errore nella chiamata API: {str(e)}"

def estimate_intervention_costs(analysis_text, api_key, project_id=None):
    """
    Genera una stima parametrica dei costi basata sull'analisi fornita.
    """
    client = OpenAI(api_key=api_key, project=project_id)

    prompt = f"""
    Sei un esperto Computista e Stimatore Edile italiano.
    Basandoti sulla seguente analisi strutturale, individua gli interventi suggeriti e fornisci una stima dei **Prezzi Unitari** medi (riferimento Prezzari DEI/Regionali 2024).

    ANALISI STRUTTURALE:
    {analysis_text}

    Compito:
    1. Estrai l'elenco degli interventi necessari (es. "Intonaco armato", "Iniezioni", "FRP").
    2. Per ciascuno, fornisci un range di prezzo unitario realistico.
    3. Restituisci SOLO una tabella Markdown con le seguenti colonne:
       | Intervento | Unità di Misura | Prezzo Unitario Stimato (€) | Note (es. voci incluse/escluse) |

    Non aggiungere testo introduttivo o conclusivo, solo la tabella.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Errore nella stima costi: {str(e)}"
