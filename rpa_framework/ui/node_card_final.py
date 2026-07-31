from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QMimeData, QPoint
from PyQt6.QtGui import QDrag, QFont, QColor, QPixmap, QPainter
from .node_definitions import NodeDefinition

class NodeCardFinal(QWidget):
    """Tarjeta de nodo moderna y profesional con icono, nombre y descripción truncada"""
    
    def __init__(self, node_def: NodeDefinition, parent=None):
        super().__init__(parent)
        self.node_def = node_def
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # Icono grande y centrado
        self.icon_label = QLabel(self.node_def.icon)
        self.icon_label.setFont(QFont("Segoe UI Emoji", 20))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)
        
        # Nombre del nodo (Negrita)
        self.name_label = QLabel(self.node_def.name)
        self.name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setObjectName("node_name")
        layout.addWidget(self.name_label)
        
        # Breve descripción truncada
        desc = self.node_def.description
        if len(desc) > 30:
            desc = desc[:28] + "..."
        self.desc_label = QLabel(desc)
        self.desc_label.setFont(QFont("Segoe UI", 7))
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setWordWrap(True)
        self.desc_label.setObjectName("node_desc")
        self.desc_label.setStyleSheet("color: #64748b;")
        layout.addWidget(self.desc_label)
        
        # Tooltip completo con nombre y descripción
        self.setToolTip(f"<b>{self.node_def.name}</b><br/>{self.node_def.description}")
        
        # Estilo CSS moderno, consistente con tokens
        self.setObjectName("NodeCard")
        self.setStyleSheet("""
            #NodeCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            #NodeCard:hover {
                background-color: #f0fdf4;
                border: 1px solid #10b981;
            }
        """)
        
        # Tamaño adaptable pero estable
        self.setFixedSize(110, 105)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            
            # Pasar el ID del nodo como texto para la escena
            mime_data.setText(self.node_def.id)
            drag.setMimeData(mime_data)
            
            # Crear pixmap para la vista previa del arrastre
            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setOpacity(0.85)
            self.render(painter)
            painter.end()
            
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            
            # Iniciar arrastre
            drag.exec(Qt.DropAction.CopyAction)
