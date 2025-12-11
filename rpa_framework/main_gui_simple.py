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
    QProgressBar, QCheckBox, QGroupBox, QFormLayout, QTextEdit
)
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
            
            # Contar
            recordings = list(recordings_dir.glob("*.json"))
            modules = [d for d in modules_dir.iterdir() if d.is_dir()]
            
            self.stat_recordings.setText(f"📁 Grabaciones: {len(recordings)}")
            self.stat_modules.setText(f"📦 Módulos: {len(modules)}")
            
            if recordings:
                latest = max(recordings, key=lambda p: p.stat().st_mtime)
                self.stat_recent.setText(f"⏱️ Última: {latest.name}")
            
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
        """Carga lista de grabaciones."""
        self.recordings_list.clear()
        recordings_dir = Path("recordings")
        if not recordings_dir.exists():
            recordings_dir.mkdir()
            
        files = sorted(list(recordings_dir.glob("*.json")), reverse=True, key=lambda p: p.stat().st_mtime)
        
        for p in files:
            date_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            self.recordings_list.addItem(f"{p.name}  ({date_str})")
            
    def generate(self):
        current_item = self.recordings_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "⚠️ Advertencia", "Selecciona una grabación de la lista")
            return
            
        filename = current_item.text().split("  (")[0]
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
        tabs.addTab(DashboardPanel(), "📊 Dashboard")
        tabs.addTab(RecordPanel(self.config), "📹 Grabar")
        tabs.addTab(ReplayPanel(self.config), "▶ Reproducir")
        tabs.addTab(GeneratorPanel(self.config), "🔧 Generar")
        
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
