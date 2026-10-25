import os
import sys
import warnings
import subprocess
import traceback

# --- AUTO-BOOTSTRAP VIRTUAL ENVIRONMENT ---
# If executed directly with system Python (e.g. double-click), switch to project venv
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
_venv_python = os.path.join(_project_root, "venv", "Scripts", "python.exe")
_venv_pythonw = os.path.join(_project_root, "venv", "Scripts", "pythonw.exe")

_in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
if not _in_venv:
    target_py = _venv_pythonw if (os.path.exists(_venv_pythonw) and "pythonw" in sys.executable.lower()) else _venv_python
    if os.path.exists(target_py):
        try:
            res = subprocess.run([target_py] + sys.argv)
            sys.exit(res.returncode)
        except Exception as _e:
            pass

# Configure UTF-8 for console output on Windows to prevent UnicodeEncodeError
if sys.platform.startswith('win'):
    try:
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr is not None:
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# --- SUPPRESS CONSOLE NOISE ---
import logging
import json
import threading
import time
from pathlib import Path
from datetime import datetime

# --- GLOBAL EXCEPTION HANDLER ---
def _global_exception_handler(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        print(f"❌ [CRASH] Excepción no capturada:\n{err_msg}", file=sys.stderr)
    except Exception:
        pass
    try:
        log_dir = os.path.join(_script_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "gui_crash.log"), "a", encoding="utf-8") as f:
            f.write(f"\n==================== CRASH: {datetime.now()} ====================\n{err_msg}\n")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Se produjo un error inesperado en la aplicación:\n\n{exc_value}\n\nLos detalles han sido guardados en 'logs/gui_crash.log'.",
            "Error - RPA Framework",
            0x10
        )
    except Exception:
        pass

sys.excepthook = _global_exception_handler
if hasattr(threading, 'excepthook'):
    def _threading_exception_handler(args):
        _global_exception_handler(args.exc_type, args.exc_value, args.exc_traceback)
    threading.excepthook = _threading_exception_handler

# 1. Suppress pywinauto / COM warnings
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning:pywinauto"
warnings.filterwarnings("ignore", category=UserWarning, message=".*coinit_flags.*")

# 2. Suppress Qt DPI / Window logs
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false;qt.qpa.plugin=false"

# 3. Suppress noisy library logs
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("selenium").setLevel(logging.ERROR)
logging.getLogger("matplotlib").setLevel(logging.ERROR)

# 4. Custom Filter for console noise (Separators, Dashboard updates, etc.)
class ConsoleNoiseFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if "=====" in msg:
            return False
        if "Dashboard actualizado" in msg:
            return False
        if "categorical units" in msg:
            return False
        return True

logging.getLogger().addFilter(ConsoleNoiseFilter())

# Force STA mode for COM/PyQt compatibility
sys.coinit_flags = 2

# Force running from script dir
os.chdir(_script_dir)


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QTabWidget, QPushButton, QMessageBox, QSpinBox, QComboBox, 
    QDoubleSpinBox, QProgressBar, QTextEdit, QGroupBox, QGraphicsDropShadowEffect,
    QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon, QCursor

# Imports RPA Framework
try:
    from utils.config_loader import load_config
    from utils.logging_setup import setup_logging
    
    # UI Panels
    from ui.styles import STYLESHEET as GLOBAL_STYLESHEET
    from ui.panels.dashboard_panel import DashboardPanel
    from ui.panels.record_panel_final import RecordPanelFinal
    from ui.panels.replay_panel import ReplayPanel
    from ui.panels.ocr_panel import OCRPanel
    from ui.panels.web_record_panel import WebRecordPanel
    from ui.workflow_panel_final import WorkflowPanelFinal
    from ui.panels.debug_panel import DebugPanel
    from ui.panels.llm_panel import LLMPanel
    from ui.panels.pacs_validation_panel import PacsValidationPanel
    from ui.panels.operaciones import (
        CUSTOM_STYLESHEET,
        FINAL_STYLESHEET,
        ActionTile,
        ModernOperacionesPanel,
    )

    from core.models import Workflow
    from ui.workflow_panel import WorkflowExecutorWorker
    from utils.log_cleanup import cleanup_old_logs, PeriodicCleanup
    
except ImportError as e:
    err_str = traceback.format_exc()
    print(f"❌ Error importando módulos RPA: {e}")
    print("Asegúrate de estar en rpa_framework/")
    try:
        log_dir = os.path.join(_script_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "gui_crash.log"), "a", encoding="utf-8") as f:
            f.write(f"\n==================== IMPORT ERROR: {datetime.now()} ====================\n{err_str}\n")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Error importando módulos del RPA Framework:\n\n{e}\n\nAsegúrate de utilizar el entorno virtual (venv). Revisa logs/gui_crash.log.",
            "Error de Importación - RPA Framework",
            0x10
        )
    except Exception:
        pass
    sys.exit(1)


# ============================================================================
# VENTANA PRINCIPAL (UNIFICADA)
# ============================================================================

class MainWindow(QMainWindow):
    """Ventana principal que unifica los modos de Operación y Desarrollo."""
    
    def __init__(self):
        super().__init__()
        self.dev_mode = False  # Por defecto: Modo Operación
        
        try:
            self.config = load_config("config/ris_config.yaml")
            setup_logging()
        except Exception as e:
            print(f"⚠️ Error cargando configuración: {e}")
            self.config = {}
            
        self.cleanup_manager = PeriodicCleanup()
        
        self.init_ui()
        self.update_profile_tabs()
        
    def init_ui(self):
        self.setWindowTitle("🤖 RPA Framework - Panel de Control Unificado")
        self.setGeometry(80, 80, 1200, 800)
        self.setMinimumSize(1024, 720)
        
        # Central widget
        central = QWidget()
        central.setObjectName("central_widget")
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header bar
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_widget.setMinimumHeight(60)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        # Header title
        lbl_header = QLabel("🤖 RPA Framework")
        lbl_header.setObjectName("header_title")
        header_layout.addWidget(lbl_header)
        
        header_layout.addStretch()
        
        # Profile switch button
        self.btn_profile = QPushButton("🔧 Cambiar a Desarrollo")
        self.btn_profile.setObjectName("profile_toggle_btn")
        self.btn_profile.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_profile.clicked.connect(self.toggle_profile)
        header_layout.addWidget(self.btn_profile)
        
        main_layout.addWidget(header_widget)
        
        # Tabs widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(self.tab_widget)
        
        # Instanciar paneles una sola vez para preservar sus estados
        self.panel_operaciones = ModernOperacionesPanel(self.config, self)
        self.llm_panel = LLMPanel()
        self.pacs_panel = PacsValidationPanel(self.config, self)
        
        # Definición de pestañas
        self.tabs_list = [
            {"widget": DashboardPanel(), "title": "📊 Dashboard", "dev_only": False},
            {"widget": self.panel_operaciones, "title": "⚡ Operaciones", "dev_only": False},
            {"widget": WorkflowPanelFinal(self.config), "title": "✨ Workflows", "dev_only": False},
            {"widget": RecordPanelFinal(self.config), "title": "Grabar", "dev_only": True},
            {"widget": ReplayPanel(self.config), "title": "Reproducir", "dev_only": True},
            {"widget": OCRPanel(self), "title": "OCR", "dev_only": True},
            {"widget": WebRecordPanel(self.config), "title": "Web Recorder", "dev_only": True},
            {"widget": DebugPanel(self.config), "title": "🐛 Debug", "dev_only": True},
            {"widget": self.llm_panel, "title": "🤖 Modelos LLM", "dev_only": True},
            {"widget": self.pacs_panel, "title": "🔍 Validación PACS", "dev_only": True},
        ]
        
        # Footer con año dinámico
        current_year = datetime.now().year
        footer = QLabel(f"✅ RPA Framework v2 | {current_year}")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #64748b; margin: 10px; font-size: 10px; font-weight: 500;")
        main_layout.addWidget(footer)
        
        central.setLayout(main_layout)
        self.setCentralWidget(central)
        
        # Aplicar estilos combinados
        self.setStyleSheet(FINAL_STYLESHEET)
        
    def toggle_profile(self):
        """Alterna el perfil activo (Operación <-> Desarrollo)."""
        self.dev_mode = not self.dev_mode
        if self.dev_mode:
            self.btn_profile.setText("⚡ Cambiar a Operación")
            self.btn_profile.setStyleSheet("background-color: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe;")
        else:
            self.btn_profile.setText("🔧 Cambiar a Desarrollo")
            self.btn_profile.setStyleSheet("")
            
        self.update_profile_tabs()
        
    def update_profile_tabs(self):
        """Actualiza las pestañas visibles en el QTabWidget basándose en el perfil."""
        current_widget = self.tab_widget.currentWidget()
        
        self.tab_widget.blockSignals(True)
        self.tab_widget.clear()
        
        for tab_info in self.tabs_list:
            if not tab_info["dev_only"] or self.dev_mode:
                self.tab_widget.addTab(tab_info["widget"], tab_info["title"])
                
        self.tab_widget.blockSignals(False)
        
        # Intentar restaurar pestaña seleccionada
        index = self.tab_widget.indexOf(current_widget)
        if index != -1:
            self.tab_widget.setCurrentIndex(index)
        else:
            self.tab_widget.setCurrentIndex(0)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    # Validar base de datos MySQL antes del arranque
    cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    db_check = os.path.join("recordings", "sistema", "check_db_connection.py")
    if os.path.exists(db_check):
        print("🚀 Iniciando validación de servicio MySQL...")
        subprocess.run([sys.executable, db_check], creationflags=cflags)
        
    # Limpieza inicial de logs
    try:
        cleanup_old_logs()
    except Exception:
        pass
        
    # Sincronización en segundo plano con SharePoint
    try:
        _sync_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "quick_scripts", "sync_medicos_sharepoint.py"
        )
        if os.path.exists(_sync_script):
            def _run_sync():
                try:
                    proc = subprocess.Popen(
                        [sys.executable, _sync_script],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=cflags
                    )
                    proc.wait()
                except Exception as _e:
                    print(f"[sync_medicos] Error: {_e}")
            threading.Thread(target=_run_sync, daemon=True, name="SyncMedicos").start()
            print("Sincronización de médicos SharePoint iniciada en segundo plano.")
    except Exception as e:
        print(f"[sync_medicos] No se pudo iniciar: {e}")
        
    # Asegurar que el servicio de Telegram/Notificador independiente esté corriendo
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        result = s.connect_ex(("127.0.0.1", 28374))
        s.close()
        
        if result == 0:
            print("🤖 Servicio de Telegram/Notificador independiente detectado (ya está corriendo).")
        else:
            print("🤖 Iniciando servicio de Telegram/Notificador independiente...")
            bot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "servicio_bot_telegram.py")
            if os.path.exists(bot_path):
                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                
                subprocess.Popen(
                    [sys.executable, bot_path],
                    creationflags=creation_flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True
                )
                print("🚀 Servicio de Telegram/Notificador lanzado en segundo plano de forma independiente.")
            else:
                print("⚠️ No se encontró servicio_bot_telegram.py para iniciar.")
    except Exception as e:
        print(f"⚠️ Error al verificar/iniciar el servicio de Telegram independiente: {e}")

    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()

        # Validar y actualizar modelos LLM automáticamente en segundo plano
        try:
            from utils.llm_validator import run_background_llm_validation
            run_background_llm_validation()
        except Exception as _e:
            print(f"⚠️ No se pudo lanzar validación LLM al inicio: {_e}")

        sys.exit(app.exec())
    except Exception as e:
        err_str = traceback.format_exc()
        print(f"❌ Error fatal en la GUI: {e}\n{err_str}")
        try:
            log_dir = os.path.join(_script_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "gui_crash.log"), "a", encoding="utf-8") as f:
                f.write(f"\n==================== FATAL MAIN ERROR: {datetime.now()} ====================\n{err_str}\n")
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Error fatal al ejecutar la interfaz gráfica:\n\n{e}\n\nRevisa logs/gui_crash.log para más detalles.",
                "Error Fatal - RPA Framework",
                0x10
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        err_str = traceback.format_exc()
        print(f"❌ Error en entry point: {e}\n{err_str}")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Error iniciando RPA Framework:\n\n{e}", "Error", 0x10)
        except Exception:
            pass
        sys.exit(1)
