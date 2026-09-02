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
# ESTILOS MODERNOS (DESIGN TOKENS & OVERRIDES)
# ============================================================================

CUSTOM_STYLESHEET = """
/* Ventana Principal */
QMainWindow {
    background-color: #f8fafc;
}

QWidget#central_widget {
    background-color: #f8fafc;
}

/* Header */
#header_widget {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}

#header_title {
    color: #0f172a;
    font-weight: 800;
    font-size: 16pt;
}

/* Botón de perfil */
#profile_toggle_btn {
    background-color: #f1f5f9;
    color: #475569;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 10pt;
}
#profile_toggle_btn:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}
#profile_toggle_btn:pressed {
    background-color: #cbd5e1;
}

/* Encabezado del panel de operaciones */
QFrame#ops_header_box {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}
QFrame#ops_header_box QLabel {
    background: transparent;
    border: none;
}

/* Tarjetas Generales */
QFrame#ops_card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}
QFrame#ops_card QLabel {
    background: transparent;
    border: none;
}

/* KPI Tiles */
QFrame[cssClass="kpi_tile"] {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}
QFrame[cssClass="kpi_tile"]:hover {
    background-color: #f1f5f9;
    border-color: #cbd5e1;
}
QFrame[cssClass="kpi_tile"] QLabel {
    background: transparent;
    border: none;
}

/* Botones de Presets / Chips */
QPushButton[cssClass="preset_chip"] {
    background-color: #f1f5f9;
    color: #475569;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 9pt;
    font-weight: 600;
    min-height: 24px;
}
QPushButton[cssClass="preset_chip"]:hover {
    background-color: #e2e8f0;
    color: #0f172a;
    border-color: #94a3b8;
}
QPushButton[cssClass="preset_chip"]:pressed {
    background-color: #dbeafe;
    color: #1d4ed8;
    border-color: #3b82f6;
}

/* Botón Lanzador de Loop */
QPushButton#btn_action_loop {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6366f1);
    color: #ffffff;
    border: 1px solid #6d28d9;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: bold;
    font-size: 10.5pt;
}
QPushButton#btn_action_loop:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6d28d9, stop:1 #4f46e5);
    border-color: #5b21b6;
}
QPushButton#btn_action_loop:pressed {
    background-color: #4f46e5;
}
QPushButton#btn_action_loop:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border: 1px solid #e2e8f0;
}

/* Botón Stop */
QPushButton#btn_action_stop {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #dc2626);
    color: #ffffff;
    border: 1px solid #dc2626;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: bold;
    font-size: 10pt;
}
QPushButton#btn_action_stop:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #b91c1c);
    border-color: #b91c1c;
}
QPushButton#btn_action_stop:pressed {
    background-color: #b91c1c;
}
QPushButton#btn_action_stop:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border: 1px solid #e2e8f0;
}

/* Form inputs */
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    color: #0f172a;
    font-size: 10pt;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
    background-color: #ffffff;
}

/* Progress bar */
QProgressBar#ops_progress {
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    background-color: #f1f5f9;
    height: 8px;
}
QProgressBar#ops_progress::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981);
    border-radius: 3px;
}

/* Terminal Card */
QFrame#ops_terminal_card {
    background-color: #090d16;
    border: 1px solid #1e293b;
    border-radius: 12px;
}

QWidget#terminal_header {
    background-color: #111827;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid #1f2937;
}
QWidget#terminal_header QLabel {
    background: transparent;
    border: none;
}

QTextEdit#ops_terminal {
    background-color: #090d16;
    color: #e2e8f0;
    font-family: 'Consolas', 'Cascadia Code', 'Courier New', monospace;
    font-size: 9pt;
    border: none;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
    padding: 10px;
}
"""

FINAL_STYLESHEET = GLOBAL_STYLESHEET + CUSTOM_STYLESHEET


# ============================================================================
# COMPONENTE: ACTION TILE (TARJETA DE ACCIÓN INTERACTIVA)
# ============================================================================

class ActionTile(QFrame):
    """Tarjeta de acción interactiva moderna con icono destacado, títulos claros y micro-interacciones."""
    clicked = pyqtSignal()
    
    def __init__(self, title, subtitle, icon="🚀", theme="emerald", parent=None):
        super().__init__(parent)
        self._enabled = True
        self.theme = theme
        self.setObjectName(f"action_tile_{theme}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(62)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 14, 10)
        layout.setSpacing(12)
        
        # Icon Container (Badge)
        self.icon_badge = QLabel(icon)
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_badge.setFixedSize(38, 38)
        self.icon_badge.setObjectName("action_icon_badge")
        layout.addWidget(self.icon_badge)
        
        # Text VBox
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)
        text_vbox.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 10.5pt; font-weight: 700; color: #0f172a; background: transparent; border: none;")
        
        self.lbl_sub = QLabel(subtitle)
        self.lbl_sub.setStyleSheet("font-size: 8.5pt; color: #64748b; background: transparent; border: none;")
        
        text_vbox.addWidget(self.lbl_title)
        text_vbox.addWidget(self.lbl_sub)
        layout.addLayout(text_vbox, stretch=1)
        
        # Right Arrow Indicator
        self.lbl_arrow = QLabel("➔")
        self.lbl_arrow.setObjectName("action_arrow")
        layout.addWidget(self.lbl_arrow)
        
        self.update_style()
        
    def update_style(self):
        themes = {
            "emerald": {
                "border": "#10b981",
                "badge_bg": "#ecfdf5",
                "badge_color": "#059669",
                "hover_bg": "#f0fdf4",
                "arrow_color": "#10b981"
            },
            "blue": {
                "border": "#3b82f6",
                "badge_bg": "#eff6ff",
                "badge_color": "#2563eb",
                "hover_bg": "#f8faff",
                "arrow_color": "#3b82f6"
            },
            "amber": {
                "border": "#f59e0b",
                "badge_bg": "#fffbeb",
                "badge_color": "#d97706",
                "hover_bg": "#fffdf5",
                "arrow_color": "#f59e0b"
            }
        }
        t = themes.get(self.theme, themes["emerald"])
        
        if self._enabled:
            self.setStyleSheet(f"""
                QFrame#action_tile_{self.theme} {{
                    background-color: #ffffff;
                    border: 1.5px solid #e2e8f0;
                    border-left: 5px solid {t['border']};
                    border-radius: 10px;
                }}
                QFrame#action_tile_{self.theme}:hover {{
                    background-color: {t['hover_bg']};
                    border-color: {t['border']};
                }}
                QLabel#action_icon_badge {{
                    background-color: {t['badge_bg']};
                    color: {t['badge_color']};
                    border-radius: 8px;
                    font-size: 15pt;
                    border: none;
                }}
                QLabel#action_arrow {{
                    color: {t['arrow_color']};
                    font-size: 11pt;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#action_tile_{self.theme} {{
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-left: 5px solid #cbd5e1;
                    border-radius: 10px;
                }}
                QLabel#action_icon_badge {{
                    background-color: #f1f5f9;
                    color: #94a3b8;
                    border-radius: 8px;
                    font-size: 15pt;
                    border: none;
                }}
                QLabel#action_arrow {{
                    color: #cbd5e1;
                    font-size: 11pt;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)
            
    def setEnabled(self, enabled: bool):
        self._enabled = enabled
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ForbiddenCursor)
        self.lbl_title.setStyleSheet(f"font-size: 10.5pt; font-weight: 700; color: {'#0f172a' if enabled else '#94a3b8'}; background: transparent; border: none;")
        self.lbl_sub.setStyleSheet(f"font-size: 8.5pt; color: {'#64748b' if enabled else '#cbd5e1'}; background: transparent; border: none;")
        self.update_style()
        super().setEnabled(enabled)
        
    def mousePressEvent(self, event):
        if self._enabled and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ============================================================================
# PANEL DE OPERACIONES REDISEÑADO (MODERNO & FÁCIL USO)
# ============================================================================

class ModernOperacionesPanel(QWidget):
    """Panel de Operaciones con diseño moderno, intuitivo, telemetría en tiempo real y 2 columnas."""
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.worker = None
        self.is_bg_running = False
        self.start_time = None
        
        self.init_ui()
        
        # Timer para sincronizar estado con el servicio de Telegram en background
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self.check_background_state)
        self.state_timer.start(2000) # Chequeo cada 2 segundos
        
        # Timer para actualizar tiempo transcurrido
        self.duration_timer = QTimer(self)
        self.duration_timer.timeout.connect(self.update_elapsed_time)
        
    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 14, 16, 16)
        root_layout.setSpacing(12)
        
        # Función auxiliar para aplicar sombra suave
        def apply_card_shadow(widget):
            shadow = QGraphicsDropShadowEffect(widget)
            shadow.setBlurRadius(14)
            shadow.setXOffset(0)
            shadow.setYOffset(3)
            shadow.setColor(QColor(15, 23, 42, 18))
            widget.setGraphicsEffect(shadow)

        # --------------------------------------------------------------------
        # 1. HEADER BANNER
        # --------------------------------------------------------------------
        header_box = QFrame()
        header_box.setObjectName("ops_header_box")
        apply_card_shadow(header_box)
        
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(16, 10, 16, 10)
        
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_title = QLabel("⚡ Centro de Control de Operaciones")
        lbl_title.setStyleSheet("font-size: 13pt; font-weight: 800; color: #0f172a; background: transparent;")
        lbl_sub = QLabel("Monitoreo en tiempo real, automatización cíclica y control de flujos RPA")
        lbl_sub.setStyleSheet("font-size: 9pt; color: #64748b; background: transparent;")
        title_vbox.addWidget(lbl_title)
        title_vbox.addWidget(lbl_sub)
        h_layout.addLayout(title_vbox)
        
        h_layout.addStretch()
        
        # Badge de estado del sistema
        self.badge_system = QLabel("● Sistema Listo")
        self.badge_system.setStyleSheet("""
            background-color: #ecfdf5;
            color: #059669;
            border: 1px solid #a7f3d0;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 9pt;
            font-weight: 700;
        """)
        h_layout.addWidget(self.badge_system)
        
        root_layout.addWidget(header_box)

        # --------------------------------------------------------------------
        # 2. CONTENIDO EN 2 COLUMNAS (SPLIT LAYOUT)
        # --------------------------------------------------------------------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)
        
        # ====================================================================
        # COLUMNA IZQUIERDA: ACCIONES Y CONFIGURACIÓN (STRETCH 53%)
        # ====================================================================
        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        
        # --- TARJETA 1: ACCIONES RÁPIDAS ---
        card_acciones = QFrame()
        card_acciones.setObjectName("ops_card")
        apply_card_shadow(card_acciones)
        
        layout_acciones = QVBoxLayout(card_acciones)
        layout_acciones.setSpacing(10)
        layout_acciones.setContentsMargins(16, 14, 16, 14)
        
        card_acc_head = QHBoxLayout()
        lbl_acc_title = QLabel("⚡ Acciones Rápidas")
        lbl_acc_title.setStyleSheet("font-size: 11pt; font-weight: 700; color: #1e293b;")
        lbl_acc_badge = QLabel("Ejecución Directa")
        lbl_acc_badge.setStyleSheet("background-color: #eff6ff; color: #2563eb; font-size: 8pt; font-weight: 600; padding: 3px 8px; border-radius: 6px;")
        card_acc_head.addWidget(lbl_acc_title)
        card_acc_head.addStretch()
        card_acc_head.addWidget(lbl_acc_badge)
        layout_acciones.addLayout(card_acc_head)
        
        lbl_acc_sub = QLabel("Haga clic en una acción para iniciar su ejecución de forma directa:")
        lbl_acc_sub.setStyleSheet("font-size: 9pt; color: #64748b; margin-bottom: 2px;")
        layout_acciones.addWidget(lbl_acc_sub)
        
        # 1. Inicio Completo
        self.btn_inicio = ActionTile(
            "Inicio Completo (Flujo Principal)",
            "Ejecuta el flujo maestro automatizado (Sub_work.json)",
            icon="🚀",
            theme="emerald"
        )
        self.btn_inicio.clicked.connect(self.ejecutar_inicio_completo)
        self.btn_inicio.setToolTip("Inicia el flujo completo maestro del workflow Sub_work.json")
        layout_acciones.addWidget(self.btn_inicio)
        
        # 2. Solo Pega en Integra
        self.btn_pega = ActionTile(
            "Solo Pega en Integra",
            "Validación y procesamiento directo de PACS (pacs.json)",
            icon="📋",
            theme="blue"
        )
        self.btn_pega.clicked.connect(self.ejecutar_pega_integra)
        self.btn_pega.setToolTip("Inicia el workflow pacs.json")
        layout_acciones.addWidget(self.btn_pega)
        
        # 3. Rehabilitar Último
        self.btn_rehabilitar = ActionTile(
            "Rehabilitar Último Registro",
            "Restaura el estado a 'En Proceso' en la BD MySQL",
            icon="🔄",
            theme="amber"
        )
        self.btn_rehabilitar.clicked.connect(self.rehabilitar_ultimo_registro)
        self.btn_rehabilitar.setToolTip("Cambia el estado del último registro de la base de datos a 'En Proceso'")
        layout_acciones.addWidget(self.btn_rehabilitar)
        
        left_column.addWidget(card_acciones)
        
        # --- TARJETA 2: CONFIGURACIÓN DE LOOP CONTINUO ---
        card_loop = QFrame()
        card_loop.setObjectName("ops_card")
        apply_card_shadow(card_loop)
        
        layout_loop = QVBoxLayout(card_loop)
        layout_loop.setSpacing(10)
        layout_loop.setContentsMargins(16, 14, 16, 14)
        
        card_loop_head = QHBoxLayout()
        lbl_loop_title = QLabel("🔁 Ejecución Continua (Loop)")
        lbl_loop_title.setStyleSheet("font-size: 11pt; font-weight: 700; color: #1e293b;")
        lbl_loop_badge = QLabel("Automatización Cíclica")
        lbl_loop_badge.setStyleSheet("background-color: #f5f3ff; color: #7c3aed; font-size: 8pt; font-weight: 600; padding: 3px 8px; border-radius: 6px;")
        card_loop_head.addWidget(lbl_loop_title)
        card_loop_head.addStretch()
        card_loop_head.addWidget(lbl_loop_badge)
        layout_loop.addLayout(card_loop_head)
        
        # Modo de Ejecución Selector
        mode_row = QHBoxLayout()
        lbl_mode = QLabel("Modo:")
        lbl_mode.setStyleSheet("font-weight: 600; color: #334155; min-width: 50px;")
        self.combo_loop_type = QComboBox()
        self.combo_loop_type.addItems(["🔢 Por Cantidad de Ciclos", "⏱️ Por Tiempo Programado (Horas)", "♾️ Continuo Infinito"])
        self.combo_loop_type.setMinimumHeight(34)
        self.combo_loop_type.currentIndexChanged.connect(self.actualizar_visibilidad_loop)
        mode_row.addWidget(lbl_mode)
        mode_row.addWidget(self.combo_loop_type, stretch=1)
        layout_loop.addLayout(mode_row)
        
        # Contenedor Cantidad con Presets Rápidos
        self.container_count = QWidget()
        layout_count = QVBoxLayout(self.container_count)
        layout_count.setContentsMargins(0, 0, 0, 0)
        layout_count.setSpacing(6)
        
        presets_count_layout = QHBoxLayout()
        presets_count_layout.setSpacing(4)
        lbl_presets = QLabel("Atajos:")
        lbl_presets.setStyleSheet("font-size: 8.5pt; color: #64748b; font-weight: 600; margin-right: 2px;")
        presets_count_layout.addWidget(lbl_presets)
        
        for val in [1, 5, 10, 25, 50, 100]:
            btn_p = QPushButton(f"{val}x")
            btn_p.setProperty("cssClass", "preset_chip")
            btn_p.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_p.clicked.connect(lambda checked, v=val: self.spin_iterations.setValue(v))
            presets_count_layout.addWidget(btn_p)
        presets_count_layout.addStretch()
        layout_count.addLayout(presets_count_layout)
        
        row_spin_c = QHBoxLayout()
        lbl_spin_c = QLabel("Reiteraciones totales:")
        lbl_spin_c.setStyleSheet("color: #475569;")
        self.spin_iterations = QSpinBox()
        self.spin_iterations.setRange(1, 9999)
        self.spin_iterations.setValue(5)
        self.spin_iterations.setMinimumHeight(32)
        row_spin_c.addWidget(lbl_spin_c)
        row_spin_c.addWidget(self.spin_iterations, stretch=1)
        layout_count.addLayout(row_spin_c)
        layout_loop.addWidget(self.container_count)
        
        # Contenedor Tiempo con Presets Rápidos
        self.container_timed = QWidget()
        layout_timed = QVBoxLayout(self.container_timed)
        layout_timed.setContentsMargins(0, 0, 0, 0)
        layout_timed.setSpacing(6)
        
        presets_time_layout = QHBoxLayout()
        presets_time_layout.setSpacing(4)
        lbl_p_time = QLabel("Atajos:")
        lbl_p_time.setStyleSheet("font-size: 8.5pt; color: #64748b; font-weight: 600; margin-right: 2px;")
        presets_time_layout.addWidget(lbl_p_time)
        
        for label, val in [("30 min", 0.5), ("1h", 1.0), ("2h", 2.0), ("4h", 4.0), ("8h", 8.0)]:
            btn_t = QPushButton(label)
            btn_t.setProperty("cssClass", "preset_chip")
            btn_t.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_t.clicked.connect(lambda checked, v=val: self.spin_duration.setValue(v))
            presets_time_layout.addWidget(btn_t)
        presets_time_layout.addStretch()
        layout_timed.addLayout(presets_time_layout)
        
        row_spin_t = QHBoxLayout()
        lbl_spin_t = QLabel("Duración máxima:")
        lbl_spin_t.setStyleSheet("color: #475569;")
        self.spin_duration = QDoubleSpinBox()
        self.spin_duration.setRange(0.1, 72.0)
        self.spin_duration.setValue(1.0)
        self.spin_duration.setSuffix(" horas")
        self.spin_duration.setMinimumHeight(32)
        row_spin_t.addWidget(lbl_spin_t)
        row_spin_t.addWidget(self.spin_duration, stretch=1)
        layout_timed.addLayout(row_spin_t)
        layout_loop.addWidget(self.container_timed)
        self.container_timed.hide()
        
        # Fila de Pausa ante Errores
        row_delay = QHBoxLayout()
        lbl_delay = QLabel("Pausa tras error:")
        lbl_delay.setStyleSheet("color: #475569;")
        self.spin_error_delay = QSpinBox()
        self.spin_error_delay.setRange(0, 3600)
        self.spin_error_delay.setValue(0)
        self.spin_error_delay.setSuffix(" seg")
        self.spin_error_delay.setMinimumHeight(32)
        row_delay.addWidget(lbl_delay)
        row_delay.addWidget(self.spin_error_delay, stretch=1)
        
        for d_label, d_val in [("0s", 0), ("15s", 15), ("30s", 30), ("60s", 60)]:
            btn_d = QPushButton(d_label)
            btn_d.setProperty("cssClass", "preset_chip")
            btn_d.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_d.clicked.connect(lambda checked, v=d_val: self.spin_error_delay.setValue(v))
            row_delay.addWidget(btn_d)
            
        layout_loop.addLayout(row_delay)
        
        # Botón Iniciar Loop
        self.btn_loop = QPushButton("🚀  Iniciar Flujo Continuo (Loop)")
        self.btn_loop.setObjectName("btn_action_loop")
        self.btn_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_loop.setMinimumHeight(44)
        self.btn_loop.clicked.connect(self.ejecutar_loop_reiteraciones)
        layout_loop.addWidget(self.btn_loop)
        
        left_column.addWidget(card_loop)
        left_column.addStretch()
        
        content_layout.addLayout(left_column, stretch=53)

        # ====================================================================
        # COLUMNA DERECHA: TELEMETRÍA, MONITOR Y LOGS (STRETCH 48%)
        # ====================================================================
        right_column = QVBoxLayout()
        right_column.setSpacing(12)
        
        # --- TARJETA 3: TELEMETRÍA Y ESTADO EN VIVO ---
        card_telemetry = QFrame()
        card_telemetry.setObjectName("ops_card")
        apply_card_shadow(card_telemetry)
        
        layout_telemetry = QVBoxLayout(card_telemetry)
        layout_telemetry.setSpacing(10)
        layout_telemetry.setContentsMargins(16, 14, 16, 14)
        
        card_telem_head = QHBoxLayout()
        lbl_telem_title = QLabel("📡 Telemetría y Estado en Vivo")
        lbl_telem_title.setStyleSheet("font-size: 11pt; font-weight: 700; color: #1e293b;")
        card_telem_head.addWidget(lbl_telem_title)
        card_telem_head.addStretch()
        layout_telemetry.addLayout(card_telem_head)
        
        # Banner Hero de Estado Dinámico
        self.status_banner = QFrame()
        self.status_banner.setStyleSheet("""
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 4px;
        """)
        layout_banner = QHBoxLayout(self.status_banner)
        layout_banner.setContentsMargins(10, 8, 10, 8)
        
        self.lbl_status_icon = QLabel("⚪")
        self.lbl_status_icon.setStyleSheet("font-size: 13pt;")
        self.lbl_status_val = QLabel("Sistema en Reposo (Listo para operar)")
        self.lbl_status_val.setStyleSheet("font-size: 10pt; font-weight: 700; color: #475569;")
        
        layout_banner.addWidget(self.lbl_status_icon)
        layout_banner.addWidget(self.lbl_status_val)
        layout_banner.addStretch()
        layout_telemetry.addWidget(self.status_banner)
        
        # Cuadrícula 2x2 de KPIs Métricos
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(8)
        
        # KPI 1: Cronómetro
        self.tile_time = QFrame()
        self.tile_time.setProperty("cssClass", "kpi_tile")
        l_t1 = QVBoxLayout(self.tile_time)
        l_t1.setContentsMargins(10, 8, 10, 8)
        l_t1.setSpacing(2)
        lbl_t1_h = QLabel("⏱️ Tiempo Transcurrido")
        lbl_t1_h.setStyleSheet("font-size: 8pt; color: #64748b; font-weight: 600;")
        self.lbl_time = QLabel("00:00:00")
        self.lbl_time.setStyleSheet("font-family: 'Consolas', monospace; font-size: 13pt; font-weight: 800; color: #0f172a;")
        l_t1.addWidget(lbl_t1_h)
        l_t1.addWidget(self.lbl_time)
        kpi_grid.addWidget(self.tile_time, 0, 0)
        
        # KPI 2: Workflow Activo
        self.tile_wf = QFrame()
        self.tile_wf.setProperty("cssClass", "kpi_tile")
        l_t2 = QVBoxLayout(self.tile_wf)
        l_t2.setContentsMargins(10, 8, 10, 8)
        l_t2.setSpacing(2)
        lbl_t2_h = QLabel("📋 Workflow en Curso")
        lbl_t2_h.setStyleSheet("font-size: 8pt; color: #64748b; font-weight: 600;")
        self.lbl_active_wf = QLabel("Ninguno")
        self.lbl_active_wf.setStyleSheet("font-size: 10pt; font-weight: 700; color: #334155;")
        l_t2.addWidget(lbl_t2_h)
        l_t2.addWidget(self.lbl_active_wf)
        kpi_grid.addWidget(self.tile_wf, 0, 1)
        
        # KPI 3: Modo
        self.tile_mode = QFrame()
        self.tile_mode.setProperty("cssClass", "kpi_tile")
        l_t3 = QVBoxLayout(self.tile_mode)
        l_t3.setContentsMargins(10, 8, 10, 8)
        l_t3.setSpacing(2)
        lbl_t3_h = QLabel("🔁 Modo de Ejecución")
        lbl_t3_h.setStyleSheet("font-size: 8pt; color: #64748b; font-weight: 600;")
        self.lbl_active_mode = QLabel("Individual")
        self.lbl_active_mode.setStyleSheet("font-size: 10pt; font-weight: 700; color: #334155;")
        l_t3.addWidget(lbl_t3_h)
        l_t3.addWidget(self.lbl_active_mode)
        kpi_grid.addWidget(self.tile_mode, 1, 0)
        
        # KPI 4: Origen
        self.tile_origin = QFrame()
        self.tile_origin.setProperty("cssClass", "kpi_tile")
        l_t4 = QVBoxLayout(self.tile_origin)
        l_t4.setContentsMargins(10, 8, 10, 8)
        l_t4.setSpacing(2)
        lbl_t4_h = QLabel("📡 Canal de Disparo")
        lbl_t4_h.setStyleSheet("font-size: 8pt; color: #64748b; font-weight: 600;")
        self.lbl_active_channel = QLabel("Panel Local")
        self.lbl_active_channel.setStyleSheet("font-size: 10pt; font-weight: 700; color: #334155;")
        l_t4.addWidget(lbl_t4_h)
        l_t4.addWidget(self.lbl_active_channel)
        kpi_grid.addWidget(self.tile_origin, 1, 1)
        
        layout_telemetry.addLayout(kpi_grid)
        
        # Barra de Progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("ops_progress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout_telemetry.addWidget(self.progress_bar)
        
        # Botón de Parada de Emergencia
        self.btn_stop = QPushButton("🛑  Detener Ejecución Actual")
        self.btn_stop.setObjectName("btn_action_stop")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.detiene_todo)
        layout_telemetry.addWidget(self.btn_stop)
        
        right_column.addWidget(card_telemetry)
        
        # --- TARJETA 4: CONSOLA / TERMINAL DE EVENTOS EN VIVO ---
        card_terminal = QFrame()
        card_terminal.setObjectName("ops_terminal_card")
        apply_card_shadow(card_terminal)
        
        layout_term = QVBoxLayout(card_terminal)
        layout_term.setSpacing(0)
        layout_term.setContentsMargins(0, 0, 0, 0)
        
        # Header de la consola
        term_head = QWidget()
        term_head.setObjectName("terminal_header")
        l_th = QHBoxLayout(term_head)
        l_th.setContentsMargins(12, 6, 12, 6)
        
        lbl_term_title = QLabel("📟 Consola de Operaciones en Vivo")
        lbl_term_title.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 9pt;")
        l_th.addWidget(lbl_term_title)
        l_th.addStretch()
        
        btn_copy_log = QPushButton("📋 Copiar")
        btn_copy_log.setStyleSheet("background: transparent; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; padding: 2px 8px; font-size: 8pt;")
        btn_copy_log.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy_log.clicked.connect(self.copiar_logs)
        l_th.addWidget(btn_copy_log)
        
        btn_clear_log = QPushButton("🗑️ Limpiar")
        btn_clear_log.setStyleSheet("background: transparent; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; padding: 2px 8px; font-size: 8pt; margin-left: 4px;")
        btn_clear_log.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_log.clicked.connect(self.limpiar_logs)
        l_th.addWidget(btn_clear_log)
        
        layout_term.addWidget(term_head)
        
        # Visor de Logs
        self.log_viewer = QTextEdit()
        self.log_viewer.setObjectName("ops_terminal")
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMinimumHeight(140)
        self.log_viewer.setPlaceholderText("Esperando eventos de ejecución...")
        layout_term.addWidget(self.log_viewer)
        
        right_column.addWidget(card_terminal)
        
        content_layout.addLayout(right_column, stretch=48)
        root_layout.addLayout(content_layout)

    def actualizar_visibilidad_loop(self):
        """Muestra u oculta campos según el modo de loop seleccionado."""
        modo = self.combo_loop_type.currentText()
        self.container_count.setVisible("Por Cantidad" in modo)
        self.container_timed.setVisible("Por Tiempo" in modo)
        
    def ejecutar_inicio_completo(self):
        wf_path = os.path.join("workflows", "Sub_work.json")
        self.run_workflow(wf_path)

    def ejecutar_pega_integra(self):
        wf_path = os.path.join("workflows", "pacs.json")
        self.run_workflow(wf_path)

    def add_log(self, msg, level="info"):
        """Agrega un mensaje con timestamp y formato estilizado al terminal."""
        now_str = datetime.now().strftime("%H:%M:%S")
        
        # Detección inteligente de color si level es genérico
        if "error" in msg.lower() or "falló" in msg.lower() or "❌" in msg or level == "error":
            color = "#f87171" # rojo suave
            badge = "❌"
        elif "éxito" in msg.lower() or "completado" in msg.lower() or "finalizado" in msg.lower() or "✅" in msg or level == "success":
            color = "#34d399" # esmeralda
            badge = "✅"
        elif "iniciando" in msg.lower() or "🚀" in msg or "ejecutando" in msg.lower() or level == "start":
            color = "#38bdf8" # celeste
            badge = "🚀"
        elif "advertencia" in msg.lower() or "aviso" in msg.lower() or "⚠️" in msg or level == "warn":
            color = "#fbbf24" # ambar
            badge = "⚠️"
        elif "detectada ejecución externa" in msg.lower() or "servicio" in msg.lower() or "🔄" in msg:
            color = "#c084fc" # violeta
            badge = "🔄"
        else:
            color = "#e2e8f0" # slate claro
            badge = "ℹ️"
            
        html_msg = f'<div style="margin-bottom: 2px;"><span style="color: #64748b; font-size: 8pt;">[{now_str}]</span> <span style="color: {color}; font-size: 9pt;">{msg}</span></div>'
        self.log_viewer.append(html_msg)
        sb = self.log_viewer.verticalScrollBar()
        sb.setValue(sb.maximum())

    def limpiar_logs(self):
        """Limpia el terminal de logs."""
        self.log_viewer.clear()

    def copiar_logs(self):
        """Copia el contenido del terminal al portapapeles."""
        text = self.log_viewer.toPlainText()
        if text.strip():
            QApplication.clipboard().setText(text)
            self.add_log("📋 Logs copiados al portapapeles con éxito.")

    def update_elapsed_time(self):
        """Actualiza el label del tiempo transcurrido desde el inicio."""
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            seconds = int(elapsed.total_seconds())
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.lbl_time.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def check_background_state(self):
        """Chequea si el servicio de Telegram está ejecutando un flujo mediante el archivo state.json."""
        config_dir = Path(__file__).resolve().parent / "config"
        state_file = config_dir / "execution_state.json"
        stop_signal_file = config_dir / "stop_signal.txt"

        # Si se detecta señal de parada externa (de Telegram o Tray) y hay un worker local corriendo:
        if stop_signal_file.exists() and self.worker and self.worker.isRunning():
            self.add_log("🛑 Señal de parada externa detectada (Telegram/Tray). Deteniendo worker local...", level="warn")
            self.worker.stop()
            try:
                stop_signal_file.unlink()
            except Exception:
                pass

        bg_running = False
        wf_name = ""
        
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    bg_running = state.get("is_running", False)
                    wf_name = state.get("workflow", "")
            except Exception:
                pass
                
        # Solo actualizamos la UI si el estado cambió
        if bg_running != self.is_bg_running:
            self.is_bg_running = bg_running
            self._update_buttons_state()
            
            if bg_running:
                if wf_name == "Validación PACS":
                    self.lbl_status_icon.setText("🔍")
                    self.lbl_status_val.setText("Validación PACS en curso...")
                    self.status_banner.setStyleSheet("background-color: #fffbeb; border: 1px solid #f59e0b; border-radius: 8px; padding: 4px;")
                    self.lbl_active_wf.setText("Validación PACS")
                else:
                    self.lbl_status_icon.setText("🟣")
                    self.lbl_status_val.setText(f"Servicio Remoto: {wf_name}")
                    self.status_banner.setStyleSheet("background-color: #f5f3ff; border: 1px solid #8b5cf6; border-radius: 8px; padding: 4px;")
                    self.lbl_active_wf.setText(wf_name)
                    
                self.lbl_active_mode.setText("Servicio Telegram")
                self.lbl_active_channel.setText("Bot Telegram")
                self.badge_system.setText("● Ocupado (Background)")
                self.badge_system.setStyleSheet("background-color: #fef3c7; color: #d97706; border: 1px solid #fcd34d; border-radius: 12px; padding: 4px 12px; font-size: 9pt; font-weight: 700;")
                
                self.progress_bar.setRange(0, 0)
                self.start_time = datetime.now()
                self.duration_timer.start(1000)
                self.add_log(f"🔄 Detectada ejecución externa: {wf_name}")
            else:
                if not (self.worker and self.worker.isRunning()):
                    self._set_ui_idle_state()

    def _set_ui_idle_state(self):
        """Restaura todos los indicadores visuales al estado de reposo."""
        self.lbl_status_icon.setText("⚪")
        self.lbl_status_val.setText("Sistema en Reposo (Listo para operar)")
        self.status_banner.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px;")
        self.lbl_active_wf.setText("Ninguno")
        self.lbl_active_mode.setText("Individual")
        self.lbl_active_channel.setText("Panel Local")
        self.badge_system.setText("● Sistema Listo")
        self.badge_system.setStyleSheet("background-color: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; border-radius: 12px; padding: 4px 12px; font-size: 9pt; font-weight: 700;")
        
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.duration_timer.stop()
        self.lbl_time.setText("00:00:00")

    def _update_buttons_state(self):
        # Deshabilitar botones de inicio si hay algo corriendo (UI o BG)
        is_busy = bool(self.is_bg_running or (self.worker and self.worker.isRunning()))
        self.btn_inicio.setEnabled(not is_busy)
        self.btn_pega.setEnabled(not is_busy)
        self.btn_loop.setEnabled(not is_busy)
        self.btn_rehabilitar.setEnabled(not is_busy)
        
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
            modo_ui = "Telegram"
            print(f"🔄 Modo loop desde Telegram: {tipo_loop}")
        else:
            modo_texto = self.combo_loop_type.currentText()
            if "Por Cantidad" in modo_texto:
                tipo_loop = "count"
                reiteraciones = str(self.spin_iterations.value())
                duracion = 1.0
                modo_ui = f"Cantidad ({reiteraciones} ciclos)"
            elif "Por Tiempo" in modo_texto:
                tipo_loop = "timed"
                reiteraciones = "5"
                duracion = self.spin_duration.value()
                modo_ui = f"Tiempo ({duracion}h)"
            else:
                tipo_loop = "infinite"
                reiteraciones = "9999"
                duracion = 72.0
                modo_ui = "Infinito"
                
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

            self.add_log(f"🚀 Iniciando loop continuo en modo: {modo_ui}", level="start")
            
            self.worker = WorkflowExecutorWorker(workflow)
            self.worker.log_update.connect(self.handle_log_update)
            self.worker.finished.connect(self.on_workflow_finished)
            self.worker.error.connect(self.on_workflow_finished)
            
            self.start_time = datetime.now()
            self.duration_timer.start(1000)
            self.progress_bar.setRange(0, 0)
            
            self.lbl_status_icon.setText("🟢")
            self.lbl_status_val.setText(f"Loop en Ejecución ({modo_ui})")
            self.status_banner.setStyleSheet("background-color: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 4px;")
            self.lbl_active_wf.setText("loop.json")
            self.lbl_active_mode.setText(f"Loop: {modo_ui}")
            self.lbl_active_channel.setText("Panel Local")
            self.badge_system.setText("● Ejecutando")
            self.badge_system.setStyleSheet("background-color: #dbeafe; color: #1d4ed8; border: 1px solid #93c5fd; border-radius: 12px; padding: 4px 12px; font-size: 9pt; font-weight: 700;")
            
            self.worker.start()
            self._set_local_execution_state(True, "loop.json")
            self._update_buttons_state()
            
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
            wf_name = os.path.basename(wf_path)
            self.add_log(f"🚀 Iniciando workflow: {wf_name}", level="start")
            
            self.worker = WorkflowExecutorWorker(workflow)
            self.worker.log_update.connect(self.handle_log_update)
            self.worker.finished.connect(self.on_workflow_finished)
            self.worker.error.connect(self.on_workflow_finished)
            
            self.start_time = datetime.now()
            self.duration_timer.start(1000)
            self.progress_bar.setRange(0, 0)
            
            self.lbl_status_icon.setText("🟢")
            self.lbl_status_val.setText(f"Ejecutando: {wf_name}")
            self.status_banner.setStyleSheet("background-color: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 4px;")
            self.lbl_active_wf.setText(wf_name)
            self.lbl_active_mode.setText("Individual")
            self.lbl_active_channel.setText("Panel Local")
            self.badge_system.setText("● Ejecutando")
            self.badge_system.setStyleSheet("background-color: #dbeafe; color: #1d4ed8; border: 1px solid #93c5fd; border-radius: 12px; padding: 4px 12px; font-size: 9pt; font-weight: 700;")
            
            self.worker.start()
            self._set_local_execution_state(True, wf_name)
            self._update_buttons_state()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error iniciando workflow: {e}")
            import traceback
            traceback.print_exc()

    def handle_log_update(self, msg):
        print(f"[WORKFLOW]: {msg}")
        self.add_log(msg)

    def _set_local_execution_state(self, is_running, wf_name=""):
        try:
            cfg_dir = Path(__file__).resolve().parent / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            with open(cfg_dir / "execution_state.json", "w", encoding="utf-8") as f:
                json.dump({
                    "is_running": is_running,
                    "workflow": wf_name,
                    "updated_at": time.time()
                }, f)
        except Exception:
            pass

    def on_workflow_finished(self, result):
        self.duration_timer.stop()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        
        self.lbl_status_icon.setText("⏸️")
        self.lbl_status_val.setText("Inactivo")
        self.status_banner.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px;")
        self.lbl_active_wf.setText("Ninguno")
        self.lbl_active_mode.setText("-")
        self.lbl_active_channel.setText("-")
        self.badge_system.setText("● Listo")
        self.badge_system.setStyleSheet("background-color: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; border-radius: 12px; padding: 4px 12px; font-size: 9pt; font-weight: 700;")
        
        if isinstance(result, str): # Mensaje de error
            self.add_log(f"❌ Error en la ejecución:\n{result}", level="error")
            QMessageBox.critical(self, "Error de Ejecución", f"La ejecución falló con el error:\n{result}")
        elif isinstance(result, dict) and result.get("status") == "stopped":
            self.add_log("🛑 Ejecución detenida por el usuario.", level="warn")
            QMessageBox.warning(self, "Detenido", "Ejecución detenida por el usuario.")
        else:
            self.add_log("✅ La ejecución ha finalizado con éxito.", level="success")
            QMessageBox.information(self, "Completado", "La ejecución ha finalizado con éxito.")
            
        self.worker = None
        self._set_local_execution_state(False)
        self._update_buttons_state()

    def detiene_todo(self):
        """Detiene la ejecución actual del worker local o del servicio en background."""
        config_dir = Path(__file__).resolve().parent / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.add_log("🛑 Solicitando detención de worker local...", level="warn")
            self.btn_stop.setEnabled(False)
            
        # Señalizar stop_signal.txt siempre para abarcar background/telegram/tray
        try:
            with open(config_dir / "stop_signal.txt", "w", encoding="utf-8") as f:
                f.write("stop")
            self.add_log("🛑 Señal de parada enviada (stop_signal.txt).", level="warn")
            self.btn_stop.setEnabled(False)
        except Exception as e:
            print(f"Error escribiendo stop_signal.txt: {e}")

    def rehabilitar_ultimo_registro(self):
        # CONFIRMACIÓN PREVIA
        reply = QMessageBox.question(
            self, 
            "Confirmar Acción Crítica", 
            "¿Está seguro de que desea rehabilitar el último registro?\nEsto modificará el estado a 'En Proceso' en la base de datos MySQL.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            import mysql.connector
            
            # Cargar credenciales desde configuración o usar default
            db_cfg = self.config.get("database", {
                'host': 'localhost',
                'user': 'root',
                'password': '',
                'database': 'ris'
            })
            
            conn = mysql.connector.connect(**db_cfg, connect_timeout=5)
            cursor = conn.cursor()
            
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
                self.add_log("🔄 Último registro rehabilitado en la base de datos ('En Proceso').", level="success")
                QMessageBox.information(self, "Éxito", "Se ha rehabilitado el último registro correctamente ('En Proceso').")
            else:
                self.add_log("⚠️ No se encontró ningún registro para rehabilitar.", level="warn")
                QMessageBox.warning(self, "Aviso", "No se encontró ningún registro para actualizar o ya estaba en proceso.")
                
        except Exception as e:
            self.add_log(f"❌ Error al conectar a la BD: {e}", level="error")
            QMessageBox.critical(self, "Error de Base de Datos", f"No se pudo conectar a la base de datos o ejecutar la consulta:\n{e}")
            import traceback
            traceback.print_exc()


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
