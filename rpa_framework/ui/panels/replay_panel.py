
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QComboBox, QCheckBox, QProgressBar, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from datetime import datetime
import json
from utils.config_loader import load_config
from ui.workers import ReplayWorker
from utils.paths import get_all_recordings, RECORDINGS_DIR
from pathlib import Path
from PyQt6.QtWidgets import QListWidgetItem

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
        
        self.recordings_list = QListWidget()
        self.recordings_list.setMaximumHeight(150)
        layout.addWidget(self.recordings_list)
        
        btns_top = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Recargar Lista")
        btn_refresh.clicked.connect(self.load_recordings)
        btns_top.addWidget(btn_refresh)
        
        btn_delete = QPushButton("🗑️ Eliminar")
        btn_delete.setStyleSheet("QPushButton { color: #f44336; }")
        btn_delete.clicked.connect(self.delete_recording)
        btns_top.addWidget(btn_delete)
        
        layout.addLayout(btns_top)
        
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
        """Carga lista de grabaciones desde el directorio principal recursivamente."""
        self.recordings_list.clear()
        
        # Obtener todas las grabaciones (JSON y PY) recursivamente
        files = get_all_recordings(recording_type=None)  
        
        for p in files:
            # Calcular ruta relativa para mostrar en la lista
            try:
                display_path = p.relative_to(RECORDINGS_DIR)
            except ValueError:
                display_path = p.name # Fallback si está fuera de recordings
                
            date_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            
            item = QListWidgetItem(f"{display_path}  ({date_str})")
            item.setData(Qt.ItemDataRole.UserRole, str(p)) # Guardar ruta completa
            self.recordings_list.addItem(item)
            
    def start_replay(self):
        current_item = self.recordings_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "⚠️ Advertencia", "Selecciona una grabación de la lista")
            return
            
        # Recuperar ruta completa desde los datos del item
        file_path_str = current_item.data(Qt.ItemDataRole.UserRole)
        file_path = Path(file_path_str)
        
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

    def delete_recording(self):
        """Elimina la grabación seleccionada físicamente."""
        current_item = self.recordings_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "⚠️ Advertencia", "Selecciona una grabación para eliminar")
            return
            
        file_path_str = current_item.data(Qt.ItemDataRole.UserRole)
        file_path = Path(file_path_str)
        
        reply = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Estás seguro de que deseas eliminar permanentemente esta grabación?\n\nRuta: {file_path.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if file_path.exists():
                    file_path.unlink()
                    QMessageBox.information(self, "Eliminado", "La grabación ha sido eliminada.")
                    self.load_recordings()
                else:
                    QMessageBox.error(self, "Error", "El archivo ya no existe.")
                    self.load_recordings()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo eliminar el archivo:\n{e}")
