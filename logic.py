def get_vulnerabilities(year, material):
    """
    Restituisce la normativa probabile e una lista di vulnerabilità tipiche
    basate sull'anno di costruzione e il materiale.
    """
    vulnerabilities = []
    normativa = "Sconosciuta"

    if year < 1974:
        normativa = "Pre-Normativa Sismica (R.D. 1939 o precedenti)"
        if material == "Cemento Armato":
            vulnerabilities = [
                "Barre lisce (aderenza degradata)",
                "Staffe rade e non chiuse a 135° (scarso confinamento)",
                "Nodi non confinati (rottura fragile nodo)",
                "Telai monodirezionali (scarsa resistenza in una direzione)",
                "Assenza di gerarchia delle resistenze"
            ]
        elif material == "Muratura":
            vulnerabilities = [
                "Assenza di cordoli in c.a.",
                "Solai deformabili nel proprio piano",
                "Scarsa connessione tra pareti ortogonali",
                "Muratura a sacco o di scarsa qualità"
            ]
    elif 1974 <= year < 1996:
        normativa = "L. 64/1974 - D.M. 1984 (Vecchia Normativa Sismica)"
        if material == "Cemento Armato":
            vulnerabilities = [
                "Possibile mancanza di dettagli per la duttilità",
                "Staffe ancora potenzialmente insufficienti nei nodi",
                "Verifiche alle tensioni ammissibili (non allo stato limite)"
            ]
        elif material == "Muratura":
            vulnerabilities = [
                "Connessioni migliorabili ma non garantite",
                "Possibile assenza di intonaco armato o catene"
            ]
    elif 1996 <= year < 2008:
        normativa = "D.M. 1996"
        vulnerabilities = ["Adeguamento sismico parziale rispetto agli standard moderni"]
    else:
        normativa = "NTC 2008 / NTC 2018 (Moderna)"
        vulnerabilities = ["Generalmente conforme, verificare degrado o errori esecutivi"]

    return normativa, vulnerabilities

def calculate_knowledge_level(geom, dettagli, materiali):
    """
    Calcola il Livello di Conoscenza (LC) e il Fattore di Confidenza (FC).
    """
    # Logica semplificata basata sulla quantità di info
    score = 0
    if geom: score += 1
    if dettagli: score += 1
    if materiali: score += 1

    lc = "LC1"
    fc = 1.35
    suggestions = []

    if score == 1:
        lc = "LC1 (Conoscenza Limitata)"
        fc = 1.35
        if not geom: suggestions.append("Eseguire rilievo geometrico completo.")
        if not dettagli: suggestions.append("Eseguire indagini simulate o limitate per dettagli costruttivi.")
        if not materiali: suggestions.append("Eseguire prove limitate sui materiali.")
    elif score == 2:
        lc = "LC2 (Conoscenza Adeguata)"
        fc = 1.20
        if not geom: suggestions.append("Completare il rilievo geometrico.")
        if not dettagli: suggestions.append("Estendere le indagini sui dettagli costruttivi.")
        if not materiali: suggestions.append("Estendere le prove sui materiali.")
    elif score == 3:
        lc = "LC3 (Conoscenza Accurata)"
        fc = 1.00
        suggestions = ["Livello di conoscenza massimo raggiunto."]
    else:
        lc = "LC0 (Insufficiente)"
        fc = 1.35 # Default penalizzante
        suggestions = ["Acquisire almeno la geometria e dati base."]

    return lc, fc, suggestions

def recommend_analysis_type(material, reg_pianta, reg_altezza):
    """
    Consiglia il tipo di analisi strutturale.
    """
    if material == "Muratura":
        if reg_pianta and reg_altezza:
            return "Analisi Statica Non Lineare (Pushover) o Statica Lineare (se applicabile)"
        else:
            return "Analisi Statica Non Lineare (Pushover) con modello a telaio equivalente o continuo"
    
    # Cemento Armato
    if reg_pianta and reg_altezza:
        return "Analisi Dinamica Lineare (Modale) o Statica Lineare (se T1 < 2.5 Tc)"
    elif not reg_pianta and reg_altezza:
        return "Analisi Dinamica Lineare (Modale) con eccentricità accidentale"
    else:
        return "Analisi Statica Non Lineare (Pushover) o Dinamica Non Lineare (Time History) per irregolarità forti"
