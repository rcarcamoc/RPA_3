
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QHBoxLayout, QPushButton, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from datetime import datetime

# ============================================================================
# FLOATING CONTROL WINDOW
# ============================================================================
class FloatingControlWindow(QWidget):
    """Ventana flotante para controlar la grabación web."""

    # Signals
    finish_recording = pyqtSignal()
    pause_recording = pyqtSignal()
    ocr_state_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setWindowTitle("Control de Grabación")
        self.setGeometry(50, 50, 350, 400)

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # Display de acciones
        display_group = QGroupBox("Acciones Capturadas")
        display_layout = QVBoxLayout()
        self.actions_display = QTextEdit()
        self.actions_display.setReadOnly(True)
        self.actions_display.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas;")
        display_layout.addWidget(self.actions_display)
        display_group.setLayout(display_layout)
        main_layout.addWidget(display_group)

        # Controles
        controls_layout = QHBoxLayout()
        self.btn_pause = QPushButton("Pausar")
        self.btn_finish = QPushButton("Finalizar y Guardar")
        self.btn_finish.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold;")

        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_finish)
        main_layout.addLayout(controls_layout)

        # Opciones de captura
        self.check_ocr = QCheckBox("Capturar imagen para OCR en clicks")
        main_layout.addWidget(self.check_ocr)

        self.setLayout(main_layout)

        # Conectar signals
        self.btn_finish.clicked.connect(self.finish_recording.emit)
        self.btn_pause.clicked.connect(self.pause_recording.emit)
        self.check_ocr.stateChanged.connect(lambda state: self.ocr_state_changed.emit(state == Qt.CheckState.Checked.value))

    def add_log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.actions_display.append(f"[{timestamp}] {message}")

class WebRecordPanel(QWidget):
    """Panel para Grabador Web (Playwright)."""
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.recorder = None
        self.floating_window = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        title = QLabel("🌐 Web Recorder (Navegador)")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        config_group = QGroupBox("Configuración de Sesión")
        config_layout = QFormLayout()
        
        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("https://www.google.com")
        self.input_url.setText("https://www.google.com")
        config_layout.addRow("URL Inicial:", self.input_url)

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("mi_flujo_web")
        self.input_name.setText("demo_web")
        config_layout.addRow("Nombre Grabación:", self.input_name)

        self.combo_browser = QComboBox()
        self.combo_browser.addItems(["chrome", "edge", "firefox"])
        config_layout.addRow("Navegador:", self.combo_browser)

        self.check_maximize = QCheckBox("Iniciar navegador maximizado")
        self.check_maximize.setChecked(True)
        config_layout.addRow(self.check_maximize)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        self.btn_start = QPushButton("▶ Iniciar Grabación")
        self.btn_start.setMinimumHeight(45)
        self.btn_start.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold;")
        self.btn_start.clicked.connect(self.start_recording)
        layout.addWidget(self.btn_start)
        
        layout.addStretch()
        self.setLayout(layout)
        
    def start_recording(self):
        url = self.input_url.text()
        name = self.input_name.text()
        
        if not url or not name:
            QMessageBox.warning(self, "Datos incompletos", "Por favor ingresa URL y Nombre.")
            return

        try:
            from modules.web_recorder.web_recorder import WebRecorder, RecorderSettings
            
            if not self.floating_window:
                self.floating_window = FloatingControlWindow()
                self.floating_window.finish_recording.connect(self.stop_recording)
                self.floating_window.pause_recording.connect(self.toggle_pause)
                self.floating_window.ocr_state_changed.connect(self.set_ocr_state)

            self.floating_window.show()
            self.floating_window.add_log_message(f"Iniciando navegador en {url}...")
            
            settings = RecorderSettings(slowmo=500)
            self.recorder = WebRecorder(settings, log_callback=self.floating_window.add_log_message)
            
            browser = self.combo_browser.currentText()
            self.recorder.start_session(name, browser, url, maximized=self.check_maximize.isChecked())
            
            self.btn_start.setEnabled(False)
            
        except ImportError:
             QMessageBox.critical(self, "Error", "Módulo web_recorder no encontrado o dependencias faltantes.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al iniciar: {e}")

    def set_ocr_state(self, is_enabled: bool):
        if self.recorder:
            self.recorder.set_ocr_state(is_enabled)

    def toggle_pause(self):
        if self.recorder:
            self.recorder.toggle_pause()

    def stop_recording(self):
        if self.recorder:
            try:
                self.recorder.stop_session()
                self.floating_window.add_log_message("⏹ Grabación detenida.")
                
                path = self.recorder.export_to_python()
                self.floating_window.add_log_message(f"🐍 Python guardado: {path}")

                QMessageBox.information(self, "Finalizado", f"Sesión finalizada y guardada en:\n{path}")
                
            except Exception as e:
                self.floating_window.add_log_message(f"❌ Error al detener: {e}")
            finally:
                self.btn_start.setEnabled(True)
                if self.floating_window:
                    self.floating_window.close()
                self.floating_window = None
