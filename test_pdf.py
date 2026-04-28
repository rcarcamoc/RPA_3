# -*- coding: utf-8 -*-
import pypdf
import re

pdf_path = r'c:\Desarrollo\RPA_3\rpa_framework\utils\pat_cr1.pdf'

pages_text = []
try:
    with open(pdf_path, 'rb') as f:
        reader = pypdf.PdfReader(f)
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                pages_text.append(txt)
except Exception as e:
    print('Error loading pdf:', e)

text_content = ' '.join(pages_text)

# Logic from procesar_pdf_doctor (non-greedy .*?)
PAGE_MARKER = ' [PAGE_BREAK_HERE] '
text_content_pm = PAGE_MARKER.join(pages_text)
pattern_body = r'N[úu]mero de ficha.*?\n(.*?)(?=Atentamente|\Z)'
match_body = re.search(pattern_body, text_content_pm, re.DOTALL | re.IGNORECASE)
diag1 = match_body.group(1) if match_body else 'NOT FOUND'
print('--- procesar_pdf_doctor logic (First Atentamente) ---')
print('Length:', len(diag1))
print('End of diag1 text (Last 100 chars):', diag1[-100:].replace('\n', ' '))


# Logic from procesar_pdf_doctor_url (last Atentamente)
text_content_nl = '\n'.join(pages_text)
start_search = re.search(r'N[úu]mero de ficha.*?\n', text_content_nl, re.IGNORECASE)
if start_search:
    start_index = start_search.end()
    last_atentamente = list(re.finditer(r'Atentamente', text_content_nl, re.IGNORECASE))
    if last_atentamente:
        end_index = last_atentamente[-1].start()
    else:
        end_index = len(text_content_nl)
    diag2 = text_content_nl[start_index:end_index]
else:
    diag2 = 'NOT FOUND'
print('\n--- procesar_pdf_doctor_url logic (Last Atentamente) ---')
print('Length:', len(diag2))
print('End of diag2 text (Last 100 chars):', diag2[-100:].replace('\n', ' '))
