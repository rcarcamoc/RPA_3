from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QComboBox, QGridLayout, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QFont
from datetime import datetime, timedelta
import sys

# Import matplotlib for charts
try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available. Install with: pip install matplotlib")

# Import MySQL connector
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False
    print("Warning: mysql-connector-python not available. Install with: pip install mysql-connector-python")


class StatCard(QFrame):
    """Card widget for displaying statistics"""
    
    def __init__(self, title, value, icon="📊", color="#1976D2"):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # Remove padding/min-height from CSS to let Layout handle geometry
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 2px solid {color};
                border-radius: 8px;
            }}
        """)
        
        self.setMinimumHeight(100)  # Set ref height via logic, not CSS
        
        layout = QVBoxLayout()
        layout.setSpacing(0)  # Keep title and value close
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 1. Stretch at top (pushes content down)
        layout.addStretch(1)
        
        # Icon and title
        header = QLabel(f"{icon} {title}")
        header.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 10pt; border: none;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Value
        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(f"color: {color}; font-size: 20pt; font-weight: bold; border: none;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)
        
        # 2. Stretch at bottom (pushes content up)
        # Result: Content stays in the middle
        layout.addStretch(1)
        
        self.setLayout(layout)
    
    def update_value(self, value):
        """Update the card value"""
        self.value_label.setText(str(value))


class ChartWidget(QWidget):
    """Widget for displaying matplotlib charts"""
    
    def __init__(self, title):
        super().__init__()
        self.title = title
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 10, 5, 10)
        
        # Title
        title_label = QLabel(self.title)
        title_label.setStyleSheet("font-weight: bold; font-size: 11pt; color: #333; margin-bottom: 5px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        if HAS_MATPLOTLIB:
            # Create matplotlib figure with MORE vertical space
            self.figure = Figure(figsize=(6, 5), facecolor='white')
            # Adjust subplot parameters to give more room for labels at the bottom
            self.figure.subplots_adjust(bottom=0.25, top=0.90, left=0.10, right=0.95)
            
            self.canvas = FigureCanvas(self.figure)
            
            # Make canvas responsive and set a generous minimum height
            from PyQt6.QtWidgets import QSizePolicy
            self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.canvas.setMinimumHeight(400) # Force more vertical space
            
            layout.addWidget(self.canvas)
        else:
            error_label = QLabel("⚠️ Matplotlib no disponible")
            error_label.setStyleSheet("color: #999; font-style: italic;")
            layout.addWidget(error_label)
        
        self.setLayout(layout)
    
    def plot_bar_chart(self, data_dict, xlabel, ylabel, color='#1976D2'):
        """Plot a bar chart from a dictionary"""
        if not HAS_MATPLOTLIB or not data_dict:
            return
        
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        labels = list(data_dict.keys())
        values = list(data_dict.values())
        
        # Less aggressive truncation to allow reading labels
        labels = [label[:40] + '...' if len(str(label)) > 40 else str(label) for label in labels]
        
        bars = ax.bar(labels, values, color=color, alpha=0.7, edgecolor='black', linewidth=1.2)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_ylabel(ylabel, fontsize=10, fontweight='bold')
        
        # Improve x-axis labels readability
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
        
        ax.tick_params(axis='y', labelsize=9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Use tight_layout but with padding to respect our manual adjustments if possible, 
        # or just rely on subplots_adjust set in init_ui if tight_layout interferes.
        # Ideally tight_layout with padding works best:
        self.figure.tight_layout() 
        
        self.canvas.draw()
    
    def plot_pie_chart(self, data_dict, title_suffix=''):
        """Plot a pie chart from a dictionary"""
        if not HAS_MATPLOTLIB or not data_dict:
            return
        
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        labels = list(data_dict.keys())
        values = list(data_dict.values())
        
        # Truncate long labels
        labels = [label[:25] + '...' if len(str(label)) > 25 else str(label) for label in labels]
        
        colors = ['#1976D2', '#4CAF50', '#FFC107', '#F44336', '#9C27B0', '#00BCD4', '#FF9800', '#795548']
        
        wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%',
                                           colors=colors[:len(labels)], startangle=90, pctdistance=0.85)
        
        # Donut style for modern look (optional, but cleaner)
        centre_circle = matplotlib.patches.Circle((0,0),0.70,fc='white')
        ax.add_artist(centre_circle)
        
        for autotext in autotexts:
            autotext.set_color('black')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(8)
        
        for text in texts:
            text.set_fontsize(9)
        
        ax.axis('equal')
        self.figure.tight_layout()
        self.canvas.draw()


    def plot_line_chart(self, data_dict, xlabel, ylabel, color='#1976D2'):
        """Plot a line chart for temporal data"""
        if not HAS_MATPLOTLIB or not data_dict:
            return
        
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # Sort keys if they are strings representing dates/hours
        sorted_keys = sorted(data_dict.keys())
        values = [data_dict[k] for k in sorted_keys]
        
        ax.plot(sorted_keys, values, marker='o', linestyle='-', color=color, linewidth=2, markersize=6)
        ax.fill_between(sorted_keys, values, color=color, alpha=0.1)
        
        ax.set_ylabel(ylabel, fontsize=10, fontweight='bold')
        
        # Improve x-axis labels
        ax.set_xticks(range(len(sorted_keys)))
        ax.set_xticklabels(sorted_keys, rotation=45, ha='right', fontsize=9)
        
        ax.tick_params(axis='y', labelsize=9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        self.figure.tight_layout()
        self.canvas.draw()


class DashboardPanel(QWidget):
    """Panel with execution statistics from registro_acciones table"""
    
    def __init__(self):
        super().__init__()
        
        # Database config
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }
        
        self.init_ui()
        
        # Auto-refresh every 5 minutes (300,000 ms)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_data)
        self.refresh_timer.start(300000)  # 5 minutes
        
        # Initial load
        self.load_data()
    
    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Title
        title = QLabel("📊 Dashboard de Ejecuciones RPA")
        title_font = QFont("Arial", 16, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #1976D2; margin: 10px;")
        main_layout.addWidget(title)
        
        # Filters section
        filters_layout = QHBoxLayout()
        
        # Date from
        filters_layout.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-7))  # Last 7 days
        self.date_from.setDisplayFormat("dd/MM/yyyy")
        self.date_from.dateChanged.connect(self.load_data) # Auto-update
        filters_layout.addWidget(self.date_from)
        
        # Date to
        filters_layout.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("dd/MM/yyyy")
        self.date_to.dateChanged.connect(self.load_data) # Auto-update
        filters_layout.addWidget(self.date_to)
        
        # Granularity
        filters_layout.addWidget(QLabel("Granularidad:"))
        self.granularity = QComboBox()
        self.granularity.addItems(["Por Día", "Por Hora"])
        self.granularity.currentTextChanged.connect(self.load_data) # Auto-update
        filters_layout.addWidget(self.granularity)
        
        # Refresh button (Partial redundancy but useful for manual refresh)
        refresh_btn = QPushButton("🔄 Actualizar Ahora")
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        """)
        filters_layout.addWidget(refresh_btn)
        
        filters_layout.addStretch()
        main_layout.addLayout(filters_layout)

        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        
        # Summary cards - Single row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)
        
        self.card_total = StatCard("Total Ejecuciones", "0", "📁", "#1976D2")
        self.card_success = StatCard("Completadas", "0", "✅", "#4CAF50")
        self.card_error = StatCard("Con Error", "0", "❌", "#F44336")
        self.card_process = StatCard("En Proceso", "0", "⏳", "#FFC107")
        self.card_avg_time = StatCard("Tiempo Promedio", "0s", "⏱️", "#9C27B0")
        
        cards_layout.addWidget(self.card_total)
        cards_layout.addWidget(self.card_success)
        cards_layout.addWidget(self.card_error)
        cards_layout.addWidget(self.card_process)
        cards_layout.addWidget(self.card_avg_time)
        
        scroll_layout.addLayout(cards_layout)
        
        # Charts section
        charts_layout = QGridLayout()
        
        self.chart_timeline = ChartWidget("📈 Evolución Temporal (Ejecuciones)")
        self.chart_estado = ChartWidget("📊 Distribución por Estado")
        self.chart_doctor = ChartWidget("👨‍⚕️ Top 10 Doctores Detectados")
        self.chart_diagnostico = ChartWidget("🩺 Top 10 Diagnósticos")
        self.chart_patologia = ChartWidget("⚠️ Top 10 Patologías Críticas")
        
        # Full width for timeline
        charts_layout.addWidget(self.chart_timeline, 0, 0, 1, 2)
        
        # Grid for others
        charts_layout.addWidget(self.chart_estado, 1, 0)
        charts_layout.addWidget(self.chart_doctor, 1, 1)
        charts_layout.addWidget(self.chart_diagnostico, 2, 0)
        charts_layout.addWidget(self.chart_patologia, 2, 1)
        
        scroll_layout.addLayout(charts_layout)
        
        scroll_content.setLayout(scroll_layout)
        scroll.setWidget(scroll_content)
        
        main_layout.addWidget(scroll)
        
        self.setLayout(main_layout)
    
    def get_db_connection(self):
        """Get database connection"""
        if not HAS_MYSQL:
            return None
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            print(f"Error connecting to database: {e}")
            return None
    
    def load_data(self):
        """Load data from database and update UI"""
        conn = self.get_db_connection()
        if not conn:
            print("⚠️ No se pudo conectar a la base de datos")
            return
        
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get date range
            date_from = self.date_from.date().toPyDate()
            date_to = self.date_to.date().toPyDate()
            
            # Base query with date filter
            base_query = """
                SELECT 
                    id,
                    inicio,
                    doctor_detectado,
                    User,
                    estado,
                    ultimo_nodo,
                    `update`,
                    numero_documento,
                    diagnostico,
                    patologia_critica,
                    fecha_agendada,
                    examen,
                    patologia_critica_detectada,
                    TIMESTAMPDIFF(SECOND, inicio, `update`) as duracion_segundos
                FROM registro_acciones
                WHERE DATE(inicio) BETWEEN %s AND %s
            """
            
            cursor.execute(base_query, (date_from, date_to))
            records = cursor.fetchall()
            
            if not records:
                print("No hay datos para el rango de fechas seleccionado")
                self.update_empty_state()
                return
            
            # Calculate statistics
            total = len(records)
            
            # Count by state
            estados = {}
            for record in records:
                estado = record['estado'] or 'Sin Estado'
                estados[estado] = estados.get(estado, 0) + 1
            
            success = estados.get('Completado', 0) + estados.get('completado', 0)
            error = estados.get('error', 0) + estados.get('Error', 0)
            process = estados.get('En Proceso', 0)
            
            # Calculate average execution time (only for completed records)
            completed_records = [r for r in records if r['duracion_segundos'] and r['duracion_segundos'] > 0]
            if completed_records:
                avg_time = sum(r['duracion_segundos'] for r in completed_records) / len(completed_records)
                avg_time_str = f"{int(avg_time)}s"
                if avg_time > 60:
                    avg_time_str = f"{int(avg_time/60)}m {int(avg_time%60)}s"
            else:
                avg_time_str = "N/A"
            
            # Update cards
            self.card_total.update_value(total)
            self.card_success.update_value(success)
            self.card_error.update_value(error)
            self.card_process.update_value(process)
            self.card_avg_time.update_value(avg_time_str)
            
            # Count by doctor
            doctores = {}
            for record in records:
                doctor = record['doctor_detectado'] or 'Sin Doctor'
                if doctor and doctor.strip():
                    doctores[doctor] = doctores.get(doctor, 0) + 1
            
            # Count by diagnostico
            diagnosticos = {}
            for record in records:
                diag = record['diagnostico'] or 'Sin Diagnóstico'
                if diag and diag.strip() and diag != 'Sin Diagnóstico':
                    # Truncate long diagnostics
                    diag_short = diag[:50] + '...' if len(diag) > 50 else diag
                    diagnosticos[diag_short] = diagnosticos.get(diag_short, 0) + 1
            
            # Count by patologia critica
            patologias = {}
            for record in records:
                pat = record['patologia_critica_detectada'] or record['patologia_critica'] or 'Sin Patología'
                if pat and pat.strip() and pat != 'Sin Patología':
                    patologias[pat] = patologias.get(pat, 0) + 1
            
            # Sort and get top 10
            doctores_top = dict(sorted(doctores.items(), key=lambda x: x[1], reverse=True)[:10])
            diagnosticos_top = dict(sorted(diagnosticos.items(), key=lambda x: x[1], reverse=True)[:10])
            patologias_top = dict(sorted(patologias.items(), key=lambda x: x[1], reverse=True)[:10])
            
            # Count by Time (Granularity)
            temporal_data = {}
            gran = self.granularity.currentText()
            
            for record in records:
                if record['inicio']:
                    dt = record['inicio']
                    if gran == "Por Día":
                        key = dt.strftime("%Y-%m-%d")
                    else:  # Por Hora
                        key = dt.strftime("%Y-%m-%d %H:00")
                    temporal_data[key] = temporal_data.get(key, 0) + 1
            
            # Fill missing periods if needed (optional, just sort for now)
            
            # Update charts
            self.chart_timeline.plot_line_chart(temporal_data, "Tiempo", "Ejecuciones", "#1976D2")
            self.chart_estado.plot_pie_chart(estados)
            self.chart_doctor.plot_bar_chart(doctores_top, "Doctor", "Cantidad", "#1976D2")
            self.chart_diagnostico.plot_bar_chart(diagnosticos_top, "Diagnóstico", "Cantidad", "#4CAF50")
            self.chart_patologia.plot_bar_chart(patologias_top, "Patología Crítica", "Cantidad", "#F44336")
            
            print(f"✅ Dashboard actualizado: {total} registros cargados")
            
        except Exception as e:
            print(f"Error loading data: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def update_empty_state(self):
        """Update UI when no data is available"""
        self.card_total.update_value("0")
        self.card_success.update_value("0")
        self.card_error.update_value("0")
        self.card_process.update_value("0")
        self.card_avg_time.update_value("N/A")
