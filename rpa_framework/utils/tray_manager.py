import os
import sys
import json
import time
import threading
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import MenuItem as item, Menu

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from utils.notificador_resumen import notificaciones_pausadas, pausar_notificaciones, reanudar_notificaciones
from utils.llm_auto_manager import get_llm_status_summary, run_auto_verification_logic

def get_rpa_summary_info():
    """
    Obtiene el estado actual de ejecución del RPA y las métricas de casos gestionados en el día.
    """
    is_running = False
    workflow_name = ""
    
    # 1. Verificar estado de ejecución desde execution_state.json
    state_file = Path(__file__).resolve().parent.parent / "config" / "execution_state.json"
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("is_running", False):
                    if time.time() - data.get("updated_at", 0) < 900:
                        is_running = True
                        workflow_name = data.get("workflow", "En ejecución")
        except Exception:
            pass

    # 2. Consultar BD MySQL (registro_acciones) para obtener total del día en curso
    total_hoy = 0
    ok_hoy = 0
    err_hoy = 0
    try:
        import datetime
        import mysql.connector
        from utils.mysql_auto_starter import ensure_mysql_running
        ensure_mysql_running()

        conn = mysql.connector.connect(host="localhost", user="root", password="", database="ris")
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT estado, COUNT(*) as cant 
        FROM registro_acciones 
        WHERE inicio >= %s 
          AND (
              (ultimo_nodo IS NULL OR ultimo_nodo NOT IN ('Validación PACS', 'valida_pacs', 'seleccion int casos pendientes', 'casos_pendientes', 'Inicia RIS'))
              OR numero_documento IS NOT NULL
          )
          AND (observacion IS NULL OR (observacion NOT LIKE '%validación PACS%' AND observacion NOT LIKE '%validacion PACS%') OR numero_documento IS NOT NULL)
        GROUP BY estado
        """
        cursor.execute(query, (today,))
        rows = cursor.fetchall()
        for r in rows:
            cant = r.get("cant", 0)
            total_hoy += cant
            est = str(r.get("estado", "")).lower()
            if "error" in est:
                err_hoy += cant
            elif "terminado" in est or "finalizado" in est:
                ok_hoy += cant
        conn.close()
    except Exception:
        pass

    return {
        "is_running": is_running,
        "workflow_name": workflow_name,
        "total_hoy": total_hoy,
        "ok_hoy": ok_hoy,
        "err_hoy": err_hoy
    }

def build_tooltip_text(info):
    """Genera el texto multilínea que se muestra al pasar el puntero sobre el icono."""
    if info.get("is_running"):
        wf = info.get("workflow_name", "En ejecución")
        wf_str = f"▶️ {wf}" if len(wf) <= 25 else f"▶️ {wf[:22]}..."
    else:
        wf_str = "⏸️ Estado: Inactivo (En espera)"
        
    total = info.get("total_hoy", 0)
    if total > 0:
        casos_str = f"📊 Casos: {total} (✅{info.get('ok_hoy', 0)} | ❌{info.get('err_hoy', 0)})"
    else:
        casos_str = "📊 Casos hoy: 0"
        
    llm_str = get_llm_status_summary()
    tip = f"Bot RPA - Atrys\n{wf_str}\n{casos_str}\n{llm_str}"
    if len(tip) > 127:
        tip = tip[:124] + "..."
    return tip

def create_robot_icon(status='idle'):
    """
    Crea una imagen de icono para la bandeja del sistema utilizando el emoji 🤖
    con una etiqueta 'RPA', sobre un fondo moderno con indicador de estado.
    """
    size = (64, 64)
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Fondo circular elegante con borde (Indigo/Dark Theme)
    draw.ellipse([2, 2, 61, 61], fill=(24, 28, 40, 255), outline=(99, 102, 241, 255), width=2)
    
    # Renderizado de Emoji 🤖 mediante la fuente del sistema Segoe UI Emoji
    emoji_drawn = False
    font_path = "C:/Windows/Fonts/seguiemj.ttf"
    if os.path.exists(font_path):
        try:
            font = ImageFont.truetype(font_path, 34)
            draw.text((15, 2), "🤖", font=font, embedded_color=True)
            emoji_drawn = True
        except Exception:
            emoji_drawn = False
            
    if not emoji_drawn:
        # Fallback gráfico vectorial de robot en caso de fallar la fuente de emoji
        draw.rectangle([20, 14, 44, 38], fill=(99, 102, 241, 255))
        draw.ellipse([24, 20, 30, 26], fill=(255, 255, 255, 255))
        draw.ellipse([34, 20, 40, 26], fill=(255, 255, 255, 255))
        draw.line([32, 8, 32, 14], fill=(99, 102, 241, 255), width=3)
        draw.ellipse([29, 4, 35, 10], fill=(239, 68, 68, 255))

    # Cápsula distintiva con texto 'RPA' para identificar el bot en la bandeja
    draw.rounded_rectangle([14, 42, 50, 58], radius=4, fill=(99, 102, 241, 255))
    try:
        font_txt = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 11)
        draw.text((21, 44), "RPA", font=font_txt, fill=(255, 255, 255, 255))
    except Exception:
        draw.text((21, 44), "RPA", fill=(255, 255, 255, 255))

    # Punto indicador de estado:
    # Verde = Ejecutando workflow / Azul = En espera (Idle) / Amarillo = Notificaciones pausadas
    if status == 'active':
        status_color = (34, 197, 94, 255)   # Verde
    elif status == 'paused':
        status_color = (234, 179, 8, 255)   # Amarillo
    else:
        status_color = (59, 130, 246, 255)  # Azul
        
    draw.ellipse([46, 4, 58, 16], fill=status_color, outline=(24, 28, 40, 255), width=2)
    
    return img

class SystemTrayManager:
    """Administrador del icono en la bandeja de sistema (System Tray) para el servicio RPA Bot."""
    
    def __init__(self, on_stop_callback=None):
        self.icon = None
        self.on_stop_callback = on_stop_callback
        self.running = False

    def _get_workflow_menu_label(self, item=None):
        info = get_rpa_summary_info()
        if info["is_running"]:
            return f"▶️ Flujo Activo: {info['workflow_name']}"
        return "⏸️ Estado: Inactivo (En espera)"

    def _get_cases_menu_label(self, item=None):
        info = get_rpa_summary_info()
        if info["total_hoy"] > 0:
            return f"📊 Casos Hoy: {info['total_hoy']} (✅ {info['ok_hoy']} | ❌ {info['err_hoy']})"
        return "📊 Casos Hoy: 0 gestionados"

    def _get_llm_menu_label(self, item=None):
        return get_llm_status_summary()

    def _manual_update_llm(self, icon, item):
        def task():
            print("⚡ Iniciando actualización manual de modelos LLM desde la bandeja de sistema...")
            if self.icon:
                try:
                    self.icon.notify("Iniciando validación y autoreemplazo de modelos LLM...", "🤖 Bot RPA - Modelos LLM")
                except Exception:
                    pass
            res = run_auto_verification_logic(force=True)
            self.update_icon()
            if self.icon:
                try:
                    status_text = res.get("status", "Completado")
                    details = res.get("details", "")
                    self.icon.notify(f"Resultado: {status_text}\n{details}", "🤖 Modelos LLM Actualizados")
                except Exception:
                    pass

        threading.Thread(target=task, daemon=True, name="ManualLLMUpdateTray").start()

    def _get_notification_label(self, item=None):
        if notificaciones_pausadas():
            return "🔕 Notificaciones: Suspendidas"
        return "🔔 Notificaciones: Activas"

    def _toggle_notifications(self, icon, item):
        if notificaciones_pausadas():
            reanudar_notificaciones()
        else:
            pausar_notificaciones()
        self.update_icon()

    def _open_logs_folder(self, icon, item):
        try:
            logs_dir = Path(__file__).resolve().parent.parent / "logs"
            logs_dir.mkdir(exist_ok=True)
            os.startfile(str(logs_dir))
        except Exception as e:
            print(f"Error al abrir carpeta de logs: {e}")

    def _stop_service(self, icon, item):
        print("🛑 Deteniendo el servicio Bot RPA desde el menú contextual...")
        self.running = False
        if self.on_stop_callback:
            try:
                self.on_stop_callback()
            except Exception as e:
                print(f"Error en callback de detención: {e}")
        self.stop()
        os._exit(0)

    def update_icon(self):
        if self.icon:
            try:
                info = get_rpa_summary_info()
                if notificaciones_pausadas():
                    status = 'paused'
                elif info.get('is_running', False):
                    status = 'active'
                else:
                    status = 'idle'
                    
                self.icon.icon = create_robot_icon(status)
                self.icon.title = build_tooltip_text(info)
            except Exception as e:
                pass

    def notify(self, message: str, title: str = "🤖 Bot RPA - Atrys"):
        """Muestra una burbuja o notificación emergente desde el icono de la bandeja."""
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception as e:
                print(f"Error mostrando notificación tray: {e}")

    def _start_auto_update_loop(self):
        def loop():
            while self.running:
                try:
                    self.update_icon()
                except Exception:
                    pass
                time.sleep(5)
                
        threading.Thread(target=loop, daemon=True, name="TrayAutoUpdate").start()

    def start(self):
        """Inicia el icono en la bandeja de sistema de forma desacoplada."""
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Bot.RPA.Servicio.Atrys")
            except Exception:
                pass

        self.running = True
        info = get_rpa_summary_info()
        status = 'paused' if notificaciones_pausadas() else ('active' if info['is_running'] else 'idle')
        
        menu = Menu(
            item("🤖 Bot RPA - Atrys", None, enabled=False),
            item(self._get_workflow_menu_label, None, enabled=False),
            item(self._get_cases_menu_label, None, enabled=False),
            item(self._get_llm_menu_label, None, enabled=False),
            Menu.SEPARATOR,
            item("⚡ Actualizar Modelos LLM Manualmente", self._manual_update_llm),
            item(self._get_notification_label, self._toggle_notifications),
            item("📋 Abrir carpeta de logs", self._open_logs_folder),
            Menu.SEPARATOR,
            item("🛑 Detener Servicio Bot RPA", self._stop_service)
        )
        
        self.icon = pystray.Icon(
            "Bot_RPA_Service",
            create_robot_icon(status),
            build_tooltip_text(info),
            menu
        )
        self.icon.run_detached()
        self._start_auto_update_loop()
        print("🤖 Icono de Bot RPA con resumen interactivo activado correctamente.")

    def stop(self):
        self.running = False
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
