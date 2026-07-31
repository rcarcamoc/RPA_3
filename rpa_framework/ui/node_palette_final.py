from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, 
                             QLabel, QPushButton, QLineEdit, QFrame,
                             QHBoxLayout, QGridLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from .node_definitions import NODE_CATALOG, NodeDefinition
from .node_card_final import NodeCardFinal

class NodePaletteFinal(QWidget):
    """Panel lateral con paleta de nodos categorizados para la GUI final"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header (Profesional y limpio)
        header = QLabel("Componentes Disponibles")
        header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        header.setStyleSheet("""
            padding: 12px; 
            background-color: #f8fafc; 
            border-bottom: 1px solid #e2e8f0;
            color: #0f172a;
        """)
        layout.addWidget(header)
        
        # Buscador
        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(8, 8, 8, 8)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar componente...")
        self.search_box.textChanged.connect(self.filter_nodes)
        self.search_box.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #ffffff;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 1px solid #10b981;
            }
        """)
        search_layout.addWidget(self.search_box)
        layout.addWidget(search_container)
        
        # Scroll Area para las categorias
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #f8fafc; }")
        
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: #f8fafc;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 0, 8, 8)
        self.content_layout.setSpacing(8)
        
        # Crear categorias
        self.category_widgets = {}
        
        # Orden preferido de categorias
        categories = ['Control Flow', 'Ejecuta un programa', 'Database', 'Transform', 'Integrations', 'Documentation']
        
        for cat_name in categories:
            if cat_name in NODE_CATALOG:
                self.add_category(cat_name, NODE_CATALOG[cat_name])
        
        self.content_layout.addStretch()
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)
        
    def add_category(self, name: str, nodes: list[NodeDefinition]):
        """Agrega una categoria colapsable con sus nodos y badge de conteo"""
        # Container de la categoria
        cat_container = QWidget()
        cat_layout = QVBoxLayout(cat_container)
        cat_layout.setContentsMargins(0, 0, 0, 0)
        cat_layout.setSpacing(2)
        
        # Boton Header (toggle) con badge de conteo
        header_btn = QPushButton(f"▼ {name} ({len(nodes)})")
        header_btn.setCheckable(True)
        header_btn.setChecked(True) # Expandido por defecto
        header_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        header_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 6px;
                background-color: transparent;
                border: none;
                color: #475569;
            }
            QPushButton:hover {
                color: #0f172a;
            }
        """)
        
        # Grid de nodos
        nodes_container = QWidget()
        nodes_grid_layout = QGridLayout(nodes_container)
        nodes_grid_layout.setContentsMargins(2, 2, 2, 2)
        nodes_grid_layout.setSpacing(6)
        
        row = 0
        col = 0
        max_cols = 2 # 2 columnas de nodos
        
        node_widgets = []
        for node_def in nodes:
            card = NodeCardFinal(node_def)
            nodes_grid_layout.addWidget(card, row, col)
            node_widgets.append(card)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        cat_layout.addWidget(header_btn)
        cat_layout.addWidget(nodes_container)
        
        # Logica de colapso - Corregido el bug de doble-trigger (conectado una sola vez)
        def toggle_category(checked):
            nodes_container.setVisible(checked)
            header_btn.setText(f"{'▼' if checked else '▶'} {name} ({len(nodes)})")
            
        header_btn.clicked.connect(toggle_category)
        
        # Guardar referencias
        self.category_widgets[name] = {
            'container': cat_container,
            'header': header_btn,
            'nodes_container': nodes_container,
            'node_cards': node_widgets,
            'defs': nodes
        }
        
        self.content_layout.addWidget(cat_container)
 
    def filter_nodes(self, text: str):
        """Filtra nodos y categorias segun texto"""
        text = text.lower().strip()
        
        for cat_name, data in self.category_widgets.items():
            visible_count = 0
            
            # Verificar cada nodo
            for i, card in enumerate(data['node_cards']):
                node_def = data['defs'][i]
                if text in node_def.name.lower() or text in node_def.description.lower():
                    card.setVisible(True)
                    visible_count += 1
                else:
                    card.setVisible(False)
            
            # Ocultar categoria si no tiene nodos visibles
            if visible_count > 0:
                data['container'].setVisible(True)
                # Si estamos buscando, expandimos todo
                if text:
                    data['nodes_container'].setVisible(True)
                    data['header'].setChecked(True)
                    data['header'].setText(f"▼ {cat_name} ({len(data['defs'])})")
            else:
                data['container'].setVisible(False)
