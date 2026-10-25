# -*- coding: utf-8 -*-
"""
llm_panel_actions_mixin.py — Lógica de negocio, consultas a BD, actualización de
configuración y gestión de autoverificación para LLMPanel.
Extraído de ui/panels/llm_panel.py.
"""

import sys
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import QLabel, QTableWidgetItem, QMessageBox
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont, QColor

from .llm_workers import (
    BackgroundAutoVerificationWorker,
    ValidationWorker,
    AutoReplaceWorker,
)

# Ruta al directorio utils (padre de ui/panels)
UTILS_DIR = Path(__file__).resolve().parent.parent.parent / "utils"
CONFIG_FILE = UTILS_DIR / "llm_config.py"


class LLMPanelActionsMixin:
    """Mixin con las acciones, consultas a BD y controladores de eventos de LLMPanel."""

    # ─── Lógica de Datos y Modelos ───────────────────────────────────────────

    def _query_db_stats(self) -> dict:
        """Consulta ris.log_llm_ranking y ris.catalogo_modelos_llm para obtener estadísticas y aptitudes."""
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
            for row in rows:
                stats[row['modelo']] = row

            cursor.execute("""
                SELECT modelo, proveedor, tamano_estimado, apto_ocr, apto_patologia, justificacion_agente
                FROM ris.catalogo_modelos_llm
            """)
            cat_rows = cursor.fetchall()
            self._catalogo_cache = {r['modelo']: r for r in cat_rows}

            conn.close()
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

        # Columna 2: Aptitud / Rol dictaminada por el Catálogo / Agente
        cat_info = getattr(self, '_catalogo_cache', {}).get(model_id)
        apt_text = "⚡ Solo OCR"
        apt_color = "#0284c7"
        if cat_info:
            if cat_info.get("apto_patologia") and cat_info.get("apto_ocr"):
                apt_text = "⚡ OCR + 🩺 Patología"
                apt_color = "#7c3aed"
            elif cat_info.get("apto_patologia"):
                apt_text = "🩺 Solo Patología"
                apt_color = "#059669"
            if not detail and cat_info.get("justificacion_agente"):
                detail = cat_info.get("justificacion_agente")
        elif any(kw in model_id.lower() for kw in ["90b", "30b", "31b", "120b"]):
            apt_text = "⚡ OCR + 🩺 Patología"
            apt_color = "#7c3aed"

        apt_item = QTableWidgetItem(apt_text)
        apt_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        apt_item.setForeground(QColor(apt_color))
        self.table.setItem(row, 2, apt_item)

        # Poblar estadísticas (Columnas 3, 4, 5)
        if model_stats:
            intentos = model_stats['total_intentos']
            exitos = int(model_stats['total_exitos'] or 0)
            tiempo = model_stats['tiempo_promedio_ms'] or 0
            tasa = (exitos / intentos * 100) if intentos > 0 else 0.0

            self.table.setItem(row, 3, QTableWidgetItem(f"{exitos} / {intentos}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{tasa:.1f}%"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{tiempo / 1000:.2f}s"))
        else:
            self.table.setItem(row, 3, QTableWidgetItem("0 / 0"))
            self.table.setItem(row, 4, QTableWidgetItem("—"))
            self.table.setItem(row, 5, QTableWidgetItem("—"))

        # Columna 6: Estado, Columna 7: Detalle
        self.table.setItem(row, 6, self._colored_item(status, color))
        self.table.setItem(row, 7, QTableWidgetItem(detail))

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
            if freq == "diario_24h":
                idx = 0
            elif freq in ["cada_6h", "6h", "cada_6_horas"]:
                idx = 1
            else:
                idx = 2
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
            sel_idx = self.combo_auto_freq.currentIndex()
            if sel_idx == 0:
                cfg["frequency"] = "diario_24h"
            elif sel_idx == 1:
                cfg["frequency"] = "cada_6h"
            else:
                cfg["frequency"] = "hora_fija"
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
