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

def estimate_intervention_costs(analysis_text, api_key, project_id=None, context_data=None, final_synthesis=None):
    """
    Genera una stima parametrica dei costi basata sull'analisi fornita.
    """
    client = OpenAI(api_key=api_key, project=project_id)

    context_lines = []
    if context_data:
        dati_generali = context_data.get("dati_generali", {}) or {}
        vulnerabilita_attese = context_data.get("vulnerabilita_attese", {}) or {}
        context_lines.append("DATI GENERALI:")
        context_lines.append(f"- Materiale: {dati_generali.get('materiale', 'N/D')}")
        context_lines.append(f"- Anno: {dati_generali.get('anno', 'N/D')}")
        context_lines.append(f"- Zona sismica: {dati_generali.get('zona_sismica', 'N/D')}")
        context_lines.append(f"- Terreno: {dati_generali.get('terreno', 'N/D')}")
        context_lines.append(f"- Topografia: {dati_generali.get('topografia', 'N/D')}")
        context_lines.append(f"- Comune/CAP: {dati_generali.get('comune_cap', 'N/D')}")
        context_lines.append("")
        context_lines.append("VULNERABILITA' ATTESE:")
        context_lines.append(f"- Normativa probabile: {vulnerabilita_attese.get('normativa_probabile', 'N/D')}")
        for voce in vulnerabilita_attese.get("vulnerabilita_attese", []) or []:
            context_lines.append(f"- {voce}")

    if final_synthesis:
        context_lines.append("")
        context_lines.append("SINTESI FINALE:")
        context_lines.append(f"- Quadro sintetico: {final_synthesis.get('quadro_sintetico', 'N/D')}")
        context_lines.append(f"- Indizio di attenzione: {final_synthesis.get('indizio_attenzione', 'N/D')}")
        context_lines.append(f"- Motivazione: {final_synthesis.get('motivazione_indizio', 'N/D')}")
        for passo in final_synthesis.get("prossimi_passi", []) or []:
            context_lines.append(f"- Prossimo passo: {passo}")

    context_block = "\n".join(context_lines).strip()

    if context_block:
        context_block = f"\n{context_block}\n"

    prompt = f"""
    Sei un Computista e Stimatore Edile italiano.
    Basandoti sull'analisi seguente e sul contesto tecnico fornito, estrai gli interventi e produci una stima parametrica dei prezzi unitari medi (riferimento DEI/Regionali 2024).

    CONTEXTO TECNICO:
    {context_block}

    ANALISI STRUTTURALE:
    {analysis_text}

    Restituisci SOLO una tabella Markdown con colonne:
    | Problema | Urgenza | Intervento | Unità di Misura | Quantità Stimata | Prezzo Unitario Stimato (€) | Totale Stimato (€) | Note |

    Regole:
    - Usa range realistici (min-max) quando il testo non consente un valore puntuale.
    - Se il dato non è stimabile da testo, scrivi "Da definire in sopralluogo".
    - Se il contesto consente una stima, indica una quantità plausibile e il totale coerente.
    - Privilegia interventi coerenti con il materiale, l'anno, la vulnerabilità attesa e la sintesi finale.
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
