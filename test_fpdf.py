from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.cell(40, 10, 'Hello World!')
output = pdf.output(dest='S')
print(f"Type: {type(output)}")
try:
    encoded = output.encode('latin-1')
    print("Encoding success")
except Exception as e:
    print(f"Encoding failed: {e}")
