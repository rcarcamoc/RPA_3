"""
Diagnóstico profundo del diálogo "Carestream Client" con botón Aceptar.
Ejecutar con el diálogo visible en pantalla.
"""
import sys
import os
import ctypes
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from pywinauto import Application, Desktop, findwindows
import pywinauto
import win32gui
import win32con
import win32process
import win32api

print("=" * 80)
print("DIAGNÓSTICO DEL DIÁLOGO CARESTREAM CLIENT")
print("=" * 80)

# 1. Verificar si el script se ejecuta como Administrador
is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
print(f"\n[1] ¿Script ejecutándose como Administrador? {'SÍ ✅' if is_admin else 'NO ❌'}")

# 2. Listar TODAS las ventanas con win32gui (nivel más bajo posible)
print("\n[2] TODAS las ventanas visibles del sistema (win32gui):")
print("-" * 80)

all_windows = []
def enum_callback(hwnd, results):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        results.append((hwnd, title, class_name, pid))

win32gui.EnumWindows(enum_callback, all_windows)

carestream_pids = set()
dialog_hwnd = None
for hwnd, title, class_name, pid in all_windows:
    if title:  # Solo las que tienen título
        marker = ""
        if "Carestream" in title or "Workflow" in title:
            carestream_pids.add(pid)
            marker = " ★ CARESTREAM"
        if "Carestream Client" == title:
            dialog_hwnd = hwnd
            marker = " ★★★ DIÁLOGO TARGET"
        print(f"  hwnd={hwnd:8d} | PID={pid:6d} | '{title}' | Class='{class_name}'{marker}")

# 3. Buscar el diálogo específicamente entre las ventanas HIJAS
print("\n[3] Buscando ventanas hijas de los PIDs de Carestream:")
print("-" * 80)

for pid in carestream_pids:
    print(f"\n  --- PID {pid} ---")
    child_windows = []
    def enum_child_callback(hwnd, results):
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        results.append((hwnd, title, class_name))
    
    # Buscar todas las ventanas de este PID
    for hwnd, title, class_name, wpid in all_windows:
        if wpid == pid:
            print(f"    TOP: hwnd={hwnd:8d} | '{title}' | Class='{class_name}'")
            # Enumerar hijos
            child_wins = []
            try:
                win32gui.EnumChildWindows(hwnd, enum_child_callback, child_wins)
                for chwnd, chtitle, chclass in child_wins:
                    if chtitle:
                        marker = " ◄◄◄ BOTÓN!" if "Aceptar" in chtitle or "aceptar" in chtitle.lower() or "OK" == chtitle or "Accept" in chtitle else ""
                        print(f"      HIJO: hwnd={chwnd:8d} | '{chtitle}' | Class='{chclass}'{marker}")
            except Exception as e:
                print(f"      Error enumerando hijos: {e}")

# 4. Buscar el botón Aceptar en CUALQUIER ventana del sistema
print("\n[4] Búsqueda exhaustiva del botón 'Aceptar' en TODAS las ventanas:")
print("-" * 80)
found_btn = False
for hwnd, title, class_name, pid in all_windows:
    child_wins = []
    try:
        win32gui.EnumChildWindows(hwnd, enum_child_callback, child_wins)
        for chwnd, chtitle, chclass in child_wins:
            if chtitle and ("aceptar" in chtitle.lower() or chtitle == "OK" or chtitle == "&Aceptar"):
                print(f"  ENCONTRADO en ventana '{title}' (hwnd={hwnd}, PID={pid})")
                print(f"    Botón: hwnd={chwnd} | Texto='{chtitle}' | Class='{chclass}'")
                
                # Verificar privilegios del proceso
                try:
                    handle = win32api.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
                    import win32security
                    token = win32security.OpenProcessToken(handle, win32security.TOKEN_QUERY)
                    elevation = win32security.GetTokenInformation(token, win32security.TokenElevation)
                    print(f"    Proceso elevado (Admin): {'SÍ ★★★' if elevation else 'NO'}")
                except Exception as pe:
                    print(f"    No se pudo verificar elevación: {pe}")
                found_btn = True
    except:
        pass

if not found_btn:
    print("  ❌ NO se encontró ningún botón Aceptar en NINGUNA ventana del sistema!")
    print("     Posibles causas:")
    print("     - El botón tiene un texto diferente (verificar visualmente)")
    print("     - El diálogo es dibujado por el propio control (custom rendering)")
    print("     - UIPI bloquea la enumeración desde un proceso no elevado")

# 5. Intentar conectar directamente al diálogo
print("\n[5] Intentando conectar al diálogo por pywinauto (ambos backends):")
print("-" * 80)

for backend in ['uia', 'win32']:
    print(f"\n  Backend: {backend}")
    try:
        desktop = Desktop(backend=backend)
        for w in desktop.windows():
            try:
                wt = w.window_text()
                if "Carestream" in wt and "PACS" not in wt:
                    print(f"    Ventana: '{wt}' | Class: '{w.class_name()}'")
                    # Intentar listar hijos
                    try:
                        children = w.children()
                        for child in children:
                            try:
                                ct = child.window_text()
                                cc = child.class_name() if hasattr(child, 'class_name') else 'N/A'
                                print(f"      Hijo: '{ct}' | Class: '{cc}'")
                            except:
                                pass
                    except Exception as e:
                        print(f"      Error listando hijos: {e}")
            except:
                pass
    except Exception as e:
        print(f"    Error: {e}")

# 6. Verificar integridad (UIPI)
print("\n[6] Verificación UIPI (User Interface Privilege Isolation):")
print("-" * 80)
if dialog_hwnd:
    try:
        _, dialog_pid = win32process.GetWindowThreadProcessId(dialog_hwnd)
        import psutil
        proc = psutil.Process(dialog_pid)
        print(f"  Proceso del diálogo: {proc.name()} (PID: {dialog_pid})")
        print(f"  Ejecutable: {proc.exe()}")
        print(f"  Usuario: {proc.username()}")
    except Exception as e:
        print(f"  Error obteniendo info del proceso: {e}")

    # Intentar enviar un mensaje simple al hwnd del diálogo
    try:
        result = win32gui.SendMessage(dialog_hwnd, win32con.WM_NULL, 0, 0)
        print(f"  SendMessage(WM_NULL) al diálogo: OK (result={result}) — UIPI probablemente NO es el problema")
    except Exception as e:
        print(f"  SendMessage(WM_NULL) al diálogo: FALLÓ — {e} — ★★★ UIPI ESTÁ BLOQUEANDO ★★★")
else:
    print("  No se encontró ventana con título 'Carestream Client' para verificar UIPI")
    print("  El diálogo podría ser un hijo modal sin título propio")

print("\n" + "=" * 80)
print("FIN DEL DIAGNÓSTICO")
print("=" * 80)
