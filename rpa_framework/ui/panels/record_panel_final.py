import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFormLayout, 
    QLineEdit, QPushButton, QTextEdit, QMessageBox, QFrame, QListWidget, 
    QAbstractItemView, QInputDialog, QStyle
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QAction

# Import the existing RPARecorder
try:
    from core.recorder import RPARecorder
    from generators.ui_script_generator_final import UIScriptGeneratorFinal
except ImportError as e:
    print(f"Error importing RPARecorder dependencies: {e}")
    RPARecorder = None

# ============================================================================
# FLOATING CONTROL WINDOW FOR DESKTOP RECORDING (NATIVE PyQt6)
# ============================================================================

class DesktopFloatingControlWindow(QWidget):
    """Ventana flotante nativa PyQt6 para controlar la grabación de escritorio sin congelar la aplicación principal"""
    
    sig_recording_saved = pyqtSignal(str) # Emite la ruta del script guardado
    
    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config or {}
        self.recorder = RPARecorder(self.config) if RPARecorder else None
        
        self.last_action_count = 0
        self.elapsed_seconds = 0
        self.is_recording = False
        self.is_paused = False
        self.start_time = None
        self.last_script_path = None
        
        # Mantener ventana encima y como herramienta flotante
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setWindowTitle("🎬 Control de Grabación Desktop")
        self.resize(420, 580)
        
        self.setStyleSheet("""
            QWidget { 
                background-color: #f8fafc; 
                color: #0f172a; 
                font-family: 'Segoe UI', sans-serif; 
                font-size: 11px; 
            }
            QLabel { 
                color: #334155;
            }
            QPushButton { 
                padding: 6px 12px; 
                border-radius: 6px; 
                border: 1px solid #cbd5e1; 
                background-color: #ffffff;
                color: #334155;
                font-weight: bold;
                min-height: 28px;
            }
            QPushButton:hover { 
                background-color: #f1f5f9; 
            }
            QPushButton:disabled { 
                background-color: #e2e8f0; 
                color: #94a3b8; 
                border: 1px solid #e2e8f0; 
            }
            QGroupBox { 
                border: 1px solid #cbd5e1; 
                margin-top: 12px; 
                font-weight: bold; 
                border-radius: 6px; 
                background-color: #ffffff;
                color: #0f172a;
            }
            QGroupBox::title { 
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px; 
                background-color: #f8fafc;
            }
            QListWidget { 
                border: 1px solid #cbd5e1; 
                background-color: #ffffff; 
                color: #0f172a;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        
        self.init_ui()
        
        # Timer para actualizar estadísticas e historial de eventos cada 200ms
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_live_data)
        
        # Timer de tiempo transcurrido (segundos)
        self.seconds_timer = QTimer(self)
        self.seconds_timer.timeout.connect(self.increment_timer)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header
        header = QLabel("🔴 Grabadora Desktop Activa")
        header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("color: #ef4444; margin-bottom: 4px;")
        layout.addWidget(header)
        
        # Status Label
        self.lbl_status = QLabel("Estado: Listo para comenzar")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-weight: bold; color: #475569; font-size: 10pt;")
        layout.addWidget(self.lbl_status)
        
        # Stats Panel
        stats_group = QGroupBox("Métricas en Vivo")
        stats_layout = QFormLayout(stats_group)
        stats_layout.setContentsMargins(12, 12, 12, 12)
        stats_layout.setSpacing(6)
        
        self.lbl_actions_cnt = QLabel("0")
        self.lbl_clicks_cnt = QLabel("0")
        self.lbl_keys_cnt = QLabel("0")
        self.lbl_time_elapsed = QLabel("00:00")
        
        stat_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        for lbl in [self.lbl_actions_cnt, self.lbl_clicks_cnt, self.lbl_keys_cnt, self.lbl_time_elapsed]:
            lbl.setFont(stat_font)
            lbl.setStyleSheet("color: #2563eb;")
            
        stats_layout.addRow("Total Acciones:", self.lbl_actions_cnt)
        stats_layout.addRow("Clicks Mouse:", self.lbl_clicks_cnt)
        stats_layout.addRow("Escritura / Teclado:", self.lbl_keys_cnt)
        stats_layout.addRow("Tiempo Grabado:", self.lbl_time_elapsed)
        layout.addWidget(stats_group)
        
        # Controls Bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        
        self.btn_rec = QPushButton("⏺ Grabar")
        self.btn_rec.clicked.connect(self.start_recording)
        self.btn_rec.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; border: none; font-weight: bold; }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #a7f3d0; }
        """)
        btn_layout.addWidget(self.btn_rec)
        
        self.btn_pause = QPushButton("⏸ Pausar")
        self.btn_pause.clicked.connect(self.pause_recording)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setStyleSheet("""
            QPushButton { background-color: #f59e0b; color: white; border: none; font-weight: bold; }
            QPushButton:hover { background-color: #d97706; }
            QPushButton:disabled { background-color: #fde68a; }
        """)
        btn_layout.addWidget(self.btn_pause)
        
        self.btn_stop = QPushButton("⏹ Terminar")
        self.btn_stop.clicked.connect(self.stop_recording)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; border: none; font-weight: bold; }
            QPushButton:hover { background-color: #dc2626; }
            QPushButton:disabled { background-color: #fca5a5; }
        """)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_play_test = QPushButton("🔄 Validar")
        self.btn_play_test.clicked.connect(self.play_last_recording)
        self.btn_play_test.setEnabled(False)
        self.btn_play_test.setStyleSheet("""
            QPushButton { background-color: #8b5cf6; color: white; border: none; font-weight: bold; }
            QPushButton:hover { background-color: #7c3aed; }
            QPushButton:disabled { background-color: #ddd6fe; }
        """)
        self.btn_play_test.setToolTip("Reproducir el script grabado para validar")
        btn_layout.addWidget(self.btn_play_test)
        
        layout.addLayout(btn_layout)
        
        # Live Event Log
        event_group = QGroupBox("Eventos Capturados (En Vivo)")
        event_layout = QVBoxLayout(event_group)
        event_layout.setContentsMargins(5, 12, 5, 5)
        
        self.log_list = QListWidget()
        self.log_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.log_list.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10px; border: none;")
        self.log_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        event_layout.addWidget(self.log_list)
        
        layout.addWidget(event_group)
        
    def start_recording(self):
        if not self.recorder:
            QMessageBox.critical(self, "Error", "El módulo grabador core.recorder no está disponible.")
            return
            
        if self.is_paused:
            self.recorder.recording = True
            self.is_paused = False
        else:
            self.recorder.start()
            self.log_list.clear()
            self.last_action_count = 0
            self.elapsed_seconds = 0
            
        self.is_recording = True
        self.lbl_status.setText("Grabando... 🔴")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #ef4444; font-size: 10pt;")
        
        self.btn_rec.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.btn_play_test.setEnabled(False)
        
        self.update_timer.start(200)
        self.seconds_timer.start(1000)
        
    def pause_recording(self):
        if self.recorder and self.is_recording:
            self.recorder.recording = False
            self.is_recording = False
            self.is_paused = True
            self.lbl_status.setText("Grabación Pausada ⏸")
            self.lbl_status.setStyleSheet("font-weight: bold; color: #f59e0b; font-size: 10pt;")
            
            self.btn_rec.setEnabled(True)
            self.btn_rec.setText("▶ Reanudar")
            self.btn_pause.setEnabled(False)
            self.seconds_timer.stop()
            
    def stop_recording(self):
        if not self.recorder: return
        
        self.update_timer.stop()
        self.seconds_timer.stop()
        
        self.recorder.stop()
        self.is_recording = False
        self.is_paused = False
        
        self.btn_rec.setText("⏺ Grabar")
        self.btn_rec.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Finalizado ✅")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #10b981; font-size: 10pt;")
        
        # Preguntar nombre del script usando PyQt6
        name, ok = QInputDialog.getText(self, "Guardar Grabación", "Ingresa el nombre para el módulo grabado:")
        if ok and name.strip():
            script_name = name.strip()
            try:
                # Generar JSON e inicializar UIScriptGeneratorFinal
                json_path = self.recorder.save(script_name)
                generator = UIScriptGeneratorFinal(self.recorder.actions, script_name)
                py_path = generator.generate()
                
                self.last_script_path = py_path
                self.btn_play_test.setEnabled(True)
                
                # Emitir señal al panel principal
                self.sig_recording_saved.emit(py_path)
                QMessageBox.information(self, "Guardado con éxito", 
                                        f"La grabación se guardó correctamente.\n\nJSON: {json_path}\nScript: {py_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error al generar script", f"Error: {e}")
        else:
            QMessageBox.warning(self, "Cancelado", "No se generó el script porque cancelaste o ingresaste un nombre vacío.")

    def play_last_recording(self):
        if self.last_script_path and os.path.exists(self.last_script_path):
            try:
                # Minimizar ventana de control flotante para no interferir con la automatización
                self.showMinimized()
                time.sleep(0.5)
                
                # Ejecutar script de prueba en un nuevo proceso de forma no bloqueante
                subprocess.Popen([sys.executable, self.last_script_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
            except Exception as e:
                QMessageBox.critical(self, "Error al reproducir", f"No se pudo ejecutar la prueba:\n{e}")

    def increment_timer(self):
        self.elapsed_seconds += 1
        mins = self.elapsed_seconds // 60
        secs = self.elapsed_seconds % 60
        self.lbl_time_elapsed.setText(f"{mins:02d}:{secs:02d}")
        
    def update_live_data(self):
        if not self.recorder: return
        
        # Actualizar contadores
        actions = self.recorder.actions
        curr_len = len(actions)
        self.lbl_actions_cnt.setText(str(curr_len))
        
        # Contar clicks e inputs
        clicks = sum(1 for a in actions if a.get("type") == "click")
        inputs = sum(1 for a in actions if a.get("type") in ["type_text", "key", "key_combination"])
        
        self.lbl_clicks_cnt.setText(str(clicks))
        self.lbl_keys_cnt.setText(str(inputs))
        
        # Procesar y listar nuevas acciones
        if curr_len > self.last_action_count:
            for i in range(self.last_action_count, curr_len):
                action = actions[i]
                atype = action.get("type", "")
                timestamp_str = datetime.now().strftime("%H:%M:%S")
                
                desc = "Acción registrada"
                if atype == "click":
                    name = action.get("element_info", {}).get("name", "")
                    pos = action.get("position", {"x":0, "y":0})
                    elem_desc = f'"{name}"' if name else f"Coord ({pos.get('x')}, {pos.get('y')})"
                    desc = f"🖱️ CLICK en {elem_desc}"
                elif atype == "type_text":
                    txt = action.get("text", "")
                    desc = f'⌨️ ESCRIBIR: "{txt}"'
                elif atype == "key":
                    key_code = action.get("key_code", "")
                    desc = f"⌨️ TECLA: {key_code}"
                elif atype == "key_combination":
                    combo = action.get("combination", "")
                    desc = f"⌨️ COMBO: {combo}"
                    
                item_text = f"[{timestamp_str}] {desc}"
                self.log_list.addItem(item_text)
                self.log_list.scrollToBottom()
                
            self.last_action_count = curr_len

    def closeEvent(self, event):
        if self.is_recording or self.is_paused:
            reply = QMessageBox.question(self, 'Salir', 
                                         "¿Desea cerrar la grabadora flotante? Se detendrá la sesión activa sin guardar.", 
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if self.recorder:
                    self.recorder.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

# ============================================================================
# MAIN PANEL (DESKTOP RECORD PANEL)
# ============================================================================

class RecordPanelFinal(QWidget):
    """Panel principal de Grabación Desktop de nivel empresarial y diseño premium"""
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.floating_window = None
        self.last_script = None
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("📹 Grabadora de Escritorio (Desktop Recorder)")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #10b981;") # Green Emerald color
        layout.addWidget(title)
        
        # Subtitle / Description
        desc = QLabel(
            "Registra tus interacciones de mouse y teclado sobre cualquier aplicación Windows para generar "
            "de forma automática scripts robóticos ejecutables (.py) que puedes arrastrar a tus workflows."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(desc)
        
        # Instructions Card (Professional QGroupBox)
        inst_group = QGroupBox("Guía de Operación")
        inst_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
                margin-top: 10px;
                padding-top: 12px;
                color: #0f172a;
            }
        """)
        inst_layout = QVBoxLayout(inst_group)
        inst_layout.setContentsMargins(15, 15, 15, 15)
        inst_layout.setSpacing(8)
        
        instructions = QLabel(
            "<b>1.</b> Presiona el botón <b>Lanzar Consola de Grabación</b>.<br/>"
            "<b>2.</b> Se abrirá una pequeña consola flotante interactiva que permanecerá visible encima de otras ventanas.<br/>"
            "<b>3.</b> Haz click en <b>Grabar</b> en la consola flotante para iniciar la captura de eventos.<br/>"
            "<b>4.</b> Trabaja de forma natural. Verás en vivo cada click y entrada de teclado registrada en el historial.<br/>"
            "<b>5.</b> Si necesitas hacer una pausa, pulsa <b>Pausar</b> y reanuda cuando estés listo.<br/>"
            "<b>6.</b> Haz click en <b>Terminar</b>, introduce el nombre del script y el sistema generará tu script .py en la carpeta de grabaciones.<br/>"
            "<b>7.</b> Pulsa <b>Validar</b> en el panel flotante para ejecutar una prueba automática y verificar el comportamiento del bot."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #334155; line-height: 1.5; font-size: 10pt;")
        inst_layout.addWidget(instructions)
        layout.addWidget(inst_group)
        
        # Primary Action Button
        self.btn_launch = QPushButton("▶ Lanzar Consola de Grabación")
        self.btn_launch.setMinimumHeight(45)
        self.btn_launch.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_launch.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
        """)
        self.btn_launch.clicked.connect(self.launch_recording_window)
        layout.addWidget(self.btn_launch)
        
        # Last Recording Card Group (Hidden by default, shown when a script is generated)
        self.result_group = QGroupBox("Última Grabación Generada")
        self.result_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #10b981;
                border-radius: 8px;
                background-color: #f0fdf4;
                margin-top: 10px;
                padding-top: 12px;
                color: #0f172a;
            }
        """)
        self.result_group.setVisible(False)
        
        res_layout = QVBoxLayout(self.result_group)
        res_layout.setContentsMargins(15, 15, 15, 15)
        res_layout.setSpacing(10)
        
        self.lbl_script_info = QLabel("Archivo: recordings/test_script.py")
        self.lbl_script_info.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.lbl_script_info.setStyleSheet("color: #047857;")
        res_layout.addWidget(self.lbl_script_info)
        
        # Action links layout
        res_btn_layout = QHBoxLayout()
        res_btn_layout.setSpacing(8)
        
        btn_open_folder = QPushButton("📂 Abrir Carpeta")
        btn_open_folder.clicked.connect(self.open_recordings_folder)
        res_btn_layout.addWidget(btn_open_folder)
        
        btn_edit_script = QPushButton("✏️ Editar Código")
        btn_edit_script.clicked.connect(self.edit_last_script)
        res_btn_layout.addWidget(btn_edit_script)
        
        btn_run_test = QPushButton("▶ Probar Bot")
        btn_run_test.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; border: none;")
        btn_run_test.clicked.connect(self.run_last_script_test)
        res_btn_layout.addWidget(btn_run_test)
        
        res_layout.addLayout(res_btn_layout)
        layout.addWidget(self.result_group)
        
        layout.addStretch()
        
    def launch_recording_window(self):
        # Si ya existe y está abierto, traerlo al frente
        if self.floating_window and self.floating_window.isVisible():
            self.floating_window.raise_()
            self.floating_window.activateWindow()
            return
            
        self.floating_window = DesktopFloatingControlWindow(self.config)
        self.floating_window.sig_recording_saved.connect(self.on_recording_saved)
        self.floating_window.show()
        
    def on_recording_saved(self, script_path):
        self.last_script = script_path
        self.lbl_script_info.setText(f"Archivo generado: {os.path.basename(script_path)}")
        self.result_group.setVisible(True)
        
    def open_recordings_folder(self):
        recordings_dir = os.path.join(os.getcwd(), "recordings")
        if not os.path.exists(recordings_dir):
            os.makedirs(recordings_dir, exist_ok=True)
        try:
            os.startfile(recordings_dir)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir la carpeta:\n{e}")
            
    def edit_last_script(self):
        if self.last_script and os.path.exists(self.last_script):
            try:
                os.startfile(self.last_script)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo abrir el archivo:\n{e}")
                
    def run_last_script_test(self):
        if self.last_script and os.path.exists(self.last_script):
            try:
                QMessageBox.information(self, "Prueba de Bot", 
                                        "Se iniciará la ejecución del script. Asegúrate de tener la ventana objetivo visible.")
                subprocess.Popen([sys.executable, self.last_script], creationflags=subprocess.CREATE_NEW_CONSOLE)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Fallo al ejecutar el bot:\n{e}")
