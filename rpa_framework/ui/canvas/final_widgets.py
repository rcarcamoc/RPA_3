"""
Widgets auxiliares y hojas de estilo para WorkflowPanelFinal (LogWindowFinal, ZoomControlsFinal, WORKFLOW_STYLESHEET).
Extraído de ui/workflow_panel_final.py.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit, QDialog
from PyQt6.QtCore import Qt

WORKFLOW_STYLESHEET = """
    /* Ribbon/Toolbar */
    QToolBar {
        background-color: #ffffff;
        border-bottom: 1px solid #e2e8f0;
        spacing: 12px;
        padding: 6px;
    }
    
    QToolBar QFrame {
        background-color: #cbd5e1;
        width: 1px;
        max-width: 1px;
        margin: 2px 4px;
    }
    
    /* Panel lateral de Workflows */
    #WorkflowList {
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        background-color: #ffffff;
        padding: 5px;
    }
    
    #WorkflowList::item {
        padding: 8px 12px;
        border-radius: 4px;
        color: #334155;
    }
    
    #WorkflowList::item:hover {
        background-color: #f1f5f9;
        color: #0f172a;
    }
    
    #WorkflowList::item:selected {
        background-color: #e2e8f0;
        color: #0f172a;
        font-weight: bold;
    }
    
    /* Log Panel */
    #LogTerminal {
        background-color: #0f172a;
        color: #e2e8f0;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 11px;
        border: 1px solid #1e293b;
        border-radius: 6px;
        padding: 5px;
    }
    
    /* Botones de acción del Log */
    QPushButton#log_action_btn {
        background-color: transparent;
        border: none;
        padding: 4px;
        border-radius: 4px;
    }
    QPushButton#log_action_btn:hover {
        background-color: #f1f5f9;
    }
    
    /* Barra de Progreso */
    QProgressBar {
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        text-align: center;
        background-color: #f1f5f9;
        color: #334155;
        font-weight: bold;
    }
    QProgressBar::chunk {
        background-color: #10b981;
        border-radius: 3px;
    }
"""


class LogWindowFinal(QDialog):
    """Ventana de log flotante rediseñada como QDialog para corregir el bug de la señal 'finished'"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Monitor de Ejecución en Tiempo Real")
        self.resize(700, 450)
        self.setWindowFlags(Qt.WindowType.Window)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setObjectName("LogTerminal")
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                color: #e2e8f0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: none;
            }
        """)
        layout.addWidget(self.text_edit)
        
    def append_html(self, html):
        self.text_edit.append(html)
        self.text_edit.verticalScrollBar().setValue(
            self.text_edit.verticalScrollBar().maximum()
        )

    def set_html(self, html):
        self.text_edit.setHtml(html)
        
    def clear(self):
        self.text_edit.clear()


class ZoomControlsFinal(QWidget):
    """Pill bar flotante para controles de zoom en la esquina inferior del canvas"""
    
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setWindowFlags(Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        
        # Estilo Pill
        self.setObjectName("ZoomPill")
        self.setStyleSheet("""
            #ZoomPill {
                background-color: rgba(15, 23, 42, 0.85); /* Slate 900 semi-transparente */
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 18px;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                min-width: 26px;
                min-height: 26px;
                border-radius: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QLabel {
                color: #e2e8f0;
                font-weight: bold;
                font-size: 10px;
                padding: 0 4px;
            }
        """)
        
        btn_out = QPushButton("−")
        btn_out.setToolTip("Alejar (Ctrl+Wheel)")
        btn_out.clicked.connect(lambda: self.adjust_zoom(1/1.2))
        layout.addWidget(btn_out)
        
        self.lbl_pct = QLabel("100%")
        layout.addWidget(self.lbl_pct)
        
        btn_in = QPushButton("+")
        btn_in.setToolTip("Acercar (Ctrl+Wheel)")
        btn_in.clicked.connect(lambda: self.adjust_zoom(1.2))
        layout.addWidget(btn_in)
        
        btn_fit = QPushButton("⛶")
        btn_fit.setToolTip("Ajustar al Canvas")
        btn_fit.clicked.connect(self.fit_view)
        layout.addWidget(btn_fit)
        
    def adjust_zoom(self, factor):
        self.canvas.scale_view(factor)
        self.update_label()
        
    def fit_view(self):
        rect = self.canvas.scene.itemsBoundingRect()
        if not rect.isEmpty():
            self.canvas.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            transform = self.canvas.transform()
            self.canvas._zoom = transform.m11()
        else:
            self.canvas._zoom = 1.0
            self.canvas.resetTransform()
        self.update_label()
        
    def update_label(self):
        pct = int(self.canvas._zoom * 100)
        self.lbl_pct.setText(f"{pct}%")
