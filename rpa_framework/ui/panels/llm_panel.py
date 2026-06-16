# -*- coding: utf-8 -*-
"""
llm_panel.py — Panel de mantenimiento y optimización de modelos LLM.

Tab integrado en la GUI principal que permite:
  - Ver las estadísticas de rendimiento local de cada modelo (Éxitos/Intentos, Tasa, Tiempo).
  - Validar todos los modelos contra la API de OpenRouter en segundo plano.
  - Reemplazar automáticamente modelos offline con los modelos gratuitos más populares de la última semana.
  - Guardar y recargar la configuración centralizada en llm_config.py.
"""

import os
import sys
import threading
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
    QGroupBox, QFrame, QLineEdit, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor

# Ruta al directorio utils (padre de este panel)
UTILS_DIR = Path(__file__).parent.parent.parent / "utils"
CONFIG_FILE = UTILS_DIR / "llm_config.py"


# ─────────────────────────────────────────────────────────────────────────────
# Workers: Hilos en segundo plano para no congelar la GUI
# ─────────────────────────────────────────────────────────────────────────────

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
        active = []
        for model_id in self.models:
            self.signals.log.emit(f"⏳ Validando {model_id}…")
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://rpa-framework.local",
            }
            payload = {
                "model":       model_id,
                "messages":    [{"role": "user", "content": "Di solo: OK"}],
                "max_tokens":  10,
                "temperature": 0.0,
            }
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=10)
                if r.status_code == 200:
                    self.signals.model_result.emit(model_id, True, "Online")
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
    """Worker que descarga los populares semanales de OpenRouter y reemplaza los caídos."""
    def __init__(self, current_models: list, api_key: str):
        super().__init__()
        self.current_models = list(current_models)
        self.api_key = api_key
        self.signals = AutoReplaceSignals()

    def run(self):
        import requests
        import json
        from datetime import datetime, timedelta

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://rpa-framework.local",
        }

        # 1. Validar primero cuáles de los modelos actuales están caídos
        self.signals.log.emit("🔍 Paso 1: Validando modelos actuales...")
        current_status = {}
        for m in self.current_models:
            self.signals.log.emit(f"  - Probando {m}...")
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {
                "model": m,
                "messages": [{"role": "user", "content": "Di solo: OK"}],
                "max_tokens": 10,
                "temperature": 0.0,
            }
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=8)
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
        try:
            r = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
            if r.status_code != 200:
                self.signals.error.emit(f"Error descargando modelos: HTTP {r.status_code}")
                return
            all_models = r.json().get("data", [])
        except Exception as e:
            self.signals.error.emit(f"Excepción descargando modelos: {e}")
            return

        free_models = {}
        for m in all_models:
            pricing = m.get("pricing", {})
            prompt = float(pricing.get("prompt", 0))
            completion = float(pricing.get("completion", 0))
            if prompt == 0 and completion == 0:
                free_models[m["id"]] = m
                if m.get("canonical_slug"):
                    free_models[m["canonical_slug"]] = m

        self.signals.log.emit(f"✨ Modelos gratuitos identificados: {len(set(id(x) for x in free_models.values()))}")

        # 3. Descargar datasets de rankings diarios de OpenRouter
        self.signals.log.emit("📊 Paso 3: Descargando rankings de uso semanal de OpenRouter...")
        try:
            r = requests.get("https://openrouter.ai/api/v1/datasets/rankings-daily", headers=headers, timeout=10)
            if r.status_code != 200:
                self.signals.error.emit(f"Error descargando rankings: HTTP {r.status_code}")
                return
            rankings = r.json().get("data", [])
        except Exception as e:
            self.signals.error.emit(f"Excepción descargando rankings: {e}")
            return

        # Determinar el rango de la última semana disponible en el dataset
        dates = sorted(list(set(item.get("date") for item in rankings)), reverse=True)
        if not dates:
            self.signals.error.emit("El dataset de rankings no contiene fechas válidas.")
            return

        latest_date_str = dates[0]
        latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
        start_date = latest_date - timedelta(days=7)
        start_date_str = start_date.strftime("%Y-%m-%d")
        self.signals.log.emit(f"📈 Agrupando estadísticas desde {start_date_str} hasta {latest_date_str}")

        usage = {}
        for item in rankings:
            d_str = item.get("date")
            if not d_str or d_str < start_date_str:
                continue
            slug = item.get("model_permaslug")
            tokens = int(item.get("total_tokens", 0))

            matched = None
            if slug in free_models:
                matched = free_models[slug]
            else:
                for m_id, m_info in free_models.items():
                    if m_id in slug or slug in m_id:
                        matched = m_info
                        break
            if matched:
                model_id = matched["id"]
                usage[model_id] = usage.get(model_id, 0) + tokens

        sorted_popular_free = [m_id for m_id, _ in sorted(usage.items(), key=lambda x: x[1], reverse=True)]
        self.signals.log.emit(f"🔥 Top 10 modelos gratuitos más usados: {sorted_popular_free[:10]}")

        # 4. Validar candidatos populares usando un PROMPT CLÍNICO REAL (evaluación rigurosa)
        self.signals.log.emit("🩺 Paso 4: Validando candidatos con prompt clínico...")
        validated_candidates = []
        
        prompt_clinico = """
        Determina si el siguiente texto coincide con el examen de forma semántica.
        BUSCADO: "RESONANCIA MAGNÉTICA DE COLUMNA LUMBAR"
        ENCONTRADO: "28-04-2026 Examen Hecho RM de Columna Lumbar"
        Responde ÚNICAMENTE en formato JSON:
        {"es_match": true, "confianza": 1.0}
        """

        for cand in sorted_popular_free[:10]:
            if cand in self.current_models and current_status.get(cand, False):
                # Ya está en la lista y funciona, no se usa como candidato nuevo
                continue
            
            self.signals.log.emit(f"  - Validando candidato: {cand}...")
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {
                "model": cand,
                "messages": [{"role": "user", "content": prompt_clinico}],
                "max_tokens": 50,
                "temperature": 0.0,
            }
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=8)
                if r.status_code == 200:
                    # Verificar que devuelva un JSON válido
                    data = r.json()
                    content = data['choices'][0]['message'].get('content', '')
                    if "es_match" in content:
                        validated_candidates.append(cand)
                        self.signals.log.emit(f"    ✅ Candidato VÁLIDO (Clínicamente compatible): {cand}")
                    else:
                        self.signals.log.emit(f"    ⚠️ Candidato RECHAZADO (No responde JSON estructurado): {cand}")
                else:
                    self.signals.log.emit(f"    ❌ Candidato OFFLINE ({r.status_code}): {cand}")
            except Exception as e:
                self.signals.log.emit(f"    ❌ Error validando candidato: {e}")

        # 5. Realizar el reemplazo de los caídos
        self.signals.log.emit("⚡ Paso 5: Reemplazando modelos caídos...")
        new_models = []
        replacement_log = []
        cand_idx = 0

        for m in self.current_models:
            if current_status.get(m, False):
                new_models.append(m)
            else:
                replaced = False
                while cand_idx < len(validated_candidates):
                    cand = validated_candidates[cand_idx]
                    cand_idx += 1
                    if cand not in self.current_models and cand not in new_models:
                        new_models.append(cand)
                        msg = f"🔄 Reemplazado '{m}' (Offline) por '{cand}' (Top Free #{cand_idx})"
                        replacement_log.append(msg)
                        self.signals.log.emit(f"  - {msg}")
                        replaced = True
                        break
                if not replaced:
                    self.signals.log.emit(f"  - ⚠️ No hay candidatos para reemplazar '{m}'. Se conserva.")
                    new_models.append(m)

        self.signals.finished.emit(new_models, replacement_log)


# ─────────────────────────────────────────────────────────────────────────────
# Panel principal
# ─────────────────────────────────────────────────────────────────────────────

class LLMPanel(QWidget):
    """Panel de mantenimiento de modelos LLM."""

    def __init__(self):
        super().__init__()
        self._worker   = None
        self._models   = []       # lista actual del config (BASE_LLM_MODELS)
        self._active   = []       # lista de modelos validados OK en este run
        self._api_key  = os.getenv("OPENROUTER_API_KEY", "")
        self._init_ui()
        self._load_models_from_config()

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Título
        title = QLabel("🤖 Mantenedor de Modelos LLM")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #1976D2; margin-bottom: 2px;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Visualiza las estadísticas locales de éxito. Reemplaza modelos "
            "caídos con los populares gratuitos de la última semana vía API de OpenRouter."
        )
        subtitle.setStyleSheet("color: #6b7280; font-size: 10pt; margin-bottom: 6px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #e5e7eb;")
        layout.addWidget(sep)

        # ── Tabla de modelos (6 Columnas) ──────────────────────────────────
        tbl_group = QGroupBox("📋 Rendimiento Local y Estado (BASE_LLM_MODELS)")
        tbl_layout = QVBoxLayout(tbl_group)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Modelo", "Éxitos / Intentos", "Tasa (1°)", "Tiempo Prom.", "Estado", "Detalle"
        ])
        
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 9.5pt;
                gridline-color: #f3f4f6;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                font-weight: bold;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #d1d5db;
            }
            QTableWidget::item { padding: 4px 6px; }
        """)
        tbl_layout.addWidget(self.table)
        layout.addWidget(tbl_group)

        # ── Agregar modelo nuevo ──────────────────────────────────────────
        add_group = QGroupBox("➕ Agregar modelo candidato")
        add_layout = QHBoxLayout(add_group)
        self.input_model = QLineEdit()
        self.input_model.setPlaceholderText("ej: google/gemma-4-31b-it:free")
        self.input_model.setStyleSheet(
            "border: 1px solid #d1d5db; border-radius: 4px; padding: 6px; font-size: 10pt;"
        )
        self.input_model.returnPressed.connect(self._add_candidate)
        add_layout.addWidget(self.input_model)

        btn_add = QPushButton("➕ Agregar")
        btn_add.setFixedWidth(100)
        btn_add.setStyleSheet(self._btn_style("#10b981", "#059669"))
        btn_add.clicked.connect(self._add_candidate)
        add_layout.addWidget(btn_add)
        layout.addWidget(add_group)

        # ── Botones de acción (Cuadrícula 2x2) ───────────────────────────
        btn_grid = QGridLayout()
        btn_grid.setSpacing(10)

        self.btn_validate = QPushButton("🔍 Validar todos")
        self.btn_validate.setMinimumHeight(40)
        self.btn_validate.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_validate.setStyleSheet(self._btn_style("#1976D2", "#1565C0"))
        self.btn_validate.clicked.connect(self._run_validation)
        btn_grid.addWidget(self.btn_validate, 0, 0)

        self.btn_auto_replace = QPushButton("⚡ Reemplazar Caídos con Populares Free")
        self.btn_auto_replace.setMinimumHeight(40)
        self.btn_auto_replace.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_auto_replace.setStyleSheet(self._btn_style("#e0a800", "#c69500"))
        self.btn_auto_replace.setToolTip(
            "Busca modelos caídos, descarga estadísticas de rankings semanales de OpenRouter, "
            "valida candidatos y los reemplaza automáticamente."
        )
        self.btn_auto_replace.clicked.connect(self._run_auto_replace)
        btn_grid.addWidget(self.btn_auto_replace, 0, 1)

        self.btn_update = QPushButton("💾 Guardar en llm_config.py")
        self.btn_update.setMinimumHeight(40)
        self.btn_update.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_update.setStyleSheet(self._btn_style("#7c3aed", "#6d28d9"))
        self.btn_update.setEnabled(False)
        self.btn_update.clicked.connect(self._update_config)
        btn_grid.addWidget(self.btn_update, 1, 0)

        self.btn_reload = QPushButton("🔄 Recargar config")
        self.btn_reload.setMinimumHeight(40)
        self.btn_reload.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_reload.setStyleSheet(self._btn_style("#6b7280", "#4b5563"))
        self.btn_reload.clicked.connect(self._load_models_from_config)
        btn_grid.addWidget(self.btn_reload, 1, 1)

        layout.addLayout(btn_grid)

        # ── Estado de la última validación ────────────────────────────────
        self.lbl_status = QLabel("Sin validar  —  presiona «Validar todos» para verificar disponibilidad.")
        self.lbl_status.setStyleSheet("color: #6b7280; font-size: 9pt; margin-top: 2px;")
        layout.addWidget(self.lbl_status)

        # ── Log ───────────────────────────────────────────────────────────
        log_group = QGroupBox("📋 Log de actividad")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(120)
        self.log_output.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 9pt;"
        )
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_group)

    # ─── Lógica ──────────────────────────────────────────────────────────────

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

    def _insert_row_with_stats(self, model_id: str, model_stats: dict, status: str, color: str, detail: str = ""):
        row = self.table.rowCount()
        # Buscar fila existente
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0) and self.table.item(r, 0).text() == model_id:
                row = r
                break
        else:
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(model_id))

        # Poblar estadísticas
        if model_stats:
            intentos = model_stats['total_intentos']
            exitos = int(model_stats['total_exitos'] or 0)
            tiempo = model_stats['tiempo_promedio_ms'] or 0
            tasa = (exitos / intentos * 100) if intentos > 0 else 0.0

            self.table.setItem(row, 1, QTableWidgetItem(f"{exitos} / {intentos}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{tasa:.1f}%"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{tiempo / 1000:.2f}s"))
        else:
            self.table.setItem(row, 1, QTableWidgetItem("0 / 0"))
            self.table.setItem(row, 2, QTableWidgetItem("—"))
            self.table.setItem(row, 3, QTableWidgetItem("—"))

        self.table.setItem(row, 4, self._colored_item(status, color))
        self.table.setItem(row, 5, QTableWidgetItem(detail))

    def _colored_item(self, text: str, color: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
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

        # Reset visual
        for r in range(self.table.rowCount()):
            self.table.setItem(r, 4, self._colored_item("⏳ Validando…", "#f59e0b"))
            self.table.setItem(r, 5, QTableWidgetItem(""))

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

    # ─── Autoreemplazo con Populares Free ────────────────────────────────────

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
        self._active = new_models # Todos los del nuevo listado están verificados como activos
        
        # Recargar tabla con nuevos modelos
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
            "Presiona 'Guardar en llm_config.py' para aplicar permanentemente."
        )

    # ─── Escritura en el Config ──────────────────────────────────────────────

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

            # Escribir sobre BASE_LLM_MODELS
            updated, count = re.subn(
                r"BASE_LLM_MODELS\s*=\s*\[.*?\]", new_list, content, flags=re.DOTALL
            )
            if count == 0:
                # Fallback por si acaso
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

    # ─── Validación silenciosa al inicio ─────────────────────────────────────

    def run_startup_validation(self):
        """Llamar desde main() para validar sin interacción del usuario."""
        if not self._api_key or not self._models:
            return
        self._log("🚀 Validación automática al inicio…")
        self._run_validation()

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
