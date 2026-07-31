
from pywinauto import Desktop
import re

def find_pacs():
    print("Buscando ventana de PACS...")
    for win in Desktop(backend="uia").windows():
        try:
            title = win.window_text()
            if "Carestream" in title or "PACS" in title or "Vue" in title:
                print(f"ENCONTRADA: '{title}'")
                # Intentar obtener info del proceso
                try:
                    proc_id = win.process_id()
                    print(f"  - PID: {proc_id}")
                except: pass
        except:
            pass

if __name__ == "__main__":
    find_pacs()
