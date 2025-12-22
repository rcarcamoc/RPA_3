
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QPushButton, QGroupBox,
    QFormLayout, QCheckBox, QLineEdit, QTextEdit, QMessageBox
)
from PyQt6.QtGui import QFont
from datetime import datetime
from generators.script_generator import QuickScriptGenerator
from generators.module_generator import ModuleGenerator
from utils.paths import get_all_json_recordings, get_all_scripts, UI_RECORDINGS_DIR, OCR_RECORDINGS_DIR

class GeneratorPanel(QWidget):
    """Panel para generar scripts y módulos."""
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Título
        title = QLabel("🔧 Generar Scripts y Módulos")
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # LISTA DE ARCHIVOS (Unificada con Replay)
        list_label = QLabel("Selecciona una grabación:")
        layout.addWidget(list_label)
        
        self.recordings_list = QListWidget()
        self.recordings_list.setMaximumHeight(150)
        layout.addWidget(self.recordings_list)
        
        btn_refresh = QPushButton("🔄 Recargar Lista")
        btn_refresh.clicked.connect(self.load_recordings)
        layout.addWidget(btn_refresh)
        
        # Opciones
        options_group = QGroupBox("Opciones de Generación")
        options_layout = QFormLayout()
        
        self.gen_script_check = QCheckBox("Generar Script Rápido (*_script.py)")
        self.gen_script_check.setChecked(True)
        options_layout.addRow(self.gen_script_check)
        
        self.gen_module_check = QCheckBox("Generar Módulo Independiente")
        self.gen_module_check.setChecked(True)
        options_layout.addRow(self.gen_module_check)
        
        self.module_name = QLineEdit()
        self.module_name.setPlaceholderText("mi_automacion")
        options_layout.addRow("Nombre del módulo:", self.module_name)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Botón
        btn_generate = QPushButton("🚀 Generar Código")
        btn_generate.setMinimumHeight(45)
        btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #8E24AA; /* Purple 500 */
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2; /* Purple 700 */
            }
        """)
        btn_generate.clicked.connect(self.generate)
        layout.addWidget(btn_generate)
        
        # Resultados
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)
        
        layout.addStretch()
        self.setLayout(layout)
        
        self.load_recordings()
    
    def load_recordings(self):
        """Carga lista de grabaciones y módulos OCR."""
        self.recordings_list.clear()
        
        # 1. Grabaciones JSON (Acciones UI)
        json_files = get_all_json_recordings(recording_type='ui')
        
        # 2. Módulos OCR Generados (Python)
        py_files = []
        if OCR_RECORDINGS_DIR.exists():
            py_files = sorted(list(OCR_RECORDINGS_DIR.glob("*.py")), reverse=True, key=lambda p: p.stat().st_mtime)

        # Agregar JSONs
        for p in json_files:
            date_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            self.recordings_list.addItem(f"[REC] {p.name}  ({date_str})")
            
        # Agregar OCR Modules (visualización)
        for p in py_files:
            if p.name != "__init__.py":
                date_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                self.recordings_list.addItem(f"[OCR] {p.name}  ({date_str})")
            
    def generate(self):
        current_item = self.recordings_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "⚠️ Advertencia", "Selecciona una grabación de la lista")
            return
            
        text = current_item.text()
        filename = text.split("  (")[0]
        
        # Detectar tipo por prefijo
        is_ocr = "[OCR]" in filename
        is_rec = "[REC]" in filename
        
        # Limpiar prefijo para obtener nombre real
        filename = filename.replace("[OCR] ", "").replace("[REC] ", "")

        if is_ocr:
            # Si es OCR, solo mostrar el código pues ya es un módulo .py
            file_path = OCR_RECORDINGS_DIR / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.results_text.setText(f.read())
                QMessageBox.information(self, "ℹ️ Info", f"Visualizando módulo existente:\n{filename}")
                return
        
        # Si es [REC] (JSON), procedemos a generar código
        file_path = UI_RECORDINGS_DIR / filename
        
        if not file_path.exists():
            QMessageBox.warning(self, "⚠️ Error", "Archivo no encontrado")
            return

        results = []
        try:
            if self.gen_script_check.isChecked():
                gen_script = QuickScriptGenerator(str(file_path))
                script_path = gen_script.generate()
                results.append(f"✅ Script generado: {script_path}")
            
            if self.gen_module_check.isChecked():
                module_name = self.module_name.text() or "mi_automacion"
                gen_module = ModuleGenerator(str(file_path), module_name, self.config)
                module_dir = gen_module.generate()
                results.append(f"📦 Módulo generado: {module_dir}")
            
            self.results_text.setText("\n".join(results))
            QMessageBox.information(self, "✅ Éxito", "\n".join(results))
        
        except Exception as e:
            self.results_text.setText(f"❌ Error: {e}")
            QMessageBox.critical(self, "❌ Error", f"Error: {e}")
