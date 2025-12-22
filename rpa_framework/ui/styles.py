
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
        width: 12px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""
