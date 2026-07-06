from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)

print("X:", pdf.get_x())
print("Y:", pdf.get_y())
print("EPW:", pdf.epw)

pdf.multi_cell(pdf.epw, 8, text="Hola mundo")

pdf.output("test.pdf")

print("PDF generado correctamente")