from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QMimeData, QPoint
from PyQt6.QtGui import QDrag, QFont, QColor, QPixmap, QPainter

from .node_definitions import NodeDefinition

class NodeCard(QWidget):
    """Tarjeta de nodo arrastrable para la paleta"""
    
    def __init__(self, node_def: NodeDefinition, parent=None):
        super().__init__(parent)
        self.node_def = node_def
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # Icono
        icon_label = QLabel(self.node_def.icon)
        icon_label.setFont(QFont("Segoe UI Emoji", 20)) # Emoji font
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # Nombre
        name_label = QLabel(self.node_def.name)
        name_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        # Limitar lineas si es muy largo
        layout.addWidget(name_label)
        
        # Estilo
        self.setStyleSheet("""
            NodeCard {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
            NodeCard:hover {
                background-color: #f0f8ff;
                border: 1px solid #4facfe;
            }
        """)
        
        self.setFixedSize(90, 80)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            
            # Pasar el ID del nodo como texto
            mime_data.setText(self.node_def.id)
            drag.setMimeData(mime_data)
            
            # Crear pixmap para la vista previa del arrastre
            pixmap = QPixmap(self.size())
            self.render(pixmap)
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            
            # Iniciar arrastre
            drag.exec(Qt.DropAction.CopyAction)
