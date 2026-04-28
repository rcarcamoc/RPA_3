# -*- coding: utf-8 -*-
"""
debug_panel.py — Panel de depuración de scripts RPA.

Tab integrado en la GUI principal que permite:
  - Seleccionar un script .py de la lista de grabaciones
  - Ver información del script seleccionado
  - Lanzar el depurador interactivo (DebugOverlay)
  - Ver el log de ejecución en tiempo real
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QTextEdit, QListWidgetItem, QMessageBox,
    QGroupBox, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QFont, QColor
from pathlib import Path
from datetime import datetime

from utils.paths import get_all_recordings, RECORDINGS_DIR


class DebugPanel(QWidget):
    """Panel de selección y lanzamiento del depurador de scripts."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.worker = None
        self.overlay = None
        self.init_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Título ---
        title = QLabel("🐛 Depurador de Scripts RPA")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #1976D2; margin-bottom: 4px;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Selecciona un script grabado y ejecútalo paso a paso con control total."
        )
        subtitle.setStyleSheet("color: #6b7280; font-size: 10pt; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        # --- Separador ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #e5e7eb;")
        layout.addWidget(sep)

        # --- Splitter principal ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: lista de scripts
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)

        lbl_list = QLabel("📂 Scripts disponibles:")
        lbl_list.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        left_layout.addWidget(lbl_list)

        self.scripts_list = QListWidget()
        self.scripts_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: #ffffff;
                font-size: 10pt;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #f3f4f6;
            }
            QListWidget::item:selected {
                background-color: #eff6ff;
                color: #1e40af;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: #f9fafb;
            }
        """)
        self.scripts_list.currentItemChanged.connect(self._on_script_selected)
        left_layout.addWidget(self.scripts_list)

        btn_refresh = QPushButton("🔄 Recargar lista")
        btn_refresh.clicked.connect(self.load_scripts)
        left_layout.addWidget(btn_refresh)

        splitter.addWidget(left_widget)

        # Panel derecho: info + botón de lanzamiento
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)

        # Info del script seleccionado
        info_group = QGroupBox("ℹ️ Script seleccionado")
        info_layout = QVBoxLayout(info_group)

        self.lbl_script_name = QLabel("Ninguno")
        self.lbl_script_name.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.lbl_script_name.setStyleSheet("color: #1976D2;")
        self.lbl_script_name.setWordWrap(True)
        info_layout.addWidget(self.lbl_script_name)

        self.lbl_script_info = QLabel("Selecciona un script de la lista")
        self.lbl_script_info.setStyleSheet("color: #6b7280; font-size: 9pt;")
        self.lbl_script_info.setWordWrap(True)
        info_layout.addWidget(self.lbl_script_info)

        self.lbl_steps_info = QLabel("")
        self.lbl_steps_info.setStyleSheet("color: #374151; font-size: 10pt;")
        info_layout.addWidget(self.lbl_steps_info)

        right_layout.addWidget(info_group)

        # Botón principal de debug
        self.btn_debug = QPushButton("🐛  Iniciar Depurador")
        self.btn_debug.setMinimumHeight(52)
        self.btn_debug.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_debug.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1976D2, stop:1 #1565C0);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2196F3, stop:1 #1976D2);
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
            QPushButton:disabled {
                background-color: #9ca3af;
                color: #e5e7eb;
            }
        """)
        self.btn_debug.setEnabled(False)
        self.btn_debug.clicked.connect(self.launch_debugger)
        right_layout.addWidget(self.btn_debug)

        # Instrucciones de uso
        help_group = QGroupBox("💡 Cómo usar el depurador")
        help_layout = QVBoxLayout(help_group)
        help_text = QLabel(
            "1. Selecciona un script .py de la lista\n"
            "2. Haz clic en <b>Iniciar Depurador</b>\n"
            "3. En la ventana flotante:\n"
            "   • <b>⏭ Siguiente</b> — avanza un paso manualmente\n"
            "   • <b>⏯ Paso a Paso</b> — avance automático con delay\n"
            "   • <b>▶ Ejecutar</b> — ejecuta todo sin pausa\n"
            "   • <b>⏮ Anterior</b> — retrocede un paso\n"
            "   • <b>🔄 Reiniciar</b> — vuelve al paso 1\n"
            "4. Edita el código en el visor y presiona\n"
            "   <b>💾 Guardar y Reiniciar</b> para probar cambios"
        )
        help_text.setTextFormat(Qt.TextFormat.RichText)
        help_text.setStyleSheet("color: #374151; font-size: 9pt; line-height: 1.5;")
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)
        right_layout.addWidget(help_group)

        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 350])
        layout.addWidget(splitter)

        # --- Log de actividad ---
        log_group = QGroupBox("📋 Log de actividad")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(130)
        self.log_output.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 9pt;"
        )
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_group)

        # Cargar scripts al inicio
        self.load_scripts()

    # ------------------------------------------------------------------
    # Lógica
    # ------------------------------------------------------------------

    def load_scripts(self):
        """Carga la lista de scripts .py disponibles."""
        self.scripts_list.clear()

        all_files = get_all_recordings(recording_type=None)
        py_files = [p for p in all_files if p.suffix.lower() == ".py"]

        if not py_files:
            item = QListWidgetItem("(No se encontraron scripts .py)")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.scripts_list.addItem(item)
            return

        for p in py_files:
            try:
                display = p.relative_to(RECORDINGS_DIR)
            except ValueError:
                display = p.name

            date_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            item = QListWidgetItem(f"🐍 {display}  ({date_str})")
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            self.scripts_list.addItem(item)

        self._log(f"✅ {len(py_files)} scripts cargados")

    def _on_script_selected(self, current, previous):
        """Actualiza la info cuando se selecciona un script."""
        if not current:
            self.btn_debug.setEnabled(False)
            return

        path_str = current.data(Qt.ItemDataRole.UserRole)
        if not path_str:
            return

        p = Path(path_str)
        self.lbl_script_name.setText(p.name)

        size_kb = p.stat().st_size / 1024
        date_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        self.lbl_script_info.setText(
            f"📁 {p.parent}\n📅 Modificado: {date_str}  |  📦 {size_kb:.1f} KB"
        )

        # Contar pasos detectados
        try:
            from ui.debug_worker import extract_steps_from_script
            steps = extract_steps_from_script(path_str)
            n = len(steps)
            self.lbl_steps_info.setText(f"🔢 Pasos detectados: {n}")
        except Exception:
            self.lbl_steps_info.setText("🔢 Pasos: (no calculado)")

        self.btn_debug.setEnabled(True)

    def launch_debugger(self):
        """Lanza el DebugOverlay para el script seleccionado."""
        current = self.scripts_list.currentItem()
        if not current:
            QMessageBox.warning(self, "⚠️ Advertencia", "Selecciona un script de la lista")
            return

        path_str = current.data(Qt.ItemDataRole.UserRole)
        if not Path(path_str).exists():
            QMessageBox.critical(self, "❌ Error", f"Archivo no encontrado:\n{path_str}")
            return

        # Si ya hay un overlay abierto, cerrarlo
        if self.overlay and self.overlay.isVisible():
            self.overlay.close()

        try:
            from ui.debug_worker import DebugWorker, extract_steps_from_script
            from ui.debug_overlay import DebugOverlay

            steps = extract_steps_from_script(path_str)
            if not steps:
                QMessageBox.warning(
                    self, "⚠️ Sin pasos",
                    "No se pudieron detectar pasos en el script.\n"
                    "Verifica que el script tenga comentarios '# Acción N:' o un método run()."
                )
                return

            self.worker = DebugWorker(path_str)
            self.overlay = DebugOverlay(path_str, steps, self.worker, parent=None)

            # Conectar log del worker al panel
            self.worker.log_line.connect(self._log)
            self.worker.script_finished.connect(self._on_debug_finished)

            self.overlay.show()
            self.worker.start()

            self._log(f"🐛 Depurador iniciado: {Path(path_str).name}")

        except Exception as e:
            import traceback
            QMessageBox.critical(self, "❌ Error", f"Error al iniciar el depurador:\n{e}")
            self._log(f"❌ Error: {e}\n{traceback.format_exc()}")

    def _on_debug_finished(self, success: bool):
        status = "✅ Completado" if success else "❌ Finalizado con errores"
        self._log(f"{status}")

    def _log(self, text: str):
        # Filtrar ruido antes de mostrar en la UI
        noise_keywords = [
            "==================================================",
            "✅ Dashboard actualizado",
            "categorical units to plot",
            "Using categorical units"
        ]
        
        if any(kw in text for kw in noise_keywords):
            return

        self.log_output.append(text)
        sb = self.log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

