
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem
)
from PyQt6.QtGui import QFont
import json
from utils.paths import get_all_json_recordings, MODULES_DIR

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
            # Use centralized path management
            recordings = get_all_json_recordings()  # Gets all from ui/ and web/
            
            # Modules directory
            modules = []
            if MODULES_DIR.exists():
                modules = [d for d in MODULES_DIR.iterdir() if d.is_dir()]
            
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
                    with open(rec, encoding='utf-8') as f:
                        data = json.load(f)
                        self.table.setItem(i, 0, QTableWidgetItem(rec.name))
                        
                        # Detectar esquema (UI vs WEB)
                        if 'metadata' in data:
                            meta = data['metadata']
                            self.table.setItem(i, 1, QTableWidgetItem(str(meta.get('total_actions', 0))))
                            self.table.setItem(i, 2, QTableWidgetItem(f"{meta.get('duration_seconds', 0):.2f}"))
                            self.table.setItem(i, 3, QTableWidgetItem(meta.get('created_at', 'N/A')[:10]))
                        elif 'metrics' in data:
                            metrics = data['metrics']
                            self.table.setItem(i, 1, QTableWidgetItem(str(metrics.get('total_steps', 0))))
                            self.table.setItem(i, 2, QTableWidgetItem(f"{metrics.get('total_duration', 0):.2f}"))
                            self.table.setItem(i, 3, QTableWidgetItem(metrics.get('exported_at', 'N/A')[:10]))
                except Exception as e:
                    print(f"Error parsing {rec.name}: {e}")
        except Exception as e:
            print(f"Error cargando stats: {e}")
