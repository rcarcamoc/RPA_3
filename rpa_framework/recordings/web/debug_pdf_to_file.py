import pypdf
import os

pdf_path = r"c:\Desarrollo\RPA_3\rpa_framework\utils\pdf.pdf"
output_path = r"c:\Desarrollo\RPA_3\rpa_framework\recordings\web\debug_pdf_output.txt"

if not os.path.exists(pdf_path):
    with open(output_path, 'w') as out:
        out.write(f"Error: {pdf_path} no existe.")
else:
    try:
        with open(pdf_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            with open(output_path, 'w', encoding='utf-8') as out:
                out.write(f"Número de páginas: {len(reader.pages)}\n")
                for i, page in enumerate(reader.pages):
                    out.write(f"\n--- PAGINA {i+1} ---\n")
                    text = page.extract_text()
                    if text:
                        out.write(text + "\n")
                    else:
                        out.write("[Vacia o sin texto extraible]\n")
        print(f"Salida escrita en {output_path}")
    except Exception as e:
        with open(output_path, 'w') as out:
            out.write(f"Error al leer el PDF: {e}")
