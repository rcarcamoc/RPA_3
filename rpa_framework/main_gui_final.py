import os
import sys
import warnings
import subprocess

# Configure UTF-8 for console output on Windows to prevent UnicodeEncodeError
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# --- SUPPRESS CONSOLE NOISE ---
import logging
import json
import threading
from datetime import datetime

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
os.chdir(os.path.dirname(os.path.abspath(__file__)))


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QTabWidget, QPushButton, QMessageBox, QSpinBox, QComboBox, 
    QDoubleSpinBox, QProgressBar, QTextEdit, QGroupBox, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon

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
    print(f"❌ Error importando módulos RPA: {e}")
    print("Asegúrate de estar en rpa_framework/")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# ============================================================================
# ESTILOS ADICIONALES (DESIGN TOKENS & OVERRIDES)
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
    border-radius: 6px;
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

/* GroupBox como Cards */
#operation_card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 15px;
    padding: 15px;
}

QGroupBox#operation_card::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    left: 15px;
    color: #3b82f6;
    background-color: #ffffff;
    font-weight: bold;
    font-size: 10pt;
}

/* Botones del panel de operaciones */
QPushButton[cssClass="primary"] {
    background-color: #10b981;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-weight: bold;
    font-size: 10pt;
}
QPushButton[cssClass="primary"]:hover {
    background-color: #059669;
}
QPushButton[cssClass="primary"]:pressed {
    background-color: #047857;
}
QPushButton[cssClass="primary"]:disabled {
    background-color: #a7f3d0;
    color: #ffffff;
}

QPushButton[cssClass="secondary"] {
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-weight: bold;
    font-size: 10pt;
}
QPushButton[cssClass="secondary"]:hover {
    background-color: #2563eb;
}
QPushButton[cssClass="secondary"]:pressed {
    background-color: #1d4ed8;
}
QPushButton[cssClass="secondary"]:disabled {
    background-color: #bfdbfe;
    color: #ffffff;
}

QPushButton[cssClass="warning"] {
    background-color: #f59e0b;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-weight: bold;
    font-size: 10pt;
}
QPushButton[cssClass="warning"]:hover {
    background-color: #d97706;
}
QPushButton[cssClass="warning"]:pressed {
    background-color: #b45309;
}
QPushButton[cssClass="warning"]:disabled {
    background-color: #fde68a;
    color: #ffffff;
}

QPushButton[cssClass="danger"] {
    background-color: #ef4444;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-weight: bold;
    font-size: 10pt;
}
QPushButton[cssClass="danger"]:hover {
    background-color: #dc2626;
}
QPushButton[cssClass="danger"]:pressed {
    background-color: #b91c1c;
}
QPushButton[cssClass="danger"]:disabled {
    background-color: #fca5a5;
    color: #ffffff;
}

QPushButton[cssClass="loop"] {
    background-color: #8b5cf6;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-weight: bold;
    font-size: 10pt;
}
QPushButton[cssClass="loop"]:hover {
    background-color: #7c3aed;
}
QPushButton[cssClass="loop"]:pressed {
    background-color: #6d28d9;
}
QPushButton[cssClass="loop"]:disabled {
    background-color: #ddd6fe;
    color: #ffffff;
}

/* Estilos de inputs */
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px;
    color: #0f172a;
    font-size: 10pt;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
}
"""

FINAL_STYLESHEET = GLOBAL_STYLESHEET + CUSTOM_STYLESHEET


# ============================================================================
# PANEL DE OPERACIONES REDISEÑADO
# ============================================================================

class ModernOperacionesPanel(QWidget):
    """Panel de Operaciones rediseñado con sistema de tarjetas y feedback no bloqueante."""
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
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Etiqueta de título
        lbl_titulo = QLabel("⚡ Panel de Control de Operaciones")
        lbl_titulo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #0f172a; margin-bottom: 5px;")
        main_layout.addWidget(lbl_titulo)
        
        # Función auxiliar para aplicar sombra
        def apply_shadow(widget):
            shadow = QGraphicsDropShadowEffect(widget)
            shadow.setBlurRadius(10)
            shadow.setXOffset(0)
            shadow.setYOffset(3)
            shadow.setColor(QColor(0, 0, 0, 20))
            widget.setGraphicsEffect(shadow)

        # --- CARD 1: ACCIONES RÁPIDAS ---
        card_acciones = QGroupBox("Acciones Rápidas")
        card_acciones.setObjectName("operation_card")
        apply_shadow(card_acciones)
        
        layout_acciones = QVBoxLayout(card_acciones)
        layout_acciones.setSpacing(10)
        
        # Descripción
        lbl_desc_acc = QLabel("Ejecute tareas individuales de forma inmediata o rehabilite registros en la base de datos.")
        lbl_desc_acc.setWordWrap(True)
        lbl_desc_acc.setStyleSheet("color: #64748b; margin-bottom: 5px;")
        layout_acciones.addWidget(lbl_desc_acc)
        
        buttons_layout = QHBoxLayout()
        
        self.btn_inicio = QPushButton("▶ Inicio Completo")
        self.btn_inicio.setMinimumHeight(45)
        self.btn_inicio.setProperty("cssClass", "primary")
        self.btn_inicio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_inicio.clicked.connect(self.ejecutar_inicio_completo)
        self.btn_inicio.setToolTip("Inicia el flujo completo del workflow Sub_work.json")
        buttons_layout.addWidget(self.btn_inicio)
        
        self.btn_pega = QPushButton("▶ Solo Pega en Integra")
        self.btn_pega.setMinimumHeight(45)
        self.btn_pega.setProperty("cssClass", "secondary")
        self.btn_pega.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pega.clicked.connect(self.ejecutar_pega_integra)
        self.btn_pega.setToolTip("Inicia el workflow pacs.json")
        buttons_layout.addWidget(self.btn_pega)
        
        self.btn_rehabilitar = QPushButton("🔄 Rehabilitar Último")
        self.btn_rehabilitar.setMinimumHeight(45)
        self.btn_rehabilitar.setProperty("cssClass", "warning")
        self.btn_rehabilitar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rehabilitar.clicked.connect(self.rehabilitar_ultimo_registro)
        self.btn_rehabilitar.setToolTip("Cambia el estado del último registro de la base de datos a 'En Proceso'")
        buttons_layout.addWidget(self.btn_rehabilitar)
        
        layout_acciones.addLayout(buttons_layout)
        main_layout.addWidget(card_acciones)
        
        # --- CARD 2: CONFIGURACIÓN DE LOOP CONTINUO ---
        card_loop = QGroupBox("⚙️ Configuración de Loop Continuo (Flujo Continuo)")
        card_loop.setObjectName("operation_card")
        apply_shadow(card_loop)
        
        layout_loop = QVBoxLayout(card_loop)
        layout_loop.setSpacing(10)
        
        lbl_desc_loop = QLabel("Ejecute de forma cíclica el flujo principal basado en el criterio definido a continuación.")
        lbl_desc_loop.setStyleSheet("color: #64748b; margin-bottom: 5px;")
        layout_loop.addWidget(lbl_desc_loop)
        
        # Grid para controles
        grid_loop = QGridLayout()
        grid_loop.setSpacing(10)
        
        # Modo
        grid_loop.addWidget(QLabel("Modo de Ejecución:"), 0, 0)
        self.combo_loop_type = QComboBox()
        self.combo_loop_type.addItems(["Por Cantidad", "Por Tiempo (Horas)", "Infinito"])
        self.combo_loop_type.setMinimumHeight(35)
        self.combo_loop_type.currentIndexChanged.connect(self.actualizar_visibilidad_loop)
        grid_loop.addWidget(self.combo_loop_type, 0, 1)
        
        # Contenedores variables
        # Cantidad
        self.container_count = QWidget()
        layout_count = QHBoxLayout(self.container_count)
        layout_count.setContentsMargins(0, 0, 0, 0)
        layout_count.addWidget(QLabel("Cantidad de reiteraciones:"))
        self.spin_iterations = QSpinBox()
        self.spin_iterations.setRange(1, 9999)
        self.spin_iterations.setValue(5)
        self.spin_iterations.setMinimumHeight(35)
        self.spin_iterations.setToolTip("Número total de veces que se ejecutará el loop")
        layout_count.addWidget(self.spin_iterations)
        grid_loop.addWidget(self.container_count, 1, 0, 1, 2)
        
        # Tiempo
        self.container_timed = QWidget()
        layout_timed = QHBoxLayout(self.container_timed)
        layout_timed.setContentsMargins(0, 0, 0, 0)
        layout_timed.addWidget(QLabel("Duración límite:"))
        self.spin_duration = QDoubleSpinBox()
        self.spin_duration.setRange(0.1, 72.0)
        self.spin_duration.setValue(1.0)
        self.spin_duration.setSuffix(" horas")
        self.spin_duration.setMinimumHeight(35)
        self.spin_duration.setToolTip("Duración máxima del flujo en horas")
        layout_timed.addWidget(self.spin_duration)
        grid_loop.addWidget(self.container_timed, 1, 0, 1, 2)
        self.container_timed.hide()
        
        # Delay Error
        grid_loop.addWidget(QLabel("Pausa si ocurre un fallo:"), 2, 0)
        self.spin_error_delay = QSpinBox()
        self.spin_error_delay.setRange(0, 3600)
        self.spin_error_delay.setValue(0)
        self.spin_error_delay.setSuffix(" segundos")
        self.spin_error_delay.setMinimumHeight(35)
        self.spin_error_delay.setToolTip("Espera de tiempo en caso de que ocurra un error antes de reintentar")
        grid_loop.addWidget(self.spin_error_delay, 2, 1)
        
        layout_loop.addLayout(grid_loop)
        
        self.btn_loop = QPushButton("🚀 Iniciar Flujo Continuo (Loop)")
        self.btn_loop.setMinimumHeight(45)
        self.btn_loop.setProperty("cssClass", "loop")
        self.btn_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_loop.clicked.connect(self.ejecutar_loop_reiteraciones)
        layout_loop.addWidget(self.btn_loop)
        
        main_layout.addWidget(card_loop)
        
        # --- CARD 3: ESTADO Y CONTROL ---
        card_estado = QGroupBox("Status de Ejecución")
        card_estado.setObjectName("operation_card")
        apply_shadow(card_estado)
        
        layout_estado = QVBoxLayout(card_estado)
        layout_estado.setSpacing(10)
        
        # Status details layout
        status_info_layout = QHBoxLayout()
        lbl_status_title = QLabel("Estado Actual:")
        lbl_status_title.setStyleSheet("font-weight: bold; color: #475569;")
        self.lbl_status_val = QLabel("⚪ Inactivo")
        self.lbl_status_val.setObjectName("status_value")
        self.lbl_status_val.setStyleSheet("color: #64748b; font-weight: bold;")
        
        status_info_layout.addWidget(lbl_status_title)
        status_info_layout.addWidget(self.lbl_status_val)
        status_info_layout.addStretch()
        
        self.lbl_time = QLabel("Tiempo transcurrido: --:--:--")
        self.lbl_time.setStyleSheet("color: #64748b; font-family: monospace; font-size: 10pt;")
        status_info_layout.addWidget(self.lbl_time)
        
        layout_estado.addLayout(status_info_layout)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                background-color: #f1f5f9;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 4px;
            }
        """)
        layout_estado.addWidget(self.progress_bar)
        
        # Mini log viewer
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumHeight(100)
        self.log_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                color: #38bdf8;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        self.log_viewer.setPlaceholderText("Los logs de ejecución aparecerán aquí...")
        layout_estado.addWidget(self.log_viewer)
        
        self.btn_stop = QPushButton("🛑 Detener Ejecución")
        self.btn_stop.setMinimumHeight(45)
        self.btn_stop.setProperty("cssClass", "danger")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.detiene_todo)
        layout_estado.addWidget(self.btn_stop)
        
        main_layout.addWidget(card_estado)
        
        main_layout.addStretch()
        self.setLayout(main_layout)

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

    def update_elapsed_time(self):
        """Actualiza el label del tiempo transcurrido desde el inicio."""
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            seconds = int(elapsed.total_seconds())
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.lbl_time.setText(f"Tiempo transcurrido: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def check_background_state(self):
        """Chequea si el servicio de Telegram está ejecutando un flujo mediante el archivo state.json."""
        state_file = os.path.join("config", "execution_state.json")
        bg_running = False
        wf_name = ""
        
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
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
                    self.lbl_status_val.setText("🔍 Validación PACS en curso...")
                    self.lbl_status_val.setStyleSheet("color: #d97706; font-weight: bold;")
                else:
                    self.lbl_status_val.setText(f"🟢 Servicio BG: {wf_name}")
                    self.lbl_status_val.setStyleSheet("color: #8b5cf6; font-weight: bold;")
                self.progress_bar.setRange(0, 0)
                self.start_time = datetime.now()
                self.duration_timer.start(1000)
                self.log_viewer.append(f"🔄 Detectada ejecución externa: {wf_name}")
            else:
                if not (self.worker and self.worker.isRunning()):
                    self.lbl_status_val.setText("⚪ Inactivo")
                    self.lbl_status_val.setStyleSheet("color: #64748b; font-weight: bold;")
                    self.progress_bar.setRange(0, 100)
                    self.progress_bar.setValue(0)
                    self.duration_timer.stop()
                    self.lbl_time.setText("Tiempo transcurrido: --:--:--")

    def _update_buttons_state(self):
        # Deshabilitar botones de inicio si hay algo corriendo (UI o BG)
        is_busy = bool(self.is_bg_running or (self.worker and self.worker.isRunning()))
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
            modo_ui = "Telegram"
            print(f"🔄 Modo loop desde Telegram: {tipo_loop}")
        else:
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

            self.log_viewer.clear()
            self.log_viewer.append(f"🚀 Iniciando loop continuo en modo: {modo_ui}")
            
            self.worker = WorkflowExecutorWorker(workflow)
            self.worker.log_update.connect(self.handle_log_update)
            self.worker.finished.connect(self.on_workflow_finished)
            self.worker.error.connect(self.on_workflow_finished)
            
            self.start_time = datetime.now()
            self.duration_timer.start(1000)
            self.progress_bar.setRange(0, 0)
            self.lbl_status_val.setText(f"🟢 Loop: {modo_ui}")
            self.lbl_status_val.setStyleSheet("color: #10b981; font-weight: bold;")
            
            self.worker.start()
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
            self.log_viewer.clear()
            self.log_viewer.append(f"🚀 Iniciando workflow: {os.path.basename(wf_path)}")
            
            self.worker = WorkflowExecutorWorker(workflow)
            self.worker.log_update.connect(self.handle_log_update)
            self.worker.finished.connect(self.on_workflow_finished)
            self.worker.error.connect(self.on_workflow_finished)
            
            self.start_time = datetime.now()
            self.duration_timer.start(1000)
            self.progress_bar.setRange(0, 0)
            self.lbl_status_val.setText(f"🟢 {os.path.basename(wf_path)}")
            self.lbl_status_val.setStyleSheet("color: #10b981; font-weight: bold;")
            
            self.worker.start()
            self._update_buttons_state()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error iniciando workflow: {e}")
            import traceback
            traceback.print_exc()

    def handle_log_update(self, msg):
        print(f"[WORKFLOW]: {msg}")
        self.log_viewer.append(msg)
        sb = self.log_viewer.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_workflow_finished(self, result):
        self.duration_timer.stop()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.lbl_status_val.setText("⚪ Inactivo")
        self.lbl_status_val.setStyleSheet("color: #64748b; font-weight: bold;")
        
        if isinstance(result, str): # Mensaje de error
            self.log_viewer.append(f"❌ Error en la ejecución:\n{result}")
            QMessageBox.critical(self, "Error de Ejecución", f"La ejecución falló con el error:\n{result}")
        elif isinstance(result, dict) and result.get("status") == "stopped":
            self.log_viewer.append("🛑 Ejecución detenida por el usuario.")
            QMessageBox.warning(self, "Detenido", "Ejecución detenida por el usuario.")
        else:
            self.log_viewer.append("✅ La ejecución ha finalizado con éxito.")
            QMessageBox.information(self, "Completado", "La ejecución ha finalizado con éxito.")
            
        self.worker = None
        self._update_buttons_state()
        self.lbl_time.setText("Tiempo transcurrido: --:--:--")

    def detiene_todo(self):
        """Detiene la ejecución actual del worker local o del servicio en background."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.log_viewer.append("🛑 Solicitando detención de UI local...")
            self.btn_stop.setEnabled(False)
            
        if self.is_bg_running:
            try:
                os.makedirs("config", exist_ok=True)
                with open(os.path.join("config", "stop_signal.txt"), "w") as f:
                    f.write("stop")
                self.log_viewer.append("🛑 Señal de parada enviada al servicio en background.")
                self.btn_stop.setEnabled(False)
            except Exception as e:
                print(f"Error escribiendo stop_signal.txt: {e}")

    def rehabilitar_ultimo_registro(self):
        # CONFIRMACIÓN PREVIA
        reply = QMessageBox.question(
            self, 
            "Confirmar Acción Crítica", 
            "¿Está seguro de que desea rehabilitar el último registro?\nEsto modificará el estado a 'En Proceso' en la base de datos.",
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
                self.log_viewer.append("🔄 Último registro rehabilitado en la base de datos.")
                QMessageBox.information(self, "Éxito", "Se ha rehabilitado el último registro correctamente ('En Proceso').")
            else:
                self.log_viewer.append("⚠️ No se encontró ningún registro para rehabilitar.")
                QMessageBox.warning(self, "Aviso", "No se encontró ningún registro para actualizar o ya estaba en proceso.")
                
        except Exception as e:
            self.log_viewer.append(f"❌ Error al conectar a la BD: {e}")
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
        self.setGeometry(100, 100, 1024, 768)
        
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


if __name__ == "__main__":
    main()
