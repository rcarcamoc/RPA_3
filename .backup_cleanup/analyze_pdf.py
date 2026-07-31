import pypdf
import re

path = r'c:\Desarrollo\RPA_3\48571197_0011441546.pdf'
text_content = ""

try:
    reader = pypdf.PdfReader(path)
    for page in reader.pages:
        text_content += page.extract_text() + "\n"
    
    # Normalize some potential weird spaces in PDF text extraction
    # text_content = re.sub(r'\s+', ' ', text_content) 
    # Actually, keep newlines for "between line X and Y" logic
    
    print("--- CONTENT START ---")
    print(text_content[:2000]) # First 2000 chars
    print("--- CONTENT END ---")
    
    # Test specific extraction
    print("\n--- TEST EXTRACTION ---")
    
    # 1. Numero de documento
    # User said format: "Número de documento 0019975798-"
    # Regex trying to be robust
    match_doc = re.search(r'Número de documento\s*[:\.]?\s*([\d\-]+)', text_content, re.IGNORECASE)
    if match_doc:
        print(f"Doc Number Found: {match_doc.group(1)}")
    else:
        print("Doc Number NOT Found")
        
    # 2. Text between "Número de ficha" (next line) and "Atentamente"
    # The user said "entre la linea siguiente a Número de ficha y Atentamente"
    # So look for "Número de ficha", gobble the rest of that line, then start capturing until Atentamente.
    
    pattern_body = r'Número de ficha.*?\n(.*?)(?=\n\s*Atentamente|\Z)'
    match_body = re.search(pattern_body, text_content, re.DOTALL | re.IGNORECASE)
    
    if match_body:
        extracted = match_body.group(1).strip()
        print(f"Body Content Found:\n{extracted}")
    else:
        print("Body Content NOT Found")

except Exception as e:
    print(f"Error: {e}")
