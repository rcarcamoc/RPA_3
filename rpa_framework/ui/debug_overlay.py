# -*- coding: utf-8 -*-
"""
debug_overlay.py — Ventana flotante de control para el depurador RPA.

Contiene:
  - Panel de botones de control (Ejecutar, Paso a Paso, Pausar, Siguiente, Anterior, Detener, Reiniciar)
  - Slider de velocidad
  - Indicador de estado y progreso
  - Visor/editor de código con resaltado del paso actual
  - Botón Guardar y Reiniciar para aplicar cambios al script
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSlider, QProgressBar, QSizePolicy, QFrame,
    QSplitter, QWidget, QScrollBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import (
    QFont, QTextCursor, QTextCharFormat, QColor,
    QSyntaxHighlighter, QTextDocument, QKeySequence
)
from pathlib import Path
from typing import List, Tuple, Optional
import re


# ---------------------------------------------------------------------------
# Syntax Highlighter básico para Python
# ---------------------------------------------------------------------------

class PythonHighlighter(QSyntaxHighlighter):
    """Resaltado de sintaxis Python básico."""

    def __init__(self, document: QTextDocument):
        super().__init__(document)
        self._rules = []

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#569CD6"))
        kw_fmt.setFontWeight(700)
        keywords = [
            "import", "from", "class", "def", "return", "if", "else", "elif",
            "for", "while", "try", "except", "finally", "with", "as", "in",
            "not", "and", "or", "True", "False", "None", "self", "pass",
            "break", "continue", "raise", "yield", "lambda", "global", "nonlocal"
        ]
        for kw in keywords:
            self._rules.append((re.compile(rf"\b{kw}\b"), kw_fmt))

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#CE9178"))
        self._rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), str_fmt))
        self._rules.append((re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), str_fmt))
        self._rules.append((re.compile(r'"""[\s\S]*?"""'), str_fmt))
        self._rules.append((re.compile(r"'''[\s\S]*?'''"), str_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6A9955"))
        self._rules.append((re.compile(r"#[^\n]*"), comment_fmt))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#B5CEA8"))
        self._rules.append((re.compile(r"\b\d+\.?\d*\b"), num_fmt))

        func_fmt = QTextCharFormat()
        func_fmt.setForeground(QColor("#DCDCAA"))
        self._rules.append((re.compile(r"\b\w+(?=\()"), func_fmt))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ---------------------------------------------------------------------------
# Overlay principal
# ---------------------------------------------------------------------------

class DebugOverlay(QDialog):
    """
    Ventana flotante de depuración.

    Parámetros:
        script_path: ruta al script .py a depurar
        steps: lista de (start_line, end_line, desc) extraída por debug_worker
        worker: instancia de DebugWorker ya configurada
        parent: widget padre (opcional)
    """

    def __init__(self, script_path: str, steps: List[Tuple[int, int, str]], worker, parent=None):
        super().__init__(parent)
        self.script_path = script_path
        self.steps = steps
        self.worker = worker
        self.total_steps = len(steps)
        self.current_step = 0
        self._is_running = False
        self._is_paused = False
        self._step_mode = False
        self._auto_run = False

        self.setWindowTitle(f"🐛 RPA Debugger — {Path(script_path).name}")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(900, 650)
        self.setMinimumSize(700, 500)

        self._apply_dark_theme()
        self._init_ui()
        self._connect_worker()
        self._load_source()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', 'Consolas', sans-serif;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 10pt;
                font-weight: 600;
                min-height: 32px;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #89b4fa;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            QPushButton:disabled {
                background-color: #1e1e2e;
                color: #585b70;
                border-color: #313244;
            }
            QPushButton#btn_run {
                background-color: #40a02b;
                color: white;
                border-color: #40a02b;
            }
            QPushButton#btn_run:hover { background-color: #4ec94c; }
            QPushButton#btn_step_mode {
                background-color: #1e66f5;
                color: white;
                border-color: #1e66f5;
            }
            QPushButton#btn_step_mode:hover { background-color: #4d8ef5; }
            QPushButton#btn_pause {
                background-color: #df8e1d;
                color: white;
                border-color: #df8e1d;
            }
            QPushButton#btn_pause:hover { background-color: #f0a832; }
            QPushButton#btn_stop {
                background-color: #d20f39;
                color: white;
                border-color: #d20f39;
            }
            QPushButton#btn_stop:hover { background-color: #e8294f; }
            QPushButton#btn_save {
                background-color: #8839ef;
                color: white;
                border-color: #8839ef;
            }
            QPushButton#btn_save:hover { background-color: #a45ef5; }
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                selection-background-color: #45475a;
            }
            QProgressBar {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 4px;
                height: 8px;
                text-align: center;
                color: #cdd6f4;
                font-size: 9pt;
            }
            QProgressBar::chunk {
                background-color: #89b4fa;
                border-radius: 4px;
            }
            QSlider::groove:horizontal {
                background: #313244;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #89b4fa;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #89b4fa;
                border-radius: 3px;
            }
            QFrame#separator {
                background-color: #45475a;
                max-height: 1px;
            }
            QSplitter::handle {
                background-color: #45475a;
                width: 2px;
            }
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # --- Status bar ---
        status_layout = QHBoxLayout()

        self.lbl_status = QLabel("⚪ Listo")
        self.lbl_status.setStyleSheet("font-size: 12pt; font-weight: bold;")
        status_layout.addWidget(self.lbl_status)

        status_layout.addStretch()

        self.lbl_step = QLabel("Paso 0 / 0")
        self.lbl_step.setStyleSheet("font-size: 11pt; color: #89b4fa;")
        status_layout.addWidget(self.lbl_step)

        main_layout.addLayout(status_layout)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, max(1, self.total_steps))
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m pasos")
        self.progress.setFixedHeight(18)
        main_layout.addWidget(self.progress)

        # Separator
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(sep)

        # --- Control buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_run = QPushButton("▶ Ejecutar")
        self.btn_run.setObjectName("btn_run")
        self.btn_run.setToolTip("Ejecutar todos los pasos restantes sin pausa")
        self.btn_run.clicked.connect(self._on_run)

        self.btn_step_mode = QPushButton("⏯ Paso a Paso")
        self.btn_step_mode.setObjectName("btn_step_mode")
        self.btn_step_mode.setToolTip("Avanzar automáticamente con pausa entre cada paso")
        self.btn_step_mode.clicked.connect(self._on_step_mode)

        self.btn_pause = QPushButton("⏸ Pausar")
        self.btn_pause.setObjectName("btn_pause")
        self.btn_pause.setToolTip("Pausar / reanudar ejecución")
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_pause.setEnabled(False)

        self.btn_next = QPushButton("⏭ Siguiente")
        self.btn_next.setToolTip("Ejecutar el siguiente paso manualmente")
        self.btn_next.clicked.connect(self._on_next)

        self.btn_back = QPushButton("⏮ Anterior")
        self.btn_back.setToolTip("Retroceder al paso anterior")
        self.btn_back.clicked.connect(self._on_back)
        self.btn_back.setEnabled(False)

        self.btn_restart = QPushButton("🔄 Reiniciar")
        self.btn_restart.setToolTip("Volver al paso 1")
        self.btn_restart.clicked.connect(self._on_restart)

        self.btn_stop = QPushButton("⏹ Detener")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setToolTip("Abortar ejecución")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)

        for btn in [self.btn_run, self.btn_step_mode, self.btn_pause,
                    self.btn_next, self.btn_back, self.btn_restart, self.btn_stop]:
            btn_layout.addWidget(btn)

        main_layout.addLayout(btn_layout)

        # --- Speed slider ---
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("⚡ Velocidad:"))

        self.lbl_speed = QLabel("1.0s")
        self.lbl_speed.setFixedWidth(35)
        self.lbl_speed.setStyleSheet("color: #89b4fa;")

        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(1, 50)   # 0.1s – 5.0s (×0.1)
        self.slider_speed.setValue(10)       # default 1.0s
        self.slider_speed.setFixedWidth(180)
        self.slider_speed.setToolTip("Delay entre pasos en modo Paso a Paso")
        self.slider_speed.valueChanged.connect(self._on_speed_changed)

        speed_layout.addWidget(self.slider_speed)
        speed_layout.addWidget(self.lbl_speed)
        speed_layout.addStretch()

        # Save button
        self.btn_save = QPushButton("💾 Guardar y Reiniciar")
        self.btn_save.setObjectName("btn_save")
        self.btn_save.setToolTip("Guarda los cambios del editor y reinicia desde el paso 1")
        self.btn_save.clicked.connect(self._on_save_restart)
        speed_layout.addWidget(self.btn_save)

        main_layout.addLayout(speed_layout)

        # Separator
        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(sep2)

        # --- Splitter: code editor + log ---
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Code editor
        code_widget = QWidget()
        code_layout = QVBoxLayout(code_widget)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(4)

        code_header = QHBoxLayout()
        lbl_code = QLabel("📄 Código fuente (editable):")
        lbl_code.setStyleSheet("font-weight: bold; color: #89b4fa;")
        code_header.addWidget(lbl_code)
        code_header.addStretch()
        self.lbl_current_action = QLabel("")
        self.lbl_current_action.setStyleSheet("color: #f9e2af; font-style: italic;")
        code_header.addWidget(self.lbl_current_action)
        code_layout.addLayout(code_header)

        self.code_editor = QTextEdit()
        self.code_editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.code_editor.setTabStopDistance(28)
        self.highlighter = PythonHighlighter(self.code_editor.document())
        code_layout.addWidget(self.code_editor)

        splitter.addWidget(code_widget)

        # Log output
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)

        lbl_log = QLabel("📋 Log de ejecución:")
        lbl_log.setStyleSheet("font-weight: bold; color: #89b4fa;")
        log_layout.addWidget(lbl_log)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(160)
        self.log_output.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 9pt;"
        )
        log_layout.addWidget(self.log_output)

        splitter.addWidget(log_widget)
        splitter.setSizes([420, 160])

        main_layout.addWidget(splitter)

    def _connect_worker(self):
        """Conecta las señales del worker a los slots del overlay."""
        w = self.worker
        w.script_ready.connect(self._on_script_ready)
        w.step_ready.connect(self._on_step_ready)
        w.step_started.connect(self._on_step_started)
        w.step_done.connect(self._on_step_done)
        w.step_error.connect(self._on_step_error)
        w.log_line.connect(self._on_log_line)
        w.script_finished.connect(self._on_script_finished)

    def _load_source(self):
        """Carga el código fuente en el editor."""
        try:
            with open(self.script_path, "r", encoding="utf-8") as f:
                source = f.read()
            self.code_editor.setPlainText(source)
        except Exception as e:
            self.code_editor.setPlainText(f"# Error al cargar el archivo:\n# {e}")

    # ------------------------------------------------------------------
    # Resaltado de paso actual
    # ------------------------------------------------------------------

    def _highlight_step(self, step_n: int):
        """Resalta el bloque de código correspondiente al paso N."""
        if step_n < 1 or step_n > len(self.steps):
            return

        start_line, end_line, desc = self.steps[step_n - 1]

        # Limpiar resaltado anterior
        cursor = self.code_editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        fmt_clear = QTextCharFormat()
        fmt_clear.setBackground(QColor("transparent"))
        cursor.setCharFormat(fmt_clear)
        cursor.clearSelection()

        # Aplicar resaltado amarillo al bloque actual
        doc = self.code_editor.document()
        fmt_highlight = QTextCharFormat()
        fmt_highlight.setBackground(QColor("#3d3a00"))  # amarillo oscuro

        block = doc.findBlockByLineNumber(start_line - 1)
        end_block = doc.findBlockByLineNumber(end_line - 1)

        if block.isValid():
            cursor = QTextCursor(block)
            if end_block.isValid():
                end_cursor = QTextCursor(end_block)
                end_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
                cursor.setPosition(block.position())
                cursor.setPosition(end_cursor.position(), QTextCursor.MoveMode.KeepAnchor)
            else:
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)

            cursor.setCharFormat(fmt_highlight)

            # Scroll al bloque resaltado
            scroll_cursor = QTextCursor(block)
            self.code_editor.setTextCursor(scroll_cursor)
            self.code_editor.ensureCursorVisible()

        self.lbl_current_action.setText(f"→ {desc[:60]}")

    # ------------------------------------------------------------------
    # Slots de control (botones)
    # ------------------------------------------------------------------

    def _on_run(self):
        """▶ Ejecutar: modo continuo sin pausa."""
        self._auto_run = True
        self._step_mode = False
        self._is_running = True
        self._is_paused = False
        self._update_button_states()
        self._set_status("🟢 Ejecutando", "#a6e3a1")
        self.worker.set_auto_run(True)

    def _on_step_mode(self):
        """⏯ Paso a Paso: avance automático con delay."""
        self._step_mode = True
        self._auto_run = False
        self._is_running = True
        self._is_paused = False
        self._update_button_states()
        delay = self.slider_speed.value() / 10.0
        self._set_status("⏯ Paso a Paso", "#89b4fa")
        self.worker.set_step_mode(True, delay)

    def _on_pause(self):
        """⏸ Pausar / Reanudar."""
        if self._is_paused:
            self._is_paused = False
            self.btn_pause.setText("⏸ Pausar")
            self._set_status("🟢 Ejecutando", "#a6e3a1")
            self.worker.set_paused(False)
        else:
            self._is_paused = True
            self.btn_pause.setText("▶ Reanudar")
            self._set_status("🟡 Pausado", "#f9e2af")
            self.worker.set_paused(True)

    def _on_next(self):
        """⏭ Siguiente paso manual."""
        self._auto_run = False
        self._step_mode = False
        self._is_running = True
        self._is_paused = False
        self._update_button_states()
        self._set_status("⏭ Avanzando...", "#89b4fa")
        self.worker.cmd_next()

    def _on_back(self):
        """⏮ Paso anterior."""
        self._set_status("⏮ Retrocediendo...", "#f9e2af")
        self.worker.cmd_back()

    def _on_restart(self):
        """🔄 Reiniciar desde el paso 1."""
        self._auto_run = False
        self._step_mode = False
        self._is_running = False
        self._is_paused = False
        self.current_step = 0
        self.progress.setValue(0)
        self.lbl_step.setText(f"Paso 0 / {self.total_steps}")
        self._set_status("🔄 Reiniciando...", "#cba6f7")
        self._update_button_states()
        self.worker.cmd_restart()

    def _on_stop(self):
        """⏹ Detener ejecución."""
        self._auto_run = False
        self._step_mode = False
        self._is_running = False
        self._is_paused = False
        self._set_status("⏹ Detenido", "#f38ba8")
        self._update_button_states()
        self.worker.cmd_stop()

    def _on_speed_changed(self, value: int):
        delay = value / 10.0
        self.lbl_speed.setText(f"{delay:.1f}s")
        self.worker.set_step_delay(delay)

    def _on_save_restart(self):
        """💾 Guardar cambios y reiniciar desde el paso 1."""
        try:
            new_source = self.code_editor.toPlainText()
            with open(self.script_path, "w", encoding="utf-8") as f:
                f.write(new_source)
            self._log("💾 Archivo guardado. Reiniciando...")

            # Recargar pasos (el código puede haber cambiado)
            from ui.debug_worker import extract_steps_from_script
            self.steps = extract_steps_from_script(self.script_path)
            self.total_steps = len(self.steps)
            self.progress.setRange(0, max(1, self.total_steps))
            self.worker.steps = self.steps
            self.worker.total_steps = self.total_steps

            self._on_restart()
        except Exception as e:
            self._log(f"❌ Error al guardar: {e}")

    # ------------------------------------------------------------------
    # Slots del worker
    # ------------------------------------------------------------------

    @pyqtSlot(int)
    def _on_script_ready(self, total: int):
        self.total_steps = total
        self.progress.setRange(0, max(1, total))
        self.lbl_step.setText(f"Paso 0 / {total}")
        self._set_status("⚪ Listo — presiona ▶ o ⏭", "#cdd6f4")
        self._log(f"✅ Script cargado: {total} pasos detectados")

    @pyqtSlot(int, str)
    def _on_step_ready(self, n: int, desc: str):
        self.current_step = n
        self.lbl_step.setText(f"Paso {n} / {self.total_steps}")
        self.progress.setValue(n)
        self._highlight_step(n)
        self.btn_back.setEnabled(n > 1)
        self.btn_stop.setEnabled(True)

    @pyqtSlot(int, str)
    def _on_step_started(self, n: int, desc: str):
        self._set_status(f"🟢 Ejecutando paso {n}", "#a6e3a1")
        self._log(f"▶ [{n}/{self.total_steps}] {desc}")

    @pyqtSlot(int)
    def _on_step_done(self, n: int):
        self._log(f"✅ Paso {n} completado")

    @pyqtSlot(int, str)
    def _on_step_error(self, n: int, msg: str):
        self._set_status(f"🔴 Error en paso {n}", "#f38ba8")
        self._log(f"❌ Error en paso {n}: {msg}")
        self._auto_run = False
        self._step_mode = False
        self._is_running = False
        self._update_button_states()

    @pyqtSlot(str)
    def _on_log_line(self, line: str):
        self._log(line)

    @pyqtSlot(bool)
    def _on_script_finished(self, success: bool):
        self._is_running = False
        self._auto_run = False
        self._step_mode = False
        self._update_button_states()
        if success:
            self._set_status("✅ Completado", "#a6e3a1")
            self._log("🎉 Script finalizado correctamente")
            self.progress.setValue(self.total_steps)
        else:
            self._set_status("❌ Finalizado con errores", "#f38ba8")
            self._log("⚠️ Script finalizado con errores")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, text: str, color: str = "#cdd6f4"):
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {color};")

    def _log(self, text: str):
        self.log_output.append(text)
        # Auto-scroll
        sb = self.log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _update_button_states(self):
        running = self._is_running
        self.btn_run.setEnabled(not running or self._is_paused)
        self.btn_step_mode.setEnabled(not running or self._is_paused)
        self.btn_pause.setEnabled(running)
        self.btn_next.setEnabled(not running or self._is_paused)
        self.btn_stop.setEnabled(running)
        self.btn_restart.setEnabled(True)

    def closeEvent(self, event):
        """Al cerrar, detener el worker."""
        if self.worker.isRunning():
            self.worker.cmd_stop()
            self.worker.wait(2000)
        event.accept()
