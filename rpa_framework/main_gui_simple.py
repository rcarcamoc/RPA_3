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
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QTabWidget
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
    from ui.panels.record_panel import RecordPanel
    from ui.panels.replay_panel import ReplayPanel
    from ui.panels.ocr_panel import OCRPanel
    from ui.panels.web_record_panel import WebRecordPanel
    from ui.workflow_panel_v2 import WorkflowPanelV2
    from ui.panels.debug_panel import DebugPanel
    from ui.panels.llm_panel import LLMPanel

    from utils.log_cleanup import cleanup_old_logs, PeriodicCleanup
    
except ImportError as e:
    print(f"❌ Error importando módulos RPA: {e}")
    print("Asegúrate de estar en rpa_framework/")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    """Ventana principal."""
    
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
        self.setWindowTitle("🤖 RPA Framework v2 - Panel de Control")
        self.setGeometry(100, 100, 1000, 700)
        
        # Central widget
        central = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("🤖 RPA Framework v2")
        header_font = QFont("Arial", 16, QFont.Weight.Bold)
        header.setFont(header_font)
        header.setStyleSheet("color: #1976D2; margin: 10px;")
        layout.addWidget(header)
        
        # Tabs
        tabs = QTabWidget()
        tabs.addTab(DashboardPanel(), "Dashboard")
        tabs.addTab(WorkflowPanelV2(self.config), "✨ Workflows")
        tabs.addTab(RecordPanel(self.config), "Grabar")
        tabs.addTab(ReplayPanel(self.config), "Reproducir")
        tabs.addTab(OCRPanel(self), "OCR")
        tabs.addTab(WebRecordPanel(self.config), "Web Recorder")
        tabs.addTab(DebugPanel(self.config), "🐛 Debug")
        self.llm_panel = LLMPanel()
        tabs.addTab(self.llm_panel, "🤖 Modelos LLM")

     
        
        layout.addWidget(tabs)
        
        # Footer
        footer = QLabel("✅ RPA Framework v2 | Production Ready | 2025")
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
    
    # 🔄 Sincronizar tabla ris.medicos con SharePoint en segundo plano
    try:
        _sync_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "quick_scripts", "sync_medicos_sharepoint.py"
        )
        if os.path.exists(_sync_script):
            import threading
            def _run_sync():
                try:
                    proc = subprocess.Popen(
                        [sys.executable, _sync_script],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    proc.wait()
                except Exception as _e:
                    print(f"[sync_medicos] Error: {_e}")
            threading.Thread(target=_run_sync, daemon=True, name="SyncMedicos").start()
            print("Sincronizacion de medicos SharePoint iniciada en segundo plano.")
    except Exception as e:
        print(f"[sync_medicos] No se pudo iniciar: {e}")
    
    # 🤖 Iniciar Listener de Telegram en segundo plano para procesar botones y comandos
    try:
        import threading
        from utils.telegram_manager import registrar_usuarios
        from utils.notificador_resumen import main as start_notificador
        
        telegram_thread = threading.Thread(target=registrar_usuarios, daemon=True)
        telegram_thread.start()
        
        notifier_thread = threading.Thread(target=start_notificador, daemon=True)
        notifier_thread.start()
        
        print("🤖 Listener de Telegram y Notificador de Resúmenes iniciados.")
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el listener de Telegram: {e}")
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # Validar y actualizar modelos LLM automáticamente en segundo plano al arrancar
    try:
        from utils.llm_validator import run_background_llm_validation
        run_background_llm_validation()
    except Exception as _e:
        print(f"⚠️ No se pudo lanzar validación LLM al inicio: {_e}")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
