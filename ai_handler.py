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

    def _build_context_block():
        context_lines = []

        if context_data:
            dati_generali = context_data.get("dati_generali", {}) or {}
            vulnerabilita_attese = context_data.get("vulnerabilita_attese", {}) or {}
            context_lines.append("DATI DELL'EDIFICIO E CONTESTO:")
            for key, label in [
                ("destinazione_uso", "Destinazione d'uso"),
                ("numero_piani", "Numero di piani"),
                ("superficie_totale", "Superficie totale"),
                ("altezza_edificio", "Altezza edificio"),
                ("anno", "Anno di costruzione"),
                ("materiale", "Materiale strutturale"),
                ("zona_sismica", "Zona sismica"),
                ("classe_uso", "Classe d'uso"),
                ("stato_conservazione", "Stato di conservazione"),
                ("livello_vulnerabilita", "Livello di vulnerabilità stimato"),
                ("terreno", "Categoria sottosuolo / terreno"),
                ("topografia", "Categoria topografica"),
                ("comune_cap", "Comune / CAP"),
            ]:
                value = dati_generali.get(key, "N/D")
                context_lines.append(f"- {label}: {value}")

            criticita = dati_generali.get("criticita_riscontrate", []) or []
            if criticita:
                context_lines.append("- Principali criticità riscontrate:")
                for voce in criticita:
                    context_lines.append(f"  - {voce}")

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
        return f"\n{context_block}\n" if context_block else ""

    context_block = _build_context_block()

    prompt = f"""
    Sei un ingegnere civile strutturista e computista estimativo con esperienza in interventi di miglioramento e adeguamento sismico in Italia.
    Il tuo compito è stimare il costo indicativo degli interventi strutturali necessari su un edificio sulla base delle informazioni fornite.
    Usa come base un prezzario ufficiale, ad esempio Prezzario DEI o prezzario regionale coerente con il contesto italiano, selezionando le voci più pertinenti e motivando la scelta.

    Obiettivo:
    1. Individua gli interventi strutturali più appropriati.
    2. Spiega brevemente perché ogni intervento è consigliato.
    3. Stima un intervallo di costo realistico basato sui prezzi medi italiani aggiornati.
    4. Specifica l'unità di misura utilizzata.
    5. Indica il livello di affidabilità della stima.
    6. Evidenzia le principali variabili che possono modificare significativamente il costo.

    CONTEXTO TECNICO:
    {context_block}

    ANALISI STRUTTURALE:
    {analysis_text}

    Restituisci la risposta in Markdown, con questa struttura obbligatoria:

    ## Tabella costi interventi
    | Intervento | Motivazione | Costo minimo (€) | Costo massimo (€) | Unità di misura | Affidabilità |

    ## Costo totale stimato
    - minimo: ...
    - massimo: ...

    ## Ipotesi adottate
    - ...

    ## Lavorazioni non comprese
    - ...

    ## Fattori che possono modificare il costo
    - ...

    Regole:
    - Non fare una semplice stima generica: scegli interventi specifici e coerenti con i dati dell'edificio.
    - Se mancano dati chiave, usa ipotesi esplicite e conserva l'affidabilità su "Bassa" o "Media".
    - Se il dato non è stimabile con ragionevole affidabilità, scrivi "Da definire in sopralluogo".
    - Usa intervalli realistici min-max per ogni costo.
    - Il totale minimo e massimo deve essere coerente con la somma delle voci.
    - Nessun testo extra fuori dalle sezioni richieste.
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
