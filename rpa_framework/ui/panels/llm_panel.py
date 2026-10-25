# -*- coding: utf-8 -*-
"""
llm_panel.py — Panel de mantenimiento y optimización de modelos LLM.

Diseño visualmente refinado y profesional con soporte de tarjetas con bordes suaves,
scroll container resizable, badges de estado interactivos y gestión de autoverificación.
Refactorizado de forma modular junto con llm_workers.py y llm_panel_actions_mixin.py.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTextEdit, QTableWidget,
    QGroupBox, QFrame, QLineEdit, QHeaderView,
    QCheckBox, QComboBox, QSpinBox, QScrollArea
)
from PyQt6.QtGui import QFont

from .llm_workers import (
    BackgroundAutoVerificationSignals,
    BackgroundAutoVerificationWorker,
    ValidationSignals,
    ValidationWorker,
    AutoReplaceSignals,
    AutoReplaceWorker,
)
from .llm_panel_actions_mixin import (
    UTILS_DIR,
    CONFIG_FILE,
    LLMPanelActionsMixin,
)


# ─────────────────────────────────────────────────────────────────────────────
# Panel principal con ScrollArea y Diseño Premium
# ─────────────────────────────────────────────────────────────────────────────

class LLMPanel(LLMPanelActionsMixin, QWidget):
    """Panel de mantenimiento de modelos LLM."""

    def __init__(self):
        super().__init__()
        self._worker   = None
        self._auto_bg_worker = None
        self._models   = []       # lista actual del config (BASE_LLM_MODELS)
        self._active   = []       # lista de modelos validados OK en este run
        self._catalogo_cache = {} # caché de ris.catalogo_modelos_llm
        self._api_key  = os.getenv("OPENROUTER_API_KEY", "")
        self._init_ui()
        self._load_models_from_config()
        self._load_auto_config_ui()
        self._load_history_log_ui()
        self._start_auto_check_timer()

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _init_ui(self):
        # Layout principal de la pestaña
        main_vlayout = QVBoxLayout(self)
        main_vlayout.setContentsMargins(0, 0, 0, 0)
        main_vlayout.setSpacing(0)

        # QScrollArea para navegabilidad fluida
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f8fafc;
            }
            QScrollBar:vertical {
                border: none;
                background: #f1f5f9;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 25px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background-color: #f8fafc;")
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Hero Banner / Header elegante ────────────────────────────────────
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e293b);
                border-radius: 12px;
                padding: 16px 20px;
                border: 1px solid #334155;
            }
            QLabel {
                background: transparent;
            }
        """)
        header_layout = QVBoxLayout(header_card)
        header_layout.setSpacing(6)

        title = QLabel("🤖 Mantenedor y Optimizador de Modelos LLM")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; font-size: 16pt;")
        header_layout.addWidget(title)

        subtitle = QLabel(
            "Monitoreo continuo de rendimiento local, validación de estado en línea y autoreemplazo inteligente "
            "con modelos de alta disponibilidad vía OpenRouter y Nvidia NIM."
        )
        subtitle.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)

        # Badges métricos rápidos
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)
        metrics_layout.setContentsMargins(0, 8, 0, 0)

        self.lbl_metric_total = self._create_metric_pill("📦 Modelos Configurados", "0")
        self.lbl_metric_online = self._create_metric_pill("🟢 Modelos Online", "Sin probar")
        self.lbl_metric_auto = self._create_metric_pill("⚡ Verificación Automática", "Diaria (24h)")
        self.lbl_metric_log = self._create_metric_pill("📜 Historial de Logs", "Últimos 5 días")

        metrics_layout.addWidget(self.lbl_metric_total)
        metrics_layout.addWidget(self.lbl_metric_online)
        metrics_layout.addWidget(self.lbl_metric_auto)
        metrics_layout.addWidget(self.lbl_metric_log)
        metrics_layout.addStretch()

        header_layout.addLayout(metrics_layout)
        layout.addWidget(header_card)

        # ── Card 1: Tabla de Modelos y Rendimiento ───────────────────────────
        tbl_card = QGroupBox("📋 Rendimiento Local y Estado en Tiempo Real (BASE_LLM_MODELS)")
        tbl_card.setStyleSheet(self._card_group_style())
        tbl_layout = QVBoxLayout(tbl_card)
        tbl_layout.setSpacing(10)
        tbl_layout.setContentsMargins(14, 18, 14, 14)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Modelo", "Proveedor", "Aptitud / Rol", "Éxitos / Intentos", "Tasa (1°)", "Tiempo Prom.", "Estado", "Detalle / Auditoría"
        ])
        
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(200)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                font-size: 9.5pt;
                gridline-color: #f1f5f9;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #334155;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #cbd5e1;
            }
            QTableWidget::item {
                padding: 6px;
            }
        """)
        tbl_layout.addWidget(self.table)
        layout.addWidget(tbl_card)

        # ── Card 2: Agregar candidato manual ─────────────────────────────────
        add_card = QGroupBox("➕ Agregar modelo candidato manualmente")
        add_card.setStyleSheet(self._card_group_style())
        add_layout = QHBoxLayout(add_card)
        add_layout.setContentsMargins(14, 18, 14, 14)

        icon_lbl = QLabel("🏷️")
        icon_lbl.setFont(QFont("Segoe UI", 11))
        add_layout.addWidget(icon_lbl)

        self.input_model = QLineEdit()
        self.input_model.setPlaceholderText("Ejemplo: google/gemma-4-31b-it:free o nvidia/nemotron-3-nano...")
        self.input_model.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 9.5pt;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border: 2px solid #6366f1;
            }
        """)
        self.input_model.returnPressed.connect(self._add_candidate)
        add_layout.addWidget(self.input_model)

        btn_add = QPushButton("➕ Agregar Candidato")
        btn_add.setFixedWidth(160)
        btn_add.setMinimumHeight(38)
        btn_add.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn_add.setStyleSheet(self._btn_style("#10b981", "#059669"))
        btn_add.clicked.connect(self._add_candidate)
        add_layout.addWidget(btn_add)
        layout.addWidget(add_card)

        # ── Card 3: Acciones Principales ─────────────────────────────────────
        btn_grid = QGridLayout()
        btn_grid.setSpacing(12)

        self.btn_validate = QPushButton("🔍 Validar Todos los Modelos")
        self.btn_validate.setMinimumHeight(44)
        self.btn_validate.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_validate.setStyleSheet(self._btn_style("#2563eb", "#1d4ed8"))
        self.btn_validate.clicked.connect(self._run_validation)
        btn_grid.addWidget(self.btn_validate, 0, 0)

        self.btn_auto_replace = QPushButton("⚡ Auto-Reemplazar Caídos (Nvidia / OpenRouter)")
        self.btn_auto_replace.setMinimumHeight(44)
        self.btn_auto_replace.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_auto_replace.setStyleSheet(self._btn_style("#d97706", "#b45309"))
        self.btn_auto_replace.setToolTip(
            "Busca modelos caídos, descarga catálogo de Nvidia y rankings semanales de OpenRouter, "
            "valida candidatos y los reemplaza automáticamente."
        )
        self.btn_auto_replace.clicked.connect(self._run_auto_replace)
        btn_grid.addWidget(self.btn_auto_replace, 0, 1)

        self.btn_update = QPushButton("💾 Guardar Cambios en llm_config.py")
        self.btn_update.setMinimumHeight(44)
        self.btn_update.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_update.setStyleSheet(self._btn_style("#7c3aed", "#6d28d9"))
        self.btn_update.setEnabled(False)
        self.btn_update.clicked.connect(self._update_config)
        btn_grid.addWidget(self.btn_update, 1, 0)

        self.btn_reload = QPushButton("🔄 Recargar Configuración")
        self.btn_reload.setMinimumHeight(44)
        self.btn_reload.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_reload.setStyleSheet(self._btn_style("#475569", "#334155"))
        self.btn_reload.clicked.connect(self._load_models_from_config)
        btn_grid.addWidget(self.btn_reload, 1, 1)

        layout.addLayout(btn_grid)

        # ── Status Label ─────────────────────────────────────────────────────
        self.lbl_status = QLabel("Sin validar — Presiona «Validar Todos los Modelos» para verificar disponibilidad.")
        self.lbl_status.setStyleSheet("""
            QLabel {
                color: #475569;
                font-size: 9.5pt;
                font-weight: 600;
                background-color: #f1f5f9;
                border-radius: 6px;
                padding: 8px 12px;
                border: 1px solid #e2e8f0;
            }
        """)
        layout.addWidget(self.lbl_status)

        # ── Card 4: Log de actividad Terminal ────────────────────────────────
        log_card = QGroupBox("📟 Terminal de Registro de Operaciones")
        log_card.setStyleSheet(self._card_group_style())
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(14, 18, 14, 14)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(130)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                padding: 8px;
            }
        """)
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_card)

        # ── Card 5: Configuración de Autoverificación Periódica (1 vez al día) ──
        cfg_card = QGroupBox("⚙️ Configuración de Verificación y Auto-Reemplazo Automático (Diario)")
        cfg_card.setStyleSheet(self._card_group_style())
        cfg_layout = QVBoxLayout(cfg_card)
        cfg_layout.setSpacing(12)
        cfg_layout.setContentsMargins(14, 18, 14, 14)

        self.chk_auto_enabled = QCheckBox("Habilitar Verificación y Auto-Reemplazo Automático (1 vez al día)")
        self.chk_auto_enabled.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.chk_auto_enabled.setStyleSheet("color: #0f172a;")
        cfg_layout.addWidget(self.chk_auto_enabled)

        grid_cfg = QGridLayout()
        grid_cfg.setSpacing(12)

        lbl_freq = QLabel("Frecuencia de Verificación:")
        lbl_freq.setStyleSheet("color: #334155; font-weight: bold;")
        grid_cfg.addWidget(lbl_freq, 0, 0)

        self.combo_auto_freq = QComboBox()
        self.combo_auto_freq.addItems([
            "Cada 24 horas desfasadas (diario_24h)",
            "Cada 6 horas (cada_6h)",
            "A una hora fija del día (hora_fija)"
        ])
        self.combo_auto_freq.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #ffffff;
                color: #0f172a;
            }
        """)
        grid_cfg.addWidget(self.combo_auto_freq, 0, 1)

        lbl_hour = QLabel("Hora Programada (0-23h):")
        lbl_hour.setStyleSheet("color: #334155; font-weight: bold;")
        grid_cfg.addWidget(lbl_hour, 0, 2)

        self.spin_auto_hour = QSpinBox()
        self.spin_auto_hour.setRange(0, 23)
        self.spin_auto_hour.setValue(3)
        self.spin_auto_hour.setSuffix(":00 hrs")
        self.spin_auto_hour.setStyleSheet("""
            QSpinBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #ffffff;
                color: #0f172a;
            }
        """)
        grid_cfg.addWidget(self.spin_auto_hour, 0, 3)

        self.chk_auto_apply = QCheckBox("Aplicar cambios en llm_config.py automáticamente al encontrar reemplazos")
        self.chk_auto_apply.setChecked(True)
        self.chk_auto_apply.setStyleSheet("color: #475569;")
        grid_cfg.addWidget(self.chk_auto_apply, 1, 0, 1, 4)

        cfg_layout.addLayout(grid_cfg)

        self.lbl_auto_status_info = QLabel("Última ejecución: Sin datos  |  Próxima: Pendiente")
        self.lbl_auto_status_info.setStyleSheet("""
            QLabel {
                background-color: #f1f5f9;
                color: #334155;
                font-weight: 600;
                font-size: 9pt;
                padding: 6px 12px;
                border-radius: 6px;
            }
        """)
        cfg_layout.addWidget(self.lbl_auto_status_info)

        btn_cfg_row = QHBoxLayout()
        btn_cfg_row.setSpacing(12)

        self.btn_auto_now = QPushButton("⚡ Ejecutar Verificación Automática Ahora")
        self.btn_auto_now.setMinimumHeight(38)
        self.btn_auto_now.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_auto_now.setStyleSheet(self._btn_style("#0284c7", "#0369a1"))
        self.btn_auto_now.clicked.connect(self._run_auto_verification_manual)
        btn_cfg_row.addWidget(self.btn_auto_now)

        self.btn_save_auto_cfg = QPushButton("💾 Guardar Configuración")
        self.btn_save_auto_cfg.setMinimumHeight(38)
        self.btn_save_auto_cfg.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_save_auto_cfg.setStyleSheet(self._btn_style("#10b981", "#059669"))
        self.btn_save_auto_cfg.clicked.connect(self._save_auto_config_ui)
        btn_cfg_row.addWidget(self.btn_save_auto_cfg)

        cfg_layout.addLayout(btn_cfg_row)
        layout.addWidget(cfg_card)

        # ── Card 6: Historial de Verificaciones (Últimos 5 Días) ──────────────
        hist_card = QGroupBox("📜 Historial de Verificaciones y Autoreemplazos (Últimos 5 Días)")
        hist_card.setStyleSheet(self._card_group_style())
        hist_layout = QVBoxLayout(hist_card)
        hist_layout.setSpacing(10)
        hist_layout.setContentsMargins(14, 18, 14, 14)

        self.table_history = QTableWidget(0, 5)
        self.table_history.setHorizontalHeaderLabels([
            "Fecha / Hora", "Estado", "Modelos Activos", "Reemplazos", "Detalle / Registro"
        ])
        self.table_history.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_history.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_history.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_history.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_history.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table_history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_history.setAlternatingRowColors(True)
        self.table_history.setMinimumHeight(150)
        self.table_history.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                font-size: 9pt;
                gridline-color: #f1f5f9;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #334155;
                font-weight: bold;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #cbd5e1;
            }
        """)
        hist_layout.addWidget(self.table_history)

        btn_hist_row = QHBoxLayout()
        self.btn_refresh_history = QPushButton("🔄 Refrescar Historial")
        self.btn_refresh_history.setFixedWidth(170)
        self.btn_refresh_history.setMinimumHeight(36)
        self.btn_refresh_history.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_refresh_history.setStyleSheet(self._btn_style("#64748b", "#475569"))
        self.btn_refresh_history.clicked.connect(self._load_history_log_ui)
        btn_hist_row.addWidget(self.btn_refresh_history)
        btn_hist_row.addStretch()
        hist_layout.addLayout(btn_hist_row)

        layout.addWidget(hist_card)

        # Ensamblar Scroll Area en la pestaña principal
        scroll.setWidget(container)
        main_vlayout.addWidget(scroll)

    # ─── Dynamic UI Helpers ──────────────────────────────────────────────────

    def _create_metric_pill(self, label: str, val: str) -> QFrame:
        pill = QFrame()
        pill.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 6px 12px;
            }
            QLabel {
                background: transparent;
            }
        """)
        v = QVBoxLayout(pill)
        v.setContentsMargins(6, 4, 6, 4)
        v.setSpacing(2)

        lbl_t = QLabel(label)
        lbl_t.setStyleSheet("color: #94a3b8; font-size: 8pt; font-weight: bold;")
        
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet("color: #38bdf8; font-size: 10pt; font-weight: bold;")

        v.addWidget(lbl_t)
        v.addWidget(lbl_v)
        return pill

    @staticmethod
    def _card_group_style() -> str:
        return """
            QGroupBox {
                font-weight: bold;
                font-size: 10pt;
                color: #1e293b;
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                margin-top: 8px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                left: 14px;
                background-color: #ffffff;
                color: #1e293b;
            }
        """
