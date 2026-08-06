from fpdf import FPDF
import tempfile
import os

class PDFReport(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 15)
        self.cell(0, 10, 'Structural 3age - Report Analisi', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 6, title, 0, 1, 'L', True)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 5, body)
        self.ln()


def _format_synthesis_text(final_synthesis):
    if not final_synthesis:
        return "Sintesi finale non disponibile."

    lines = []
    quadro = final_synthesis.get("quadro_sintetico", "")
    if quadro:
        lines.append(quadro)

    tabella = final_synthesis.get("tabella_vulnerabilita", [])
    if tabella:
        lines.append("")
        lines.append("Vulnerabilita' attese vs riscontrate:")
        for row in tabella:
            lines.append(
                f"- {row.get('vulnerabilita', 'N/D')} | Attesa: {row.get('attesa', row.get('attesa_da_normativa', 'N/D'))} | Confermata: {row.get('confermata_da_foto', 'N/D')} | Note: {row.get('note', 'N/D')}"
            )

    indizio = final_synthesis.get("indizio_attenzione", "")
    motivazione = final_synthesis.get("motivazione_indizio", "")
    if indizio or motivazione:
        lines.append("")
        lines.append(f"Indizio di attenzione complessivo: {indizio}")
        if motivazione:
            lines.append(f"Motivazione: {motivazione}")

    prossimi_passi = final_synthesis.get("prossimi_passi", [])
    if prossimi_passi:
        lines.append("")
        lines.append("Prossimi passi consigliati:")
        for passo in prossimi_passi:
            lines.append(f"- {passo}")

    disclaimer = final_synthesis.get("disclaimer", "")
    if disclaimer:
        lines.append("")
        lines.append(disclaimer)

    return "\n".join(lines).strip()


def generate_pdf(data, analysis_text, images, final_synthesis=None, intervention_text=None):
    pdf = PDFReport()
    pdf.add_page()
    
    # 1. Dati Generali
    pdf.chapter_title("1. Dati Generali della Struttura")
    info_text = (
        f"Materiale: {data.get('materiale', 'N/A')}\n"
        f"Anno di Costruzione: {data.get('anno', 'N/A')}\n"
        f"Zona Sismica: {data.get('zona_sismica', 'N/A')}\n"
        f"Terreno: {data.get('terreno', 'N/A')}\n"
        f"Topografia: {data.get('topografia', 'N/A')}\n"
        f"Normativa Probabile: {data.get('normativa', 'N/A')}\n"
        f"Localita: {data.get('localita', 'N/A')}"
    )
    pdf.chapter_body(info_text)

    # 2. Analisi AI
    pdf.chapter_title("2. Analisi AI e Diagnosi")
    # Clean up markdown symbols for better PDF rendering
    # Clean up markdown symbols and handle unicode for standard fonts
    clean_analysis = (analysis_text or "Nessuna analisi AI disponibile.").replace('**', '').replace('###', '')
    clean_analysis = clean_analysis.replace('€', 'EUR').replace('à', "a'").replace('è', "e'").replace('é', "e'").replace('ì', "i'").replace('ò', "o'").replace('ù', "u'")
    # Encode/decode to strip other non-latin-1 chars
    clean_analysis = clean_analysis.encode('latin-1', 'replace').decode('latin-1')
    pdf.chapter_body(clean_analysis)

    # 3. Interventi consigliati
    if intervention_text:
        pdf.chapter_title("3. Interventi Consigliati")
        clean_intervention = intervention_text.replace('**', '').replace('###', '')
        clean_intervention = clean_intervention.replace('€', 'EUR').replace('à', "a'").replace('è', "e'").replace('é', "e'").replace('ì', "i'").replace('ò', "o'").replace('ù', "u'")
        clean_intervention = clean_intervention.encode('latin-1', 'replace').decode('latin-1')
        pdf.chapter_body(clean_intervention)

    # 4. Sintesi finale
    if final_synthesis:
        pdf.chapter_title("4. Sintesi Finale e Report")
        clean_synthesis = _format_synthesis_text(final_synthesis)
        clean_synthesis = clean_synthesis.replace('€', 'EUR').replace('à', "a'").replace('è', "e'").replace('é', "e'").replace('ì', "i'").replace('ò', "o'").replace('ù', "u'")
        clean_synthesis = clean_synthesis.encode('latin-1', 'replace').decode('latin-1')
        pdf.chapter_body(clean_synthesis)

    # 5. Immagini
    if images:
        pdf.add_page()
        pdf.chapter_title("5. Documentazione Fotografica")
        for img_file in images:
            try:
                # Save temp file to read it with FPDF
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(img_file.getvalue())
                    tmp_path = tmp.name
                
                # Add image (limit width to 100mm)
                pdf.image(tmp_path, w=100)
                pdf.ln(5)
                
                # Clean up
                os.unlink(tmp_path)
            except Exception as e:
                pdf.cell(0, 10, f"Errore caricamento immagine: {str(e)}", 0, 1)

    # Restituisci il PDF come bytes
    return pdf.output(dest="S").encode("latin1")
