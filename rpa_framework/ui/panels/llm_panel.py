# -*- coding: utf-8 -*-
"""
llm_panel.py — Panel de mantenimiento y optimización de modelos LLM.

Diseño visualmente refinado y profesional con soporte de tarjetas con bordes suaves,
scroll container resizable, badges de estado interactivos y gestión de autoverificación.
"""

import os
import sys
import threading
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
    QGroupBox, QFrame, QLineEdit, QHeaderView, QMessageBox,
    QCheckBox, QComboBox, QSpinBox, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QFont, QColor

# Ruta al directorio utils (padre de este panel)
UTILS_DIR = Path(__file__).parent.parent.parent / "utils"
CONFIG_FILE = UTILS_DIR / "llm_config.py"


# ─────────────────────────────────────────────────────────────────────────────
# Workers: Hilos en segundo plano para no congelar la GUI
# ─────────────────────────────────────────────────────────────────────────────

class BackgroundAutoVerificationSignals(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)


class BackgroundAutoVerificationWorker(QThread):
    def __init__(self, force=False):
        super().__init__()
        self.force = force
        self.signals = BackgroundAutoVerificationSignals()

    def run(self):
        try:
            from utils.llm_auto_manager import run_auto_verification_logic
            res = run_auto_verification_logic(
                force=self.force,
                log_callback=lambda msg: self.signals.log.emit(msg)
            )
            self.signals.finished.emit(res)
        except Exception as e:
            self.signals.finished.emit({"status": "Error", "message": str(e)})


class ValidationSignals(QObject):
    model_result  = pyqtSignal(str, bool, str)   # model_id, is_ok, msg
    finished      = pyqtSignal(list)              # lista de modelos activos
    log           = pyqtSignal(str)


class ValidationWorker(QThread):
    """Worker para validar el estado básico (HTTP 200) de una lista de modelos."""
    def __init__(self, models: list, api_key: str):
        super().__init__()
        self.models  = models
        self.api_key = api_key
        self.signals = ValidationSignals()

    def run(self):
        import requests
        try:
            from utils.llm_config import get_llm_request_params
        except Exception:
            try:
                from rpa_framework.utils.llm_config import get_llm_request_params
            except Exception:
                def get_llm_request_params(m):
                    return "https://openrouter.ai/api/v1", self.api_key, "openrouter"

        active = []
        for model_id in self.models:
            base_url, target_key, provider = get_llm_request_params(model_id)
            if not target_key:
                target_key = self.api_key
            self.signals.log.emit(f"⏳ Validando {model_id} ({provider.upper()})…")
            url = f"{base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {target_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://rpa-framework.local",
            }
            payload = {
                "model":       model_id,
                "messages":    [{"role": "user", "content": "Di solo: OK"}],
                "max_tokens":  250,
                "temperature": 0.0,
            }
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=15)
                if r.status_code == 200:
                    self.signals.model_result.emit(model_id, True, f"Online ({provider.upper()})")
                    active.append(model_id)
                else:
                    try:
                        err = r.json().get("error", {}).get("message", f"HTTP {r.status_code}")
                    except Exception:
                        err = f"HTTP {r.status_code}"
                    self.signals.model_result.emit(model_id, False, err[:80])
            except Exception as e:
                self.signals.model_result.emit(model_id, False, str(e)[:80])

        self.signals.finished.emit(active)


class AutoReplaceSignals(QObject):
    log           = pyqtSignal(str)
    finished      = pyqtSignal(list, list) # new_models_list, replacement_log_messages
    error         = pyqtSignal(str)


class AutoReplaceWorker(QThread):
    """Worker que descarga catálogos de Nvidia NIM y OpenRouter, valida y reemplaza los caídos."""
    def __init__(self, current_models: list, api_key: str):
        super().__init__()
        self.current_models = list(current_models)
        self.api_key = api_key
        self.signals = AutoReplaceSignals()

    def run(self):
        import requests
        import json
        import concurrent.futures
        from datetime import datetime, timedelta

        try:
            from utils.llm_config import get_llm_request_params
        except Exception:
            try:
                from rpa_framework.utils.llm_config import get_llm_request_params
            except Exception:
                def get_llm_request_params(m):
                    return "https://openrouter.ai/api/v1", self.api_key, "openrouter"

        # 1. Validar primero cuáles de los modelos actuales están caídos
        self.signals.log.emit("🔍 Paso 1: Validando modelos actuales con sus respectivos proveedores...")
        current_status = {}
        for m in self.current_models:
            base_url, target_key, provider = get_llm_request_params(m)
            if not target_key:
                target_key = self.api_key
            self.signals.log.emit(f"  - Probando {m} ({provider.upper()})...")
            url = f"{base_url}/chat/completions"
            headers_call = {
                "Authorization": f"Bearer {target_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://rpa-framework.local",
            }
            payload = {
                "model": m,
                "messages": [{"role": "user", "content": "Di solo: OK"}],
                "max_tokens": 250,
                "temperature": 0.0,
            }
            try:
                r = requests.post(url, headers=headers_call, json=payload, timeout=15)
                current_status[m] = (r.status_code == 200)
            except Exception:
                current_status[m] = False

        offline_models = [m for m, active in current_status.items() if not active]
        self.signals.log.emit(f"❌ Modelos caídos detectados ({len(offline_models)}): {offline_models}")

        if not offline_models:
            self.signals.log.emit("✅ Todos los modelos actuales están online. No se requiere reemplazo.")
            self.signals.finished.emit(self.current_models, ["No se requirieron reemplazos, todos online."])
            return

        # 2. Descargar todos los modelos libres de OpenRouter
        self.signals.log.emit("📥 Paso 2: Descargando lista de modelos de OpenRouter...")
        free_models = {}
        try:
            r = requests.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=10)
            if r.status_code == 200:
                all_models = r.json().get("data", [])
                for m in all_models:
                    pricing = m.get("pricing", {})
                    prompt = float(pricing.get("prompt", 0))
                    completion = float(pricing.get("completion", 0))
                    if prompt == 0 and completion == 0:
                        free_models[m["id"]] = m
                        if m.get("canonical_slug"):
                            free_models[m["canonical_slug"]] = m
                self.signals.log.emit(f"✨ Modelos OpenRouter gratuitos identificados: {len(set(id(x) for x in free_models.values()))}")
            else:
                self.signals.log.emit(f"⚠️ Error descargando modelos OpenRouter: HTTP {r.status_code}")
        except Exception as e:
            self.signals.log.emit(f"⚠️ Excepción descargando modelos OpenRouter: {e}")

        # 3. Descargar datasets de rankings diarios de OpenRouter
        self.signals.log.emit("📊 Paso 3: Descargando rankings de uso semanal de OpenRouter...")
        usage = {}
        try:
            headers_or = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://rpa-framework.local",
            }
            r = requests.get("https://openrouter.ai/api/v1/datasets/rankings-daily", headers=headers_or, timeout=10)
            if r.status_code == 200:
                rankings = r.json().get("data", [])
                dates = sorted(list(set(item.get("date") for item in rankings if item.get("date"))), reverse=True)
                if dates:
                    latest_date = datetime.strptime(dates[0], "%Y-%m-%d")
                    start_date = latest_date - timedelta(days=7)
                    start_date_str = start_date.strftime("%Y-%m-%d")
                    self.signals.log.emit(f"📈 Agrupando estadísticas OpenRouter desde {start_date_str} hasta {dates[0]}")

                    for item in rankings:
                        d_str = item.get("date")
                        if not d_str or d_str < start_date_str:
                            continue
                        slug = item.get("model_permaslug")
                        tokens = int(item.get("total_tokens", 0))

                        matched = free_models.get(slug)
                        if not matched:
                            for m_id, m_info in free_models.items():
                                if m_id in slug or slug in m_id:
                                    matched = m_info
                                    break
                        if matched:
                            mid = matched["id"]
                            usage[mid] = usage.get(mid, 0) + tokens
        except Exception as e:
            self.signals.log.emit(f"⚠️ Excepción procesando rankings OpenRouter: {e}")

        # Asegurar fallbacks clave de OpenRouter
        for fallback_or in [
            "nvidia/nemotron-nano-12b-v2-vl:free",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "openai/gpt-oss-20b:free",
            "openrouter/free",
            "nvidia/nemotron-3.5-lightning:free",
            "google/gemma-4-26b-a4b-it:free",
            "google/gemma-4-31b-it:free"
        ]:
            if fallback_or in free_models and fallback_or not in usage:
                usage[fallback_or] = 1

        sorted_openrouter_free = [m_id for m_id, _ in sorted(usage.items(), key=lambda x: x[1], reverse=True)]

        # 3.1 Descargar y sondear modelos activos de Nvidia NIM
        nvidia_validated = []
        nvidia_key = os.getenv("NVIDIA_API_KEY", "")
        if nvidia_key:
            self.signals.log.emit("📥 Paso 3.1: Descargando catálogo y testeando modelos activos de Nvidia NIM...")
            try:
                r_nv = requests.get("https://integrate.api.nvidia.com/v1/models", headers={"Authorization": f"Bearer {nvidia_key}"}, timeout=10)
                if r_nv.status_code == 200:
                    exclude_keywords = [
                        "embed", "rerank", "parse", "pii", "clip", "translation", "translate", 
                        "reward", "safety", "guard", "diffusion", "deplot", "fuyu", "vila", "detector", "calibration"
                    ]
                    include_keywords = [
                        "instruct", "-it", "chat", "large", "medium", "small", "pro", "flash", "nemotron", "super", "omni", "nano"
                    ]
                    raw_nvidia_models = []
                    for m in r_nv.json().get("data", []):
                        m_id = m["id"]
                        m_lower = m_id.lower()
                        if any(kw in m_lower for kw in exclude_keywords):
                            continue
                        if any(kw in m_lower for kw in include_keywords):
                            raw_nvidia_models.append(m_id)

                    # Priorizar modelos conocidos robustos de Nvidia
                    known_priority_nv = [
                        "meta/llama-3.1-8b-instruct",
                        "nvidia/llama-3.3-nemotron-super-49b-v1",
                        "meta/llama-3.2-11b-vision-instruct",
                        "nvidia/nemotron-nano-12b-v2-vl",
                        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
                        "nvidia/nemotron-3-super-120b-a12b",
                        "meta/llama-3.1-70b-instruct",
                        "nvidia/nemotron-3-nano-30b-a3b"
                    ]
                    ordered_nv = [m for m in known_priority_nv if m in raw_nvidia_models] + [m for m in raw_nvidia_models if m not in known_priority_nv]
                    
                    # Sondeo concurrente rápido para descartar 404s
                    def _probe_nv(mid):
                        u = "https://integrate.api.nvidia.com/v1/chat/completions"
                        h = {"Authorization": f"Bearer {nvidia_key}", "Content-Type": "application/json"}
                        p = {"model": mid, "messages": [{"role": "user", "content": "OK"}], "max_tokens": 10, "temperature": 0.0}
                        try:
                            res = requests.post(u, headers=h, json=p, timeout=5)
                            return mid, (res.status_code == 200)
                        except Exception:
                            return mid, False

                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                        probe_results = dict(ex.map(lambda mid: _probe_nv(mid), ordered_nv[:25]))
                        nvidia_validated = [mid for mid in ordered_nv[:25] if probe_results.get(mid, False)]
                        self.signals.log.emit(f"✨ Modelos Nvidia NIM activos confirmados: {len(nvidia_validated)}")
            except Exception as e:
                self.signals.log.emit(f"⚠️ Error obteniendo catálogo de Nvidia: {e}")

        # 4. Validar candidatos con prompt clínico estructurado
        self.signals.log.emit("🩺 Paso 4: Validando candidatos con prueba de coincidencia clínica...")
        
        prompt_clinico = """Determina si el examen en el texto OCR coincide semánticamente con el examen buscado.
TEXTO OCR: "28-04-2026 Examen Hecho RM de Columna Lumbar"
EXAMEN BUSCADO: "RESONANCIA MAGNÉTICA DE COLUMNA LUMBAR"
Responde ÚNICAMENTE en formato JSON plano:
{"es_match": true, "confianza": 1.0}"""

        def _test_candidate_clinical(cand):
            b_url, t_key, prov = get_llm_request_params(cand)
            if not t_key:
                t_key = self.api_key
            u = f"{b_url}/chat/completions"
            h = {
                "Authorization": f"Bearer {t_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://rpa-framework.local",
            }
            p = {
                "model": cand,
                "messages": [{"role": "user", "content": prompt_clinico}],
                "max_tokens": 300,
                "temperature": 0.0,
            }
            try:
                res = requests.post(u, headers=h, json=p, timeout=10)
                if res.status_code == 200:
                    cnt = res.json().get('choices', [{}])[0].get('message', {}).get('content') or ""
                    cnt_l = cnt.lower()
                    if '"es_match": true' in cnt_l or '"es_match":true' in cnt_l or 'es_match: true' in cnt_l or 'es_match": 1' in cnt_l:
                        return cand, True, prov, "OK"
                    return cand, False, prov, f"No JSON match: {cnt[:40]}"
                return cand, False, prov, f"HTTP {res.status_code}"
            except Exception as exc:
                return cand, False, prov, str(exc)

        # Candidatos a probar: Top Nvidia + Top OpenRouter Free
        candidates_to_test = []
        for c in nvidia_validated[:8]:
            if c not in candidates_to_test:
                candidates_to_test.append(c)
        for c in sorted_openrouter_free[:10]:
            if c not in candidates_to_test:
                candidates_to_test.append(c)

        validated_nvidia = []
        validated_openrouter = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(_test_candidate_clinical, cand): cand for cand in candidates_to_test}
            for fut in concurrent.futures.as_completed(futures):
                cand, ok, prov, msg = fut.result()
                if ok:
                    self.signals.log.emit(f"  ✅ Candidato VÁLIDO ({prov.upper()}): {cand}")
                    if prov == "nvidia":
                        validated_nvidia.append(cand)
                    else:
                        validated_openrouter.append(cand)
                else:
                    self.signals.log.emit(f"  ❌ Candidato descartado ({prov.upper()}): {cand} ({msg})")

        # 5. Reemplazo y conformación de la lista balanceada (5 Nvidia + 5 OpenRouter)
        self.signals.log.emit("⚡ Paso 5: Reconstruyendo lista balanceada de 10 modelos (5 Nvidia + 5 OpenRouter)...")
        new_models = []
        replacement_log = []

        # Mantener modelos actuales que estén online
        current_online_nv = [m for m in self.current_models if current_status.get(m, False) and get_llm_request_params(m)[2] == "nvidia"]
        current_online_or = [m for m in self.current_models if current_status.get(m, False) and get_llm_request_params(m)[2] == "openrouter"]

        selected_nv = list(current_online_nv)
        for c in validated_nvidia:
            if len(selected_nv) >= 5:
                break
            if c not in selected_nv:
                selected_nv.append(c)
                replacement_log.append(f"Agregado Nvidia NIM: {c}")

        selected_or = list(current_online_or)
        for c in validated_openrouter:
            if len(selected_or) >= 5:
                break
            if c not in selected_or:
                selected_or.append(c)
                replacement_log.append(f"Agregado OpenRouter Free: {c}")

        # Si falta cupo en alguno, rellenar con el otro proveedor
        all_pool = selected_nv + selected_or
        for c in validated_nvidia + validated_openrouter:
            if len(all_pool) >= 10:
                break
            if c not in all_pool:
                all_pool.append(c)

        new_models = all_pool[:10]
        self.signals.log.emit(f"🎯 Nueva lista consolidada ({len(new_models)} modelos): {new_models}")
        self.signals.finished.emit(new_models, replacement_log)


# ─────────────────────────────────────────────────────────────────────────────
# Panel principal con ScrollArea y Diseño Premium
# ─────────────────────────────────────────────────────────────────────────────

class LLMPanel(QWidget):
    """Panel de mantenimiento de modelos LLM."""

    def __init__(self):
        super().__init__()
        self._worker   = None
        self._auto_bg_worker = None
        self._models   = []       # lista actual del config (BASE_LLM_MODELS)
        self._active   = []       # lista de modelos validados OK en este run
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

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Modelo", "Proveedor", "Éxitos / Intentos", "Tasa (1°)", "Tiempo Prom.", "Estado", "Detalle"
        ])
        
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        
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

    # ─── Lógica de Datos y Modelos ───────────────────────────────────────────

    def _query_db_stats(self) -> dict:
        """Consulta ris.log_llm_ranking para obtener estadísticas de los modelos (es_primer_intento=1)."""
        stats = {}
        try:
            import mysql.connector
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=1)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    modelo,
                    COUNT(*) as total_intentos,
                    SUM(es_match) as total_exitos,
                    AVG(tiempo_ms) as tiempo_promedio_ms
                FROM ris.log_llm_ranking
                WHERE es_primer_intento = 1
                GROUP BY modelo
            """)
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                stats[row['modelo']] = row
        except Exception as e:
            self._log(f"⚠️ Error conectando a DB para estadísticas: {e}")
        return stats

    def _load_models_from_config(self):
        """Lee BASE_LLM_MODELS de llm_config.py e inserta filas en la tabla con estadísticas locales."""
        self._models = []
        try:
            sys.path.insert(0, str(UTILS_DIR.parent))
            import importlib
            import utils.llm_config as llm_cfg
            importlib.reload(llm_cfg)
            self._models = list(llm_cfg.BASE_LLM_MODELS)
        except Exception as e:
            self._log(f"❌ No se pudo leer llm_config.py: {e}")
            return

        stats = self._query_db_stats()

        self.table.setRowCount(0)
        for model in self._models:
            self._insert_row_with_stats(model, stats.get(model), "—", "#6b7280")

        self._log(f"📂 {len(self._models)} modelos cargados desde llm_config.py")
        self.btn_update.setEnabled(False)
        self._active = []

        # Actualizar métrica total
        total_str = str(len(self._models))
        try:
            self.lbl_metric_total.findChildren(QLabel)[1].setText(total_str)
        except Exception:
            pass

    def _insert_row_with_stats(self, model_id: str, model_stats: dict, status: str, color: str, detail: str = ""):
        row = self.table.rowCount()
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0) and self.table.item(r, 0).text() == model_id:
                row = r
                break
        else:
            self.table.insertRow(row)
            item_m = QTableWidgetItem(model_id)
            item_m.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(row, 0, item_m)

        # Determinar Proveedor
        prov_text = "OpenRouter"
        try:
            from utils.llm_config import get_llm_request_params
            _, _, provider = get_llm_request_params(model_id)
            prov_text = "Nvidia" if provider == "nvidia" else "OpenRouter"
        except Exception:
            if not model_id.endswith(":free"):
                nvidia_prefixes = (
                    "01-ai/", "abacusai/", "adept/", "ai21labs/", "aisingapore/", "baai/", "bigcode/",
                    "bytedance/", "databricks/", "deepseek-ai/", "google/", "ibm/", "meta/", "microsoft/",
                    "minimaxai/", "mistralai/", "moonshotai/", "nv-mistralai/", "nvidia/", "openai/",
                    "poolside/", "qwen/", "sarvamai/", "snowflake/", "stepfun-ai/", "thinkingmachines/",
                    "upstage/", "writer/", "z-ai/", "zyphra/"
                )
                if any(model_id.startswith(p) for p in nvidia_prefixes):
                    prov_text = "Nvidia"

        prov_item = QTableWidgetItem(prov_text)
        prov_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        if prov_text == "Nvidia":
            prov_item.setForeground(QColor("#059669"))
        else:
            prov_item.setForeground(QColor("#0284c7"))
        self.table.setItem(row, 1, prov_item)

        # Poblar estadísticas
        if model_stats:
            intentos = model_stats['total_intentos']
            exitos = int(model_stats['total_exitos'] or 0)
            tiempo = model_stats['tiempo_promedio_ms'] or 0
            tasa = (exitos / intentos * 100) if intentos > 0 else 0.0

            self.table.setItem(row, 2, QTableWidgetItem(f"{exitos} / {intentos}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{tasa:.1f}%"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{tiempo / 1000:.2f}s"))
        else:
            self.table.setItem(row, 2, QTableWidgetItem("0 / 0"))
            self.table.setItem(row, 3, QTableWidgetItem("—"))
            self.table.setItem(row, 4, QTableWidgetItem("—"))

        self.table.setItem(row, 5, self._colored_item(status, color))
        self.table.setItem(row, 6, QTableWidgetItem(detail))

    def _colored_item(self, text: str, color: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        return item

    def _add_candidate(self):
        model_id = self.input_model.text().strip()
        if not model_id:
            return
        if model_id in self._models:
            self._log(f"⚠️ {model_id} ya está en la lista.")
            return
        self._models.append(model_id)
        self._insert_row_with_stats(model_id, None, "Pendiente", "#f59e0b", "Nuevo candidato manual")
        self.input_model.clear()
        self._log(f"➕ Modelo agregado a la lista de prueba: {model_id}")

    def _run_validation(self):
        if not self._api_key:
            QMessageBox.warning(
                self, "⚠️ API Key faltante",
                "OPENROUTER_API_KEY no está configurada en el archivo .env"
            )
            return

        if self._worker and self._worker.isRunning():
            return

        for r in range(self.table.rowCount()):
            self.table.setItem(r, 5, self._colored_item("⏳ Validando…", "#f59e0b"))
            self.table.setItem(r, 6, QTableWidgetItem(""))

        self.btn_validate.setEnabled(False)
        self.btn_auto_replace.setEnabled(False)
        self.btn_update.setEnabled(False)
        self.lbl_status.setText("🔍 Validando modelos contra OpenRouter…")

        self._worker = ValidationWorker(list(self._models), self._api_key)
        self._worker.signals.model_result.connect(self._on_model_result)
        self._worker.signals.finished.connect(self._on_validation_done)
        self._worker.signals.log.connect(self._log)
        self._worker.start()

    def _on_model_result(self, model_id: str, is_ok: bool, msg: str):
        stats = self._query_db_stats()
        if is_ok:
            self._insert_row_with_stats(model_id, stats.get(model_id), "✅ Online", "#10b981", "")
        else:
            self._insert_row_with_stats(model_id, stats.get(model_id), "❌ Offline", "#ef4444", msg)

    def _on_validation_done(self, active: list):
        self._active = active
        ts = datetime.now().strftime("%H:%M:%S")
        total = len(self._models)
        ok    = len(active)
        self.lbl_status.setText(
            f"Última validación: {ts}  |  {ok}/{total} modelos activos"
        )
        self.btn_validate.setEnabled(True)
        self.btn_auto_replace.setEnabled(True)
        self.btn_update.setEnabled(bool(active))
        self._log(f"✅ Validación completa: {ok}/{total} activos.")

        # Actualizar métrica online
        try:
            self.lbl_metric_online.findChildren(QLabel)[1].setText(f"{ok} / {total}")
        except Exception:
            pass

    def _run_auto_replace(self):
        if not self._api_key:
            QMessageBox.warning(
                self, "⚠️ API Key faltante",
                "OPENROUTER_API_KEY no está configurada en el archivo .env"
            )
            return

        self.btn_validate.setEnabled(False)
        self.btn_auto_replace.setEnabled(False)
        self.btn_update.setEnabled(False)
        self.lbl_status.setText("⚡ Buscando y reemplazando modelos caídos...")
        self.log_output.clear()

        self._replace_worker = AutoReplaceWorker(list(self._models), self._api_key)
        self._replace_worker.signals.log.connect(self._log)
        self._replace_worker.signals.error.connect(self._on_auto_replace_error)
        self._replace_worker.signals.finished.connect(self._on_auto_replace_done)
        self._replace_worker.start()

    def _on_auto_replace_error(self, err_msg: str):
        self.lbl_status.setText("❌ Error en el proceso de autoreemplazo.")
        self._log(f"❌ ERROR: {err_msg}")
        self.btn_validate.setEnabled(True)
        self.btn_auto_replace.setEnabled(True)
        QMessageBox.critical(self, "❌ Error", err_msg)

    def _on_auto_replace_done(self, new_models: list, logs: list):
        self._models = new_models
        self._active = new_models
        
        self.table.setRowCount(0)
        stats = self._query_db_stats()
        for model in self._models:
            self._insert_row_with_stats(model, stats.get(model), "✅ Activo", "#10b981", "Listo para guardar")

        self.lbl_status.setText("⚡ Autoreemplazo completado. Revisa la tabla y presiona Guardar.")
        self.btn_validate.setEnabled(True)
        self.btn_auto_replace.setEnabled(True)
        self.btn_update.setEnabled(True)
        
        for msg in logs:
            self._log(f"✨ {msg}")
        QMessageBox.information(
            self, "⚡ Reemplazo completado",
            f"Se han procesado los reemplazos. Nuevos modelos totales: {len(new_models)}. "
            "Presiona 'Guardar Cambios en llm_config.py' para aplicar permanentemente."
        )

    def _update_config(self):
        if not self._active:
            QMessageBox.warning(self, "Sin modelos activos",
                                "No hay modelos activos que escribir en llm_config.py")
            return

        try:
            import re
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                content = f.read()

            new_list = "BASE_LLM_MODELS = [\n"
            for i, model in enumerate(self._active):
                role = "Primario" if i == 0 else f"Fallback {i}"
                line = f'   "{model}",'
                new_list += f"{line:<60} # {role} — Validado OK\n"
            new_list += "]"

            updated, count = re.subn(
                r"BASE_LLM_MODELS\s*=\s*\[.*?\]", new_list, content, flags=re.DOTALL
            )
            if count == 0:
                updated, count = re.subn(
                    r"LLM_MODELS\s*=\s*\[.*?\]", new_list.replace("BASE_LLM_MODELS", "LLM_MODELS"), content, flags=re.DOTALL
                )
                if count == 0:
                    raise ValueError("No se encontró BASE_LLM_MODELS ni LLM_MODELS en llm_config.py")

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(updated)

            self._log(f"💾 llm_config.py actualizado con {len(self._active)} modelos en BASE_LLM_MODELS.")
            QMessageBox.information(
                self, "✅ Configuración actualizada",
                f"llm_config.py actualizado con {len(self._active)} modelos activos en BASE_LLM_MODELS."
            )
            self.btn_update.setEnabled(False)
        except Exception as e:
            self._log(f"❌ Error actualizando config: {e}")
            QMessageBox.critical(self, "❌ Error", str(e))

    def run_startup_validation(self):
        """Llamar desde main() para validar sin interacción del usuario."""
        if not self._api_key or not self._models:
            return
        self._log("🚀 Validación automática al inicio…")
        self._run_validation()

    # ─── Autoverificación Periódica y Gestión de Historial (5 Días) ─────────

    def _start_auto_check_timer(self):
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(15 * 60 * 1000)
        self._auto_timer.timeout.connect(self._check_periodic_auto_verification)
        self._auto_timer.start()
        QTimer.singleShot(10000, self._check_periodic_auto_verification)

    def _check_periodic_auto_verification(self):
        try:
            from utils.llm_auto_manager import should_run_auto_verification
            should, reason = should_run_auto_verification(force=False)
            if should and not (self._auto_bg_worker and self._auto_bg_worker.isRunning()):
                self._log(f"⏰ Temporizador automático: disparando autoverificación ({reason})...")
                self._run_auto_verification_bg(force=False)
        except Exception as e:
            self._log(f"⚠️ Error verificando estado de autoverificación: {e}")

    def _run_auto_verification_manual(self):
        if self._auto_bg_worker and self._auto_bg_worker.isRunning():
            QMessageBox.information(self, "Verificación en curso", "Ya hay una autoverificación ejecutándose en segundo plano.")
            return
        self._run_auto_verification_bg(force=True)

    def _run_auto_verification_bg(self, force=False):
        if self._auto_bg_worker and self._auto_bg_worker.isRunning():
            return
        
        self.btn_auto_now.setEnabled(False)
        self.lbl_auto_status_info.setText("⏳ Ejecutando autoverificación y autoreemplazo diario...")
        self._log("⚡ Iniciando autoverificación periódica de modelos en segundo plano...")

        self._auto_bg_worker = BackgroundAutoVerificationWorker(force=force)
        self._auto_bg_worker.signals.log.connect(self._log)
        self._auto_bg_worker.signals.finished.connect(self._on_auto_bg_finished)
        self._auto_bg_worker.start()

    def _on_auto_bg_finished(self, result: dict):
        self.btn_auto_now.setEnabled(True)
        status = result.get("status", "Completado")
        details = result.get("details", result.get("reason", ""))
        self._log(f"✅ Autoverificación finalizada: {status}. {details}")
        
        self._load_models_from_config()
        self._load_auto_config_ui()
        self._load_history_log_ui()

    def _load_auto_config_ui(self):
        try:
            from utils.llm_auto_manager import load_auto_config
            cfg = load_auto_config()
            self.chk_auto_enabled.setChecked(cfg.get("enabled", True))
            freq = cfg.get("frequency", "diario_24h")
            idx = 0 if freq == "diario_24h" else 1
            self.combo_auto_freq.setCurrentIndex(idx)
            self.spin_auto_hour.setValue(cfg.get("scheduled_hour", 3))
            self.chk_auto_apply.setChecked(cfg.get("auto_apply", True))

            last_ts = cfg.get("last_run_timestamp", "Sin ejecuciones aún")
            last_st = cfg.get("last_status", "Pendiente")
            self.lbl_auto_status_info.setText(f"Última verificación: {last_ts}  |  Estado: {last_st}")
        except Exception as e:
            self._log(f"⚠️ Error cargando auto config UI: {e}")

    def _save_auto_config_ui(self):
        try:
            from utils.llm_auto_manager import load_auto_config, save_auto_config
            cfg = load_auto_config()
            cfg["enabled"] = self.chk_auto_enabled.isChecked()
            cfg["frequency"] = "diario_24h" if self.combo_auto_freq.currentIndex() == 0 else "hora_fija"
            cfg["scheduled_hour"] = self.spin_auto_hour.value()
            cfg["auto_apply"] = self.chk_auto_apply.isChecked()
            
            if save_auto_config(cfg):
                self._log("💾 Configuración de autoverificación guardada.")
                QMessageBox.information(self, "✅ Guardado", "Configuración de autoverificación diaria actualizada correctamente.")
                self._load_auto_config_ui()
            else:
                QMessageBox.critical(self, "❌ Error", "No se pudo guardar la configuración.")
        except Exception as e:
            self._log(f"❌ Error guardando auto config UI: {e}")
            QMessageBox.critical(self, "❌ Error", str(e))

    def _load_history_log_ui(self):
        try:
            from utils.llm_auto_manager import load_verification_log
            logs = load_verification_log()
            self.table_history.setRowCount(0)
            
            for entry in logs:
                row = self.table_history.rowCount()
                self.table_history.insertRow(row)
                
                ts = entry.get("timestamp", "—")
                st = entry.get("status", "—")
                checked = entry.get("models_checked", 0)
                online = entry.get("models_online", 0)
                replaced = entry.get("models_replaced", 0)
                details = entry.get("details", "—")

                self.table_history.setItem(row, 0, QTableWidgetItem(ts))
                
                st_item = QTableWidgetItem(st)
                if "Éxito" in st:
                    st_item.setForeground(QColor("#10b981"))
                elif "Reemplazo" in st:
                    st_item.setForeground(QColor("#0284c7"))
                elif "Fallo" in st or "Error" in st:
                    st_item.setForeground(QColor("#ef4444"))
                else:
                    st_item.setForeground(QColor("#d97706"))
                st_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                self.table_history.setItem(row, 1, st_item)

                self.table_history.setItem(row, 2, QTableWidgetItem(f"{online} / {checked}"))
                self.table_history.setItem(row, 3, QTableWidgetItem(str(replaced)))
                self.table_history.setItem(row, 4, QTableWidgetItem(details))

        except Exception as e:
            self._log(f"⚠️ Error cargando historial UI: {e}")

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _log(self, text: str):
        self.log_output.append(text)
        sb = self.log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    @staticmethod
    def _btn_style(color_start: str, color_end: str) -> str:
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {color_start}, stop:1 {color_end});
                color: white; border: none; border-radius: 8px; padding: 8px 16px;
            }}
            QPushButton:hover {{
                background: {color_start};
            }}
            QPushButton:pressed {{ background: {color_end}; }}
            QPushButton:disabled {{ background-color: #9ca3af; color: #e5e7eb; }}
        """
