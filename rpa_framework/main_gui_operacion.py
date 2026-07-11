import os
import sys
import warnings
import subprocess

# --- SUPPRESS CONSOLE NOISE ---
# 1. Suppress pywinauto / COM warnings
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning:pywinauto"
warnings.filterwarnings("ignore", category=UserWarning, message=".*coinit_flags.*")

# 2. Suppress Qt DPI / Window logs
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false;qt.qpa.plugin=false"

# 3. Suppress noisy library logs
import logging
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("selenium").setLevel(logging.ERROR)
logging.getLogger("matplotlib").setLevel(logging.ERROR)

# 4. Custom Filter for console noise (Separators, Dashboard updates, etc.)
class ConsoleNoiseFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        # Omitir separadores largos
        if "=====" in msg:
            return False
        # Omitir confirmación de dashboard
        if "Dashboard actualizado" in msg:
            return False
        # Omitir advertencias de matplotlib específicas (fallback)
        if "categorical units" in msg:
            return False
        return True

logging.getLogger().addFilter(ConsoleNoiseFilter())

# Force STA mode for COM/PyQt compatibility
sys.coinit_flags = 2

# Force running from script dir
os.chdir(os.path.dirname(os.path.abspath(__file__)))


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QPushButton, QMessageBox, QSpinBox, QComboBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

# Imports RPA Framework
try:
    from utils.config_loader import load_config
    from utils.logging_setup import setup_logging
    
    # UI Modules
    from ui.styles import STYLESHEET
    from ui.panels.dashboard_panel import DashboardPanel
    from ui.workflow_panel_v2 import WorkflowPanelV2

    from core.models import Workflow
    from ui.workflow_panel import WorkflowExecutorWorker
    
    from utils.log_cleanup import cleanup_old_logs, PeriodicCleanup
    
except ImportError as e:
    print(f"❌ Error importando módulos RPA: {e}")
    print("Asegúrate de estar en rpa_framework/")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# PANEL DE OPERACIONES
# ============================================================================

class OperacionesPanel(QWidget):
    """Panel personalizado con botones de operación solicitados."""
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.worker = None
        self.is_bg_running = False
        
        self.init_ui()
        
        # Timer para sincronizar estado con el servicio de Telegram en background
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self.check_background_state)
        self.state_timer.start(2000) # Chequeo cada 2 segundos
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Etiqueta de título
        lbl_titulo = QLabel("Panel de Operaciones")
        lbl_titulo.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #333; margin-bottom: 20px;")
        lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_titulo)
        
        layout.addSpacing(10)
        
        # Boton 1: Inicio completo
        self.btn_inicio = QPushButton("▶ Inicio completo")
        self.btn_inicio.setMinimumHeight(60)
        self.btn_inicio.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #4CAF50; color: white; border-radius: 8px;")
        self.btn_inicio.clicked.connect(self.ejecutar_inicio_completo)
        self.btn_inicio.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_inicio)
        
        layout.addSpacing(15)
        
        # Boton 2: Solo Pega en Integra
        self.btn_pega = QPushButton("▶ Solo Pega en Integra")
        self.btn_pega.setMinimumHeight(60)
        self.btn_pega.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #2196F3; color: white; border-radius: 8px;")
        self.btn_pega.clicked.connect(self.ejecutar_pega_integra)
        self.btn_pega.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_pega)
        
        layout.addSpacing(15)
        
        layout.addSpacing(15)
        
        # Boton 3: Rehabilitar último registro
        btn_rehabilitar = QPushButton("🔄 Rehabilitar Último Registro")
        btn_rehabilitar.setMinimumHeight(60)
        btn_rehabilitar.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #FF9800; color: white; border-radius: 8px;")
        btn_rehabilitar.clicked.connect(self.rehabilitar_ultimo_registro)
        btn_rehabilitar.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn_rehabilitar)
        
        layout.addSpacing(30)
        
        # Boton 4: Detener Todo
        self.btn_stop = QPushButton("🛑 Detener Ejecución")
        self.btn_stop.setMinimumHeight(60)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                font-size: 15px; 
                font-weight: bold; 
                background-color: #BDBDBD; 
                color: white; 
                border-radius: 8px;
            }
            QPushButton:enabled {
                background-color: #f44336;
            }
        """)
        self.btn_stop.clicked.connect(self.detiene_todo)
        self.btn_stop.setEnabled(False) 
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_stop)
        
        layout.addSpacing(30)
        
        # --- SECCIÓN DE CONFIGURACIÓN DE LOOP (AL FINAL) ---
        lbl_loop_title = QLabel("⚙️ Configuración de Loop Continuo")
        lbl_loop_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        lbl_loop_title.setStyleSheet("color: #6A1B9A; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 10px;")
        layout.addWidget(lbl_loop_title)
        
        # Tipo de Loop
        layout_type = QHBoxLayout()
        layout_type.addWidget(QLabel("Modo:"))
        self.combo_loop_type = QComboBox()
        self.combo_loop_type.addItems(["Por Cantidad", "Por Tiempo (Horas)", "Infinito"])
        self.combo_loop_type.currentIndexChanged.connect(self.actualizar_visibilidad_loop)
        self.combo_loop_type.setMinimumHeight(35)
        layout_type.addWidget(self.combo_loop_type)
        layout.addLayout(layout_type)
        
        # Contenedores para opciones variables
        # Cantidad (Count)
        self.container_count = QWidget()
        layout_count = QHBoxLayout(self.container_count)
        layout_count.setContentsMargins(0,5,0,5)
        layout_count.addWidget(QLabel("Reiteraciones:"))
        self.spin_iterations = QSpinBox()
        self.spin_iterations.setRange(1, 9999)
        self.spin_iterations.setValue(5)
        self.spin_iterations.setMinimumHeight(35)
        layout_count.addWidget(self.spin_iterations)
        layout.addWidget(self.container_count)
        
        # Tiempo (Timed)
        self.container_timed = QWidget()
        layout_timed = QHBoxLayout(self.container_timed)
        layout_timed.setContentsMargins(0,5,0,5)
        layout_timed.addWidget(QLabel("Duración:"))
        self.spin_duration = QDoubleSpinBox()
        self.spin_duration.setRange(0.1, 72.0)
        self.spin_duration.setValue(1.0)
        self.spin_duration.setSuffix(" hrs")
        self.spin_duration.setMinimumHeight(35)
        layout_timed.addWidget(self.spin_duration)
        layout.addWidget(self.container_timed)
        self.container_timed.hide()
        
        # Error Delay
        layout_delay = QHBoxLayout()
        layout_delay.addWidget(QLabel("Espera en error:"))
        self.spin_error_delay = QSpinBox()
        self.spin_error_delay.setRange(0, 3600)
        self.spin_error_delay.setValue(0)
        self.spin_error_delay.setSuffix(" seg")
        self.spin_error_delay.setMinimumHeight(35)
        layout_delay.addWidget(self.spin_error_delay)
        layout.addLayout(layout_delay)
        
        # Botón de Inicio de Loop
        self.btn_loop = QPushButton("🚀 Iniciar Flujo Continuo (Loop)")
        self.btn_loop.setMinimumHeight(65)
        self.btn_loop.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #9C27B0; color: white; border-radius: 8px; margin-top: 10px;")
        self.btn_loop.clicked.connect(self.ejecutar_loop_reiteraciones)
        self.btn_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_loop)

        layout.addStretch()
        self.setLayout(layout)

    def actualizar_visibilidad_loop(self):
        """Muestra u oculta campos según el modo de loop seleccionado."""
        modo = self.combo_loop_type.currentText()
        self.container_count.setVisible(modo == "Por Cantidad")
        self.container_timed.setVisible(modo == "Por Tiempo (Horas)")
        
    def ejecutar_inicio_completo(self):
        wf_path = os.path.join("workflows", "Sub_work.json")
        self.run_workflow(wf_path)

    def ejecutar_pega_integra(self):
        wf_path = os.path.join("workflows", "pacs.json")
        self.run_workflow(wf_path)

    def check_background_state(self):
        """Chequea si el servicio de Telegram está ejecutando un flujo mediante el archivo state.json."""
        import json
        state_file = os.path.join("config", "execution_state.json")
        bg_running = False
        wf_name = ""
        
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    bg_running = state.get("is_running", False)
                    wf_name = state.get("workflow", "")
            except:
                pass
                
        # Solo actualizamos la UI si el estado cambió
        if bg_running != self.is_bg_running:
            self.is_bg_running = bg_running
            self._update_buttons_state()
            
            if bg_running:
                self.btn_stop.setText(f"🛑 Detener (Servicio: {wf_name})")
            else:
                self.btn_stop.setText("🛑 Detener Ejecución")

    def _update_buttons_state(self):
        # Deshabilitar botones de inicio si hay algo corriendo (UI o BG)
        is_busy = self.is_bg_running or (self.worker and self.worker.isRunning())
        self.btn_inicio.setEnabled(not is_busy)
        self.btn_pega.setEnabled(not is_busy)
        self.btn_loop.setEnabled(not is_busy)
        
        # Habilitar stop si hay algo corriendo
        self.btn_stop.setEnabled(is_busy)

    def ejecutar_loop_reiteraciones(self, tg_params=None):
        """Ejecuta el workflow loop.json con las opciones avanzadas configuradas en el panel."""
        wf_path = os.path.join("workflows", "loop.json")
        
        if tg_params:
            tipo_loop = tg_params["tipo"]
            if tipo_loop == "count":
                reiteraciones = tg_params["valor"]
                duracion = 1.0
            elif tipo_loop == "timed":
                reiteraciones = "5"
                duracion = float(tg_params["valor"])
            else:
                reiteraciones = "5"
                duracion = 1.0
            delay_error = 0
            print(f"🔄 Modo loop desde Telegram: {tipo_loop}")
        else:
            # Mapeo de valores de la UI a tipos de loop internos
            modo_ui = self.combo_loop_type.currentText()
            map_tipo = {
                "Por Cantidad": "count",
                "Por Tiempo (Horas)": "timed",
                "Infinito": "infinite"
            }
            
            tipo_loop = map_tipo.get(modo_ui, "count")
            reiteraciones = str(self.spin_iterations.value())
            duracion = self.spin_duration.value()
            delay_error = self.spin_error_delay.value()
        
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Atención", "Ya hay un workflow en ejecución. Por favor espere a que termine.")
            return
            
        if not os.path.exists(wf_path):
            QMessageBox.critical(self, "Error", f"No se encontró el workflow:\n{wf_path}")
            return
            
        try:
            from core.models import LoopNode
            workflow = Workflow.from_json(wf_path)
            
            # Buscar el nodo de loop y actualizar todas sus propiedades
            found = False
            for node in workflow.nodes:
                if isinstance(node, LoopNode):
                    node.loop_type = tipo_loop
                    node.iterations = reiteraciones
                    node.duration_hours = duracion
                    node.error_delay = delay_error
                    print(f"🔄 UI: Configurando Loop '{node.label}' -> Tipo: {tipo_loop}, Iteraciones: {reiteraciones}, Duración: {duracion}h, Delay Error: {delay_error}s")
                    found = True
            
            if not found:
                print("⚠️ No se encontró ningún nodo de tipo Loop en loop.json")

            self.worker = WorkflowExecutorWorker(workflow)
            self.worker.log_update.connect(lambda msg: print(f"[WORKFLOW]: {msg}"))
            self.worker.finished.connect(self.on_workflow_finished)
            self.worker.error.connect(self.on_workflow_finished)
            self.worker.start()
            
            self.btn_stop.setEnabled(True)
            QMessageBox.information(self, "Ejecutando", f"Se inició el flujo continuo en modo '{modo_ui}'.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error iniciando loop: {e}")
            import traceback
            traceback.print_exc()

    def run_workflow(self, wf_path):
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Atención", "Ya hay un workflow en ejecución. Por favor espere a que termine.")
            return
            
        if not os.path.exists(wf_path):
            QMessageBox.critical(self, "Error", f"No se encontró el workflow:\n{wf_path}")
            return
            
        try:
            workflow = Workflow.from_json(wf_path)
            self.worker = WorkflowExecutorWorker(workflow)
            self.worker.log_update.connect(lambda msg: print(f"[WORKFLOW]: {msg}"))
            self.worker.finished.connect(self.on_workflow_finished)
            self.worker.error.connect(self.on_workflow_finished)
            self.worker.start()
            
            self.btn_stop.setEnabled(True) # Activar boton detener
            QMessageBox.information(self, "Ejecutando", f"Se inició el workflow:\n{os.path.basename(wf_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error iniciando workflow: {e}")
            import traceback
            traceback.print_exc()

    def on_workflow_finished(self, result):
        if isinstance(result, str): # Error message
            QMessageBox.critical(self, "Error", f"Error en la ejecución:\n{result}")
        elif isinstance(result, dict) and result.get("status") == "stopped":
            QMessageBox.warning(self, "Detenido", "Ejecución detenida por el usuario.")
        else:
            QMessageBox.information(self, "Completado", "La ejecución ha finalizado con éxito.")
        
        self.worker = None
        self.btn_stop.setEnabled(False) # Desactivar boton detener

    def detiene_todo(self):
        """Detiene la ejecución actual del worker local o del servicio en background."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.append_log("🛑 Solicitando detención de UI local...", "WARNING")
            self.btn_stop.setEnabled(False)
            
        if self.is_bg_running:
            # Crear archivo de señal para el background service
            try:
                os.makedirs("config", exist_ok=True)
                with open(os.path.join("config", "stop_signal.txt"), "w") as f:
                    f.write("stop")
                self.append_log("🛑 Señal de parada enviada al servicio en background.", "WARNING")
                self.btn_stop.setEnabled(False)
            except Exception as e:
                print(f"Error escribiendo stop_signal.txt: {e}")

    def append_log(self, message, level="INFO"):
        print(f"[{level}] {message}")

    def rehabilitar_ultimo_registro(self):
        try:
            import mysql.connector
            config = {
                'host': 'localhost',
                'user': 'root',
                'password': '',
                'database': 'ris'
            }
            conn = mysql.connector.connect(**config, connect_timeout=5)
            cursor = conn.cursor()
            
            # Subconsulta utilizada para prevenir el error 1093 de MySQL (actualizar la misma tabla de la que se selecciona)
            query = """
            UPDATE ris.registro_acciones 
            SET estado = 'En Proceso' 
            WHERE id = (SELECT max_id FROM (SELECT MAX(id) as max_id FROM ris.registro_acciones) as t)
            """
            cursor.execute(query)
            filas_afectadas = cursor.rowcount
            conn.commit()
            
            cursor.close()
            conn.close()
            
            if filas_afectadas > 0:
                QMessageBox.information(self, "Éxito", "Se ha rehabilitado el último registro correctamente ('En Proceso').")
            else:
                QMessageBox.warning(self, "Aviso", "No se encontró ningún registro para actualizar o ya estaba en proceso.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo conectar a la base de datos o ejecutar la consulta:\n{e}")
            import traceback
            traceback.print_exc()


# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    """Ventana principal (Operación)."""
    
    def __init__(self):
        super().__init__()
        try:
            self.config = load_config("config/ris_config.yaml")
            setup_logging()
        except Exception as e:
            print(f"⚠️ Error cargando configuración: {e}")
            self.config = {}
        
        # Iniciar limpieza periódica (cada hora en punto)
        self.cleanup_manager = PeriodicCleanup()
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("🤖 RPA Framework - Operación")
        self.setGeometry(100, 100, 1000, 700)
        
        # Central widget
        central = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("🤖 RPA Framework - Panel de Operación")
        header_font = QFont("Arial", 16, QFont.Weight.Bold)
        header.setFont(header_font)
        header.setStyleSheet("color: #1976D2; margin: 10px;")
        layout.addWidget(header)
        
        # Tabs
        tabs = QTabWidget()
        
        # 1. Dashboard
        tabs.addTab(DashboardPanel(), "📊 Dashboard")
        
        # 2. Operaciones (NUEVA PESTAÑA EN SEGUNDA POSICIÓN)
        self.panel_operaciones = OperacionesPanel(self.config, self)
        tabs.addTab(self.panel_operaciones, "⚡ Operaciones")
        
        # 3. Workflows
        tabs.addTab(WorkflowPanelV2(self.config), "✨ Workflows")

        layout.addWidget(tabs)
        
        # Footer
        footer = QLabel("✅ RPA Framework | Operación | 2025")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #666; margin: 10px; font-size: 10px;")
        layout.addWidget(footer)
        
        central.setLayout(layout)
        self.setCentralWidget(central)
        
        # Estilos Globales
        self.setStyleSheet(STYLESHEET)

# ============================================================================
# MAIN
# ============================================================================

def main():
    # Validar bases de datos antes de iniciar el GUI
    db_check = os.path.join("recordings", "sistema", "check_db_connection.py")
    if os.path.exists(db_check):
        print(f"🚀 Iniciando validación de servicio MySQL...")
        subprocess.run([sys.executable, db_check])
    
    try:
        cleanup_old_logs()
    except: pass
    
    # 🔄 Sincronizar tabla ris.medicos con SharePoint en segundo plano
    try:
        _sync_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "quick_scripts", "sync_medicos_sharepoint.py"
        )
        if os.path.exists(_sync_script):
            import threading
            def _run_sync_op():
                try:
                    proc = subprocess.Popen(
                        [sys.executable, _sync_script],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    proc.wait()
                except Exception as _e:
                    print(f"[sync_medicos] Error: {_e}")
            threading.Thread(target=_run_sync_op, daemon=True, name="SyncMedicos").start()
            print("Sincronizacion de medicos SharePoint iniciada en segundo plano.")
    except Exception as e:
        print(f"[sync_medicos] No se pudo iniciar: {e}")
    
    # 🤖 Iniciar Notificador de Resúmenes en segundo plano
    try:
        import threading
        from utils.telegram_manager import registrar_usuarios
        from utils.notificador_resumen import main as start_notificador
        
        notifier_thread = threading.Thread(target=start_notificador, daemon=True)
        notifier_thread.start()
        
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el servicio de Notificador: {e}")
    
    # El Listener de Telegram se ejecutará ahora de forma independiente.
    # Si quieres correrlo, inicia "python servicio_bot_telegram.py"
    
    app = QApplication(sys.argv)
    window = MainWindow()
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
