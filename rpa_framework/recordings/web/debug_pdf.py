import pypdf
import os

pdf_path = r"c:\Desarrollo\RPA_3\rpa_framework\utils\pdf.pdf"

if not os.path.exists(pdf_path):
    print(f"Error: {pdf_path} no existe.")
else:
    try:
        with open(pdf_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            print(f"Número de páginas: {len(reader.pages)}")
            for i, page in enumerate(reader.pages):
                print(f"\n--- PAGINA {i+1} ---")
                text = page.extract_text()
                if text:
                    print(text)
                else:
                    print("[Vacia o sin texto extraible]")
    except Exception as e:
        print(f"Error al leer el PDF: {e}")
