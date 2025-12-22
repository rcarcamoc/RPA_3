
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFormLayout, QComboBox,
    QPushButton, QLineEdit, QSpinBox, QTextEdit, QMessageBox, QInputDialog, QFileDialog, QApplication
)
from PyQt6.QtGui import QFont
from mss import mss
from pathlib import Path
from ui.workers import OCRInitWorker

class OCRPanel(QWidget):
    """Tab para funcionalidades OCR en la GUI (PyQt6)."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ocr_engine = None
        self.ocr_actions = None
        self.code_generator = None
        self.last_screenshot = None
        
        self.init_ui()
        
    def showEvent(self, event):
        """Evento al mostrar la pestaña: Auto-iniciar OCR si es necesario."""
        super().showEvent(event)
        # Si no esta inicializado y no se esta inicializando (btn habilitado)
        if self.ocr_engine is None and self.btn_init.isEnabled():
            print("[DEBUG] Auto-inicializando OCR al seleccionar pestaña...")
            self.initialize_ocr()
            
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("👁️ OCR & Computer Vision")
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        self.status_label = QLabel("Not Initialized")
        self.status_label.setStyleSheet("color: #6b7280; font-style: italic;")
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Main Layout: 2 Columns
        content_layout = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()
        
        # --- 1. Configuration ---
        config_group = QGroupBox("1. Configuración")
        config_layout = QFormLayout()
        
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(['easyocr', 'tesseract'])
        config_layout.addRow("Motor:", self.engine_combo)
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(['es', 'en', 'pt', 'fr'])
        config_layout.addRow("Idioma:", self.lang_combo)

        self.monitor_combo = QComboBox()
        self.populate_monitors()
        config_layout.addRow("Monitor:", self.monitor_combo)
        
        self.btn_init = QPushButton("🔄 Inicializar OCR")
        self.btn_init.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold;")
        self.btn_init.clicked.connect(self.initialize_ocr)
        config_layout.addRow(self.btn_init)
        
        # Save Button (New)
        self.btn_save = QPushButton("💾 Guardar Script")
        self.btn_save.setStyleSheet("background-color: #059669; color: white; font-weight: bold;")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_module)
        config_layout.addRow(self.btn_save)
        
        config_group.setLayout(config_layout)
        left_col.addWidget(config_group)
        
        # --- 2. Test / Capture ---
        test_group = QGroupBox("2. Captura y Búsqueda")
        test_layout = QVBoxLayout()
        
        self.btn_capture = QPushButton("📸 Capturar Pantalla")
        self.btn_capture.clicked.connect(self.capture_screen)
        test_layout.addWidget(self.btn_capture)
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Buscar:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Texto a encontrar...")
        search_layout.addWidget(self.search_input)
        test_layout.addLayout(search_layout)
        
        self.btn_find = QPushButton("🔍 Buscar Texto")
        self.btn_find.clicked.connect(self.find_text)
        test_layout.addWidget(self.btn_find)
        
        test_group.setLayout(test_layout)
        left_col.addWidget(test_group)

        # --- 3. Generate Action ---
        gen_group = QGroupBox("3. Generar Acción")
        gen_layout = QFormLayout()
        
        self.action_combo = QComboBox()
        self.action_combo.addItems([
            'click', 
            'double_click', 
            'right_click', 
            'hover', 
            'wait_for_text',
            'copy', 
            'select', 
            'type_near_text'
        ])
        gen_layout.addRow("Acción:", self.action_combo)
        
        offset_layout = QHBoxLayout()
        self.offset_x = QSpinBox()
        self.offset_x.setRange(-500, 500)
        self.offset_y = QSpinBox()
        self.offset_y.setRange(-500, 500)
        
        offset_layout.addWidget(QLabel("X:"))
        offset_layout.addWidget(self.offset_x)
        offset_layout.addWidget(QLabel("Y:"))
        offset_layout.addWidget(self.offset_y)
        gen_layout.addRow("Offset:", offset_layout)
        
        self.btn_generate = QPushButton("🚀 Generar Módulo")
        self.btn_generate.setStyleSheet("background-color: #7c3aed; color: white; font-weight: bold;")
        self.btn_generate.clicked.connect(self.generate_module)
        gen_layout.addRow(self.btn_generate)
        
        gen_group.setLayout(gen_layout)
        left_col.addWidget(gen_group)
        
        left_col.addStretch()
        content_layout.addLayout(left_col, 1)
        
        # --- Right Column: Results ---
        results_group = QGroupBox("Resultados / Código")
        results_layout = QVBoxLayout()
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setFont(QFont("Courier New", 9))
        self.results_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        results_layout.addWidget(self.results_text)
        results_group.setLayout(results_layout)
        
        content_layout.addWidget(results_group, 2)
        
        layout.addLayout(content_layout)
        self.setLayout(layout)
        
        # Disable controls initially
        self.enable_controls(False)

    def enable_controls(self, enable):
        """Habilitar/deshabilitar controles dependientes de init."""
        self.btn_capture.setEnabled(enable)
        self.btn_find.setEnabled(enable)
        self.btn_generate.setEnabled(enable)
        self.btn_save.setEnabled(enable)

    def populate_monitors(self):
        try:
            with mss() as sct:
                monitors = sct.monitors
                for i, m in enumerate(monitors):
                    if i == 0:
                        self.monitor_combo.addItem(f"All Monitors (0)", 0)
                    else:
                        self.monitor_combo.addItem(f"Monitor {i} ({m['width']}x{m['height']})", i)
        except Exception as e:
            self.monitor_combo.addItem("Default (All)", 0)

    def initialize_ocr(self):
        engine = self.engine_combo.currentText()
        lang = self.lang_combo.currentText()
        
        self.status_label.setText(f"Initializing {engine}...")
        self.btn_init.setEnabled(False)
        self.results_text.setText(f"🚀 Initializing OCR Engine ({engine}, {lang})...\nPlease wait, this may take a moment.")
        
        self.worker = OCRInitWorker(engine, lang)
        self.worker.finished.connect(self.on_init_finished)
        self.worker.error.connect(self.on_init_error)
        self.worker.start()

    def on_init_finished(self, engine, matcher, actions, generator):
        self.ocr_engine = engine
        self.ocr_matcher = matcher
        self.ocr_actions = actions
        self.code_generator = generator
        
        self.status_label.setText("✅ OCR Ready")
        self.status_label.setStyleSheet("color: #059669; font-weight: bold;")
        self.results_text.append("\n✅ Initialization complete!")
        self.btn_init.setEnabled(True)
        self.enable_controls(True)

    def on_init_error(self, error):
        self.status_label.setText("❌ Error")
        self.status_label.setStyleSheet("color: #dc2626; font-weight: bold;")
        self.results_text.setText(f"❌ Error initializing OCR:\n{error}")
        self.btn_init.setEnabled(True)
        QMessageBox.critical(self, "OCR Error", f"Failed to initialize:\n{error}")

    def capture_screen(self):
        try:
            if self.ocr_actions:
                monitor_idx = self.monitor_combo.currentData()
                self.last_screenshot = self.ocr_actions.capture_screenshot(monitor_index=monitor_idx)
                self.results_text.append(f"\n📸 Screen captured successfully! (Monitor {monitor_idx})")
                QMessageBox.information(self, "Capture", "Screen captured!")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def find_text(self):
        term = self.search_input.text()
        if not term:
            QMessageBox.warning(self, "Warning", "Please enter text to search")
            return
            
        try:
            if not self.ocr_actions.last_screenshot is not None:
                self.capture_screen()
                
            self.results_text.append(f"\n🔍 Searching for '{term}'...")
            QApplication.processEvents()
            
            monitor_idx = self.monitor_combo.currentData()
            matches = self.ocr_actions.capture_and_find(
                term,
                fuzzy=True,
                take_screenshot=False, # Use cached or just captured
                monitor_index=monitor_idx
            )
            
            if matches:
                 self.results_text.append(f"✅ Found {len(matches)} matches:")
                 for i, m in enumerate(matches, 1):
                     self.results_text.append(
                         f"  {i}. Text: '{m['text']}' ({m.get('match_similarity',0)}%)\n"
                         f"     Pos: {m['center']}"
                     )
            else:
                self.results_text.append("⚠️ No matches found.")
                
        except Exception as e:
            self.results_text.append(f"❌ Error: {e}")

    def generate_module(self):
        term = self.search_input.text()
        action = self.action_combo.currentText()
        
        if not term:
            QMessageBox.warning(self, "Warning", "Enter text to search first")
            return
            
        try:
            module = None
            if action == 'click':
                module = self.code_generator.generate_click_module(
                    term,
                    offset_x=self.offset_x.value(),
                    offset_y=self.offset_y.value()
                )
            elif action == 'double_click':
                module = self.code_generator.generate_double_click_module(
                    term,
                    offset_x=self.offset_x.value(),
                    offset_y=self.offset_y.value()
                )
            elif action == 'right_click':
                module = self.code_generator.generate_right_click_module(
                    term,
                    offset_x=self.offset_x.value(),
                    offset_y=self.offset_y.value()
                )
            elif action == 'hover':
                module = self.code_generator.generate_hover_module(
                    term,
                    offset_x=self.offset_x.value(),
                    offset_y=self.offset_y.value()
                )
            elif action == 'wait_for_text':
                module = self.code_generator.generate_wait_module(term)
            elif action == 'copy':
                module = self.code_generator.generate_copy_module(term)
            elif action == 'select':
                module = self.code_generator.generate_select_module(term)
            elif action == 'type_near_text':
                 # Simple prompt for text to type for now
                 from PyQt6.QtWidgets import QInputDialog
                 text, ok = QInputDialog.getText(self, "Input", "Text to type:")
                 if ok and text:
                     module = self.code_generator.generate_type_near_text_module(
                         term, text,
                         offset_x=self.offset_x.value(),
                         offset_y=self.offset_y.value()
                     )
            
            if module:
                self.results_text.setText(module['code'])
                
                # Auto-save to recordings/ocr/
                try:
                    from utils.paths import get_ocr_module_path
                    file_path = get_ocr_module_path(f"{module['name']}.py")
                    
                    # Prepare code with runner for immediate execution
                    code_to_save = module['code']
                    if 'if __name__' not in code_to_save:
                         code_to_save += f"\n\nif __name__ == '__main__':\n    import logging\n    logging.basicConfig(level=logging.INFO)\n    print('🚀 Executing {module['function_name']}...')\n    res = {module['function_name']}()\n    print(f'Result: {{res}}')\n"

                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(code_to_save)
                        
                    self.results_text.append(f"\n# ✅ Module '{module['name']}' generated!")
                    self.results_text.append(f"# 📂 Saved to: {file_path}")
                    
                except Exception as e:
                    self.results_text.append(f"\n# ⚠️ Auto-save failed: {e}")
                    self.results_text.append(f"\n# ✅ Module '{module['name']}' generated!")

                self.last_generated_module_name = module['name'] # Keep track for runner
                
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def save_module(self):
        """Guardar el código generado en un archivo .py"""
        code = self.results_text.toPlainText()
        if not code or "def execute_" not in code:
             QMessageBox.warning(self, "Warning", "No valid code generated to save.")
             return

        # Use centralized path management
        try:
            from utils.paths import OCR_RECORDINGS_DIR
            modules_dir = OCR_RECORDINGS_DIR
            modules_dir.mkdir(parents=True, exist_ok=True)
            
            self.results_text.append(f"\n[INFO] Directorio destino: {modules_dir}")
            
        except Exception as e:
            msg = f"Error creando directorio modules: {e}"
            print(f"[ERROR] {msg}")
            QMessageBox.critical(self, "Error", msg)
            return

        # Ask for filename first
        name, ok = QInputDialog.getText(self, "Guardar Módulo", "Nombre del archivo (sin .py):")
        if not ok or not name:
            return
            
        if not name.endswith(".py"):
            name += ".py"

        initial_path = modules_dir / name

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Script", str(initial_path), "Python Files (*.py)"
        )
        
        if filename:
            try:
                # Agregar bloque runner si no existe
                if 'if __name__' not in code:
                    # Intenta extraer el nombre de la funcion
                    import re
                    match = re.search(r"def (execute_\w+)\(\):", code)
                    if match:
                        func_name = match.group(1)
                        code += f"\n\nif __name__ == '__main__':\n    print('🚀 Ejecutando {func_name}...')\n    result = {func_name}()\n    print(f'Terminado: {{result}}')\n"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(code)
                
                QMessageBox.information(self, "Success", f"Script guardado en:\n{filename}")
                self.results_text.append(f"\n✅ GUARDADO EXITOSO EN:\n{filename}")
                print(f"[DEBUG] Archivo guardado correctamente: {filename}")
                
            except Exception as e:
                print(f"[ERROR] Fallo al escribir archivo: {e}")
                QMessageBox.critical(self, "Error", f"Could not save file: {e}")
