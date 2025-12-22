from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
                             QComboBox, QGroupBox, QPushButton, QHBoxLayout, 
                             QLabel, QStyle, QPlainTextEdit, QMessageBox, QFileDialog)
from PyQt6.QtCore import pyqtSignal, Qt
from pathlib import Path
from core.models import Node, NodeType, ActionNode, DecisionNode, LoopNode
import os

class PropertiesPanel(QWidget):
    """
    Panel de Propiedades para editar nodos.
    Se muestra solo cuando hay un nodo seleccionado.
    """
    
    # Señales para comunicar cambios al controlador principal
    node_updated = pyqtSignal(Node)        # Cuando se aplica un cambio
    node_deleted = pyqtSignal(Node)        # Cuando se pide borrar
    move_to_node = pyqtSignal(str)         # Click en "Siguiente Nodo" ID
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_node = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header Group
        self.group = QGroupBox("Propiedades del Nodo")
        self.group.setStyleSheet("QGroupBox { font-weight: bold; }")
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # --- Campos Comunes ---
        self.prop_id = QLineEdit()
        self.prop_id.setReadOnly(True)
        self.prop_id.setStyleSheet("background-color: #f0f0f0; color: #555;")
        form_layout.addRow("ID:", self.prop_id)
        
        self.prop_label = QLineEdit()
        self.prop_label.setPlaceholderText("Nombre del nodo")
        form_layout.addRow("Etiqueta:", self.prop_label)
        
        self.prop_type = QLineEdit() # Read only for now unless we implement type changing logic
        self.prop_type.setReadOnly(True)
        form_layout.addRow("Tipo:", self.prop_type)
        
        # --- Campos Especificos (Action/Loop) ---
        self.script_container = QWidget()
        script_layout = QHBoxLayout(self.script_container)
        script_layout.setContentsMargins(0,0,0,0)
        
        self.prop_script = QComboBox()
        self.prop_script.setEditable(True)
        self.prop_script.setPlaceholderText("Seleccionar o escribir script Python...")
        script_layout.addWidget(self.prop_script)
        
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self.browse_script)
        script_layout.addWidget(btn_browse)
        
        form_layout.addRow("Script Python:", self.script_container)
        
        self.prop_command = QLineEdit()
        self.prop_command.setPlaceholderText("Ej: echo 'Hello' >> log.txt")
        form_layout.addRow("Comando:", self.prop_command)

        # Presets combo
        self.cmd_presets = QComboBox()
        self.cmd_presets.addItem("--- Predefinidos ---")
        self.cmd_presets.addItems([
            "Abrir Notepad: start notepad",
            "Abrir Chrome: start chrome",
            "Abrir URL: start https://google.com",
            "Ping Google: ping google.com",
            "Listar Archivos: dir",
            "Info Sistema: systeminfo",
            "Maximizar (PowerShell): powershell -c (New-Object -ComObject WScript.Shell).SendKeys('% x')"
        ])
        self.cmd_presets.currentIndexChanged.connect(self.apply_preset)
        form_layout.addRow("Presets:", self.cmd_presets)
        
        self.prop_iterations = QLineEdit()
        self.prop_iterations.setPlaceholderText("Ej: 5, o variable")
        form_layout.addRow("Iteraciones:", self.prop_iterations)
        
        self.prop_delay = QLineEdit()
        self.prop_delay.setPlaceholderText("Segundos (ej: 5)")
        form_layout.addRow("Delay (s):", self.prop_delay)
        
        # --- Campos Decision ---
        self.prop_condition = QLineEdit()
        self.prop_condition.setPlaceholderText("Ej: x > 5")
        form_layout.addRow("Condición:", self.prop_condition)
        
        # --- Campos Database ---
        self.db_group = QGroupBox("Base de Datos")
        db_layout = QFormLayout()
        self.prop_db_host = QLineEdit("localhost")
        self.prop_db_port = QLineEdit("3306")
        self.prop_db_user = QLineEdit("root")
        self.prop_db_password = QLineEdit()
        self.prop_db_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.prop_db_database = QLineEdit()
        self.prop_db_query = QPlainTextEdit()
        self.prop_db_query.setMaximumHeight(80)
        self.prop_db_operation = QComboBox()
        self.prop_db_operation.addItems(["SELECT", "INSERT", "UPDATE", "DELETE"])
        
        db_layout.addRow("Host:", self.prop_db_host)
        db_layout.addRow("Port:", self.prop_db_port)
        db_layout.addRow("User:", self.prop_db_user)
        db_layout.addRow("Pass:", self.prop_db_password)
        db_layout.addRow("DB:", self.prop_db_database)
        db_layout.addRow("Op:", self.prop_db_operation)
        db_layout.addRow("Query:", self.prop_db_query)
        self.db_group.setLayout(db_layout)
        form_layout.addRow(self.db_group)
        
        # --- Campos Annotation ---
        self.note_group = QGroupBox("Nota")
        note_layout = QFormLayout()
        self.prop_note_text = QPlainTextEdit()
        self.prop_note_color = QComboBox()
        self.prop_note_color.addItems(["Amarillo", "Azul", "Rosa", "Verde"])
        
        note_layout.addRow("Texto:", self.prop_note_text)
        note_layout.addRow("Color:", self.prop_note_color)
        self.note_group.setLayout(note_layout)
        form_layout.addRow(self.note_group)

        self.group.setLayout(form_layout)
        layout.addWidget(self.group)
        
        # --- Botones de Acción ---
        btn_layout = QHBoxLayout()
        
        self.btn_apply = QPushButton("Aplicar Cambios")
        self.btn_apply.setStyleSheet("background-color: #007bff; color: white; padding: 6px;")
        self.btn_apply.clicked.connect(self.apply_changes)
        
        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.setStyleSheet("background-color: #dc3545; color: white; padding: 6px;")
        self.btn_delete.clicked.connect(self.request_delete)
        
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_delete)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        # Cargar scripts iniciales
        self.load_scripts()

    def load_node(self, node: Node):
        """Carga los datos de un nodo en el formulario"""
        self.current_node = node
        
        # 1. Resetear visibilidad
        self.input_widgets = [
            self.script_container, self.prop_command, self.cmd_presets, self.prop_iterations, self.prop_delay, 
            self.prop_condition, self.db_group, self.note_group
        ]
        for w in self.input_widgets:
            w.setVisible(False)
            if self.group.layout().labelForField(w):
                self.group.layout().labelForField(w).setVisible(False)

        # 2. Llenar datos comunes
        self.prop_id.setText(node.id)
        self.prop_label.setText(node.label)
        self.prop_type.setText(node.type.value)
        
        # 3. Llenar y mostrar especificos
        t = node.type
        
        if t == NodeType.ACTION or t == NodeType.LOOP:
            # Mostrar Script por defecto, pero si tiene comando mostrar comando
            # Permitir ambos? Generalmente es uno u otro.
            if hasattr(node, 'command') and node.command:
                self._show_field(self.prop_command)
                self._show_field(self.cmd_presets)
                self.prop_command.setText(node.command)
            else:
                 self._show_field(self.script_container)
                 if hasattr(node, 'script'):
                    self.prop_script.setCurrentText(node.script)
                
        if t == NodeType.LOOP:
             self._show_field(self.prop_iterations)
             if hasattr(node, 'iterations'):
                 self.prop_iterations.setText(str(node.iterations))
        
        if t == NodeType.DELAY:
             self._show_field(self.prop_delay)
             from core.delay_node import DelayNode
             if isinstance(node, DelayNode):
                 self.prop_delay.setText(str(node.delay_seconds))
                 
        if t == NodeType.DECISION:
            self._show_field(self.prop_condition)
            if hasattr(node, 'condition'):
                self.prop_condition.setText(node.condition)
                
        if t == NodeType.DATABASE:
            self._show_field(self.db_group)
            # Asumimos que node tiene atributos o properties dict
            # En la impl actual son atributos directos en DatabaseNode
            try:
                self.prop_db_host.setText(getattr(node, 'host', ''))
                self.prop_db_port.setText(str(getattr(node, 'port', '3306')))
                self.prop_db_user.setText(getattr(node, 'user', ''))
                self.prop_db_password.setText(getattr(node, 'password', ''))
                self.prop_db_database.setText(getattr(node, 'database', ''))
                self.prop_db_query.setPlainText(getattr(node, 'query', ''))
                self.prop_db_operation.setCurrentText(getattr(node, 'operation', 'SELECT'))
            except:
                pass

        if t == NodeType.ANNOTATION:
            self._show_field(self.note_group)
            try:
                self.prop_note_text.setPlainText(getattr(node, 'text', ''))
                color = getattr(node, 'color', '#ffffcc')
                # Mapeo simple inverso
                c_map = {"#ffffcc": "Amarillo", "#cce5ff": "Azul", "#ffccf2": "Rosa", "#ccffcc": "Verde"}
                self.prop_note_color.setCurrentText(c_map.get(color, "Amarillo"))
            except:
                pass
                
        self.setVisible(True)

    def _show_field(self, widget):
        widget.setVisible(True)
        lbl = self.group.layout().labelForField(widget)
        if lbl: lbl.setVisible(True)

    def apply_changes(self):
        """Recoge datos y emite señal de actualización"""
        if not self.current_node:
            return
            
        # Actualizar objeto nodo (en memoria) desde UI
        node = self.current_node
        node.label = self.prop_label.text()
        
        t = node.type
        if t == NodeType.ACTION:
            # Si el campo comando esta visible y tiene texto, usarlo
            if self.prop_command.isVisible() and self.prop_command.text():
                node.command = self.prop_command.text()
                node.script = "" # Prioridad a comando? O mantener ambos? Limpiamos script para evitar confusion
            else:
                node.script = self.prop_script.currentText()
                node.command = ""

        if t == NodeType.LOOP:
            node.script = self.prop_script.currentText()
            node.iterations = self.prop_iterations.text()
            
        if t == NodeType.DELAY:
            try:
                node.delay_seconds = int(self.prop_delay.text())
            except:
                node.delay_seconds = 5
            
        if t == NodeType.DECISION:
            node.condition = self.prop_condition.text()
            
        if t == NodeType.DATABASE:
            node.host = self.prop_db_host.text()
            node.port = int(self.prop_db_port.text() or 3306)
            node.user = self.prop_db_user.text()
            node.password = self.prop_db_password.text()
            node.database = self.prop_db_database.text()
            node.query = self.prop_db_query.toPlainText()
            node.operation = self.prop_db_operation.currentText()
            
        if t == NodeType.ANNOTATION:
            node.text = self.prop_note_text.toPlainText()
            color_map = {"Amarillo": "#ffffcc", "Azul": "#cce5ff", "Rosa": "#ffccf2", "Verde": "#ccffcc"}
            node.color = color_map.get(self.prop_note_color.currentText(), "#ffffcc")
            
        # Emitir señal para que el controlador haga Undo/Redo y refresque GUI
        self.node_updated.emit(node)
        QMessageBox.information(self, "Nodo Actualizado", f"Propiedades de '{node.label}' guardadas.")

    def request_delete(self):
        if self.current_node:
            reply = QMessageBox.question(self, "Eliminar", f"¿Eliminar nodo {self.current_node.label}?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.node_deleted.emit(self.current_node)

    def load_scripts(self):
        script_dir = Path("scripts")
        if script_dir.exists():
            files = [f.name for f in script_dir.glob("*.py")]
            self.prop_script.addItems(files)

    def browse_script(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Seleccionar Script", "scripts", "Python (*.py)")
        if fname:
            path = Path(fname)
            self.prop_script.setCurrentText(path.name)

    def apply_preset(self, index):
        if index <= 0: return
        text = self.cmd_presets.currentText()
        if ":" in text:
            cmd = text.split(":", 1)[1].strip()
            self.prop_command.setText(cmd)
