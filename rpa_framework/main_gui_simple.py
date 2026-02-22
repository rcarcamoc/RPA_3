import os
import sys
import warnings

# --- SUPPRESS CONSOLE NOISE ---
# 1. Suppress pywinauto / COM warnings
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning:pywinauto"
warnings.filterwarnings("ignore", category=UserWarning, message=".*coinit_flags.*")

# 2. Suppress Qt DPI / Window logs
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false;qt.qpa.plugin=false"

# 3. Suppress noisy library logs (urllib3 pool warnings)
import logging
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("selenium").setLevel(logging.ERROR)

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
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
