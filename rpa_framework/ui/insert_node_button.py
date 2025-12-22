"""
Insert Node Button for Edge - allows clicking on connections to insert intermediate nodes.
This will be integrated into workflow_panel.py
"""

from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsTextItem
from PyQt6.QtGui import QBrush, QPen, QColor, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QObject

class InsertNodeButton(QGraphicsEllipseItem):
    """+ button that appears on edges when hovering"""
    
    def __init__(self, parent_edge, parent=None):
        # Circle with 24px diameter
        super().__init__(-12, -12, 24, 24, parent)
        self.parent_edge = parent_edge
        
        # Green circle
        self.setBrush(QBrush(QColor("#28a745")))
        self.setPen(QPen(QColor("white"), 2))
        
        # + symbol
        self.plus_text = QGraphicsTextItem("+", self)
        self.plus_text.setDefaultTextColor(Qt.GlobalColor.white)
        plus_font = QFont("Arial", 16, QFont.Weight.Bold)
        self.plus_text.setFont(plus_font)
        self.plus_text.setPos(-6, -10)
        
        # Initially hidden
        self.setVisible(False)
        self.setAcceptHoverEvents(True)
        self.setZValue(100)  # Always on top
        
    def hoverEnterEvent(self, event):
        # Highlight on hover
        self.setBrush(QBrush(QColor("#218838")))
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        # Return to normal
        self.setBrush(QBrush(QColor("#28a745")))
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        # Trigger insertion
        if hasattr(self.parent_edge, 'on_insert_requested'):
            click_pos = self.scenePos()
            self.parent_edge.on_insert_requested(click_pos)
        event.accept()
