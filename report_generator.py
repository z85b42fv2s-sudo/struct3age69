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

def generate_pdf(data, analysis_text, images):
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
        f"Livello Conoscenza: {data.get('lc', 'N/A')} (FC={data.get('fc', 'N/A')})"
    )
    pdf.chapter_body(info_text)

    # 2. Analisi AI
    pdf.chapter_title("2. Analisi AI e Diagnosi")
    # Clean up markdown symbols for better PDF rendering
    # Clean up markdown symbols and handle unicode for standard fonts
    clean_analysis = analysis_text.replace('**', '').replace('###', '')
    clean_analysis = clean_analysis.replace('€', 'EUR').replace('à', "a'").replace('è', "e'").replace('é', "e'").replace('ì', "i'").replace('ò', "o'").replace('ù', "u'")
    # Encode/decode to strip other non-latin-1 chars
    clean_analysis = clean_analysis.encode('latin-1', 'replace').decode('latin-1')
    pdf.chapter_body(clean_analysis)

    # 3. Immagini
    if images:
        pdf.add_page()
        pdf.chapter_title("3. Documentazione Fotografica")
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
