
from pywinauto import Desktop
import re

def list_pacs():
    print("Buscando Carestream Vue PACS en el escritorio...")
    pacs_wins = [w for w in Desktop(backend="uia").windows() if "Vue PACS" in w.window_text()]
    
    if not pacs_wins:
        print("No se encontró ninguna ventana con 'Vue PACS' en el título.")
        return
        
    for w in pacs_wins:
        title = w.window_text()
        pid = w.process_id()
        print(f"Título: '{title}'")
        print(f"PID: {pid}")
        try:
            from pywinauto import Application
            app = Application(backend="uia").connect(process=pid)
            print(f"Conectado al proceso: {pid}")
            # Intentar ver si podemos traerla al frente
            # w.set_focus()
        except Exception as e:
            print(f"Incapaz de conectar: {e}")

if __name__ == "__main__":
    list_pacs()
