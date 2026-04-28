import psutil
import mysql.connector
import sys
import tkinter as tk
from tkinter import font as tkfont
import subprocess
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
try:
    from utils.telegram_manager import enviar_alerta_todos
except ImportError:
    def enviar_alerta_todos(msg): pass

# Nombre de este nodo para el registro
NODO_ACTUAL = "Verifica VPN"

def ejecutar_clics_vpn():
    """
    Ejecuta los clics grabados en ksy.py pero integrados aquí 
    para automatizar la conexión de la VPN.
    """
    try:
        from pywinauto import Application
        from core.executor import ActionExecutor
        from core.action import Action, ActionType
        from datetime import datetime
        import time

        print("Iniciando automatización de clics para conexión VPN...")
        
        # Setup similar a ksy.py
        try:
            app = Application(backend='uia').connect(path="explorer.exe")
        except:
            app = Application(backend='uia')
        
        executor = ActionExecutor(app, {})

        # Acción 1: CLICK Conectar inicial
        action = Action(
            type=ActionType.CLICK,
            selector={'name': 'Conectar', 'control_type': 'Button'},
            position={'x': 1747, 'y': 1003},
            duration=0.5,
            wait_before=1.0,
            timestamp=datetime.now()
        )
        executor.execute(action)

        # Acción 2: CLICK Campo de texto
        action = Action(
            type=ActionType.CLICK,
            selector={'automation_id': '1167'},
            position={'x': 1746, 'y': 911},
            duration=0.8,
            wait_before=1.5,
            timestamp=datetime.now()
        )
        executor.execute(action)

        # Acción 3: TYPE_TEXT Contraseña
        action = Action(
            type=ActionType.TYPE_TEXT,
            text='Mim21556167#',
            wait_before=1.0,
            timestamp=datetime.now()
        )
        executor.execute(action)

        # Acción 4: Presionar ENTER después de la contraseña
        print("Presionando ENTER y esperando 20 segundos para la conexión...")
        action_enter = Action(
            type=ActionType.KEY_PRESS,
            key_code='ENTER',
            wait_before=0.5,
            timestamp=datetime.now()
        )
        executor.execute(action_enter)

        # Esperar 20 segundos para que la conexión se estabilice
        time.sleep(20)
        
        print("Automatización de clics y espera completada.")
        return True
    except Exception as e:
        print(f"Error en automatización de clics: {e}")
        return False

def db_update(estado, observacion=None):
    """
    Gestiona las actualizaciones en la base de datos ris.registro_acciones.
    """
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='ris',
            connect_timeout=5
        )
        cursor = conn.cursor()
        
        if estado == 'En Proceso':
            # Inicio del script: actualiza el nodo actual y el timestamp
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (NODO_ACTUAL, estado))
        elif estado == 'Error':
            # Cierre por error: registra el estado y la observación corta
            query = "UPDATE ris.registro_acciones SET estado = 'Error', observacion = %s WHERE estado = 'En Proceso'"
            # Limitamos la observación a un largo razonable
            msg_corto = (observacion[:250] + '...') if observacion and len(observacion) > 250 else observacion
            cursor.execute(query, (msg_corto,))
            
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Advertencia: No se pudo actualizar la base de datos: {e}")

def vpn_conectada_palo_alto():
    """
    Verifica si la VPN de Palo Alto está activa buscando una interfaz 
    con IP en el rango 10.x.x.x que no sea APIPA.
    """
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        for iface, stat in stats.items():
            if stat.isup and stat.speed > 0:  # UP y con velocidad
                for addr_obj in addrs.get(iface, []):
                    # Verificamos IPv4 y rango 10.
                    if (addr_obj.family.name == 'AF_INET' and 
                        addr_obj.address.startswith('10.') and 
                        not addr_obj.address.startswith('169.254')):
                        print(f"VPN detectada: {iface} UP con IP {addr_obj.address}")
                        return True
    except Exception as e:
        print(f"Error verificando interfaces: {e}")
        
    print("No VPN detectada.")
    return False

def abrir_globalprotect():
    """
    Inicia la aplicación GlobalProtect de Palo Alto.
    """
    path = r"C:\Program Files\Palo Alto Networks\GlobalProtect\PanGPA.exe"
    if os.path.exists(path):
        try:
            subprocess.Popen([path])
            print("Iniciando GlobalProtect...")
        except Exception as e:
            print(f"Error al abrir GlobalProtect: {e}")
    else:
        print("No se encontró PanGPA.exe")

def mostrar_popup_vpn():
    """
    Muestra una ventana llamativa que pide al usuario conectar la VPN.
    """
    enviar_alerta_todos("🚨 <b>ASISTENCIA REQUERIDA</b> 🚨\nLa VPN se encuentra desconectada. El proceso está pausado esperando conexión.")
    
    root = tk.Tk()
    root.title("CONEXIÓN VPN REQUERIDA")
    
    # Hacer que la ventana aparezca al frente
    root.attributes("-topmost", True)
    
    # Dimensiones y posición central
    w, h = 500, 450
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    x = (ws/2) - (w/2)
    y = (hs/2) - (h/2)
    root.geometry('%dx%d+%d+%d' % (w, h, x, y))
    
    root.configure(bg="#1a1a1a")  # Fondo oscuro elegante

    # Fuentes
    title_font = tkfont.Font(family="Segoe UI", size=20, weight="bold")
    msg_font = tkfont.Font(family="Segoe UI", size=12)
    btn_font = tkfont.Font(family="Segoe UI", size=11, weight="bold")

    # Contenedor principal
    frame = tk.Frame(root, bg="#1a1a1a", padx=30, pady=30)
    frame.pack(expand=True, fill="both")

    # Ícono/Título
    lbl_icon = tk.Label(frame, text="🔒", font=("Segoe UI", 48), bg="#1a1a1a", fg="#e74c3c")
    lbl_icon.pack()

    lbl_titulo = tk.Label(frame, text="VPN DESCONECTADA", font=title_font, bg="#1a1a1a", fg="#ffffff")
    lbl_titulo.pack(pady=(0, 10))

    lbl_msg = tk.Label(frame, 
                       text="El sistema está esperando a que inicie la VPN.\nPor favor, conéctese para continuar con el proceso.", 
                       font=msg_font, bg="#1a1a1a", fg="#bdc3c7", justify="center")
    lbl_msg.pack(pady=(0, 25))

    # Botones con estilo
    btn_gp = tk.Button(frame, text="🚀 RE-INICIAR GLOBALPROTECT", command=abrir_globalprotect,
                      font=btn_font, bg="#3498db", fg="white", activebackground="#2980b9",
                      relief="flat", cursor="hand2", width=25, pady=8)
    btn_gp.pack(pady=5)

    def check_done():
        root.destroy()

    btn_ok = tk.Button(frame, text="✅ YA ESTOY CONECTADO", command=check_done,
                      font=btn_font, bg="#27ae60", fg="white", activebackground="#219150",
                      relief="flat", cursor="hand2", width=25, pady=8)
    btn_ok.pack(pady=5)

    def cancelar():
        msg = "El usuario canceló la espera de VPN."
        print(msg)
        # Gestionar error de negocio deteniendo el workflow
        db_update('Error', observacion=msg)
        root.destroy()
        sys.exit(1)

    btn_cancel = tk.Button(frame, text="❌ CANCELAR PROCESO", command=cancelar,
                          font=btn_font, bg="#c0392b", fg="white", activebackground="#a93226",
                          relief="flat", cursor="hand2", width=25, pady=8)
    btn_cancel.pack(pady=5)

    root.mainloop()

def main():
    try:
        # 1. Al inicio debe existir siempre el UPDATE a 'En Proceso'
        db_update('En Proceso')
        
        # 2. Lógica del script: Verificar VPN
        # Usamos un loop para esperar hasta que la VPN esté activa
        while not vpn_conectada_palo_alto():
            # Siempre intentamos abrir el programa automáticamente si no hay conexión
            abrir_globalprotect()
            # Intentamos automatizar la conexión con los clics de ksy.py
            ejecutar_clics_vpn()
            # Si después de los clics sigue desconectada, notificamos y salimos
            if not vpn_conectada_palo_alto():
                error_msg = "VPN desconectada: no se pudo conectar automáticamente a GlobalProtect."
                print(f"ERROR: {error_msg}")
                try:
                    try:
                        from utils.error_handler import handle_error_and_exit
                    except ImportError:
                        from rpa_framework.utils.error_handler import handle_error_and_exit
                    handle_error_and_exit("verifica_vpn.py", error_msg)
                except ImportError:
                    try:
                        enviar_alerta_todos(f"🚨 <b>VPN DESCONECTADA</b>🚨\n{error_msg}")
                    except: pass
                    db_update('Error', observacion=error_msg)
                    sys.exit(1)
        
        print("VPN OK. Procediendo...")
        
    except Exception as e:
        desc_falla = str(e)
        try:
            try:
                from utils.error_handler import handle_error_and_exit
            except ImportError:
                from rpa_framework.utils.error_handler import handle_error_and_exit
            handle_error_and_exit("verifica_vpn.py", desc_falla)
        except ImportError:
            db_update('Error', observacion=desc_falla)
            print(f"ERROR: {desc_falla}")
            sys.exit(1)

if __name__ == "__main__":
    main()
