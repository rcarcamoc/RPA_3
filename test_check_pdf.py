try:
    import pypdf
    print("pypdf is installed")
except ImportError:
    print("pypdf is NOT installed")

try:
    import PyPDF2
    print("PyPDF2 is installed")
except ImportError:
    print("PyPDF2 is NOT installed")

path = r'c:\Desarrollo\RPA_3\48571197_0011441546.pdf'
try:
    with open(path, 'rb') as f:
        content = f.read()
        if b'Documento' in content or b'documento' in content:
             print("Found simple text in PDF binary.")
        else:
             print("Did NOT find simple text (stream likely compressed).")
except Exception as e:
    print(e)
