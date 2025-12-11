#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RPA Framework v2 - GUI Application (Modern UI)

Una interfaz gráfica moderna con:
- Menú visual interactivo
- Dashboard con gráficos
- Botones intuitivos
- Monitoreo en tiempo real
- Reportes visuales

Requisitos adicionales:
    pip install tkinter pyqt6 matplotlib seaborn

Uso:
    python main_gui.py
"""

import sys
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QLineEdit, QComboBox, QTabWidget,
        QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog,
        QProgressBar, QSpinBox, QCheckBox, QGroupBox, QFormLayout,
        QTextEdit, QScrollArea, QFrame, QSplitter
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
    from PyQt6.QtGui import QFont, QIcon, QColor, QPixmap
    from PyQt6.QtChart import QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
    from PyQt6.QtCore import QDate
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import seaborn as sns
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("⚠️ PyQt6 no disponible. Instalando dependencias...")
    print("pip install PyQt6 pyqt6-charts matplotlib seaborn")

# Importar módulos RPA
from core.recorder import RecorderGUI
from core.player import RecordingPlayer
from generators.script_generator import QuickScriptGenerator
from generators.module_generator import ModuleGenerator
from utils.config_loader import load_config
from utils.logging_setup import setup_logging

# ============================================================================
# WORKERS (Threads para no bloquear UI)
# ============================================================================

class RecordingWorker(QObject):
    """Worker para grabación en thread."""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
    
    def run(self):
        try:
            gui = RecorderGUI(config=self.config)
            gui.run()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class ReplayWorker(QObject):
    """Worker para reproducción en thread."""
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, recording_path: str, config: dict):
        super().__init__()
        self.recording_path = recording_path
        self.config = config
    
    def run(self):
        try:
            player = RecordingPlayer(self.recording_path, self.config)
            results = player.run()
            
            # Guardar reporte
            with open(f"replay_report_{results['session_id']}.json", "w") as f:
                json.dump(results, f, indent=2)
            
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

# ============================================================================
# PANELS (Componentes reutilizables)
# ============================================================================

class RecordingPanel(QWidget):
    """Panel para grabar acciones."""
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Descripción
        desc = QLabel("📹 Grabar nuevas acciones")
        desc_font = QFont("Arial", 12, QFont.Weight.Bold)
        desc.setFont(desc_font)
        layout.addWidget(desc)
        
        # Instrucciones
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setText("""
        Pasos para grabar:
        
        1. Presiona "Iniciar Grabación"
        2. Se abrirá una ventana pequeña con botones
        3. Presiona "REC" en esa ventana
        4. Interactúa con la aplicación (clicks, typing, etc.)
        5. Presiona "STOP"
        6. Ingresa nombre del módulo
        7. Tu grabación se guardará automáticamente
        
        Las grabaciones se guardan en: recordings/
        """)
        instructions.setStyleSheet("background-color: #f0f0f0; padding: 10px;")
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
        
        self.setLayout(layout)
    
    def start_recording(self):
        try:
            gui = RecorderGUI(config=self.config)
            gui.run()
            QMessageBox.information(self, "Éxito", "Grabación completada")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error en grabación: {e}")

class ReplayPanel(QWidget):
    """Panel para reproducir grabaciones."""
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Descripción
        desc = QLabel("▶ Reproducir Grabación")
        desc_font = QFont("Arial", 12, QFont.Weight.Bold)
        desc.setFont(desc_font)
        layout.addWidget(desc)
        
        # Seleccionar archivo
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Selecciona un archivo JSON...")
        file_layout.addWidget(self.file_input)
        
        btn_browse = QPushButton("📁 Examinar")
        btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)
        
        # Opciones
        options_group = QGroupBox("Opciones")
        options_layout = QFormLayout()
        
        self.config_combo = QComboBox()
        self.config_combo.addItem("config/ris_config.yaml")
        self.config_combo.addItem("config/default_config.yaml")
        options_layout.addRow("Configuración:", self.config_combo)
        
        self.stop_on_error = QCheckBox("Detener al primer error")
        options_layout.addRow("", self.stop_on_error)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Progreso
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        # Botones
        btn_layout = QHBoxLayout()
        
        btn_play = QPushButton("▶ Reproducir")
        btn_play.setMinimumHeight(50)
        btn_play.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        btn_play.clicked.connect(self.start_replay)
        btn_layout.addWidget(btn_play)
        
        btn_preview = QPushButton("👁 Vista Previa")
        btn_preview.clicked.connect(self.preview_recording)
        btn_layout.addWidget(btn_preview)
        
        layout.addLayout(btn_layout)
        
        # Resultados
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setVisible(False)
        layout.addWidget(self.results_text)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar grabación",
            "recordings/",
            "JSON Files (*.json)"
        )
        if file_path:
            self.file_input.setText(file_path)
    
    def start_replay(self):
        file_path = self.file_input.text()
        if not file_path:
            QMessageBox.warning(self, "Advertencia", "Selecciona un archivo")
            return
        
        if not Path(file_path).exists():
            QMessageBox.error(self, "Error", f"Archivo no encontrado: {file_path}")
            return
        
        try:
            config = load_config(self.config_combo.currentText())
            player = RecordingPlayer(file_path, config)
            
            self.progress.setVisible(True)
            self.progress.setValue(50)
            
            results = player.run()
            
            self.progress.setValue(100)
            self.results_text.setVisible(True)
            self.results_text.setText(json.dumps(results, indent=2, ensure_ascii=False))
            
            status = "✅ ÉXITO" if results["status"] == "SUCCESS" else "⚠️ PARCIAL"
            QMessageBox.information(
                self,
                status,
                f"Completadas: {results['completed']}\n"
                f"Fallidas: {results['failed']}\n"
                f"Status: {results['status']}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error en reproducción: {e}")
    
    def preview_recording(self):
        file_path = self.file_input.text()
        if not file_path or not Path(file_path).exists():
            QMessageBox.warning(self, "Advertencia", "Selecciona un archivo válido")
            return
        
        try:
            with open(file_path) as f:
                data = json.load(f)
            
            preview = f"""
GRABACIÓN: {Path(file_path).name}

Metadata:
  - Creada: {data['metadata'].get('created_at', 'N/A')}
  - Acciones: {data['metadata'].get('total_actions', 0)}
  - Duración: {data['metadata'].get('duration_seconds', 0):.2f}s
  
Primeras 5 acciones:
"""
            for i, action in enumerate(data['actions'][:5]):
                preview += f"\n  {i+1}. {action['type']}"
                if action.get('position'):
                    preview += f" @ ({action['position']['x']}, {action['position']['y']})"
            
            self.results_text.setVisible(True)
            self.results_text.setText(preview)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al vista previa: {e}")

class GeneratorPanel(QWidget):
    """Panel para generar scripts y módulos."""
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Descripción
        desc = QLabel("🔧 Generar Scripts y Módulos")
        desc_font = QFont("Arial", 12, QFont.Weight.Bold)
        desc.setFont(desc_font)
        layout.addWidget(desc)
        
        # Seleccionar grabación
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Selecciona grabación JSON...")
        file_layout.addWidget(self.file_input)
        
        btn_browse = QPushButton("📁 Examinar")
        btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)
        
        # Opciones de generación
        options_group = QGroupBox("Tipo de generación")
        options_layout = QVBoxLayout()
        
        self.gen_script_check = QCheckBox("Generar Script Rápido (*_script.py)")
        self.gen_script_check.setChecked(True)
        options_layout.addWidget(self.gen_script_check)
        
        self.gen_module_check = QCheckBox("Generar Módulo Independiente")
        self.gen_module_check.setChecked(True)
        options_layout.addWidget(self.gen_module_check)
        
        # Nombre del módulo
        module_layout = QHBoxLayout()
        module_layout.addWidget(QLabel("Nombre del módulo:"))
        self.module_name = QLineEdit()
        self.module_name.setPlaceholderText("mi_automacion")
        module_layout.addWidget(self.module_name)
        options_layout.addLayout(module_layout)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Botones
        btn_generate = QPushButton("⚙ Generar")
        btn_generate.setMinimumHeight(50)
        btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e68900;
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
    
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar grabación",
            "recordings/",
            "JSON Files (*.json)"
        )
        if file_path:
            self.file_input.setText(file_path)
    
    def generate(self):
        file_path = self.file_input.text()
        if not file_path or not Path(file_path).exists():
            QMessageBox.warning(self, "Advertencia", "Selecciona un archivo válido")
            return
        
        results = []
        
        try:
            # Generar script
            if self.gen_script_check.isChecked():
                gen_script = QuickScriptGenerator(file_path)
                script_path = gen_script.generate()
                results.append(f"✅ Script generado: {script_path}")
            
            # Generar módulo
            if self.gen_module_check.isChecked():
                module_name = self.module_name.text() or "mi_automacion"
                gen_module = ModuleGenerator(file_path, module_name, self.config)
                module_dir = gen_module.generate()
                results.append(f"✅ Módulo generado: {module_dir}")
            
            self.results_text.setText("\n".join(results))
            QMessageBox.information(self, "Éxito", "\n".join(results))
        
        except Exception as e:
            self.results_text.setText(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"Error: {e}")

class DashboardPanel(QWidget):
    """Panel con estadísticas y gráficos."""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_stats()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Descripción
        desc = QLabel("📊 Dashboard y Estadísticas")
        desc_font = QFont("Arial", 12, QFont.Weight.Bold)
        desc.setFont(desc_font)
        layout.addWidget(desc)
        
        # Estadísticas
        stats_layout = QHBoxLayout()
        
        self.stat_recordings = QLabel("Grabaciones: -")
        self.stat_modules = QLabel("Módulos: -")
        self.stat_recent = QLabel("Última acción: -")
        
        for stat in [self.stat_recordings, self.stat_modules, self.stat_recent]:
            stat_frame = QFrame()
            stat_frame.setStyleSheet("background-color: #e8f5e9; padding: 10px; border-radius: 5px;")
            stat_layout_inner = QVBoxLayout()
            stat_layout_inner.addWidget(stat)
            stat_frame.setLayout(stat_layout_inner)
            stats_layout.addWidget(stat_frame)
        
        layout.addLayout(stats_layout)
        
        # Gráfico de acciones
        if PYQT_AVAILABLE:
            self.figure = Figure(figsize=(10, 4), dpi=100)
            self.canvas = FigureCanvas(self.figure)
            layout.addWidget(self.canvas)
        
        # Tabla de grabaciones recientes
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Archivo", "Acciones", "Duración (s)", "Fecha"])
        layout.addWidget(self.table)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def load_stats(self):
        """Carga estadísticas desde archivos."""
        recordings_dir = Path("recordings")
        modules_dir = Path("modules")
        
        # Contar grabaciones
        recordings = list(recordings_dir.glob("*.json"))
        self.stat_recordings.setText(f"Grabaciones: {len(recordings)}")
        
        # Contar módulos
        modules = [d for d in modules_dir.iterdir() if d.is_dir()]
        self.stat_modules.setText(f"Módulos: {len(modules)}")
        
        # Última grabación
        if recordings:
            latest = max(recordings, key=lambda p: p.stat().st_mtime)
            self.stat_recent.setText(f"Última: {latest.name}")
        
        # Llenar tabla
        self.table.setRowCount(len(recordings))
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
        
        # Dibujar gráfico
        if PYQT_AVAILABLE and recordings:
            self.draw_stats_chart(recordings)
    
    def draw_stats_chart(self, recordings):
        """Dibuja gráfico de estadísticas."""
        try:
            action_counts = []
            names = []
            
            for rec in sorted(recordings)[-10:]:
                try:
                    with open(rec) as f:
                        data = json.load(f)
                        action_counts.append(data['metadata'].get('total_actions', 0))
                        names.append(rec.stem[:15])
                except:
                    pass
            
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            
            colors = sns.color_palette("husl", len(action_counts))
            ax.bar(range(len(action_counts)), action_counts, color=colors)
            ax.set_xlabel("Grabación")
            ax.set_ylabel("Cantidad de Acciones")
            ax.set_title("Últimas 10 Grabaciones")
            ax.set_xticks(range(len(action_counts)))
            ax.set_xticklabels(names, rotation=45, ha='right')
            
            self.figure.tight_layout()
            self.canvas.draw()
        except Exception as e:
            print(f"Error dibujando gráfico: {e}")

# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    """Ventana principal de la aplicación."""
    
    def __init__(self):
        super().__init__()
        self.config = load_config("config/ris_config.yaml")
        setup_logging()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("RPA Framework v2 - GUI")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("🤖 RPA Framework v2 - Panel de Control")
        header_font = QFont("Arial", 16, QFont.Weight.Bold)
        header.setFont(header_font)
        header.setStyleSheet("color: #1976D2; margin: 10px;")
        layout.addWidget(header)
        
        # Tabs
        tabs = QTabWidget()
        
        tabs.addTab(DashboardPanel(), "📊 Dashboard")
        tabs.addTab(RecordingPanel(self.config), "📹 Grabar")
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
        
        # Aplicar estilo
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 8px 20px;
                margin-right: 2px;
                border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected {
                background-color: #fff;
            }
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
        """)

# ============================================================================
# MAIN
# ============================================================================

def main():
    if not PYQT_AVAILABLE:
        print("Error: PyQt6 no está instalado")
        print("Instala: pip install PyQt6 pyqt6-charts matplotlib seaborn")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
