import base64
import re
import os
from openai import OpenAI

# Recupera la chiave API e il project_id dalle variabili d'ambiente
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_PROJECT = os.getenv("OPENAI_PROJECT")

# Crea il client OpenAI con project_id (per chiavi sk-proj-...)
client = OpenAI(api_key=OPENAI_API_KEY, project=OPENAI_PROJECT)
import streamlit as st

def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')


def extract_markdown_section(text, heading):
    if not text:
        return ""

    pattern = rf"(^|\n)##\s*{re.escape(heading)}\s*\n"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return ""

    start = match.end()
    remaining = text[start:]
    next_heading = re.search(r"\n##\s+", remaining)
    if next_heading:
        remaining = remaining[:next_heading.start()]

    return remaining.strip()


def extract_intervention_section(text):
    section = extract_markdown_section(text, "2) Interventi consigliati")
    if section:
        return section

    return extract_markdown_section(text, "2. Interventi consigliati")

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
    Sei un Ingegnere Strutturista Senior esperto in diagnosi preliminare su edifici esistenti (NTC 2018).
    Esegui una Ispezione Visiva Preliminare basata sulle immagini fornite.

    {context_str}

    OBIETTIVO APPLICATIVO:
    L'utente vuole capire rapidamente:
    1) quali problemi strutturali probabili sono presenti,
    2) quanto sono urgenti,
    3) quali interventi fare,
    4) quali indagini servono prima dei lavori.

    Vincoli:
    - Basati solo su evidenze visive e sui dati forniti.
    - Se l'evidenza è parziale, esplicita il livello di confidenza.
    - Ignora persone, volti, targhe e dettagli non strutturali.
    - Usa linguaggio tecnico ma leggibile.

    OUTPUT OBBLIGATORIO (formato Markdown):

    ## 1) Problemi strutturali probabili
    Fornisci una tabella con colonne:
    | Problema | Evidenza osservata | Gravità (Bassa/Media/Alta) | Urgenza (Monitorare/Intervenire presto/Immediata) | Confidenza (Bassa/Media/Alta) |

    ## 2) Interventi consigliati
    Fornisci una tabella con colonne:
    | Problema collegato | Intervento consigliato | Obiettivo tecnico | Priorità (1-3) | Note operative |

    ## 3) Indagini e verifiche prima dei lavori
    Elenco puntato di prove consigliate (es. pacometria, martinetti, endoscopie, monitoraggio fessure), con motivo sintetico.

    ## 4) Sintesi decisionale
    - Rischio complessivo: Basso/Medio/Alto.
    - Azione entro 30 giorni: cosa fare subito.
    - Azione entro 90 giorni: cosa pianificare.
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
    Sei un Computista e Stimatore Edile italiano.
    Basandoti sull'analisi seguente, estrai gli interventi e produci una stima parametrica dei prezzi unitari medi (riferimento DEI/Regionali 2024).

    ANALISI STRUTTURALE:
    {analysis_text}

    Restituisci SOLO una tabella Markdown con colonne:
    | Problema | Urgenza | Intervento | Unità di Misura | Prezzo Unitario Stimato (€) | Note |

    Regole:
    - Usa range realistici (min-max).
    - Se il dato non è stimabile da testo, scrivi "Da definire in sopralluogo".
    - Nessun testo extra fuori tabella.
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
