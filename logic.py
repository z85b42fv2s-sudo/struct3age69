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
