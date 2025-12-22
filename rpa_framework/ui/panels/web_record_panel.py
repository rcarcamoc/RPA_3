
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout, QLineEdit, QComboBox,
    QHBoxLayout, QPushButton, QTextEdit, QMessageBox
)
from PyQt6.QtGui import QFont
from datetime import datetime

class WebRecordPanel(QWidget):
    """Panel para Grabador Web (Playwright)."""
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.recorder = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Título
        title = QLabel("🌐 Web Recorder (Navegador)")
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Configuración
        config_group = QGroupBox("Configuración de Sesión")
        config_layout = QFormLayout()
        
        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("https://www.google.com")
        self.input_url.setText("https://www.google.com")
        config_layout.addRow("URL Inicial:", self.input_url)
        
        self.combo_browser = QComboBox()
        self.combo_browser.addItems(["chrome", "edge", "firefox"])
        config_layout.addRow("Navegador:", self.combo_browser)
        
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("mi_flujo_web")
        self.input_name.setText("demo_web")
        config_layout.addRow("Nombre Grabación:", self.input_name)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # Botones Control
        btn_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("▶ Iniciar Grabación")
        self.btn_start.setMinimumHeight(45)
        self.btn_start.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold;")
        self.btn_start.clicked.connect(self.start_recording)
        btn_layout.addWidget(self.btn_start)
        
        self.btn_capture_click = QPushButton("🖱️ Simular Click (Test)")
        self.btn_capture_click.setToolTip("Simula un click guardado si la grabación está activa")
        self.btn_capture_click.clicked.connect(self.simulate_click)
        self.btn_capture_click.setEnabled(False)
        btn_layout.addWidget(self.btn_capture_click)
        
        self.btn_stop = QPushButton("⏹ Detener")
        self.btn_stop.setMinimumHeight(45)
        self.btn_stop.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold;")
        self.btn_stop.clicked.connect(self.stop_recording)
        self.btn_stop.setEnabled(False)
        btn_layout.addWidget(self.btn_stop)
        
        layout.addLayout(btn_layout)
        
        # Log/Status
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas;")
        layout.addWidget(self.log_text)
        
        # Export Actions
        export_group = QGroupBox("Exportar Resultados")
        export_layout = QHBoxLayout()
        
        self.btn_export_json = QPushButton("📄 JSON")
        self.btn_export_json.clicked.connect(lambda: self.export_data("json"))
        self.btn_export_json.setEnabled(False)
        export_layout.addWidget(self.btn_export_json)
        
        self.btn_export_py = QPushButton("🐍 Python")
        self.btn_export_py.clicked.connect(lambda: self.export_data("python"))
        self.btn_export_py.setEnabled(False)
        export_layout.addWidget(self.btn_export_py)
        
        self.btn_export_n8n = QPushButton("🌩️ n8n Workflow")
        self.btn_export_n8n.clicked.connect(lambda: self.export_data("n8n"))
        self.btn_export_n8n.setEnabled(False)
        export_layout.addWidget(self.btn_export_n8n)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        layout.addStretch()
        self.setLayout(layout)
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
    def start_recording(self):
        url = self.input_url.text()
        browser = self.combo_browser.currentText()
        name = self.input_name.text()
        
        if not url or not name:
            QMessageBox.warning(self, "Datos incompletos", "Por favor ingresa URL y Nombre.")
            return

        try:
            # Importar aquí para no bloquear inicio si falla dependencia
            from web_recorder.web_recorder import WebRecorder, RecorderSettings
            
            self.log(f"Iniciando navegador {browser} en {url}...")
            
            settings = RecorderSettings(slowmo=500) # Un poco lento para ver mejor
            self.recorder = WebRecorder(settings)
            
            # Lanzar en Thread aparte sería ideal, pero Playwright sync debe ir en main o worker dedicado.
            # Por simplicidad en demo, lo hacemos síncrono bloqueante brevemente al inicio,
            # pero Playwright se mantendrá abierto.
            self.recorder.start_session(name, browser, url)
            
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.btn_capture_click.setEnabled(True)
            self.log("✅ Grabación Iniciada. Interactúa con el navegador (Simulación).")
            self.log("ℹ️ NOTA: En modo 'Simulación', usa el botón 'Simular Click' para registrar acciones de prueba si la inyección JS no está activa.")
            
        except ImportError:
             QMessageBox.critical(self, "Error", "Módulo web_recorder no encontrado o dependencias faltantes.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al iniciar: {e}")
            self.log(f"❌ Error: {e}")

    def stop_recording(self):
        if self.recorder:
            try:
                self.recorder.stop_session()
                self.log("⏹ Grabación detenida.")
                self.btn_start.setEnabled(True)
                self.btn_stop.setEnabled(False)
                self.btn_capture_click.setEnabled(False)
                
                # Habilitar export
                self.btn_export_json.setEnabled(True)
                self.btn_export_py.setEnabled(True)
                self.btn_export_n8n.setEnabled(True)
                
                QMessageBox.information(self, "Finalizado", "Sesión finalizada. Ahora puedes exportar.")
            except Exception as e:
                self.log(f"❌ Error al detener: {e}")

    def simulate_click(self):
        # Demo function to add a step without real browser interaction listener
        if self.recorder:
            self.recorder.simulate_capture_click("button#demo-btn", [100, 200])
            self.log("➕ Click simulado registrado.")

    def export_data(self, format_type):
        if not self.recorder: return
        
        try:
            if format_type == "json":
                path = self.recorder.export_to_json()
                self.log(f"📄 JSON guardado: {path}")
            elif format_type == "python":
                path = self.recorder.export_to_python()
                self.log(f"🐍 Python guardado: {path}")
            elif format_type == "n8n":
                path = self.recorder.export_to_n8n()
                self.log(f"🌩️ n8n guardado: {path}")
                
            if path:
                QMessageBox.information(self, "Exportar", f"Archivo generado:\n{path}")
        except Exception as e:
             QMessageBox.critical(self, "Error Exportar", str(e))
