import json
import os
from openai import OpenAI
import streamlit as st


DEFAULT_SYNTHESIS = {
    "quadro_sintetico": "Sintesi non disponibile.",
    "tabella_vulnerabilita": [],
    "indizio_attenzione": "media",
    "motivazione_indizio": "Dati insufficienti per una sintesi affidabile.",
    "prossimi_passi": [],
    "disclaimer": "Questa è una valutazione preliminare automatizzata, non sostituisce un sopralluogo e una relazione firmata da un tecnico abilitato.",
}


def _json_block(value):
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _build_system_prompt(dati_generali, vulnerabilita_attese, esito_visivo):
    blocco_1 = _json_block(dati_generali)
    blocco_2 = _json_block(vulnerabilita_attese)
    blocco_3 = _json_block(esito_visivo)

    parts = [
        "Sei un Ingegnere Strutturista Senior che deve redigere la sintesi finale di un report di pre-screening strutturale.\n\n",
        "NOTA INTERNA: la sintesi non e' una diagnosi definitiva ma un quadro d'insieme che aiuta l'utente a capire priorita' e prossimi passi.\n\n",
        "TI VENGONO FORNITI TRE BLOCCHI DI DATI GIA' ELABORATI (non rielaborarli, usali solo come base):\n\n",
        "[BLOCCO 1 - DATI GENERALI]\n",
        blocco_1,
        "\n\n",
        "[BLOCCO 2 - VULNERABILITA' ATTESE DA NORMATIVA/ANNO/MATERIALE]\n",
        blocco_2,
        "\n\n",
        "[BLOCCO 3 - ESITO ISPEZIONE VISIVA AI]\n",
        blocco_3,
        "\n\n",
        "COMPITO:\n",
        "Incrocia i tre blocchi e produci un'unica sintesi coerente, evidenziando:\n",
        "- dove l'evidenza visiva CONFERMA le vulnerabilita' attese dalla normativa/anno\n",
        "- dove l'evidenza visiva AGGIUNGE problemi non previsti dalla sola classe normativa/anno\n",
        "- dove i dati sono insufficienti per confermare o escludere una vulnerabilita' attesa (es. elemento non visibile in foto)\n\n",
        "VINCOLI:\n",
        "- stessa cautela del prompt di analisi visiva: nessun calcolo, nessuna percentuale, nessuna scadenza temporale specifica\n",
        "- se il blocco 2 e il blocco 3 sono in contraddizione, segnalalo esplicitamente invece di scegliere arbitrariamente quale privilegiare\n\n",
        "OUTPUT OBBLIGATORIO (formato report):\n",
        "1. Quadro sintetico della struttura (2-3 righe, dati generali + tipologia normativa)\n",
        "2. Vulnerabilita' attese vs riscontrate: tabella (vulnerabilita' | attesa da normativa? | confermata da foto? | note)\n",
        "3. Indizio di attenzione complessivo (bassa/media/alta) con motivazione breve\n",
        "4. Prossimi passi consigliati, in ordine di priorita' qualitativa (non temporale)\n\n",
        "Chiudi sempre con:\n",
        '"Questa e\' una valutazione preliminare automatizzata, non sostituisce un sopralluogo e una relazione firmata da un tecnico abilitato."\n',
    ]
    return "".join(parts)


def _normalise_output(payload, fallback_message):
    result = dict(DEFAULT_SYNTHESIS)
    result["quadro_sintetico"] = fallback_message

    if isinstance(payload, dict):
        result.update({k: payload.get(k, result.get(k)) for k in result.keys()})
        if not isinstance(result.get("tabella_vulnerabilita"), list):
            result["tabella_vulnerabilita"] = []
        if not isinstance(result.get("prossimi_passi"), list):
            result["prossimi_passi"] = []
        return result

    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                result.update({k: parsed.get(k, result.get(k)) for k in result.keys()})
                if not isinstance(result.get("tabella_vulnerabilita"), list):
                    result["tabella_vulnerabilita"] = []
                if not isinstance(result.get("prossimi_passi"), list):
                    result["prossimi_passi"] = []
                return result
        except Exception:
            pass

    return result


@st.cache_data(ttl=3600, show_spinner=False)
def generate_final_synthesis(dati_generali, vulnerabilita_attese, esito_visivo):
    """
    Combina i tre blocchi di dati in un'unica chiamata OpenAI e restituisce la sintesi finale strutturata.
    """
    api_key = st.session_state.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
    project_id = st.session_state.get("openai_project") or os.getenv("OPENAI_PROJECT")
    if not api_key:
        return dict(DEFAULT_SYNTHESIS)

    client = OpenAI(api_key=api_key, project=project_id)
    system_prompt = _build_system_prompt(dati_generali, vulnerabilita_attese, esito_visivo)
    user_prompt = (
        "Restituisci esclusivamente un JSON valido con le chiavi: "
        '"quadro_sintetico", "tabella_vulnerabilita", "indizio_attenzione", '
        '"motivazione_indizio", "prossimi_passi", "disclaimer".'
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1200,
        )
        content = response.choices[0].message.content
        fallback_message = "Sintesi finale generata correttamente."
        return _normalise_output(content, fallback_message)
    except Exception as exc:
        return _normalise_output(
            None,
            f"Sintesi finale non disponibile per un errore nella chiamata AI: {exc}",
        )