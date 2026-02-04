import pypdf
import re
import sys

# Set output encoding to utf-8
sys.stdout.reconfigure(encoding='utf-8')

path = r'c:\Desarrollo\RPA_3\48571197_0011441546.pdf'
text_content = ""

try:
    reader = pypdf.PdfReader(path)
    for page in reader.pages:
        text_content += page.extract_text() + "\n"
    
    print("--- START RESULTS ---")
    
    # 1. Numero de documento
    match_doc = re.search(r'Número de documento\s*[:\.]?\s*([\d\-]+)', text_content, re.IGNORECASE)
    if match_doc:
        print(f"RESULT_DOC: {match_doc.group(1)}")
    else:
        print("RESULT_DOC: NOT FOUND")
        
    # 2. Context check
    idx = text_content.find("Número de ficha")
    if idx != -1:
         print(f"CONTEXT_FOUND_AT: {idx}")
    else:
         print("CONTEXT: 'Número de ficha' string not found in extracted text")
         # Print all text if not found (briefly)
         # print(text_content)

    # 3. Extraction
    # If "Número de ficha" is not found, maybe it's "Numero de ficha" (no accent) or different spacing
    # Making regex flexible
    pattern_body = r'N[úu]mero de ficha.*?\n(.*?)(?=\n\s*Atentamente|\Z)'
    match_body = re.search(pattern_body, text_content, re.DOTALL | re.IGNORECASE)
    
    if match_body:
        extracted = match_body.group(1).strip()
        print(f"RESULT_BODY_START: {extracted[:100].replace(chr(10), ' ')}")
    else:
        print("RESULT_BODY: NOT FOUND")

    print("--- END RESULTS ---")

except Exception as e:
    print(f"Error: {e}")
