import report_generator
import io

# Dummy data
data = {
    "materiale": "Cemento Armato",
    "anno": 1970,
    "zona_sismica": 2,
    "terreno": "B",
    "topografia": "T1",
    "normativa": "DM 1996",
    "lc": "LC1",
    "fc": 1.35
}
analysis_text = "Analisi di prova con caratteri speciali: à è ì ò ù €"
images = [] # Empty list for now

try:
    print("Generating PDF...")
    pdf_bytes = report_generator.generate_pdf(data, analysis_text, images)
    print(f"Success! Generated {len(pdf_bytes)} bytes.")
    with open("debug_output.pdf", "wb") as f:
        f.write(pdf_bytes)
    print("Saved to debug_output.pdf")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
