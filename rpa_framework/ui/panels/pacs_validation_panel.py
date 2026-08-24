#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Panel GUI: PacsValidationPanel
Pestaña en la GUI principal para visualizar estado, historial y configurar la validación diaria de PACS.
Solo visible cuando está activa la vista de Desarrollo.
"""

import os
import sys
import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, 
    QTimeEdit, QCheckBox, QSpinBox, QTableWidget, QTableWidgetItem, 
    QHeaderView, QMessageBox, QGraphicsDropShadowEffect, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QTime, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_FILE = BASE_DIR / "config" / "pacs_validation_config.json"
SCRIPT_PATH = BASE_DIR / "recordings" / "sistema" / "validar_pacs_diario.py"

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ris'
}

DIAS_NOMBRE = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


class PacsValidationPanel(QWidget):
    """Panel de Monitoreo y Configuración de Validación PACS."""
    
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config_data = self.load_config()
        self.is_executing = False
        
        self.init_ui()
        self.load_settings_to_ui()
        self.refresh_data()
        
        # Timer para autorefrescar el estado e historial cada 10 segundos
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(10000)

    def load_config(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error cargando config de validación PACS: {e}")
        return {
            "habilitado": True,
            "hora_validacion": "09:00",
            "dias_validacion": [0, 1, 2, 3, 4],
            "max_reintentos": 3,
            "timeout_minutos": 10,
            "delay_entre_reintentos_seg": 120,
            "telegram": {
                "enviar_alertas": True,
                "enviar_en_exito": False,
                "enviar_en_error": True,
                "dias_notificacion": [0, 1, 2, 3, 4],
                "hora_inicio_notificacion": 8,
                "hora_fin_notificacion": 19
            }
        }

    def save_config(self):
        try:
            CONFIG_FILE.parent.mkdir(exist_ok=True)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error guardando config de validación PACS: {e}")
            return False

    def init_ui(self):
        main_scroll = QScrollArea(self)
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Título
        lbl_titulo = QLabel("🔍 Validación Diaria de PACS")
        lbl_titulo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #0f172a; margin-bottom: 5px;")
        layout.addWidget(lbl_titulo)

        def apply_shadow(widget):
            shadow = QGraphicsDropShadowEffect(widget)
            shadow.setBlurRadius(8)
            shadow.setXOffset(0)
            shadow.setYOffset(2)
            shadow.setColor(QColor(0, 0, 0, 15))
            widget.setGraphicsEffect(shadow)

        # --- CARD 1: ESTADO ACTUAL ---
        card_estado = QGroupBox("Estado Actual del Servicio PACS")
        card_estado.setObjectName("operation_card")
        apply_shadow(card_estado)
        layout_estado = QVBoxLayout(card_estado)
        
        header_estado_layout = QHBoxLayout()
        
        self.lbl_badge_estado = QLabel("⚪ Sin Datos")
        self.lbl_badge_estado.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_badge_estado.setStyleSheet("color: #64748b; padding: 6px 12px; background: #f1f5f9; border-radius: 6px;")
        header_estado_layout.addWidget(self.lbl_badge_estado)
        
        header_estado_layout.addStretch()
        
        self.lbl_ultima_ejecucion = QLabel("Última verificación: --")
        self.lbl_ultima_ejecucion.setStyleSheet("color: #64748b; font-size: 10pt;")
        header_estado_layout.addWidget(self.lbl_ultima_ejecucion)
        
        layout_estado.addLayout(header_estado_layout)
        
        self.lbl_detalle_estado = QLabel("Observación: --")
        self.lbl_detalle_estado.setWordWrap(True)
        self.lbl_detalle_estado.setStyleSheet("color: #334155; margin-top: 5px; font-size: 10pt;")
        layout_estado.addWidget(self.lbl_detalle_estado)
        
        btn_layout = QHBoxLayout()
        self.btn_ejecutar_ahora = QPushButton("▶ Ejecutar Validación Ahora")
        self.btn_ejecutar_ahora.setMinimumHeight(40)
        self.btn_ejecutar_ahora.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ejecutar_ahora.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: white; border-radius: 6px; font-weight: bold; padding: 8px 16px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
            QPushButton:disabled { background-color: #94a3b8; }
        """)
        self.btn_ejecutar_ahora.clicked.connect(self.ejecutar_manual)
        btn_layout.addWidget(self.btn_ejecutar_ahora)
        btn_layout.addStretch()
        
        layout_estado.addLayout(btn_layout)
        layout.addWidget(card_estado)

        # --- CARD 2: CONFIGURACIÓN ---
        card_config = QGroupBox("⚙️ Configuración de Programación y Alertas")
        card_config.setObjectName("operation_card")
        apply_shadow(card_config)
        layout_config = QVBoxLayout(card_config)
        layout_config.setSpacing(12)
        
        # Fila 1: Habilitar y Hora
        f1_layout = QHBoxLayout()
        
        self.chk_habilitado = QCheckBox("Habilitar validación diaria automática")
        self.chk_habilitado.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        f1_layout.addWidget(self.chk_habilitado)
        
        f1_layout.addSpacing(30)
        
        lbl_hora = QLabel("Hora de validación:")
        lbl_hora.setStyleSheet("color: #0f172a; font-weight: bold;")
        f1_layout.addWidget(lbl_hora)
        
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setFixedWidth(100)
        f1_layout.addWidget(self.time_edit)
        
        f1_layout.addStretch()
        layout_config.addLayout(f1_layout)

        # Días de validación
        lbl_dias_val = QLabel("Días en que se realiza la validación:")
        lbl_dias_val.setStyleSheet("color: #475569; font-weight: 500;")
        layout_config.addWidget(lbl_dias_val)
        
        dias_val_layout = QHBoxLayout()
        self.chks_dias_val = []
        for i, nombre in enumerate(DIAS_NOMBRE):
            chk = QCheckBox(nombre)
            self.chks_dias_val.append(chk)
            dias_val_layout.addWidget(chk)
        dias_val_layout.addStretch()
        layout_config.addLayout(dias_val_layout)

        # Separador interno
        linea = QFrame()
        linea.setFrameShape(QFrame.Shape.HLine)
        linea.setFrameShadow(QFrame.Shadow.Sunken)
        linea.setStyleSheet("color: #e2e8f0;")
        layout_config.addWidget(linea)

        # Configuración Telegram
        lbl_tg_title = QLabel("🤖 Notificaciones de Telegram")
        lbl_tg_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_tg_title.setStyleSheet("color: #0f172a;")
        layout_config.addWidget(lbl_tg_title)

        tg_options_layout = QHBoxLayout()
        self.chk_tg_alertas = QCheckBox("Enviar alertas por Telegram")
        self.chk_tg_exito = QCheckBox("Notificar en éxito")
        self.chk_tg_error = QCheckBox("Notificar en error")
        self.chk_tg_error.setChecked(True)
        
        tg_options_layout.addWidget(self.chk_tg_alertas)
        tg_options_layout.addWidget(self.chk_tg_exito)
        tg_options_layout.addWidget(self.chk_tg_error)
        tg_options_layout.addStretch()
        layout_config.addLayout(tg_options_layout)

        # Días de notificación Telegram
        lbl_dias_tg = QLabel("Días en los que se enviarán notificaciones:")
        lbl_dias_tg.setStyleSheet("color: #475569; font-weight: 500;")
        layout_config.addWidget(lbl_dias_tg)
        
        dias_tg_layout = QHBoxLayout()
        self.chks_dias_tg = []
        for i, nombre in enumerate(DIAS_NOMBRE):
            chk = QCheckBox(nombre)
            self.chks_dias_tg.append(chk)
            dias_tg_layout.addWidget(chk)
        dias_tg_layout.addStretch()
        layout_config.addLayout(dias_tg_layout)

        # Rango de horas Telegram
        horas_tg_layout = QHBoxLayout()
        lbl_h_ini = QLabel("Horario de envío de notificaciones: Desde hora")
        lbl_h_ini.setStyleSheet("color: #475569;")
        horas_tg_layout.addWidget(lbl_h_ini)
        
        self.spin_h_ini = QSpinBox()
        self.spin_h_ini.setRange(0, 23)
        self.spin_h_ini.setValue(8)
        horas_tg_layout.addWidget(self.spin_h_ini)
        
        lbl_h_fin = QLabel("hasta hora")
        lbl_h_fin.setStyleSheet("color: #475569;")
        horas_tg_layout.addWidget(lbl_h_fin)
        
        self.spin_h_fin = QSpinBox()
        self.spin_h_fin.setRange(0, 23)
        self.spin_h_fin.setValue(19)
        horas_tg_layout.addWidget(self.spin_h_fin)
        
        horas_tg_layout.addStretch()
        layout_config.addLayout(horas_tg_layout)

        # Botón Guardar Configuración
        btn_save_layout = QHBoxLayout()
        self.btn_guardar_config = QPushButton("💾 Guardar Configuración")
        self.btn_guardar_config.setMinimumHeight(38)
        self.btn_guardar_config.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_guardar_config.setStyleSheet("""
            QPushButton {
                background-color: #10b981; color: white; border-radius: 6px; font-weight: bold; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_guardar_config.clicked.connect(self.guardar_config_desde_ui)
        btn_save_layout.addWidget(self.btn_guardar_config)
        btn_save_layout.addStretch()
        layout_config.addLayout(btn_save_layout)

        layout.addWidget(card_config)

        # --- CARD 3: HISTORIAL ---
        card_historial = QGroupBox("📋 Historial de Validaciones (Últimos 30 registros)")
        card_historial.setObjectName("operation_card")
        apply_shadow(card_historial)
        layout_historial = QVBoxLayout(card_historial)

        historial_header = QHBoxLayout()
        historial_header.addStretch()
        self.btn_refrescar = QPushButton("🔄 Refrescar Tabla")
        self.btn_refrescar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refrescar.clicked.connect(self.refresh_data)
        historial_header.addWidget(self.btn_refrescar)
        layout_historial.addLayout(historial_header)

        self.tabla_historial = QTableWidget()
        self.tabla_historial.setColumnCount(5)
        self.tabla_historial.setHorizontalHeaderLabels(["Fecha", "Estado", "Duración", "Intentos", "Observación"])
        self.tabla_historial.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_historial.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_historial.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_historial.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_historial.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tabla_historial.setMinimumHeight(220)
        self.tabla_historial.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; gridline-color: #f1f5f9;
            }
            QHeaderView::section {
                background-color: #f8fafc; font-weight: bold; color: #334155; padding: 6px; border: none;
            }
        """)
        layout_historial.addWidget(self.tabla_historial)

        layout.addWidget(card_historial)
        
        main_scroll.setWidget(content_widget)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_scroll)

    def load_settings_to_ui(self):
        c = self.config_data
        self.chk_habilitado.setChecked(c.get("habilitado", True))
        
        hora_str = c.get("hora_validacion", "09:00")
        try:
            parts = [int(x) for x in hora_str.split(":")]
            self.time_edit.setTime(QTime(parts[0], parts[1]))
        except Exception:
            self.time_edit.setTime(QTime(9, 0))
            
        dias_val = c.get("dias_validacion", [0, 1, 2, 3, 4])
        for i, chk in enumerate(self.chks_dias_val):
            chk.setChecked(i in dias_val)
            
        tg = c.get("telegram", {})
        self.chk_tg_alertas.setChecked(tg.get("enviar_alertas", True))
        self.chk_tg_exito.setChecked(tg.get("enviar_en_exito", False))
        self.chk_tg_error.setChecked(tg.get("enviar_en_error", True))
        
        dias_tg = tg.get("dias_notificacion", [0, 1, 2, 3, 4])
        for i, chk in enumerate(self.chks_dias_tg):
            chk.setChecked(i in dias_tg)
            
        self.spin_h_ini.setValue(tg.get("hora_inicio_notificacion", 8))
        self.spin_h_fin.setValue(tg.get("hora_fin_notificacion", 19))

    def guardar_config_desde_ui(self):
        self.config_data["habilitado"] = self.chk_habilitado.isChecked()
        self.config_data["hora_validacion"] = self.time_edit.time().toString("HH:mm")
        
        dias_val = [i for i, chk in enumerate(self.chks_dias_val) if chk.isChecked()]
        self.config_data["dias_validacion"] = dias_val
        
        dias_tg = [i for i, chk in enumerate(self.chks_dias_tg) if chk.isChecked()]
        self.config_data["telegram"] = {
            "enviar_alertas": self.chk_tg_alertas.isChecked(),
            "enviar_en_exito": self.chk_tg_exito.isChecked(),
            "enviar_en_error": self.chk_tg_error.isChecked(),
            "dias_notificacion": dias_tg,
            "hora_inicio_notificacion": self.spin_h_ini.value(),
            "hora_fin_notificacion": self.spin_h_fin.value()
        }
        
        if self.save_config():
            QMessageBox.information(self, "Configuración Guardada", "La configuración de validación PACS se guardó correctamente.")
        else:
            QMessageBox.critical(self, "Error", "No se pudo guardar el archivo de configuración.")

    def refresh_data(self):
        """Carga el último estado y el historial desde ris.validacion_pacs."""
        if not HAS_MYSQL:
            self.lbl_badge_estado.setText("⚠️ MySQL no disponible")
            return

        try:
            conn = mysql.connector.connect(**DB_CONFIG, connect_timeout=3)
            cursor = conn.cursor(dictionary=True)
            
            # Verificar si existe la tabla
            cursor.execute("SHOW TABLES LIKE 'validacion_pacs'")
            if not cursor.fetchone():
                conn.close()
                return

            # Cargar última ejecución
            cursor.execute("SELECT * FROM ris.validacion_pacs ORDER BY id DESC LIMIT 1")
            ultimo = cursor.fetchone()
            
            if ultimo:
                estado = ultimo.get("estado", "Sin Datos")
                fecha = ultimo.get("fecha_validacion", "--")
                obs = ultimo.get("observacion", "--")
                
                if estado == "Exitoso":
                    self.lbl_badge_estado.setText("🟢 Exitoso")
                    self.lbl_badge_estado.setStyleSheet("color: #065f46; background: #d1fae5; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
                elif estado == "Error":
                    self.lbl_badge_estado.setText("🔴 Error")
                    self.lbl_badge_estado.setStyleSheet("color: #991b1b; background: #fee2e2; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
                elif estado == "En Proceso":
                    self.lbl_badge_estado.setText("🟡 En Proceso")
                    self.lbl_badge_estado.setStyleSheet("color: #854d0e; background: #fef9c3; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
                else:
                    self.lbl_badge_estado.setText(f"⚪ {estado}")
                    self.lbl_badge_estado.setStyleSheet("color: #64748b; background: #f1f5f9; padding: 6px 12px; border-radius: 6px;")

                self.lbl_ultima_ejecucion.setText(f"Última verificación: {fecha}")
                self.lbl_detalle_estado.setText(f"Observación: {obs or 'Sin observaciones'}")
            
            # Cargar Historial (últimos 30)
            cursor.execute("SELECT * FROM ris.validacion_pacs ORDER BY id DESC LIMIT 30")
            registros = cursor.fetchall()
            
            self.tabla_historial.setRowCount(0)
            for r in registros:
                row_idx = self.tabla_historial.rowCount()
                self.tabla_historial.insertRow(row_idx)
                
                f_str = str(r.get("fecha_validacion", ""))
                est_str = r.get("estado", "")
                dur_str = f"{r.get('duracion_segundos', 0)}s" if r.get('duracion_segundos') is not None else "--"
                int_str = str(r.get("intentos", 1))
                obs_str = r.get("observacion") or ""
                
                self.tabla_historial.setItem(row_idx, 0, QTableWidgetItem(f_str))
                
                item_est = QTableWidgetItem(est_str)
                if est_str == "Exitoso":
                    item_est.setForeground(QColor("#059669"))
                elif est_str == "Error":
                    item_est.setForeground(QColor("#dc2626"))
                elif est_str == "En Proceso":
                    item_est.setForeground(QColor("#d97706"))
                self.tabla_historial.setItem(row_idx, 1, item_est)
                
                self.tabla_historial.setItem(row_idx, 2, QTableWidgetItem(dur_str))
                self.tabla_historial.setItem(row_idx, 3, QTableWidgetItem(int_str))
                self.tabla_historial.setItem(row_idx, 4, QTableWidgetItem(obs_str))

            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error al refrescar datos de validación PACS: {e}")

    def ejecutar_manual(self):
        reply = QMessageBox.question(
            self, "Confirmar Validación PACS",
            "¿Desea iniciar la validación de PACS en este momento?\n"
            "Esto ejecutará el workflow Valida_pacs.json en segundo plano.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.btn_ejecutar_ahora.setEnabled(False)
        self.btn_ejecutar_ahora.setText("⏳ Ejecutando validación...")

        def _worker():
            try:
                proc = subprocess.Popen([sys.executable, str(SCRIPT_PATH), "--manual"])
                proc.wait()
            except Exception as e:
                print(f"Error ejecutando script de validación: {e}")
            finally:
                # Usar QTimer singleShot para reactivar el botón en la thread principal
                QTimer.singleShot(0, self._on_manual_finished)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_manual_finished(self):
        self.btn_ejecutar_ahora.setEnabled(True)
        self.btn_ejecutar_ahora.setText("▶ Ejecutar Validación Ahora")
        self.refresh_data()
        QMessageBox.information(self, "Validación Finalizada", "El proceso manual de validación de PACS ha finalizado.")
