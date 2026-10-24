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
    from utils.error_handler import handle_error_and_exit
except ImportError:
    try:
        from rpa_framework.utils.telegram_manager import enviar_alerta_todos
        from rpa_framework.utils.error_handler import handle_error_and_exit
    except ImportError:
        def enviar_alerta_todos(msg): pass
        def handle_error_and_exit(s, e): sys.exit(1)

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
            text='Mim65449167#',
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
        elif estado in ['sin registros para trabajar', 'Error']:
            # No marcar VPN como Error; tratarlo como sin datos / sin registros para trabajar
            nuevo_estado = 'sin registros para trabajar'
            query = "UPDATE ris.registro_acciones SET estado = %s, observacion = %s, `update` = NOW() WHERE estado = 'En Proceso'"
            msg_corto = (observacion[:250] + '...') if observacion and len(observacion) > 250 else observacion
            cursor.execute(query, (nuevo_estado, msg_corto))
            
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

def mostrar_popup_vpn(timeout_segundos=60):
    """
    Muestra una ventana llamativa que pide al usuario conectar la VPN.
    Incluye temporizador para cerrar limpiamente como 'sin registros para trabajar'
    si no hay interacción en ejecuciones automáticas/desatendidas.
    """
    enviar_alerta_todos("🚨 <b>ASISTENCIA REQUERIDA</b> 🚨\nLa VPN se encuentra desconectada. El proceso está pausado esperando conexión.")
    
    root = tk.Tk()
    root.title("CONEXIÓN VPN REQUERIDA")
    
    # Hacer que la ventana aparezca al frente
    root.attributes("-topmost", True)
    
    # Dimensiones y posición central
    w, h = 500, 480
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
    frame = tk.Frame(root, bg="#1a1a1a", padx=30, pady=25)
    frame.pack(expand=True, fill="both")

    # Ícono/Título
    lbl_icon = tk.Label(frame, text="🔒", font=("Segoe UI", 44), bg="#1a1a1a", fg="#e74c3c")
    lbl_icon.pack()

    lbl_titulo = tk.Label(frame, text="VPN DESCONECTADA", font=title_font, bg="#1a1a1a", fg="#ffffff")
    lbl_titulo.pack(pady=(0, 8))

    lbl_msg = tk.Label(frame, 
                       text="El sistema está esperando a que inicie la VPN.\nPor favor, conéctese para continuar con el proceso.", 
                       font=msg_font, bg="#1a1a1a", fg="#bdc3c7", justify="center")
    lbl_msg.pack(pady=(0, 15))

    lbl_timer = tk.Label(frame, text=f"Auto-espera limpia en: {timeout_segundos}s", font=("Segoe UI", 10, "italic"), bg="#1a1a1a", fg="#f39c12")
    lbl_timer.pack(pady=(0, 15))

    # Botones con estilo
    btn_gp = tk.Button(frame, text="🚀 RE-INICIAR GLOBALPROTECT", command=abrir_globalprotect,
                      font=btn_font, bg="#3498db", fg="white", activebackground="#2980b9",
                      relief="flat", cursor="hand2", width=25, pady=7)
    btn_gp.pack(pady=4)

    def check_done():
        try:
            root.destroy()
        except Exception:
            pass

    btn_ok = tk.Button(frame, text="✅ YA ESTOY CONECTADO", command=check_done,
                      font=btn_font, bg="#27ae60", fg="white", activebackground="#219150",
                      relief="flat", cursor="hand2", width=25, pady=7)
    btn_ok.pack(pady=4)

    def cancelar(por_timeout=False):
        msg = "Tiempo de espera agotado sin conexión VPN." if por_timeout else "El usuario canceló la espera de VPN."
        print(f"[VPN] {msg} -> Tratando como sin datos / sin registros para trabajar.")
        try:
            root.destroy()
        except Exception:
            pass
        db_update('sin registros para trabajar', msg)
        sys.exit(2)

    btn_cancel = tk.Button(frame, text="❌ CANCELAR PROCESO", command=lambda: cancelar(False),
                          font=btn_font, bg="#c0392b", fg="white", activebackground="#a93226",
                          relief="flat", cursor="hand2", width=25, pady=7)
    btn_cancel.pack(pady=4)

    # Cuenta regresiva para desatendido
    segundos_restantes = [timeout_segundos]
    def actualizar_cuenta():
        segundos_restantes[0] -= 1
        if segundos_restantes[0] <= 0:
            cancelar(por_timeout=True)
        else:
            try:
                lbl_timer.config(text=f"Auto-espera limpia en: {segundos_restantes[0]}s")
                root.after(1000, actualizar_cuenta)
            except Exception:
                pass

    root.after(1000, actualizar_cuenta)
    root.mainloop()

def main():
    try:
        # 1. Al inicio debe existir siempre el UPDATE a 'En Proceso'
        db_update('En Proceso')
        
        # 2. Lógica del script: Verificar VPN
        max_intentos = 2
        for intento in range(max_intentos):
            if vpn_conectada_palo_alto():
                break
            print(f"Intento {intento+1}/{max_intentos} de conexión VPN...")
            abrir_globalprotect()
            ejecutar_clics_vpn()
            if vpn_conectada_palo_alto():
                break
            # Si después de los clics sigue desconectada, mostramos el popup para ayuda manual
            mostrar_popup_vpn(timeout_segundos=60)

        # Si aún no está conectada, salir limpiamente con código 2 sin marcar error
        if not vpn_conectada_palo_alto():
            msg = "VPN no conectada. Finalizando ciclo limpiamente (sin registros para trabajar)."
            print(f"[VPN] {msg}")
            db_update('sin registros para trabajar', msg)
            sys.exit(2)
        
        print("VPN OK. Procediendo...")
        sys.exit(0)
        
    except SystemExit as se:
        sys.exit(se.code)
    except Exception as e:
        # Los errores de verificación de VPN se tratan como sin datos (código 2)
        desc_falla = f"Verificación VPN: {str(e)}"
        print(f"[VPN] {desc_falla} -> Tratando como sin datos / sin registros para trabajar.")
        db_update('sin registros para trabajar', desc_falla)
        sys.exit(2)

if __name__ == "__main__":
    main()
