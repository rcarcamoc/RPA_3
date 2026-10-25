"""
Estilos modernos y componente interactivo ActionTile para el panel de operaciones.
Extraído de main_gui_final.py.
"""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from ui.styles import STYLESHEET as GLOBAL_STYLESHEET

CUSTOM_STYLESHEET = """
/* Ventana Principal */
QMainWindow {
    background-color: #f8fafc;
}

QWidget#central_widget {
    background-color: #f8fafc;
}

/* Header */
#header_widget {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}

#header_title {
    color: #0f172a;
    font-weight: 800;
    font-size: 16pt;
}

/* Botón de perfil */
#profile_toggle_btn {
    background-color: #f1f5f9;
    color: #475569;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 10pt;
}
#profile_toggle_btn:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}
#profile_toggle_btn:pressed {
    background-color: #cbd5e1;
}

/* Encabezado del panel de operaciones */
QFrame#ops_header_box {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}
QFrame#ops_header_box QLabel {
    background: transparent;
    border: none;
}

/* Tarjetas Generales */
QFrame#ops_card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}
QFrame#ops_card QLabel {
    background: transparent;
    border: none;
}

/* KPI Tiles */
QFrame[cssClass="kpi_tile"] {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}
QFrame[cssClass="kpi_tile"]:hover {
    background-color: #f1f5f9;
    border-color: #cbd5e1;
}
QFrame[cssClass="kpi_tile"] QLabel {
    background: transparent;
    border: none;
}

/* Botones de Presets / Chips */
QPushButton[cssClass="preset_chip"] {
    background-color: #f1f5f9;
    color: #475569;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 9pt;
    font-weight: 600;
    min-height: 24px;
}
QPushButton[cssClass="preset_chip"]:hover {
    background-color: #e2e8f0;
    color: #0f172a;
    border-color: #94a3b8;
}
QPushButton[cssClass="preset_chip"]:pressed {
    background-color: #dbeafe;
    color: #1d4ed8;
    border-color: #3b82f6;
}

/* Botón Lanzador de Loop */
QPushButton#btn_action_loop {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6366f1);
    color: #ffffff;
    border: 1px solid #6d28d9;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: bold;
    font-size: 10.5pt;
}
QPushButton#btn_action_loop:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6d28d9, stop:1 #4f46e5);
    border-color: #5b21b6;
}
QPushButton#btn_action_loop:pressed {
    background-color: #4f46e5;
}
QPushButton#btn_action_loop:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border: 1px solid #e2e8f0;
}

/* Botón Stop */
QPushButton#btn_action_stop {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #dc2626);
    color: #ffffff;
    border: 1px solid #dc2626;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: bold;
    font-size: 10pt;
}
QPushButton#btn_action_stop:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #b91c1c);
    border-color: #b91c1c;
}
QPushButton#btn_action_stop:pressed {
    background-color: #b91c1c;
}
QPushButton#btn_action_stop:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border: 1px solid #e2e8f0;
}

/* Form inputs */
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    color: #0f172a;
    font-size: 10pt;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
    background-color: #ffffff;
}

/* Progress bar */
QProgressBar#ops_progress {
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    background-color: #f1f5f9;
    height: 8px;
}
QProgressBar#ops_progress::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981);
    border-radius: 3px;
}

/* Terminal Card */
QFrame#ops_terminal_card {
    background-color: #090d16;
    border: 1px solid #1e293b;
    border-radius: 12px;
}

QWidget#terminal_header {
    background-color: #111827;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid #1f2937;
}
QWidget#terminal_header QLabel {
    background: transparent;
    border: none;
}

QTextEdit#ops_terminal {
    background-color: #090d16;
    color: #e2e8f0;
    font-family: 'Consolas', 'Cascadia Code', 'Courier New', monospace;
    font-size: 9pt;
    border: none;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
    padding: 10px;
}
"""

FINAL_STYLESHEET = GLOBAL_STYLESHEET + CUSTOM_STYLESHEET


class ActionTile(QFrame):
    """Tarjeta de acción interactiva moderna con icono destacado, títulos claros y micro-interacciones."""
    clicked = pyqtSignal()
    
    def __init__(self, title, subtitle, icon="🚀", theme="emerald", parent=None):
        super().__init__(parent)
        self._enabled = True
        self.theme = theme
        self.setObjectName(f"action_tile_{theme}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(62)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 14, 10)
        layout.setSpacing(12)
        
        # Icon Container (Badge)
        self.icon_badge = QLabel(icon)
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_badge.setFixedSize(38, 38)
        self.icon_badge.setObjectName("action_icon_badge")
        layout.addWidget(self.icon_badge)
        
        # Text VBox
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)
        text_vbox.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 10.5pt; font-weight: 700; color: #0f172a; background: transparent; border: none;")
        
        self.lbl_sub = QLabel(subtitle)
        self.lbl_sub.setStyleSheet("font-size: 8.5pt; color: #64748b; background: transparent; border: none;")
        
        text_vbox.addWidget(self.lbl_title)
        text_vbox.addWidget(self.lbl_sub)
        layout.addLayout(text_vbox, stretch=1)
        
        # Right Arrow Indicator
        self.lbl_arrow = QLabel("➔")
        self.lbl_arrow.setObjectName("action_arrow")
        layout.addWidget(self.lbl_arrow)
        
        self.update_style()
        
    def update_style(self):
        themes = {
            "emerald": {
                "border": "#10b981",
                "badge_bg": "#ecfdf5",
                "badge_color": "#059669",
                "hover_bg": "#f0fdf4",
                "arrow_color": "#10b981"
            },
            "blue": {
                "border": "#3b82f6",
                "badge_bg": "#eff6ff",
                "badge_color": "#2563eb",
                "hover_bg": "#f8faff",
                "arrow_color": "#3b82f6"
            },
            "amber": {
                "border": "#f59e0b",
                "badge_bg": "#fffbeb",
                "badge_color": "#d97706",
                "hover_bg": "#fffdf5",
                "arrow_color": "#f59e0b"
            }
        }
        t = themes.get(self.theme, themes["emerald"])
        
        if self._enabled:
            self.setStyleSheet(f"""
                QFrame#action_tile_{self.theme} {{
                    background-color: #ffffff;
                    border: 1.5px solid #e2e8f0;
                    border-left: 5px solid {t['border']};
                    border-radius: 10px;
                }}
                QFrame#action_tile_{self.theme}:hover {{
                    background-color: {t['hover_bg']};
                    border-color: {t['border']};
                }}
                QLabel#action_icon_badge {{
                    background-color: {t['badge_bg']};
                    color: {t['badge_color']};
                    border-radius: 8px;
                    font-size: 15pt;
                    border: none;
                }}
                QLabel#action_arrow {{
                    color: {t['arrow_color']};
                    font-size: 11pt;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#action_tile_{self.theme} {{
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-left: 5px solid #cbd5e1;
                    border-radius: 10px;
                }}
                QLabel#action_icon_badge {{
                    background-color: #f1f5f9;
                    color: #94a3b8;
                    border-radius: 8px;
                    font-size: 15pt;
                    border: none;
                }}
                QLabel#action_arrow {{
                    color: #cbd5e1;
                    font-size: 11pt;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)
            
    def setEnabled(self, enabled: bool):
        self._enabled = enabled
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ForbiddenCursor)
        self.lbl_title.setStyleSheet(f"font-size: 10.5pt; font-weight: 700; color: {'#0f172a' if enabled else '#94a3b8'}; background: transparent; border: none;")
        self.lbl_sub.setStyleSheet(f"font-size: 8.5pt; color: {'#64748b' if enabled else '#cbd5e1'}; background: transparent; border: none;")
        self.update_style()
        super().setEnabled(enabled)
        
    def mousePressEvent(self, event):
        if self._enabled and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
