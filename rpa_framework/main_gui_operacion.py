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
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QTabWidget, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt
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
        self.init_ui()
        
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
        btn_inicio = QPushButton("▶ Inicio completo")
        btn_inicio.setMinimumHeight(60)
        btn_inicio.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #4CAF50; color: white; border-radius: 8px;")
        btn_inicio.clicked.connect(self.ejecutar_inicio_completo)
        btn_inicio.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn_inicio)
        
        layout.addSpacing(15)
        
        # Boton 2: Solo Pega en Integra
        btn_pega = QPushButton("▶ Solo Pega en Integra")
        btn_pega.setMinimumHeight(60)
        btn_pega.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #2196F3; color: white; border-radius: 8px;")
        btn_pega.clicked.connect(self.ejecutar_pega_integra)
        btn_pega.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn_pega)
        
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
        
        layout.addStretch()
        self.setLayout(layout)
        
    def ejecutar_inicio_completo(self):
        wf_path = os.path.join("workflows", "Sub_work.json")
        self.run_workflow(wf_path)

    def ejecutar_pega_integra(self):
        wf_path = os.path.join("workflows", "pacs.json")
        self.run_workflow(wf_path)

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
        """Detiene la ejecución actual del worker"""
        if self.worker:
            self.worker.stop()
            self.append_log("🛑 Solicitando detención...", "WARNING")
            self.btn_stop.setEnabled(False)

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
        tabs.addTab(OperacionesPanel(self.config, self), "⚡ Operaciones")
        
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
    
    # Limpieza inicial de logs al arrancar
    try:
        cleanup_old_logs()
    except: pass
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
