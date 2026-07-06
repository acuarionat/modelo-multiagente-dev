from fpdf import FPDF
from fpdf.enums import XPos, YPos

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)

print("Inicial:")
print("X:", pdf.get_x())

pdf.multi_cell(0, 10, text="Decision Final", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

print("Despues de multi_cell con enums:")
print("X:", pdf.get_x())

try:
    pdf.multi_cell(0, 8, text="Hola", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    print("Multi_cell de 'Hola' funciono!")
except Exception as e:
    print("Error en 'Hola':", str(e))
