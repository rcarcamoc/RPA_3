from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
                             QComboBox, QGroupBox, QPushButton, QHBoxLayout, 
                             QLabel, QStyle, QPlainTextEdit, QMessageBox, QFileDialog)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QIntValidator, QFont, QColor
from pathlib import Path
from core.models import Node, NodeType, ActionNode, DecisionNode, LoopNode, WorkflowNode
import os

class PropertiesPanelFinal(QWidget):
    """
    Panel de Propiedades Rediseñado para Nodos de Workflow.
    Muestra un header coloreado según el tipo de nodo y organiza los campos de forma limpia.
    """
    
    # Señales para comunicar cambios al controlador principal
    node_updated = pyqtSignal(Node)        # Cuando se aplica un cambio
    node_deleted = pyqtSignal(Node)        # Cuando se pide borrar
    move_to_node = pyqtSignal(str)         # Click en "Siguiente Nodo" ID
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_node = None
        self._loading_node = False
        
        # Timer para guardado automático (debounce 500ms)
        self.autosave_timer = QTimer()
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(500)
        self.autosave_timer.timeout.connect(self.apply_changes)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # --- Type Colored Header ---
        self.type_header = QWidget()
        self.type_header.setObjectName("TypeHeader")
        self.type_header.setFixedHeight(40)
        self.type_header_layout = QHBoxLayout(self.type_header)
        self.type_header_layout.setContentsMargins(10, 0, 10, 0)
        
        self.type_title = QLabel("Propiedades")
        self.type_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.type_title.setStyleSheet("color: white;")
        self.type_header_layout.addWidget(self.type_title)
        self.type_header_layout.addStretch()
        
        self.type_header.setStyleSheet("""
            #TypeHeader {
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                background-color: #3b82f6;
            }
        """)
        layout.addWidget(self.type_header)
        
        # Form Container
        self.form_container = QWidget()
        form_layout = QFormLayout(self.form_container)
        form_layout.setContentsMargins(10, 5, 10, 5)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setSpacing(8)
        
        # --- 1. SECCIÓN GENERAL ---
        self.general_group = QGroupBox("Datos Generales")
        self.general_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 8px; padding-top: 8px; }")
        general_layout = QFormLayout()
        general_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.prop_id = QLineEdit()
        self.prop_id.setReadOnly(True)
        self.prop_id.setStyleSheet("background-color: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1;")
        general_layout.addRow("ID:", self.prop_id)
        
        self.prop_label = QLineEdit()
        self.prop_label.setPlaceholderText("Nombre descriptivo del nodo")
        general_layout.addRow("Etiqueta:", self.prop_label)
        
        self.prop_type = QLineEdit()
        self.prop_type.setReadOnly(True)
        self.prop_type.setStyleSheet("background-color: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1;")
        general_layout.addRow("Tipo:", self.prop_type)

        self.prop_on_error = QComboBox()
        self.prop_on_error.addItems(["stop", "continue"])
        general_layout.addRow("On Error:", self.prop_on_error)
        
        self.general_group.setLayout(general_layout)
        form_layout.addRow(self.general_group)
        
        # --- 2. SECCIÓN ESPECÍFICA (DINÁMICA) ---
        self.config_group = QGroupBox("Configuración del Nodo")
        self.config_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 8px; padding-top: 8px; }")
        config_layout = QFormLayout()
        config_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Script Python container
        self.script_container = QWidget()
        script_layout = QHBoxLayout(self.script_container)
        script_layout.setContentsMargins(0,0,0,0)
        script_layout.setSpacing(4)
        
        self.prop_script = QComboBox()
        self.prop_script.setEditable(True)
        self.prop_script.setPlaceholderText("Seleccionar o escribir script Python...")
        script_layout.addWidget(self.prop_script)
        
        btn_browse = QPushButton()
        btn_browse.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self.browse_script)
        script_layout.addWidget(btn_browse)
        
        config_layout.addRow("Script Python:", self.script_container)
        
        # Nested Workflow path container
        self.wf_container = QWidget()
        wf_layout = QHBoxLayout(self.wf_container)
        wf_layout.setContentsMargins(0,0,0,0)
        wf_layout.setSpacing(4)
        
        self.prop_workflow_path = QComboBox()
        self.prop_workflow_path.setEditable(True)
        self.prop_workflow_path.setPlaceholderText("Seleccionar workflow...")
        wf_layout.addWidget(self.prop_workflow_path)
        
        btn_browse_wf = QPushButton()
        btn_browse_wf.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        btn_browse_wf.setFixedWidth(30)
        btn_browse_wf.clicked.connect(self.browse_workflow)
        wf_layout.addWidget(btn_browse_wf)
        
        config_layout.addRow("Workflow:", self.wf_container)
        
        # Command Type Selector
        self.prop_command_type = QComboBox()
        self.prop_command_type.addItems([
            "Comando Personalizado",
            "Mostrar Escritorio",
            "Abrir Programa",
            "Cerrar Programa"
        ])
        self.prop_command_type.currentIndexChanged.connect(self.update_command_fields)
        config_layout.addRow("Comando Tipo:", self.prop_command_type)
        
        self.prop_command = QLineEdit()
        self.prop_command.setPlaceholderText("Ej: echo 'Hello' >> log.txt")
        config_layout.addRow("Comando:", self.prop_command)
        
        # Program Path for "Open Program"
        self.prop_program_path = QWidget()
        program_path_layout = QHBoxLayout(self.prop_program_path)
        program_path_layout.setContentsMargins(0,0,0,0)
        program_path_layout.setSpacing(4)
        
        self.prop_program_path_edit = QLineEdit()
        self.prop_program_path_edit.setPlaceholderText("Ruta del ejecutable...")
        program_path_layout.addWidget(self.prop_program_path_edit)
        
        btn_browse_program = QPushButton()
        btn_browse_program.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        btn_browse_program.setFixedWidth(30)
        btn_browse_program.clicked.connect(self.browse_program)
        program_path_layout.addWidget(btn_browse_program)
        
        config_layout.addRow("Ruta Programa:", self.prop_program_path)
        
        self.prop_process_name = QLineEdit()
        self.prop_process_name.setPlaceholderText("Ej: chrome.exe, notepad.exe")
        config_layout.addRow("Nombre Proceso:", self.prop_process_name)

        self.prop_output_var = QLineEdit()
        self.prop_output_var.setPlaceholderText("Nombre de variable (ej: output_text)")
        config_layout.addRow("Guardar Salida en:", self.prop_output_var)
        
        # Loop container and its fields
        self.loop_container = QWidget()
        loop_layout = QFormLayout(self.loop_container)
        loop_layout.setContentsMargins(0,0,0,0)
        loop_layout.setSpacing(6)
        
        self.prop_loop_type = QComboBox()
        self.prop_loop_type.addItems([
            "Count (N Veces)",
            "List (ForEach)",
            "While (Condición)",
            "Timed (N Horas)",
            "Infinite (Sin fin)"
        ])
        self.prop_loop_type.currentIndexChanged.connect(self.update_loop_fields)
        loop_layout.addRow("Tipo Loop:", self.prop_loop_type)

        self.prop_iterations = QLineEdit()
        self.prop_iterations.setPlaceholderText("Ej: 5")
        self.prop_iterations.setValidator(QIntValidator(1, 999999))
        loop_layout.addRow("Iteraciones:", self.prop_iterations)
        
        self.prop_iterable = QLineEdit()
        self.prop_iterable.setPlaceholderText("Ej: db_result")
        loop_layout.addRow("Lista (Variable):", self.prop_iterable)
        
        self.prop_loop_condition = QLineEdit()
        self.prop_loop_condition.setPlaceholderText("Ej: x < 10")
        loop_layout.addRow("Condición While:", self.prop_loop_condition)
        
        self.prop_duration_hours = QLineEdit()
        self.prop_duration_hours.setPlaceholderText("Ej: 1.5")
        loop_layout.addRow("Duración (horas):", self.prop_duration_hours)
        
        self.prop_loop_var = QLineEdit()
        self.prop_loop_var.setPlaceholderText("Ej: item")
        loop_layout.addRow("Variable Item:", self.prop_loop_var)

        config_layout.addRow(self.loop_container)
        
        self.prop_delay = QLineEdit()
        self.prop_delay.setPlaceholderText("Segundos (ej: 5)")
        self.prop_delay.setValidator(QIntValidator(0, 86400))
        config_layout.addRow("Delay (s):", self.prop_delay)
        
        self.prop_error_delay = QLineEdit()
        self.prop_error_delay.setPlaceholderText("Segundos (ej: 10)")
        self.prop_error_delay.setValidator(QIntValidator(0, 86400))
        config_layout.addRow("Delay por Error (s):", self.prop_error_delay)
        
        # Decision (Condition)
        self.prop_condition = QLineEdit()
        self.prop_condition.setPlaceholderText("Ej: status_code == 200")
        config_layout.addRow("Condición:", self.prop_condition)
        
        # Database specific panel layout (sub-groupbox inside properties)
        self.db_group = QGroupBox("Ajustes Conexión DB")
        self.db_group.setStyleSheet("QGroupBox { border: 1px solid #cbd5e1; font-weight: normal; margin-top: 4px; padding-top: 4px; }")
        db_layout = QFormLayout()
        db_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.prop_db_host = QLineEdit("localhost")
        self.prop_db_port = QLineEdit("3306")
        self.prop_db_port.setValidator(QIntValidator(1, 65535))
        self.prop_db_user = QLineEdit("root")
        self.prop_db_password = QLineEdit()
        self.prop_db_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.prop_db_database = QLineEdit()
        self.prop_db_query = QPlainTextEdit()
        self.prop_db_query.setMaximumHeight(80)
        self.prop_db_operation = QComboBox()
        self.prop_db_operation.addItems(["SELECT", "INSERT", "UPDATE", "DELETE"])
        
        db_layout.addRow("Host:", self.prop_db_host)
        db_layout.addRow("Puerto:", self.prop_db_port)
        db_layout.addRow("Usuario:", self.prop_db_user)
        db_layout.addRow("Contraseña:", self.prop_db_password)
        db_layout.addRow("Base Datos:", self.prop_db_database)
        db_layout.addRow("Operación:", self.prop_db_operation)
        db_layout.addRow("Consulta:", self.prop_db_query)
        self.db_group.setLayout(db_layout)
        config_layout.addRow(self.db_group)
        
        # Annotation text, color
        self.note_group = QGroupBox("Contenido Nota")
        self.note_group.setStyleSheet("QGroupBox { border: 1px solid #cbd5e1; font-weight: normal; margin-top: 4px; padding-top: 4px; }")
        note_layout = QFormLayout()
        self.prop_note_text = QPlainTextEdit()
        self.prop_note_color = QComboBox()
        self.prop_note_color.addItems(["Amarillo", "Azul", "Rosa", "Verde"])
        
        note_layout.addRow("Texto:", self.prop_note_text)
        note_layout.addRow("Color:", self.prop_note_color)
        self.note_group.setLayout(note_layout)
        config_layout.addRow(self.note_group)
        
        self.config_group.setLayout(config_layout)
        form_layout.addRow(self.config_group)
        
        layout.addWidget(self.form_container)
        
        # --- Autoguardado signals setup ---
        self._setup_autosave_connections()
        
        # --- Footer Action buttons ---
        btn_layout = QHBoxLayout()
        self.btn_delete = QPushButton("Eliminar Nodo")
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #ef4444; 
                color: white; 
                padding: 6px; 
                font-weight: bold;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        self.btn_delete.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.btn_delete.clicked.connect(self.request_delete)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        # Populate combobox values dynamically
        self.load_scripts()
        self.load_workflows()
        
    def update_loop_fields(self):
        """Muestra u oculta campos de loop según el tipo"""
        t = self.prop_loop_type.currentText()
        loop_layout = self.loop_container.layout()
        if not loop_layout: return

        self.prop_iterations.setVisible("Count" in t)
        loop_layout.labelForField(self.prop_iterations).setVisible("Count" in t)
        
        self.prop_iterable.setVisible("List" in t)
        loop_layout.labelForField(self.prop_iterable).setVisible("List" in t)
        
        self.prop_loop_condition.setVisible("While" in t)
        loop_layout.labelForField(self.prop_loop_condition).setVisible("While" in t)
        
        self.prop_duration_hours.setVisible("Timed" in t)
        loop_layout.labelForField(self.prop_duration_hours).setVisible("Timed" in t)
        
        # Variable Item solo es relevante para Count/List/While
        show_var = not ("Timed" in t or "Infinite" in t)
        self.prop_loop_var.setVisible(show_var)
        loop_layout.labelForField(self.prop_loop_var).setVisible(show_var)
    
    def update_command_fields(self):
        """Muestra u oculta campos de comando según el tipo"""
        t = self.prop_command_type.currentText()
        layout = self.config_group.layout()
        if not layout: return
        
        # Ocultar todos primero
        self.prop_command.setVisible(False)
        layout.labelForField(self.prop_command).setVisible(False)
        
        self.prop_program_path.setVisible(False)
        layout.labelForField(self.prop_program_path).setVisible(False)
        
        self.prop_process_name.setVisible(False)
        layout.labelForField(self.prop_process_name).setVisible(False)
        
        # Mostrar según tipo
        if "Personalizado" in t:
            self.prop_command.setVisible(True)
            layout.labelForField(self.prop_command).setVisible(True)
        elif "Abrir Programa" in t:
            self.prop_program_path.setVisible(True)
            layout.labelForField(self.prop_program_path).setVisible(True)
        elif "Cerrar Programa" in t:
            self.prop_process_name.setVisible(True)
            layout.labelForField(self.prop_process_name).setVisible(True)

    def _setup_autosave_connections(self):
        """Conecta todos los widgets de entrada al trigger de autoguardado"""
        line_edits = [
            self.prop_label, self.prop_command, self.prop_program_path_edit, 
            self.prop_process_name, self.prop_output_var, self.prop_iterations,
            self.prop_iterable, self.prop_loop_condition, self.prop_loop_var,
            self.prop_duration_hours, self.prop_delay, self.prop_error_delay, 
            self.prop_condition, self.prop_db_host, self.prop_db_port, 
            self.prop_db_user, self.prop_db_password, self.prop_db_database
        ]
        for le in line_edits:
            le.textChanged.connect(self.trigger_autosave)
            
        combos = [
            self.prop_on_error, self.prop_script, self.prop_command_type,
            self.prop_loop_type, self.prop_db_operation, self.prop_note_color
        ]
        for cb in combos:
            cb.currentIndexChanged.connect(self.trigger_autosave)
            if cb.isEditable():
                cb.editTextChanged.connect(self.trigger_autosave)
                
        self.prop_workflow_path.currentIndexChanged.connect(self.trigger_autosave)
        self.prop_workflow_path.editTextChanged.connect(self.trigger_autosave)

        texts = [self.prop_db_query, self.prop_note_text]
        for t in texts:
            t.textChanged.connect(self.trigger_autosave)

    def trigger_autosave(self):
        """Reinicia el timer de autoguardado si no se está cargando el nodo"""
        if not self._loading_node:
            self.autosave_timer.start()

    def update_header_style(self, node_type: NodeType):
        """Actualiza el color del header según el tipo de nodo"""
        colors = {
            NodeType.ACTION: ("#3b82f6", "Acción"),
            NodeType.DECISION: ("#ec4899", "Decisión (Condicional)"),
            NodeType.LOOP: ("#8b5cf6", "Bucle (Loop)"),
            NodeType.DATABASE: ("#eab308", "Base de Datos"),
            NodeType.ANNOTATION: ("#64748b", "Nota / Anotación"),
            NodeType.DELAY: ("#f97316", "Delay / Retraso"),
            NodeType.START: ("#10b981", "Punto Inicio"),
            NodeType.END: ("#ef4444", "Punto Fin"),
            NodeType.WORKFLOW: ("#a855f7", "Sub-Workflow")
        }
        color_val, type_label = colors.get(node_type, ("#3b82f6", "Propiedades"))
        self.type_title.setText(type_label)
        self.type_header.setStyleSheet(f"""
            #TypeHeader {{
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                background-color: {color_val};
            }}
        """)

    def load_node(self, node: Node):
        """Carga los datos de un nodo en el formulario"""
        self._loading_node = True
        self.current_node = node
        
        # Actualizar color del header
        self.update_header_style(node.type)
        
        # Ocultar todos primero
        self.input_widgets = [
            self.script_container, self.prop_command_type, self.prop_command, self.prop_program_path, 
            self.prop_process_name, self.prop_output_var, self.loop_container,
            self.prop_delay, self.prop_error_delay, self.prop_condition, 
            self.db_group, self.note_group, self.wf_container
        ]
        layout = self.config_group.layout()
        for w in self.input_widgets:
            w.setVisible(False)
            lbl = layout.labelForField(w)
            if lbl: lbl.setVisible(False)
            
        # Limpiar valores por defecto
        self.prop_command.setText("")
        self.prop_program_path_edit.setText("")
        self.prop_process_name.setText("")
        self.prop_output_var.setText("")
        self.prop_condition.setText("")
        self.prop_iterations.setText("1")
        self.prop_iterable.setText("")
        self.prop_loop_condition.setText("")
        self.prop_loop_var.setText("item")
        self.prop_delay.setText("5")
        self.prop_error_delay.setText("0")
        self.prop_workflow_path.setCurrentText("")

        # Llenar datos comunes
        self.prop_id.setText(node.id)
        self.prop_label.setText(node.label)
        self.prop_type.setText(node.type.value)
        self.prop_on_error.setCurrentText(getattr(node, 'on_error', 'stop'))
        
        t = node.type
        
        if t == NodeType.ACTION or t == NodeType.LOOP:
            has_script = hasattr(node, 'script') and node.script
            is_command = False
            if hasattr(node, 'command_type') and node.command_type != "custom" and node.command_type:
                 is_command = True
            elif hasattr(node, 'command') and node.command:
                 is_command = True
            
            if is_command:
                ctype = getattr(node, 'command_type', 'custom') or 'custom'
                type_map = {
                    "custom": "Comando Personalizado",
                    "desktop": "Mostrar Escritorio",
                    "open": "Abrir Programa",
                    "close": "Cerrar Programa"
                }
                combo_text = type_map.get(ctype, "Comando Personalizado")
                self.prop_command_type.setCurrentText(combo_text)
                
                self.prop_command.setText(getattr(node, 'command', ''))
                self.prop_program_path_edit.setText(getattr(node, 'program_path', ''))
                self.prop_process_name.setText(getattr(node, 'process_name', ''))
                
                self._show_field(self.prop_command_type)
                self.update_command_fields()
            else:
                 self._show_field(self.script_container)
                 if hasattr(node, 'script'):
                    self.prop_script.setCurrentText(node.script)
            
            if t == NodeType.ACTION:
                self._show_field(self.prop_output_var)
                self.prop_output_var.setText(getattr(node, 'output_variable', ''))
                
        if t == NodeType.LOOP:
             self._show_field(self.loop_container)
             ltype = getattr(node, 'loop_type', 'count')
             ltype_map = {'count': 0, 'list': 1, 'while': 2, 'timed': 3, 'infinite': 4}
             self.prop_loop_type.setCurrentIndex(ltype_map.get(ltype, 0))
             
             self.prop_iterations.setText(str(getattr(node, 'iterations', '1')))
             self.prop_iterable.setText(getattr(node, 'iterable', ''))
             self.prop_loop_condition.setText(getattr(node, 'condition', ''))
             self.prop_loop_var.setText(getattr(node, 'loop_var', 'item'))
             self.prop_duration_hours.setText(str(getattr(node, 'duration_hours', 1.0)))
             
             self._show_field(self.wf_container)
             if self.prop_workflow_path.count() == 0:
                 self.load_workflows()
             self.prop_workflow_path.setCurrentText(getattr(node, 'workflow_path', ''))
             
             self._show_field(self.prop_error_delay)
             self.prop_error_delay.setText(str(getattr(node, 'error_delay', 0)))
             self.update_loop_fields()
         
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
                 c_map = {"#ffffcc": "Amarillo", "#cce5ff": "Azul", "#ffccf2": "Rosa", "#ccffcc": "Verde"}
                 self.prop_note_color.setCurrentText(c_map.get(color, "Amarillo"))
             except:
                 pass

        if t == NodeType.WORKFLOW:
              self._show_field(self.wf_container)
              if self.prop_workflow_path.count() == 0:
                  self.load_workflows()
              if hasattr(node, 'workflow_path'):
                  self.prop_workflow_path.setCurrentText(node.workflow_path)
                  
        self._loading_node = False
        self.setVisible(True)

    def _show_field(self, widget):
        widget.setVisible(True)
        lbl = self.config_group.layout().labelForField(widget)
        if lbl: lbl.setVisible(True)

    def apply_changes(self):
        """Recoge datos de la UI y los aplica al nodo (Autoguardado)"""
        if not self.current_node or self._loading_node:
            return
            
        node = self.current_node
        node.label = self.prop_label.text()
        node.on_error = self.prop_on_error.currentText()
        
        t = node.type
        if t == NodeType.ACTION:
            ctype_txt = self.prop_command_type.currentText()
            ctype_map = {
                "Comando Personalizado": "custom",
                "Mostrar Escritorio": "desktop",
                "Abrir Programa": "open",
                "Cerrar Programa": "close"
            }
            ctype_val = ctype_map.get(ctype_txt, "custom")
            
            node.command_type = ctype_val
            node.program_path = self.prop_program_path_edit.text().strip()
            node.process_name = self.prop_process_name.text().strip()
            
            if self.script_container.isVisible():
                node.script = self.prop_script.currentText()
                node.command = ""
                node.command_type = ""
            elif ctype_val == "custom":
                if self.prop_command.text():
                    node.command = self.prop_command.text()
                    node.script = "" 
                else:
                    node.script = self.prop_script.currentText()
                    node.command = ""
            elif ctype_val == "desktop":
                node.command = 'powershell -command "(new-object -com shell.application).minimizeall()"'
                node.script = ""
            elif ctype_val == "open":
                path = node.program_path
                if path:
                    node.command = f'start "" "{path}"'
                node.script = ""
            elif ctype_val == "close":
                proc = node.process_name
                if proc:
                    node.command = f'taskkill /IM "{proc}" /F'
                node.script = ""
            
            node.output_variable = self.prop_output_var.text().strip()

        if t == NodeType.LOOP:
             node.script = self.prop_script.currentText()
             ltype_txt = self.prop_loop_type.currentText()
             if "Count" in ltype_txt:    node.loop_type = "count"
             elif "List" in ltype_txt:   node.loop_type = "list"
             elif "While" in ltype_txt:  node.loop_type = "while"
             elif "Timed" in ltype_txt:  node.loop_type = "timed"
             elif "Infinite" in ltype_txt: node.loop_type = "infinite"
             
             node.iterations = self.prop_iterations.text()
             node.iterable = self.prop_iterable.text()
             node.condition = self.prop_loop_condition.text()
             node.loop_var = self.prop_loop_var.text()
             node.workflow_path = self.prop_workflow_path.currentText().strip()
             
             try:
                 node.duration_hours = float(self.prop_duration_hours.text())
             except:
                 node.duration_hours = 1.0
             
             try:
                 node.error_delay = int(self.prop_error_delay.text())
             except:
                 node.error_delay = 0
            
        if t == NodeType.DELAY:
            try:
                node.delay_seconds = int(self.prop_delay.text())
            except:
                node.delay_seconds = 5
            
        if t == NodeType.DECISION:
            node.condition = self.prop_condition.text()
            
        if t == NodeType.DATABASE:
            node.host = self.prop_db_host.text()
            try:
                node.port = int(self.prop_db_port.text())
            except:
                node.port = 3306
            node.user = self.prop_db_user.text()
            node.password = self.prop_db_password.text()
            node.database = self.prop_db_database.text()
            node.query = self.prop_db_query.toPlainText()
            node.operation = self.prop_db_operation.currentText()
            
        if t == NodeType.ANNOTATION:
            node.text = self.prop_note_text.toPlainText()
            color_txt = self.prop_note_color.currentText()
            color_map = {"Amarillo": "#ffffcc", "Azul": "#cce5ff", "Rosa": "#ffccf2", "Verde": "#ccffcc"}
            node.color = color_map.get(color_txt, "#ffffcc")

        if t == NodeType.WORKFLOW:
            node.workflow_path = self.prop_workflow_path.currentText().strip()
            
        self.node_updated.emit(self.current_node)

    def request_delete(self):
        """Emite señal solicitando borrar el nodo"""
        if self.current_node:
            self.node_deleted.emit(self.current_node)

    def browse_script(self):
        """Abre buscador de archivos para scripts Python"""
        start_dir = "recordings"
        if not os.path.exists(start_dir):
            os.makedirs(start_dir, exist_ok=True)
            
        filename, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Script Python", start_dir, "Scripts Python (*.py)"
        )
        if filename:
            path = Path(filename)
            try:
                rel_path = path.relative_to(Path.cwd())
                path_str = str(rel_path)
            except ValueError:
                path_str = str(path)
                
            self.prop_script.setCurrentText(path_str)

    def browse_workflow(self):
        """Abre buscador de archivos para sub-workflows"""
        start_dir = "workflows"
        if not os.path.exists(start_dir):
            os.makedirs(start_dir, exist_ok=True)
            
        filename, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Workflow", start_dir, "Workflow Files (*.json)"
        )
        if filename:
            path = Path(filename)
            try:
                rel_path = path.relative_to(Path.cwd())
                path_str = str(rel_path)
            except ValueError:
                path_str = str(path)
                
            self.prop_workflow_path.setCurrentText(path_str)

    def browse_program(self):
        """Abre buscador de archivos para ejecutables de sistema"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Ejecutable", "", "Ejecutables (*.exe);;Todos (*.*)"
        )
        if filename:
            self.prop_program_path_edit.setText(filename)

    def load_scripts(self):
        """Escanea la carpeta recordings recursivamente buscando scripts"""
        self.prop_script.clear()
        try:
            path = Path("recordings")
            if path.exists():
                for file in path.glob("**/*.py"):
                    try:
                        rel = file.relative_to(Path.cwd())
                        self.prop_script.addItem(str(rel))
                    except:
                        self.prop_script.addItem(str(file))
        except Exception:
            pass

    def load_workflows(self):
        """Carga los workflows JSON disponibles"""
        self.prop_workflow_path.clear()
        try:
            folders = ["workflows", "rpa_framework/workflows"]
            for f in folders:
                path = Path(f)
                if path.exists():
                    for file in path.glob("**/*.json"):
                        try:
                            rel = file.relative_to(Path.cwd())
                            self.prop_workflow_path.addItem(str(rel))
                        except:
                            self.prop_workflow_path.addItem(str(file))
        except Exception:
            pass
