from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
                             QComboBox, QGroupBox, QPushButton, QHBoxLayout, 
                             QLabel, QStyle, QPlainTextEdit, QMessageBox, QFileDialog)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
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
        self._loading_node = False
        
        # Timer para guardado automático (debounce 500ms)
        self.autosave_timer = QTimer()
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(500)
        self.autosave_timer.timeout.connect(self.apply_changes)
        
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

        self.prop_on_error = QComboBox()
        self.prop_on_error.addItems(["stop", "continue"])
        form_layout.addRow("On Error:", self.prop_on_error)
        
        # --- Campos Especificos (Action/Loop) ---
        self.script_container = QWidget()
        script_layout = QHBoxLayout(self.script_container)
        script_layout.setContentsMargins(0,0,0,0)
        
        self.prop_script = QComboBox()
        self.prop_script.setEditable(True)
        self.prop_script.setPlaceholderText("Seleccionar o escribir script Python...")
        script_layout.addWidget(self.prop_script)
        
        btn_browse = QPushButton()
        btn_browse.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self.browse_script)
        script_layout.addWidget(btn_browse)
        
        form_layout.addRow("Script Python:", self.script_container)
        
        # Tipo de Comando (Predefinido o Custom)
        self.prop_command_type = QComboBox()
        self.prop_command_type.addItems([
            "Comando Personalizado",
            "Mostrar Escritorio",
            "Abrir Programa",
            "Cerrar Programa"
        ])
        self.prop_command_type.currentIndexChanged.connect(self.update_command_fields)
        form_layout.addRow("Tipo:", self.prop_command_type)
        
        self.prop_command = QLineEdit()
        self.prop_command.setPlaceholderText("Ej: echo 'Hello' >> log.txt")
        form_layout.addRow("Comando:", self.prop_command)
        
        self.prop_program_path = QWidget()
        program_path_layout = QHBoxLayout(self.prop_program_path)
        program_path_layout.setContentsMargins(0,0,0,0)
        
        self.prop_program_path_edit = QLineEdit()
        self.prop_program_path_edit.setPlaceholderText("Ej: C:\\Program Files\\MyApp\\app.exe")
        program_path_layout.addWidget(self.prop_program_path_edit)
        
        btn_browse_program = QPushButton()
        btn_browse_program.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        btn_browse_program.setFixedWidth(30)
        btn_browse_program.clicked.connect(self.browse_program)
        program_path_layout.addWidget(btn_browse_program)
        
        form_layout.addRow("Ruta Programa:", self.prop_program_path)
        
        self.prop_process_name = QLineEdit()
        self.prop_process_name.setPlaceholderText("Ej: notepad.exe, chrome.exe")
        form_layout.addRow("Nombre Proceso:", self.prop_process_name)

        self.prop_output_var = QLineEdit()
        self.prop_output_var.setPlaceholderText("Nombre variable (ej: resultado_texto)")
        form_layout.addRow("Guardar Salida en:", self.prop_output_var)
        
        self.loop_container = QWidget()
        loop_layout = QFormLayout(self.loop_container)
        loop_layout.setContentsMargins(0,0,0,0)
        
        self.prop_loop_type = QComboBox()
        self.prop_loop_type.addItems(["Count (N Veces)", "List (ForEach)", "While (Condición)"])
        self.prop_loop_type.currentIndexChanged.connect(self.update_loop_fields)
        loop_layout.addRow("Tipo Loop:", self.prop_loop_type)

        self.prop_iterations = QLineEdit()
        self.prop_iterations.setPlaceholderText("Ej: 5")
        loop_layout.addRow("Iteraciones:", self.prop_iterations)
        
        self.prop_iterable = QLineEdit()
        self.prop_iterable.setPlaceholderText("Ej: db_result")
        loop_layout.addRow("Lista (Variable):", self.prop_iterable)
        
        self.prop_loop_condition = QLineEdit()
        self.prop_loop_condition.setPlaceholderText("Ej: x < 10")
        loop_layout.addRow("Condición While:", self.prop_loop_condition)
        
        self.prop_loop_var = QLineEdit()
        self.prop_loop_var.setPlaceholderText("Ej: item")
        loop_layout.addRow("Variable Item:", self.prop_loop_var)

        form_layout.addRow(self.loop_container)
        
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
        
        # --- Conectar Señales para Autoguardado ---
        self._setup_autosave_connections()

        # --- Botones de Acción ---
        btn_layout = QHBoxLayout()
        
        self.btn_delete = QPushButton("Eliminar Nodo")
        self.btn_delete.setStyleSheet("background-color: #dc3545; color: white; padding: 6px; font-weight: bold;")
        self.btn_delete.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.btn_delete.clicked.connect(self.request_delete)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        # Cargar scripts iniciales
        self.load_scripts()
        
    def update_loop_fields(self):
        """Muestra u oculta campos de loop según el tipo"""
        t = self.prop_loop_type.currentText()
        # Ocultar todos primero (iter, iterable, cond)
        # Notas: iterotions en index 1, iterable en 2, condition en 3
        # Layouts son tricky para ocultar filas, mejor ocultar widgets
        
        # Iteraciones
        self.prop_iterations.setVisible("Count" in t)
        self.loop_container.layout().labelForField(self.prop_iterations).setVisible("Count" in t)
        
        # Lista
        self.prop_iterable.setVisible("List" in t)
        self.loop_container.layout().labelForField(self.prop_iterable).setVisible("List" in t)
        
        # Condicion
        self.prop_loop_condition.setVisible("While" in t)
        self.loop_container.layout().labelForField(self.prop_loop_condition).setVisible("While" in t)
    
    def update_command_fields(self):
        """Muestra u oculta campos de comando según el tipo"""
        t = self.prop_command_type.currentText()
        
        # Ocultar todos primero
        self.prop_command.setVisible(False)
        self.group.layout().labelForField(self.prop_command).setVisible(False)
        
        self.prop_program_path.setVisible(False)
        self.group.layout().labelForField(self.prop_program_path).setVisible(False)
        
        self.prop_process_name.setVisible(False)
        self.group.layout().labelForField(self.prop_process_name).setVisible(False)
        
        # Mostrar según tipo
        if "Personalizado" in t:
            self.prop_command.setVisible(True)
            self.group.layout().labelForField(self.prop_command).setVisible(True)
        elif "Abrir Programa" in t:
            self.prop_program_path.setVisible(True)
            self.group.layout().labelForField(self.prop_program_path).setVisible(True)
        elif "Cerrar Programa" in t:
            self.prop_process_name.setVisible(True)
            self.group.layout().labelForField(self.prop_process_name).setVisible(True)
        # "Mostrar Escritorio" no necesita campos adicionales


    def _setup_autosave_connections(self):
        """Conecta todos los widgets de entrada al trigger de autoguardado"""
        # LineEdits
        line_edits = [
            self.prop_label, self.prop_command, self.prop_program_path_edit, 
            self.prop_process_name, self.prop_output_var, self.prop_iterations,
            self.prop_iterable, self.prop_loop_condition, self.prop_loop_var,
            self.prop_delay, self.prop_condition, self.prop_db_host,
            self.prop_db_port, self.prop_db_user, self.prop_db_password,
            self.prop_db_database
        ]
        for le in line_edits:
            le.textChanged.connect(self.trigger_autosave)
            
        # ComboBoxes
        combos = [
            self.prop_on_error, self.prop_script, self.prop_command_type,
            self.prop_loop_type, self.prop_db_operation, self.prop_note_color
        ]
        for cb in combos:
            cb.currentIndexChanged.connect(self.trigger_autosave)
            if cb.isEditable():
                cb.editTextChanged.connect(self.trigger_autosave)
                
        # PlainTextEdits
        texts = [self.prop_db_query, self.prop_note_text]
        for t in texts:
            t.textChanged.connect(self.trigger_autosave)

    def trigger_autosave(self):
        """Reinicia el timer de autoguardado"""
        if not self._loading_node:
            self.autosave_timer.start()

    def load_node(self, node: Node):
        """Carga los datos de un nodo en el formulario"""
        self._loading_node = True # Bloquear autoguardado durante carga
        self.current_node = node
        
        # 1. Resetear visibilidad
        self.input_widgets = [
            self.script_container, self.prop_command_type, self.prop_command, self.prop_program_path, 
            self.prop_process_name, self.prop_output_var, self.loop_container, self.prop_delay, 
            self.prop_condition, self.db_group, self.note_group
        ]
        for w in self.input_widgets:
            w.setVisible(False)
            if self.group.layout().labelForField(w):
                self.group.layout().labelForField(w).setVisible(False)

        # 1.5. Limpiar campos para evitar "leaks" de un nodo a otro
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

        # 2. Llenar datos comunes
        self.prop_id.setText(node.id)
        self.prop_label.setText(node.label)
        self.prop_type.setText(node.type.value)
        self.prop_on_error.setCurrentText(getattr(node, 'on_error', 'stop'))
        
        # 3. Llenar y mostrar especificos
        t = node.type
        
        if t == NodeType.ACTION or t == NodeType.LOOP:
            # Lógica para mostrar Script o Comando
            has_script = hasattr(node, 'script') and node.script
            
            # Determinar qué mostrar basado en si es comando o script
            is_command = False
            if hasattr(node, 'command_type') and node.command_type != "custom" and node.command_type:
                 # Si tiene un tipo definido que no es custom, es comando
                 is_command = True
            elif hasattr(node, 'command') and node.command:
                 is_command = True
            
            # IMPORTANTE: Si es script vacio y no es comando explicito, asumimos script mode por defecto en UI nueva
            
            if is_command:
                # Cargar valores específicos de comando
                ctype = getattr(node, 'command_type', 'custom')
                if not ctype: ctype = 'custom'
                
                # Mapear valor interno a texto del combo
                type_map = {
                    "custom": "Comando Personalizado",
                    "desktop": "Mostrar Escritorio",
                    "open": "Abrir Programa",
                    "close": "Cerrar Programa"
                }
                # Buscamos el texto correspondiente o usamos Custom
                combo_text = type_map.get(ctype, "Comando Personalizado")
                self.prop_command_type.setCurrentText(combo_text)
                
                self.prop_command.setText(getattr(node, 'command', ''))
                self.prop_program_path_edit.setText(getattr(node, 'program_path', ''))
                self.prop_process_name.setText(getattr(node, 'process_name', ''))
                
                # Mostrar widgets
                self._show_field(self.prop_command_type)
                self.update_command_fields() # Esto se encarga de mostrar los campos correctos segun el tipo
                
            else:
                 # Modo Script
                 self._show_field(self.script_container)
                 if hasattr(node, 'script'):
                    self.prop_script.setCurrentText(node.script)
            
            # Mostrar campo output variable para Action
            if t == NodeType.ACTION:
                self._show_field(self.prop_output_var)
                self.prop_output_var.setText(getattr(node, 'output_variable', ''))
                
        if t == NodeType.LOOP:
             self._show_field(self.loop_container)
             
             # Mapeo de valores
             ltype = getattr(node, 'loop_type', 'count')
             idx = 0
             if ltype == 'list': idx = 1
             elif ltype == 'while': idx = 2
             self.prop_loop_type.setCurrentIndex(idx)
             
             self.prop_iterations.setText(str(getattr(node, 'iterations', '1')))
             self.prop_iterable.setText(getattr(node, 'iterable', ''))
             self.prop_loop_condition.setText(getattr(node, 'condition', ''))
             self.prop_loop_var.setText(getattr(node, 'loop_var', 'item'))
             
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
                
        self._loading_node = False # Desbloquear
        self.setVisible(True)

    def _show_field(self, widget):
        widget.setVisible(True)
        lbl = self.group.layout().labelForField(widget)
        if lbl: lbl.setVisible(True)

    def apply_changes(self):
        """Recoge datos y emite señal de actualización (Autoguardado)"""
        if not self.current_node or self._loading_node:
            return
            
        # Actualizar objeto nodo (en memoria) desde UI
        node = self.current_node
        node.label = self.prop_label.text()
        node.on_error = self.prop_on_error.currentText()
        
        t = node.type
        if t == NodeType.ACTION:
            # Recuperar tipo de comando
            ctype_txt = self.prop_command_type.currentText()
            ctype_map = {
                "Comando Personalizado": "custom",
                "Mostrar Escritorio": "desktop",
                "Abrir Programa": "open",
                "Cerrar Programa": "close"
            }
            ctype_val = ctype_map.get(ctype_txt, "custom")
            
            # Guardar metadatos en el nodo (para recuperar estado UI)
            node.command_type = ctype_val
            node.program_path = self.prop_program_path_edit.text().strip()
            node.process_name = self.prop_process_name.text().strip()
            
            # Construir el comando real que ejecutará el WorkflowExecutor
            if self.script_container.isVisible():
                # Modo Script explícito
                node.script = self.prop_script.currentText()
                node.command = ""
                node.command_type = ""
            elif ctype_val == "custom":
                # Si el campo comando esta visible y tiene texto, usarlo
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
                    # Usar start para no bloquear (o call para bloquear, start es mejor para apps GUI)
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
             # Map combo text to internal type
             ltype_txt = self.prop_loop_type.currentText()
             if "Count" in ltype_txt: node.loop_type = "count"
             elif "List" in ltype_txt: node.loop_type = "list"
             elif "While" in ltype_txt: node.loop_type = "while"
             
             node.iterations = self.prop_iterations.text()
             node.iterable = self.prop_iterable.text()
             node.condition = self.prop_loop_condition.text()
             node.loop_var = self.prop_loop_var.text()
            
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
            
        # Emitir señal para que el controlador sea notificado del cambio
        self.node_updated.emit(node)
        # QMessageBox remoto eliminado para permitir autoguardado fluido

    def browse_program(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Seleccionar Programa",  "", "Ejecutables (*.exe);;Todos (*.*)")
        if fname:
            self.prop_program_path_edit.setText(fname)

    def request_delete(self):
        if self.current_node:
            reply = QMessageBox.question(self, "Eliminar", f"¿Eliminar nodo {self.current_node.label}?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.node_deleted.emit(self.current_node)

    def load_scripts(self):
        # Intentar determinar la carpeta de recordings de forma robusta
        script_dir = Path("recordings")
        if not script_dir.exists():
             script_dir = Path("rpa_framework/recordings")
        
        if not script_dir.exists():
             # Fallback final a cwd por si acaso
             script_dir = Path.cwd()
        
        if script_dir.exists():
            # Recursive search
            files = []
            for f in script_dir.rglob("*.py"):
                # Make path relative to script_dir for cleaner display
                try:
                    rel_path = f.relative_to(script_dir)
                    files.append(str(rel_path))
                except ValueError:
                    files.append(f.name)
            
            self.prop_script.clear()
            self.prop_script.addItems(sorted(files))

    def browse_script(self):
        # Determinar directorio inicial
        start_dir = "recordings"
        if not os.path.exists(start_dir):
            start_dir = "rpa_framework/recordings"
        if not os.path.exists(start_dir):
            start_dir = "."

        fname, _ = QFileDialog.getOpenFileName(self, "Seleccionar Script", start_dir, "Python (*.py)")
        if fname:
            path = Path(fname)
            # Intentar hacerlo relativo a recordings para consistencia
            try:
                # Buscar dónde está 'recordings' en la ruta absoluta
                abs_recordings = Path(os.path.abspath(start_dir))
                if path.is_absolute() and abs_recordings in path.parents or path.is_relative_to(abs_recordings):
                    rel_path = path.relative_to(abs_recordings)
                    self.prop_script.setCurrentText(str(rel_path))
                else:
                    self.prop_script.setCurrentText(str(path))
            except Exception:
                # Si falla lo relativo (ej: disco diferente), usar nombre o path completo
                self.prop_script.setCurrentText(str(path))
