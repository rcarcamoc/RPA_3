from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, 
                             QLabel, QPushButton, QLineEdit, QFrame,
                             QHBoxLayout, QGridLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from .node_definitions import NODE_CATALOG, NodeDefinition
from .node_card import NodeCard

class NodePalette(QWidget):
    """Panel lateral con paleta de nodos categorizados"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QLabel(" 📦 Componentes")
        header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        header.setStyleSheet("padding: 8px; background-color: #f8f9fa; border-bottom: 1px solid #ddd;")
        layout.addWidget(header)
        
        # Buscador
        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(8, 8, 8, 8)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Buscar nodo...")
        self.search_box.textChanged.connect(self.filter_nodes)
        self.search_box.setStyleSheet("""
            QLineEdit {
                padding: 4px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)
        search_layout.addWidget(self.search_box)
        layout.addWidget(search_container)
        
        # Scroll Area para las categorias
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: white; }")
        
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: white;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 0, 8, 8)
        self.content_layout.setSpacing(10)
        
        # Crear categorias
        self.category_widgets = {} # Para filtrar luego
        
        # Orden preferido de categorias
        categories = ['Ejecuta un programa', 'Database', 'Control Flow', 'Transform', 'Integrations', 'Documentation']
        
        for cat_name in categories:
            if cat_name in NODE_CATALOG:
                self.add_category(cat_name, NODE_CATALOG[cat_name])
        
        self.content_layout.addStretch()
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)
        
        self.setFixedWidth(240)
        
    def add_category(self, name: str, nodes: list[NodeDefinition]):
        """Agrega una categoria colapsable con sus nodos"""
        # Container de la categoria
        cat_container = QWidget()
        cat_layout = QVBoxLayout(cat_container)
        cat_layout.setContentsMargins(0, 0, 0, 0)
        cat_layout.setSpacing(2)
        
        # Boton Header (toggle)
        header_btn = QPushButton(f"▼ {name}")
        header_btn.setCheckable(True)
        header_btn.setChecked(True) # Expandido por defecto
        header_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        header_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px;
                background-color: transparent;
                border: None;
                color: #555;
            }
            QPushButton:hover {
                color: #000;
            }
            QPushButton:checked {
                 /* Estilo cuando esta expandido */
            }
        """)
        
        # Grid de nodos
        nodes_container = QWidget()
        # Usaremos QGridLayout con columnas fijas simulando grid
        nodes_grid_layout = QGridLayout(nodes_container)
        nodes_grid_layout.setContentsMargins(2, 2, 2, 2)
        nodes_grid_layout.setSpacing(6)
        
        row = 0
        col = 0
        max_cols = 2 # 2 columnas de nodos
        
        node_widgets = []
        for node_def in nodes:
            card = NodeCard(node_def)
            nodes_grid_layout.addWidget(card, row, col)
            node_widgets.append(card)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        cat_layout.addWidget(header_btn)
        cat_layout.addWidget(nodes_container)
        
        # Logica de colapso
        def toggle_category(checked):
            nodes_container.setVisible(checked)
            header_btn.setText(f"{'▼' if checked else '▶'} {name}")
            
        header_btn.clicked.connect(toggle_category)
        header_btn.clicked.connect(lambda: toggle_category(header_btn.isChecked())) # Trigger inicial? No, connect pasa checked
        
        # Guardar referencias
        self.category_widgets[name] = {
            'container': cat_container,
            'header': header_btn,
            'nodes_container': nodes_container,
            'node_cards': node_widgets, # Lista de widgets NodeCard
            'defs': nodes # Lista de definiciones
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
                    data['header'].setText(f"▼ {cat_name}")
            else:
                data['container'].setVisible(False)

# Clase auxiliar, podriamos usar QGridLayout directamente
