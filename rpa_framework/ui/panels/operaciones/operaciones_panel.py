"""
Panel de Operaciones moderno (ModernOperacionesPanel) con telemetría en tiempo real y 2 columnas.
Extraído de main_gui_final.py.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QSpinBox, QComboBox, QDoubleSpinBox, QProgressBar,
    QTextEdit, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

from .styles_and_tiles import ActionTile
from .operaciones_actions_mixin import OperacionesActionsMixin


class ModernOperacionesPanel(OperacionesActionsMixin, QWidget):
    """Panel de Operaciones con diseño moderno, intuitivo, telemetría en tiempo real y 2 columnas."""

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.worker = None
        self.is_bg_running = False
        self._current_is_loop = False
        self.start_time = None
        
        self.init_ui()
        
        # Timer para sincronizar estado con el servicio de Telegram en background
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self.check_background_state)
        self.state_timer.start(2000) # Chequeo cada 2 segundos
        
        # Timer para actualizar tiempo transcurrido
        self.duration_timer = QTimer(self)
        self.duration_timer.timeout.connect(self.update_elapsed_time)
        
    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 14, 16, 16)
        root_layout.setSpacing(12)
        
        def apply_card_shadow(widget):
            shadow = QGraphicsDropShadowEffect(widget)
            shadow.setBlurRadius(14)
            shadow.setXOffset(0)
            shadow.setYOffset(3)
            shadow.setColor(QColor(15, 23, 42, 18))
            widget.setGraphicsEffect(shadow)

        # --------------------------------------------------------------------
        # 1. HEADER BANNER
        # --------------------------------------------------------------------
        header_box = QFrame()
        header_box.setObjectName("ops_header_box")
        apply_card_shadow(header_box)
        
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(16, 10, 16, 10)
        
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_title = QLabel("⚡ Centro de Control de Operaciones")
        lbl_title.setStyleSheet("font-size: 13pt; font-weight: 800; color: #0f172a; background: transparent;")
        lbl_sub = QLabel("Monitoreo en tiempo real, automatización cíclica y control de flujos RPA")
        lbl_sub.setStyleSheet("font-size: 9pt; color: #64748b; background: transparent;")
        title_vbox.addWidget(lbl_title)
        title_vbox.addWidget(lbl_sub)
        h_layout.addLayout(title_vbox)
        
        h_layout.addStretch()
        
        self.badge_system = QLabel("● Sistema Listo")
        self.badge_system.setStyleSheet("""
            background-color: #ecfdf5;
            color: #059669;
            border: 1px solid #a7f3d0;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 9pt;
            font-weight: 700;
        """)
        h_layout.addWidget(self.badge_system)
        
        root_layout.addWidget(header_box)

        # --------------------------------------------------------------------
        # 2. CONTENIDO EN 2 COLUMNAS (SPLIT LAYOUT)
        # --------------------------------------------------------------------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)
        
        # COLUMNA IZQUIERDA: ACCIONES Y CONFIGURACIÓN (STRETCH 53%)
        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        
        # --- TARJETA 1: ACCIONES RÁPIDAS ---
        card_acciones = QFrame()
        card_acciones.setObjectName("ops_card")
        apply_card_shadow(card_acciones)
        
        layout_acciones = QVBoxLayout(card_acciones)
        layout_acciones.setSpacing(10)
        layout_acciones.setContentsMargins(16, 14, 16, 14)
        
        card_acc_head = QHBoxLayout()
        lbl_acc_title = QLabel("⚡ Acciones Rápidas")
        lbl_acc_title.setStyleSheet("font-size: 11pt; font-weight: 700; color: #1e293b;")
        lbl_acc_badge = QLabel("Ejecución Directa")
        lbl_acc_badge.setStyleSheet("background-color: #eff6ff; color: #2563eb; font-size: 8pt; font-weight: 600; padding: 3px 8px; border-radius: 6px;")
        card_acc_head.addWidget(lbl_acc_title)
        card_acc_head.addStretch()
        card_acc_head.addWidget(lbl_acc_badge)
        layout_acciones.addLayout(card_acc_head)
        
        lbl_acc_sub = QLabel("Haga clic en una acción para iniciar su ejecución de forma directa:")
        lbl_acc_sub.setStyleSheet("font-size: 9pt; color: #64748b; margin-bottom: 2px;")
        layout_acciones.addWidget(lbl_acc_sub)
        
        self.btn_inicio = ActionTile(
            "Inicio Completo (Flujo Principal)",
            "Ejecuta el flujo maestro automatizado (Sub_work.json)",
            icon="🚀",
            theme="emerald"
        )
        self.btn_inicio.clicked.connect(self.ejecutar_inicio_completo)
        self.btn_inicio.setToolTip("Inicia el flujo completo maestro del workflow Sub_work.json")
        layout_acciones.addWidget(self.btn_inicio)
        
        self.btn_pega = ActionTile(
            "Solo Pega en Integra",
            "Validación y procesamiento directo de PACS (pacs.json)",
            icon="📋",
            theme="blue"
        )
        self.btn_pega.clicked.connect(self.ejecutar_pega_integra)
        self.btn_pega.setToolTip("Inicia el workflow pacs.json")
        layout_acciones.addWidget(self.btn_pega)
        
        self.btn_rehabilitar = ActionTile(
            "Rehabilitar Último Registro",
            "Restaura el estado a 'En Proceso' en la BD MySQL",
            icon="🔄",
            theme="amber"
        )
        self.btn_rehabilitar.clicked.connect(self.rehabilitar_ultimo_registro)
        self.btn_rehabilitar.setToolTip("Cambia el estado del último registro de la base de datos a 'En Proceso'")
        layout_acciones.addWidget(self.btn_rehabilitar)
        
        left_column.addWidget(card_acciones)
        
        # --- TARJETA 2: CONFIGURACIÓN DE LOOP CONTINUO ---
        card_loop = QFrame()
        card_loop.setObjectName("ops_card")
        apply_card_shadow(card_loop)
        
        layout_loop = QVBoxLayout(card_loop)
        layout_loop.setSpacing(10)
        layout_loop.setContentsMargins(16, 14, 16, 14)
        
        card_loop_head = QHBoxLayout()
        lbl_loop_title = QLabel("🔁 Ejecución Continua (Loop)")
        lbl_loop_title.setStyleSheet("font-size: 11pt; font-weight: 700; color: #1e293b;")
        lbl_loop_badge = QLabel("Automatización Cíclica")
        lbl_loop_badge.setStyleSheet("background-color: #f5f3ff; color: #7c3aed; font-size: 8pt; font-weight: 600; padding: 3px 8px; border-radius: 6px;")
        card_loop_head.addWidget(lbl_loop_title)
        card_loop_head.addStretch()
        card_loop_head.addWidget(lbl_loop_badge)
        layout_loop.addLayout(card_loop_head)
        
        mode_row = QHBoxLayout()
        lbl_mode = QLabel("Modo:")
        lbl_mode.setStyleSheet("font-weight: 600; color: #334155; min-width: 50px;")
        self.combo_loop_type = QComboBox()
        self.combo_loop_type.addItems(["🔢 Por Cantidad de Ciclos", "⏱️ Por Tiempo Programado (Horas)", "♾️ Continuo Infinito"])
        self.combo_loop_type.setMinimumHeight(34)
        self.combo_loop_type.currentIndexChanged.connect(self.actualizar_visibilidad_loop)
        mode_row.addWidget(lbl_mode)
        mode_row.addWidget(self.combo_loop_type, stretch=1)
        layout_loop.addLayout(mode_row)
        
        self.container_count = QWidget()
        layout_count = QVBoxLayout(self.container_count)
        layout_count.setContentsMargins(0, 0, 0, 0)
        layout_count.setSpacing(6)
        
        presets_count_layout = QHBoxLayout()
        presets_count_layout.setSpacing(4)
        lbl_presets = QLabel("Atajos:")
        lbl_presets.setStyleSheet("font-size: 8.5pt; color: #64748b; font-weight: 600; margin-right: 2px;")
        presets_count_layout.addWidget(lbl_presets)
        
        for val in [1, 5, 10, 25, 50, 100]:
            btn_p = QPushButton(f"{val}x")
            btn_p.setProperty("cssClass", "preset_chip")
            btn_p.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_p.clicked.connect(lambda checked, v=val: self.spin_iterations.setValue(v))
            presets_count_layout.addWidget(btn_p)
        presets_count_layout.addStretch()
        layout_count.addLayout(presets_count_layout)
        
        row_spin_c = QHBoxLayout()
        lbl_spin_c = QLabel("Reiteraciones totales:")
        lbl_spin_c.setStyleSheet("color: #475569;")
        self.spin_iterations = QSpinBox()
        self.spin_iterations.setRange(1, 9999)
        self.spin_iterations.setValue(5)
        self.spin_iterations.setMinimumHeight(32)
        row_spin_c.addWidget(lbl_spin_c)
        row_spin_c.addWidget(self.spin_iterations, stretch=1)
        layout_count.addLayout(row_spin_c)
        layout_loop.addWidget(self.container_count)
        
        self.container_timed = QWidget()
        layout_timed = QVBoxLayout(self.container_timed)
        layout_timed.setContentsMargins(0, 0, 0, 0)
        layout_timed.setSpacing(6)
        
        presets_time_layout = QHBoxLayout()
        presets_time_layout.setSpacing(4)
        lbl_p_time = QLabel("Atajos:")
        lbl_p_time.setStyleSheet("font-size: 8.5pt; color: #64748b; font-weight: 600; margin-right: 2px;")
        presets_time_layout.addWidget(lbl_p_time)
        
        for label, val in [("30 min", 0.5), ("1h", 1.0), ("2h", 2.0), ("4h", 4.0), ("8h", 8.0)]:
            btn_t = QPushButton(label)
            btn_t.setProperty("cssClass", "preset_chip")
            btn_t.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_t.clicked.connect(lambda checked, v=val: self.spin_duration.setValue(v))
            presets_time_layout.addWidget(btn_t)
        presets_time_layout.addStretch()
        layout_timed.addLayout(presets_time_layout)
        
        row_spin_t = QHBoxLayout()
        lbl_spin_t = QLabel("Duración máxima:")
        lbl_spin_t.setStyleSheet("color: #475569;")
        self.spin_duration = QDoubleSpinBox()
        self.spin_duration.setRange(0.1, 72.0)
        self.spin_duration.setValue(1.0)
        self.spin_duration.setSuffix(" horas")
        self.spin_duration.setMinimumHeight(32)
        row_spin_t.addWidget(lbl_spin_t)
        row_spin_t.addWidget(self.spin_duration, stretch=1)
        layout_timed.addLayout(row_spin_t)
        layout_loop.addWidget(self.container_timed)
        self.container_timed.hide()
        
        row_delay = QHBoxLayout()
        lbl_delay = QLabel("Pausa tras error:")
        lbl_delay.setStyleSheet("color: #475569;")
        self.spin_error_delay = QSpinBox()
        self.spin_error_delay.setRange(0, 3600)
        self.spin_error_delay.setValue(0)
        self.spin_error_delay.setSuffix(" seg")
        self.spin_error_delay.setMinimumHeight(32)
        row_delay.addWidget(lbl_delay)
        row_delay.addWidget(self.spin_error_delay, stretch=1)
        
        for d_label, d_val in [("0s", 0), ("15s", 15), ("30s", 30), ("60s", 60)]:
            btn_d = QPushButton(d_label)
            btn_d.setProperty("cssClass", "preset_chip")
            btn_d.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_d.clicked.connect(lambda checked, v=d_val: self.spin_error_delay.setValue(v))
            row_delay.addWidget(btn_d)
            
        layout_loop.addLayout(row_delay)
        
        self.btn_loop = QPushButton("🚀  Iniciar Flujo Continuo (Loop)")
        self.btn_loop.setObjectName("btn_action_loop")
        self.btn_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_loop.setMinimumHeight(44)
        self.btn_loop.clicked.connect(self.ejecutar_loop_reiteraciones)
        layout_loop.addWidget(self.btn_loop)
        
        left_column.addWidget(card_loop)
        left_column.addStretch()
        
        content_layout.addLayout(left_column, stretch=53)

        # COLUMNA DERECHA: TELEMETRÍA, MONITOR Y LOGS (STRETCH 48%)
        right_column = QVBoxLayout()
        right_column.setSpacing(12)
        
        # --- TARJETA 3: TELEMETRÍA Y ESTADO EN VIVO ---
        card_telemetry = QFrame()
        card_telemetry.setObjectName("ops_card")
        apply_card_shadow(card_telemetry)
        
        layout_telemetry = QVBoxLayout(card_telemetry)
        layout_telemetry.setSpacing(10)
        layout_telemetry.setContentsMargins(16, 14, 16, 14)
        
        card_telem_head = QHBoxLayout()
        lbl_telem_title = QLabel("📡 Telemetría y Estado en Vivo")
        lbl_telem_title.setStyleSheet("font-size: 11pt; font-weight: 700; color: #1e293b;")
        card_telem_head.addWidget(lbl_telem_title)
        card_telem_head.addStretch()
        layout_telemetry.addLayout(card_telem_head)
        
        self.status_banner = QFrame()
        self.status_banner.setStyleSheet("""
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 4px;
        """)
        layout_banner = QHBoxLayout(self.status_banner)
        layout_banner.setContentsMargins(10, 8, 10, 8)
        
        self.lbl_status_icon = QLabel("⚪")
        self.lbl_status_icon.setStyleSheet("font-size: 13pt;")
        self.lbl_status_val = QLabel("Sistema en Reposo (Listo para operar)")
        self.lbl_status_val.setStyleSheet("font-size: 10pt; font-weight: 700; color: #475569;")
        
        layout_banner.addWidget(self.lbl_status_icon)
        layout_banner.addWidget(self.lbl_status_val)
        layout_banner.addStretch()
        layout_telemetry.addWidget(self.status_banner)
        
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(8)
        
        self.tile_time = QFrame()
        self.tile_time.setProperty("cssClass", "kpi_tile")
        l_t1 = QVBoxLayout(self.tile_time)
        l_t1.setContentsMargins(10, 8, 10, 8)
        l_t1.setSpacing(2)
        lbl_t1_h = QLabel("⏱️ Tiempo Transcurrido")
        lbl_t1_h.setStyleSheet("font-size: 8pt; color: #64748b; font-weight: 600;")
        self.lbl_time = QLabel("00:00:00")
        self.lbl_time.setStyleSheet("font-family: 'Consolas', monospace; font-size: 13pt; font-weight: 800; color: #0f172a;")
        l_t1.addWidget(lbl_t1_h)
        l_t1.addWidget(self.lbl_time)
        kpi_grid.addWidget(self.tile_time, 0, 0)
        
        self.tile_wf = QFrame()
        self.tile_wf.setProperty("cssClass", "kpi_tile")
        l_t2 = QVBoxLayout(self.tile_wf)
        l_t2.setContentsMargins(10, 8, 10, 8)
        l_t2.setSpacing(2)
        lbl_t2_h = QLabel("📋 Workflow en Curso")
        lbl_t2_h.setStyleSheet("font-size: 8pt; color: #64748b; font-weight: 600;")
        self.lbl_active_wf = QLabel("Ninguno")
        self.lbl_active_wf.setStyleSheet("font-size: 10pt; font-weight: 700; color: #334155;")
        l_t2.addWidget(lbl_t2_h)
        l_t2.addWidget(self.lbl_active_wf)
        kpi_grid.addWidget(self.tile_wf, 0, 1)
        
        self.tile_mode = QFrame()
        self.tile_mode.setProperty("cssClass", "kpi_tile")
        l_t3 = QVBoxLayout(self.tile_mode)
        l_t3.setContentsMargins(10, 8, 10, 8)
        l_t3.setSpacing(2)
        lbl_t3_h = QLabel("🔁 Modo de Ejecución")
        lbl_t3_h.setStyleSheet("font-size: 8pt; color: #64748b; font-weight: 600;")
        self.lbl_active_mode = QLabel("Individual")
        self.lbl_active_mode.setStyleSheet("font-size: 10pt; font-weight: 700; color: #334155;")
        l_t3.addWidget(lbl_t3_h)
        l_t3.addWidget(self.lbl_active_mode)
        kpi_grid.addWidget(self.tile_mode, 1, 0)
        
        self.tile_origin = QFrame()
        self.tile_origin.setProperty("cssClass", "kpi_tile")
        l_t4 = QVBoxLayout(self.tile_origin)
        l_t4.setContentsMargins(10, 8, 10, 8)
        l_t4.setSpacing(2)
        lbl_t4_h = QLabel("📡 Canal de Disparo")
        lbl_t4_h.setStyleSheet("font-size: 8pt; color: #64748b; font-weight: 600;")
        self.lbl_active_channel = QLabel("Panel Local")
        self.lbl_active_channel.setStyleSheet("font-size: 10pt; font-weight: 700; color: #334155;")
        l_t4.addWidget(lbl_t4_h)
        l_t4.addWidget(self.lbl_active_channel)
        kpi_grid.addWidget(self.tile_origin, 1, 1)
        
        layout_telemetry.addLayout(kpi_grid)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("ops_progress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout_telemetry.addWidget(self.progress_bar)
        
        self.btn_stop = QPushButton("🛑  Detener Flujo")
        self.btn_stop.setObjectName("btn_action_stop")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.detiene_todo)
        layout_telemetry.addWidget(self.btn_stop)
        
        right_column.addWidget(card_telemetry)
        
        # --- TARJETA 4: CONSOLA / TERMINAL DE EVENTOS EN VIVO ---
        card_terminal = QFrame()
        card_terminal.setObjectName("ops_terminal_card")
        apply_card_shadow(card_terminal)
        
        layout_term = QVBoxLayout(card_terminal)
        layout_term.setSpacing(0)
        layout_term.setContentsMargins(0, 0, 0, 0)
        
        term_head = QWidget()
        term_head.setObjectName("terminal_header")
        l_th = QHBoxLayout(term_head)
        l_th.setContentsMargins(12, 6, 12, 6)
        
        lbl_term_title = QLabel("📟 Consola de Operaciones en Vivo")
        lbl_term_title.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 9pt;")
        l_th.addWidget(lbl_term_title)
        l_th.addStretch()
        
        btn_copy_log = QPushButton("📋 Copiar")
        btn_copy_log.setStyleSheet("background: transparent; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; padding: 2px 8px; font-size: 8pt;")
        btn_copy_log.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy_log.clicked.connect(self.copiar_logs)
        l_th.addWidget(btn_copy_log)
        
        btn_clear_log = QPushButton("🗑️ Limpiar")
        btn_clear_log.setStyleSheet("background: transparent; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; padding: 2px 8px; font-size: 8pt; margin-left: 4px;")
        btn_clear_log.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_log.clicked.connect(self.limpiar_logs)
        l_th.addWidget(btn_clear_log)
        
        layout_term.addWidget(term_head)
        
        self.log_viewer = QTextEdit()
        self.log_viewer.setObjectName("ops_terminal")
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMinimumHeight(140)
        self.log_viewer.setPlaceholderText("Esperando eventos de ejecución...")
        layout_term.addWidget(self.log_viewer)
        
        right_column.addWidget(card_terminal)
        
        content_layout.addLayout(right_column, stretch=48)
        root_layout.addLayout(content_layout)
