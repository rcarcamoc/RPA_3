#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RPA Framework v2 - GUI Application (Versión Simplificada)

GUI moderna y estable con:
- 4 pestañas principales
- Gráficos básicos
- Botones intuitivos
- Sin dependencias complicadas

Uso:
    cd rpa_framework
    python main_gui_simple.py
"""

import sys
# Force STA mode for COM/PyQt compatibility
sys.coinit_flags = 2
import os
import json

# Ensure we are running from the script directory for relative paths
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
from datetime import datetime

# Imports PyQt6
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog,
    QProgressBar, QCheckBox, QGroupBox, QFormLayout, QTextEdit,
    QSpinBox
)
from mss import mss
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# Imports RPA Framework
try:
    from core.recorder import RecorderGUI
    from core.player import RecordingPlayer
    from generators.script_generator import QuickScriptGenerator
    from generators.module_generator import ModuleGenerator
    from utils.config_loader import load_config
    from utils.logging_setup import setup_logging
    from ui.workflow_panel import WorkflowPanel
except ImportError as e:
    print(f"❌ Error importando módulos RPA: {e}")
    print("Asegúrate de estar en rpa_framework/")
    sys.exit(1)

# ============================================================================
# STYLES (Tema y Colores)
# ============================================================================

STYLESHEET = """
    /* Reset y Fuente Base */
    * {
        font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
        font-size: 10pt;
    }

    /* Ventana Principal y Widgets Base */
    QMainWindow, QWidget {
        background-color: #f5f7fa; /* Fondo claro suave */
        color: #2c3e50;            /* Texto oscuro casi negro */
    }

    /* Labels */
    QLabel {
        color: #2c3e50;
    }

    /* Botones Generales */
    QPushButton {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 6px 16px;
        color: #374151;
        font-weight: 600;
    }
    QPushButton:hover {
        background-color: #f3f4f6;
        border-color: #9ca3af;
    }
    QPushButton:pressed {
        background-color: #e5e7eb;
    }

    /* Inputs (QLineEdit, QTextEdit, QComboBox) */
    QLineEdit, QTextEdit, QComboBox {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 8px;
        color: #111827; /* Texto muy oscuro */
        selection-background-color: #3b82f6;
        selection-color: #ffffff;
    }
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
        border: 1px solid #3b82f6;
        background-color: #ffffff;
    }
    QLineEdit:disabled, QTextEdit:disabled {
        background-color: #f3f4f6;
        color: #9ca3af;
    }

    /* Tablas */
    QTableWidget {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        gridline-color: #f3f4f6;
        color: #111827;
        selection-background-color: #eff6ff;
        selection-color: #1e40af;
    }
    QHeaderView::section {
        background-color: #f9fafb;
        border: none;
        border-bottom: 2px solid #e5e7eb;
        padding: 8px;
        font-weight: 700;
        color: #4b5563;
    }

    /* Pestañas (Tabs) */
    QTabWidget::pane {
        border: 1px solid #e5e7eb;
        background-color: #ffffff;
        border-radius: 6px;
        margin-top: -1px; /* Pegar al borde */
    }
    QTabBar::tab {
        background-color: #f3f4f6;
        color: #6b7280;
        padding: 10px 20px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 4px;
        border: 1px solid transparent;
    }
    QTabBar::tab:selected {
        background-color: #ffffff;
        color: #2563eb; /* Azul vibrante */
        font-weight: bold;
        border: 1px solid #e5e7eb;
        border-bottom-color: #ffffff; /* Fusión visual */
    }
    QTabBar::tab:hover:!selected {
        background-color: #e5e7eb;
        color: #374151;
    }

    /* GroupBox */
    QGroupBox {
        font-weight: bold;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        margin-top: 12px;
        padding-top: 10px;
        color: #111827;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        left: 10px;
        color: #4b5563;
    }
    
    /* Scrollbars */
    QScrollBar:vertical {
        border: none;
        background: #f3f4f6;
        width: 10px;
        margin: 0;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical {
        background: #d1d5db;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover {
        background: #9ca3af;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""

# ============================================================================
# WORKERS (Threads)
# ============================================================================

class ReplayWorker(QThread):
    """Worker para reproducción sin bloquear UI."""
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, recording_path: str, config: dict):
        super().__init__()
        self.recording_path = recording_path
        self.config = config
    
    def run(self):
        print(f"[DEBUG] ReplayWorker: Iniciando thread... (TID: {int(QThread.currentThreadId())})")
        
        # Inicializar COM para este hilo (necesario para pywinauto en QThread)
        try:
            import pythoncom
            print("[DEBUG] ReplayWorker: Intentando CoInitialize...")
            pythoncom.CoInitialize()
            print("[DEBUG] ReplayWorker: CoInitialize OK")
        except ImportError:
            print("[DEBUG] ReplayWorker: pythoncom no encontrado, saltando CoInitialize")
        except Exception as e:
            print(f"[DEBUG] ReplayWorker: Error en CoInitialize: {e}")

        try:
            print(f"[DEBUG] ReplayWorker: Inicializando RecordingPlayer con {self.recording_path}")
            player = RecordingPlayer(self.recording_path, self.config)
            
            print("[DEBUG] ReplayWorker: Ejecutando player.run()...")
            results = player.run()
            
            print(f"[DEBUG] ReplayWorker: Ejecución finalizada. Status: {results.get('status')}")
            self.finished.emit(results)
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"[DEBUG] ReplayWorker: EXCEPCIÓN: {error_msg}")
            self.error.emit(str(e))
            
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
                print("[DEBUG] ReplayWorker: CoUninitialize OK")
            except:
                pass

class OCRInitWorker(QThread):
    """Worker para inicializar OCR en segundo plano."""
    finished = pyqtSignal(object, object, object, object) # engine, matcher, actions, generator
    error = pyqtSignal(str)
    
    def __init__(self, engine_name, lang):
        super().__init__()
        self.engine_name = engine_name
        self.lang = lang
        
    def run(self):
        try:
            # Importar aquí para evitar circularidad o carga temprana
            from ocr.engine import OCREngine
            from ocr.matcher import OCRMatcher
            from ocr.actions import OCRActions
            from ocr.code_generator import OCRCodeGenerator
            
            engine = OCREngine(engine=self.engine_name, language=self.lang)
            matcher = OCRMatcher(threshold=80)
            actions = OCRActions(engine, matcher)
            generator = OCRCodeGenerator(engine=self.engine_name, language=self.lang)
            
            self.finished.emit(engine, matcher, actions, generator)
        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")

# ============================================================================
# PANELS (Pestañas)
# ============================================================================

class DashboardPanel(QWidget):
    """Panel con estadísticas."""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_stats()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Título
        title = QLabel("📊 Dashboard y Estadísticas")
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Estadísticas
        stats_layout = QHBoxLayout()
        
        self.stat_recordings = QLabel("📁 Grabaciones: -")
        self.stat_modules = QLabel("📦 Módulos: -")
        self.stat_recent = QLabel("⏱️ Última: -")
        
        for stat in [self.stat_recordings, self.stat_modules, self.stat_recent]:
            stat.setStyleSheet("""
                QLabel {
                    padding: 15px;
                    background-color: #ecfdf5; /* Verde muy suave */
                    color: #047857;            /* Verde oscuro texto */
                    border: 1px solid #a7f3d0;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 11pt;
                }
            """)
            stats_layout.addWidget(stat)
        
        layout.addLayout(stats_layout)
        
        # Tabla de grabaciones
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Archivo", "Acciones", "Duración (s)", "Fecha"])
        layout.addWidget(self.table)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def load_stats(self):
        """Carga estadísticas."""
        try:
            recordings_dir = Path("recordings")
            modules_dir = Path("modules")
            
            # Ensure directories exist
            if not recordings_dir.exists():
                recordings_dir.mkdir(exist_ok=True)
            if not modules_dir.exists():
                modules_dir.mkdir(exist_ok=True)
            
            # Contar
            recordings = list(recordings_dir.glob("*.json"))
            modules = [d for d in modules_dir.iterdir() if d.is_dir()]
            
            self.stat_recordings.setText(f"📁 Grabaciones: {len(recordings)}")
            self.stat_modules.setText(f"📦 Módulos: {len(modules)}")
            
            if recordings:
                latest = max(recordings, key=lambda p: p.stat().st_mtime)
                self.stat_recent.setText(f"⏱️ Última: {latest.name}")
            else:
                self.stat_recent.setText("⏱️ Última: -")
            
            # Tabla
            self.table.setRowCount(min(10, len(recordings)))
            for i, rec in enumerate(sorted(recordings, reverse=True)[:10]):
                try:
                    with open(rec) as f:
                        data = json.load(f)
                        self.table.setItem(i, 0, QTableWidgetItem(rec.name))
                        self.table.setItem(i, 1, QTableWidgetItem(str(data['metadata'].get('total_actions', 0))))
                        self.table.setItem(i, 2, QTableWidgetItem(f"{data['metadata'].get('duration_seconds', 0):.2f}"))
                        self.table.setItem(i, 3, QTableWidgetItem(data['metadata'].get('created_at', 'N/A')[:10]))
                except:
                    pass
        except Exception as e:
            print(f"Error cargando stats: {e}")

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

class ReplayPanel(QWidget):
    """Panel para reproducir."""
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.replay_worker = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Título
        title = QLabel("▶ Reproducir Grabación")
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Selector de archivo (Lista en lugar de FileDialog)
        list_label = QLabel("Selecciona una grabación:")
        layout.addWidget(list_label)
        
        from PyQt6.QtWidgets import QListWidget
        self.recordings_list = QListWidget()
        self.recordings_list.setMaximumHeight(150)
        layout.addWidget(self.recordings_list)
        
        btn_refresh = QPushButton("� Recargar Lista")
        btn_refresh.clicked.connect(self.load_recordings)
        layout.addWidget(btn_refresh)
        
        # Configuración
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("Configuración:"))
        self.config_combo = QComboBox()
        self.config_combo.addItem("config/ris_config.yaml")
        self.config_combo.addItem("config/default_config.yaml")
        config_layout.addWidget(self.config_combo)
        layout.addLayout(config_layout)
        
        # Opciones
        self.stop_on_error = QCheckBox("Detener al primer error")
        layout.addWidget(self.stop_on_error)
        
        # Progreso
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        # Botones
        btn_layout = QHBoxLayout()
        
        btn_play = QPushButton("🎬 Reproducir Grabación")
        btn_play.setMinimumHeight(45)
        btn_play.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; /* Blue 500 */
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2; /* Blue 700 */
            }
        """)
        btn_play.clicked.connect(self.start_replay)
        btn_layout.addWidget(btn_play)
        
        layout.addLayout(btn_layout)
        
        # Resultados
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setVisible(False)
        layout.addWidget(self.results_text)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Cargar inicial
        self.load_recordings()
    
    def load_recordings(self):
        """Carga lista de grabaciones desde directorio."""
        self.recordings_list.clear()
        recordings_dir = Path("recordings")
        if not recordings_dir.exists():
            recordings_dir.mkdir()
            
        files = sorted(list(recordings_dir.glob("*.json")), reverse=True, key=lambda p: p.stat().st_mtime)
        
        for p in files:
            # Mostrar nombre y fecha
            date_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            self.recordings_list.addItem(f"{p.name}  ({date_str})")
            
    def start_replay(self):
        current_item = self.recordings_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "⚠️ Advertencia", "Selecciona una grabación de la lista")
            return
            
        # Extraer solo el nombre del archivo (antes de los paréntesis)
        filename = current_item.text().split("  (")[0]
        file_path = Path("recordings") / filename
        
        if not file_path.exists():
            QMessageBox.error(self, "❌ Error", f"Archivo no encontrado: {file_path}")
            return
        
        try:
            config = load_config(self.config_combo.currentText())
            self.progress.setVisible(True)
            self.progress.setValue(0)
            
            # Usar worker thread
            self.replay_worker = ReplayWorker(str(file_path), config)
            self.replay_worker.finished.connect(self.on_replay_finished)
            self.replay_worker.error.connect(self.on_replay_error)
            self.replay_worker.start()
            
        except Exception as e:
            QMessageBox.critical(self, "❌ Error", f"Error: {e}")
    
    def on_replay_finished(self, results):
        self.progress.setValue(100)
        self.results_text.setVisible(True)
        self.results_text.setText(json.dumps(results, indent=2, ensure_ascii=False))
        
        status = "✅ ÉXITO" if results.get("status") == "SUCCESS" else "⚠️ ERROR / PARCIAL"
        msg = (
            f"Completadas: {results.get('completed', 0)}\n"
            f"Fallidas: {results.get('failed', 0)}\n"
            f"Status: {results.get('status', 'UNKNOWN')}"
        )
        
        QMessageBox.information(self, status, msg)
    
    def on_replay_error(self, error):
        self.progress.setVisible(False)
        QMessageBox.critical(self, "❌ Error", f"Error en reproducción: {error}")

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
        
        from PyQt6.QtWidgets import QListWidget
        self.recordings_list = QListWidget()
        self.recordings_list.setMaximumHeight(150)
        layout.addWidget(self.recordings_list)
        
        btn_refresh = QPushButton("� Recargar Lista")
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
        recordings_dir = Path("recordings")
        if not recordings_dir.exists():
            recordings_dir.mkdir()
            
        json_files = sorted(list(recordings_dir.glob("*.json")), reverse=True, key=lambda p: p.stat().st_mtime)
        
        # 2. Módulos OCR Generados (Python) - Opcional, si queremos re-generar o ver
        # Por ahora, la lógica de GeneratorPanel está diseñada solo para JSON -> Python
        # Pero el usuario pidió "ver las grabaciones de OCR".
        # Dado que OCR genera .py directamente, tal vez quiera verlos listados.
        
        modules_dir = Path("modules")
        py_files = []
        if modules_dir.exists():
            py_files = sorted(list(modules_dir.glob("*.py")), reverse=True, key=lambda p: p.stat().st_mtime)

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
            file_path = Path("modules") / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.results_text.setText(f.read())
                QMessageBox.information(self, "ℹ️ Info", f"Visualizando módulo existente:\n{filename}")
                return
        
        # Si es [REC] (JSON), procedemos a generar código
        file_path = Path("recordings") / filename
        
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
                # Module generator expects Path object or str? Check import.
                # Assuming str based on usage in older code.
                gen_module = ModuleGenerator(str(file_path), module_name, self.config)
                module_dir = gen_module.generate()
                results.append(f"📦 Módulo generado: {module_dir}")
            
            self.results_text.setText("\n".join(results))
            QMessageBox.information(self, "✅ Éxito", "\n".join(results))
        
        except Exception as e:
            self.results_text.setText(f"❌ Error: {e}")
            QMessageBox.critical(self, "❌ Error", f"Error: {e}")

# ============================================================================
# OCR PANEL
# ============================================================================

class OCRTab(QWidget):
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
                
                # Auto-save to recordings
                try:
                    base_dir = Path(__file__).resolve().parent
                    save_dir = base_dir / "recordings"
                    save_dir.mkdir(parents=True, exist_ok=True)
                    
                    filename = f"{module['name']}.py"
                    file_path = save_dir / filename
                    
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

        # Ensure modules directory exists (absolute path)
        try:
            # Resolving regular path
            base_dir = Path(__file__).resolve().parent
            # User requested OCR results to be saved in 'recordings'
            modules_dir = base_dir / "recordings"
            modules_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"[DEBUG] Directorio base detectado: {base_dir}")
            print(f"[DEBUG] Carpeta de módulos objetivo: {modules_dir}")
            self.results_text.append(f"\n[INFO] Directorio destino: {modules_dir}")
            
        except Exception as e:
            msg = f"Error creando directorio modules: {e}"
            print(f"[ERROR] {msg}")
            QMessageBox.critical(self, "Error", msg)
            return

        # Ask for filename first
        from PyQt6.QtWidgets import QInputDialog
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

# ============================================================================
# WEB RECORDER PANEL
# ============================================================================

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
        tabs.addTab(RecordPanel(self.config), "Grabar")
        tabs.addTab(ReplayPanel(self.config), "Reproducir")
        tabs.addTab(GeneratorPanel(self.config), "Generar")
        tabs.addTab(OCRTab(self), "OCR")
        tabs.addTab(WebRecordPanel(self.config), "Web Recorder")
        tabs.addTab(WorkflowPanel(self.config), "Workflows")
        
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
