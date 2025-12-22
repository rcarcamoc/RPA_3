
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QMessageBox
)
from PyQt6.QtGui import QFont
from core.recorder import RecorderGUI

class RecordPanel(QWidget):
    """Panel para grabar."""
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Título
        title = QLabel("📹 Grabar Acciones")
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Instrucciones
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setText("""
CÓMO GRABAR:

1. Presiona "Iniciar Grabación"
2. Se abrirá ventana pequeña con botones
3. Presiona "REC" en esa ventana
4. Interactúa con la aplicación (clicks, typing)
5. Presiona "STOP"
6. Ingresa nombre del módulo
7. ¡Grabación guardada!

Las grabaciones se guardan en: recordings/
        """)
        instructions.setStyleSheet("""
            QTextEdit {
                background-color: #fffbeb; /* Amarillo muy suave */
                color: #92400e;            /* Marrón texto */
                border: 1px solid #fcd34d;
                border-radius: 6px;
                padding: 10px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(instructions)
        
        # Botón
        btn_record = QPushButton("▶ Iniciar Grabación")
        btn_record.setMinimumHeight(50)
        btn_record.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        btn_record.clicked.connect(self.start_recording)
        layout.addWidget(btn_record)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def start_recording(self):
        try:
            gui = RecorderGUI(config=self.config)
            gui.run()
            QMessageBox.information(self, "✅ Éxito", "Grabación completada")
        except Exception as e:
            QMessageBox.critical(self, "❌ Error", f"Error: {e}")
