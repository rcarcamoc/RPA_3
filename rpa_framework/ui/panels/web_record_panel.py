
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QHBoxLayout, QPushButton, QTextEdit, QMessageBox, QFrame, QListWidget, QAbstractItemView,
    QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QAction
from datetime import datetime
import os

# Import the NEW WebRecorder
try:
    from modules.web_recorder.web_recorder import WebRecorder, RecordingStats
    from modules.web_recorder.generator import PythonScriptGenerator
except ImportError as e:
    print(f"Error importing WebRecorder: {e}")
    WebRecorder = None

# ============================================================================
# WORKER THREAD FOR BROWSER
# ============================================================================

class BrowserWorker(QThread):
    """Thread to handle browser startup to avoid blocking UI"""
    browser_started = pyqtSignal(bool, str)
    
    def __init__(self, recorder, url, maximize):
        super().__init__()
        self.recorder = recorder
        self.url = url
        self.maximize = maximize
        
    def run(self):
        try:
            success = self.recorder.start_browser(self.url, self.maximize)
            self.browser_started.emit(success, "Browser Started" if success else "Failed to start browser")
        except Exception as e:
            self.browser_started.emit(False, str(e))

# ============================================================================
# FLOATING CONTROL WINDOW (PyQt6 Implementation)
# ============================================================================

class FloatingControlWindow(QWidget):
    """Floating window to control recording (PyQt6 impl)"""
    
    # Signals to communicate back to the main panel/recorder
    sig_start = pyqtSignal()
    sig_pause = pyqtSignal()
    sig_stop = pyqtSignal()
    sig_toggle_screenshot = pyqtSignal(bool)
    sig_replay = pyqtSignal()
    
    def __init__(self, recorder=None):
        super().__init__()
        self.recorder = recorder
        self.last_action_count = 0
        
        # Window flags to keep it on top and frameless/tool-like if desired
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setWindowTitle("🎬 Monitor de Eventos & Control")
        self.resize(450, 650)  # Larger default size
        
        # Styles (Force Light Theme)
        self.setStyleSheet("""
            QWidget { 
                background-color: #f5f5f5; 
                color: #000000; 
                font-family: Segoe UI, sans-serif; 
                font-size: 11px; 
            }
            QLabel { 
                color: #333333;
                background-color: transparent;
            }
            QPushButton { 
                padding: 8px; 
                border-radius: 4px; 
                border: 1px solid #ccc; 
                background-color: #e0e0e0;
                color: #000;
                min-height: 25px;
            }
            QPushButton:hover { background-color: #d0d0d0; }
            QPushButton:disabled { background-color: #f0f0f0; color: #aaa; border: 1px solid #ddd; }
            QGroupBox { 
                border: 1px solid #ccc; 
                margin-top: 15px; 
                font-weight: bold; 
                border-radius: 4px; 
                background-color: #fff;
                color: #333;
            }
            QGroupBox::title { 
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px; 
                background-color: #f5f5f5;
            }
            QListWidget { 
                border: 1px solid #ccc; 
                background-color: #fff; 
                color: #000;
                border-radius: 4px;
            }
            QCheckBox {
                color: #333;
                spacing: 5px;
            }
        """)
        
        self.init_ui()
        
        # Timer to update stats
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(200) # Faster updates (200ms)
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = QLabel("🔴 Grabación Web en Vivo")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("color: #d32f2f; margin-bottom: 5px;")
        layout.addWidget(header)
        
        # Status
        self.lbl_status = QLabel("Estado: Listo")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-weight: bold; color: #555;")
        layout.addWidget(self.lbl_status)
        
        # Stats Group
        stats_group = QGroupBox("Estadísticas")
        stats_layout = QFormLayout()
        stats_layout.setContentsMargins(10, 15, 10, 10)
        
        self.lbl_actions = QLabel("0")
        self.lbl_clicks = QLabel("0")
        self.lbl_inputs = QLabel("0")
        self.lbl_selects = QLabel("0")
        self.lbl_time = QLabel("00:00")
        
        # Font for numbers
        num_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        for lbl in [self.lbl_actions, self.lbl_clicks, self.lbl_inputs, self.lbl_selects, self.lbl_time]:
            lbl.setFont(num_font)
            lbl.setStyleSheet("color: #1976D2;")
        
        stats_layout.addRow("Acciones:", self.lbl_actions)
        stats_layout.addRow("Clicks:", self.lbl_clicks)
        stats_layout.addRow("Inputs:", self.lbl_inputs)
        stats_layout.addRow("Tiempo:", self.lbl_time)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("▶ Iniciar")
        self.btn_start.clicked.connect(self.on_start)
        self.btn_start.setStyleSheet("""
            QPushButton { background-color: #2E7D32; color: white; border: none; font-weight: bold; }
            QPushButton:hover { background-color: #1B5E20; }
            QPushButton:disabled { background-color: #A5D6A7; color: #eee; }
        """)
        
        self.btn_pause = QPushButton("⏸")
        self.btn_pause.setToolTip("Pausar/Reanudar")
        self.btn_pause.clicked.connect(self.on_pause)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setMaximumWidth(50)
        self.btn_pause.setStyleSheet("""
            QPushButton { background-color: #FF9800; color: white; border: none; font-weight: bold; }
            QPushButton:hover { background-color: #F57C00; }
        """)
        
        self.btn_stop = QPushButton("⏹ Terminar")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton { background-color: #C62828; color: white; border: none; font-weight: bold; }
            QPushButton:hover { background-color: #B71C1C; }
            QPushButton:disabled { background-color: #EF9A9A; color: #eee; }
        """)

        self.btn_replay_float = QPushButton("🔄 Validar")
        self.btn_replay_float.setToolTip("Reproducir script generado para validar")
        self.btn_replay_float.clicked.connect(self.sig_replay.emit)
        self.btn_replay_float.setEnabled(False)
        self.btn_replay_float.setStyleSheet("""
            QPushButton { background-color: #673AB7; color: white; border: none; font-weight: bold; }
            QPushButton:hover { background-color: #512DA8; }
            QPushButton:disabled { background-color: #D1C4E9; color: #eee; }
        """)
        
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_pause)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_replay_float)
        
        layout.addLayout(btn_layout)
        
        # Options
        self.chk_screenshot = QCheckBox("Capturar Screenshots (OCR)")
        self.chk_screenshot.toggled.connect(self.on_toggle_screenshot)
        layout.addWidget(self.chk_screenshot)
        
        # Event Log
        log_group = QGroupBox("Log de Eventos (En Vivo)")
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(5, 15, 5, 5) # Top margin for title
        
        self.log_list = QListWidget()
        self.log_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.log_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.log_list.setMinimumHeight(120)
        self.log_list.setStyleSheet("font-family: Consolas, monospace; font-size: 10px;")
        
        log_layout.addWidget(self.log_list)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        self.setLayout(layout)
        
    def update_stats(self):
        if self.recorder:
            # Update counts
            stats = self.recorder.stats
            self.lbl_actions.setText(str(stats.total_actions))
            self.lbl_clicks.setText(str(stats.clicks))
            self.lbl_inputs.setText(str(stats.inputs))
            self.lbl_selects.setText(str(stats.selects))
            self.lbl_time.setText(stats.elapsed_formatted)
            
            if self.recorder.is_paused:
                 self.lbl_status.setText("Pausado ⏸")
            elif self.recorder.is_recording:
                 self.lbl_status.setText("Grabando... 🔴")
                 
            # Update Log safely
            try:
                # Assuming actions is a simple list that grows
                current_count = len(self.recorder.actions)
                if current_count > self.last_action_count:
                    for i in range(self.last_action_count, current_count):
                        action = self.recorder.actions[i]
                        time_str = datetime.fromtimestamp(action.timestamp).strftime("%H:%M:%S")
                        
                        desc = f"unknown"
                        info = action.element_info
                        
                        element_ident = info.tag
                        if info.element_id:
                            element_ident += f"#{info.element_id}"
                        elif info.name:
                            element_ident += f"[name={info.name}]"
                            
                        if action.action_type == 'click':
                            txt = info.text[:30] + "..." if len(info.text) > 30 else info.text
                            desc = f"CLICK {element_ident} '{txt}'"
                            
                        elif action.action_type == 'input':
                             desc = f"WRITE '{action.value}' -> {element_ident}"
                             
                        elif action.action_type == 'select':
                             desc = f"SELECT '{action.value}' -> {element_ident}"
                             
                        elif action.action_type == 'navigate':
                             desc = f"NAVIGATE"
                             
                        elif action.action_type == 'page_load':
                             desc = f"PAGE LOAD {action.url[:40]}..."
                        
                        item = f"[{time_str}] {desc}"
                        self.log_list.addItem(item)
                        self.log_list.scrollToBottom()
                        
                    self.last_action_count = current_count
            except Exception as e:
                pass # Avoid crashing UI on list access race conditions

    def on_start(self):
        self.sig_start.emit()
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.btn_pause.setText("⏸ Pausar")
        self.log_list.clear() # Clear log on start
        self.last_action_count = 0
    
    def on_pause(self):
        self.sig_pause.emit()
        if self.btn_pause.text() == "⏸ Pausar":
            self.btn_pause.setText("▶ Reanudar")
        else:
            self.btn_pause.setText("⏸ Pausar")
            
    def on_stop(self):
        self.sig_stop.emit()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Finalizado ✅")
        
    def on_toggle_screenshot(self, checked):
        self.sig_toggle_screenshot.emit(checked)
        
    def closeEvent(self, event):
        if self.recorder and self.recorder.is_recording:
            reply = QMessageBox.question(self, 'Confirmar', 
                             "¿Detener grabación y cerrar?", QMessageBox.StandardButton.Yes | 
                             QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.on_stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# ============================================================================
# MAIN PANEL
# ============================================================================

class WebRecordPanel(QWidget):
    """Main Panel for Web Recorder"""
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.recorder = None
        self.floating_window = None
        self.last_script_path = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Title
        title = QLabel("🌐 Web Recorder (Selenium Engine)")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #1976D2;") # Blue instead of dark theme color
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "Este módulo permite grabar acciones en el navegador y generar un script independiente.\n"
            "Captura clicks, escritura, selecciones y opcionalmente screenshots para OCR."
        )
        desc.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc)
        
        # Settings Container - REMOVED DARK THEME
        settings_frame = QFrame()
        settings_frame.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 6px; padding: 10px;")
        settings_layout = QFormLayout(settings_frame)
        
        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("https://www.google.com (Opcional - Dejar vacío para usar pestaña actual)")
        self.input_url.setText("")
        settings_layout.addRow("URL Inicial:", self.input_url)
        
        self.check_maximize = QCheckBox("Iniciar navegador maximizado")
        self.check_maximize.setChecked(True)
        settings_layout.addRow(self.check_maximize)
        
        self.check_screenshots = QCheckBox("Capturar Screenshots por defecto")
        settings_layout.addRow(self.check_screenshots)
        
        layout.addWidget(settings_frame)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_launch = QPushButton("🚀 Lanza Navegador & Panel")
        self.btn_launch.setMinimumHeight(45)
        # Use simple colors
        self.btn_launch.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.btn_launch.clicked.connect(self.launch_session)
        
        self.btn_generate = QPushButton("💾 Generar Script .py")
        self.btn_generate.setMinimumHeight(45)
        self.btn_generate.setEnabled(False)
        self.btn_generate.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #388E3C; }
            QPushButton:disabled { background-color: #ccc; color: #666; }
        """)
        self.btn_generate.clicked.connect(self.generate_script)
        
        self.btn_replay = QPushButton("🔄 Reproducir Último")
        self.btn_replay.setMinimumHeight(45)
        self.btn_replay.setEnabled(False)
        self.btn_replay.setStyleSheet("""
            QPushButton { background-color: #673AB7; color: white; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #512DA8; }
            QPushButton:disabled { background-color: #ccc; color: #666; }
        """)
        self.btn_replay.clicked.connect(self.replay_last_script)

        btn_layout.addWidget(self.btn_launch)
        btn_layout.addWidget(self.btn_generate)
        btn_layout.addWidget(self.btn_replay)
        
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def launch_session(self):
        """Starts browser and shows floating window"""
        url = self.input_url.text().strip()
        if not url:
            url = "about:blank" # Recorder will stay on current page if already open
            
        if WebRecorder is None:
             QMessageBox.critical(self, "Error", "Módulo WebRecorder no cargado. Revisa dependencias (selenium).")
             return
        
        # Initialize Recorder
        self.recorder = WebRecorder(capture_screenshots=self.check_screenshots.isChecked())
        
        # Initialize Floating Window
        if self.floating_window:
            self.floating_window.close()
        
        self.floating_window = FloatingControlWindow(self.recorder)
        self.floating_window.sig_start.connect(self.recorder.start_recording)
        self.floating_window.sig_pause.connect(self.toggle_pause)
        self.floating_window.sig_stop.connect(self.stop_recording)
        self.floating_window.sig_toggle_screenshot.connect(self.toggle_screenshots)
        self.floating_window.sig_replay.connect(self.replay_last_script)
        self.floating_window.chk_screenshot.setChecked(self.check_screenshots.isChecked())
        
        # Start Browser in Background Thread
        self.btn_launch.setEnabled(False)
        self.btn_launch.setText("Iniciando navegador...")
        
        self.worker = BrowserWorker(self.recorder, url, self.check_maximize.isChecked())
        self.worker.browser_started.connect(self.on_browser_started)
        self.worker.start()
        
    def on_browser_started(self, success, message):
        self.btn_launch.setEnabled(True)
        self.btn_launch.setText("🚀 Lanza Navegador & Panel")
        
        if success:
            self.floating_window.show()
        else:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar el navegador: {message}")
            self.recorder = None
            
    def toggle_pause(self):
        if not self.recorder: return
        if self.recorder.is_paused:
            self.recorder.resume_recording()
        else:
            self.recorder.pause_recording()
            
    def stop_recording(self):
        if self.recorder:
            self.recorder.stop_recording()
            self.btn_generate.setEnabled(True)
            self.btn_generate.setText(f"💾 Generar Script ({self.recorder.stats.total_actions} acciones)")
            
            # Ask if user wants to save as script immediately
            if self.recorder.stats.total_actions > 0:
                reply = QMessageBox.question(
                    self, 'Guardar Grabación',
                    "¿Deseas guardar esta grabación como un script Python (.py) ahora mismo?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.generate_script()
    
    def toggle_screenshots(self, enabled):
        if self.recorder:
            self.recorder.capture_screenshots = enabled
            
    def generate_script(self):
        if not self.recorder or not self.recorder.actions:
            QMessageBox.warning(self, "Vacío", "No hay acciones grabadas.")
            return
            
        try:
            # Prepare default name
            default_name = f"web_automation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Ask for custom name
            name, ok = QInputDialog.getText(
                self, "Guardar Script", 
                "Nombre del archivo (sin .py):", 
                QLineEdit.EchoMode.Normal, 
                default_name
            )
            
            if not ok or not name.strip():
                return
                
            filename = f"{name.strip()}.py"
            
            generator = PythonScriptGenerator(self.recorder)
            content = generator.generate()
            
            # Define save directory
            save_dir = os.path.join(os.getcwd(), "recordings", "web")
            # Ensure path exists
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            
            filepath = os.path.join(save_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.last_script_path = filepath
            self.btn_replay.setEnabled(True)
            if self.floating_window:
                self.floating_window.btn_replay_float.setEnabled(True)

            QMessageBox.information(self, "Éxito", f"Script generado correctamente:\n\n{filepath}")
            
        except Exception as e:
             QMessageBox.critical(self, "Error", f"Error generando script: {e}")

    def replay_last_script(self):
        """Executes the last generated script for validation"""
        if not self.last_script_path or not os.path.exists(self.last_script_path):
            QMessageBox.warning(self, "Aviso", "No hay un script generado para reproducir.")
            return

        try:
            import subprocess
            import sys
            
            # Use the current python executable (useful for venv)
            python_exe = sys.executable
            
            # Determine if we should show a message
            self.btn_replay.setEnabled(False)
            self.btn_replay.setText("Reproduciendo...")
            if self.floating_window:
                self.floating_window.btn_replay_float.setEnabled(False)
                self.floating_window.lbl_status.setText("Validando Script... 🔄")

            # Run in background to avoid freezing UI
            # We use subprocess.Popen so we don't wait for it to finish in the main thread
            # but for a simple validation, it's fine.
            # Using Popen allows the user to see the browser without blocking the UI.
            subprocess.Popen([python_exe, self.last_script_path], 
                             creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            
            # Re-enable after a short delay or just leave it enabled
            QTimer.singleShot(2000, lambda: self._reset_replay_button())
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo reproducir el script: {e}")
            self._reset_replay_button()

    def _reset_replay_button(self):
        self.btn_replay.setEnabled(True)
        self.btn_replay.setText("🔄 Reproducir Último")
        if self.floating_window:
            self.floating_window.btn_replay_float.setEnabled(True)
            self.floating_window.lbl_status.setText("Listo para validar ✅")
