#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
core/recorder.py - MEJORADO

Captura acciones mouse/keyboard y extrae selectores inteligentes.
Prioridad: automation_id > name+control_type > class_name > position (fallback)
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from pynput import mouse, keyboard
import pythoncom 

from .selector import WindowsSelector

logger = logging.getLogger(__name__)

class RPARecorder:
    """Captura acciones con selectores inteligentes."""
    
    def __init__(self, config: dict):
        self.config = config
        self.actions: List[Dict] = []
        self.recording = False
        self.last_text_time = time.time()
        self.text_buffer = ""
        self.listeners = []
        # Usar la lógica centralizada de selectores
        self.selector_extractor = WindowsSelector()
        self.text_timer = None
        
        # Estado de teclas modificadoras
        self.modifiers = {"ctrl": False, "shift": False, "alt": False}
    
    def start(self):
        """Inicia grabación."""
        self.recording = True
        self.actions = []
        self.text_buffer = ""
        logger.info("🔴 Grabación iniciada")
        
        listener_mouse = mouse.Listener(on_click=self._on_click)
        listener_keyboard = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        
        listener_mouse.start()
        listener_keyboard.start()
        
        self.listeners = [listener_mouse, listener_keyboard]
    
    def stop(self) -> List[Dict]:
        """Detiene grabación."""
        self.recording = False
        if self.text_timer:
            self.text_timer.cancel()
        self._flush_text()  # Guardar texto pendiente
        
        for listener in self.listeners:
            listener.stop()
        logger.info(f"⏹️ Grabación detenida: {len(self.actions)} acciones")
        return self.actions
    
    def _on_click(self, x, y, button, pressed):
        """Captura clicks."""
        if not self.recording:
            return
        
        if not pressed:
             return
        
        self._flush_text() # Flush before new click interaction
        
        try:
            # Inicializar COM en este hilo si es necesario (generalmente pynput corre en su propio thread)
            try:
                pythoncom.CoInitialize()
            except:
                pass

            # Extraer información del elemento usando WindowsSelector
            element_info = self.selector_extractor.extract_from_point(x, y)
            
            # Construir selector inteligente
            selector = self.selector_extractor.build_selector(
                element_info,
                {"x": x, "y": y}
            )
            
            # Crear acción
            action = {
                "type": "click",
                "timestamp": datetime.now().isoformat(),
                "position": {"x": x, "y": y},
                "selector": selector,
                "app_context": {
                    "title": element_info.get("window_title", ""),
                    "class_name": element_info.get("window_class", "")
                },
                "modifiers": self.modifiers.copy(),
                "element_info": {
                    "name": element_info.get("name", ""),
                    "automation_id": element_info.get("automation_id", ""),
                    "class_name": element_info.get("class_name", ""),
                    "control_type": element_info.get("control_type", ""),
                }
            }
            
            self.actions.append(action)
            
            # Log
            selector_type = self._get_selector_type(selector)
            logger.info(f"📍 Click registrado ({selector_type}): {selector}")
            
            # Uninitialize COM is tricky in callback, but strict correctness would suggest it. 
            # However, mostly benign to leave initialized in thread.
        
        except Exception as e:
            logger.warning(f"Error capturando click: {e}")
    
    def _on_press(self, key):
        """Captura typing y actualiza modificadores."""
        # Actualizar estado de modificadores
        if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
            self.modifiers["ctrl"] = True
        elif key in [keyboard.Key.shift_l, keyboard.Key.shift_r, keyboard.Key.shift]:
            self.modifiers["shift"] = True
        elif key in [keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt]:
            self.modifiers["alt"] = True
            
        if not self.recording:
            return
        
        # Resetear timer
        if self.text_timer:
            self.text_timer.cancel()
            
        try:
            char = key.char
            if char:
                # No capturar si es solo modificador (se maneja arriba)
                self.text_buffer += char
                self.last_text_time = time.time()
                # Programar flush
                self.text_timer = threading.Timer(2.0, self._flush_text)
                self.text_timer.start()
        except:
            # Tecla especial -> Flush inmediato
            key_name = str(key).replace("Key.", "").upper()
            
            # Ignorar modificadores como "acciones de tecla" individuales si se desea
            # Pero para typetext a veces es útil.
            # Por ahora, guardamos teclas especiales importantes solamente.
            if key_name in ["ENTER", "TAB", "ESCAPE", "DELETE", "BACKSPACE", "SPACE", "UP", "DOWN", "LEFT", "RIGHT"]:
                self._flush_text()
                self._save_key_action(key_name)

    def _on_release(self, key):
        """Actualiza estado de modificadores al soltar."""
        if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
            self.modifiers["ctrl"] = False
        elif key in [keyboard.Key.shift_l, keyboard.Key.shift_r, keyboard.Key.shift]:
            self.modifiers["shift"] = False
        elif key in [keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt]:
            self.modifiers["alt"] = False
    
    def _flush_text(self):
        """Guarda acción de typing usando contexto del último click."""
        if not self.text_buffer: 
            return
            
        text_to_save = self.text_buffer
        self.text_buffer = "" # Clear immediate
        
        # Intentar heredar selector del último click (CONTEXTO)
        selector = None
        if self.actions and self.actions[-1]['type'] == 'click':
            selector = self.actions[-1].get('selector')
            logger.debug("Heredando selector para texto")

        action = {
            "type": "type_text",
            "timestamp": datetime.now().isoformat(),
            "text": text_to_save,
            "selector": selector,  # Usar selector del contexto
            "position": None
        }
        self.actions.append(action)
        logger.info(f"⌨️ Texto registrado: {text_to_save} (Contexto: {selector is not None})")
    
    def _save_type_action(self, text: str):
         # Wrapper for compatibility if called elsewhere
         self.text_buffer = text
         self._flush_text()

    def _save_key_action(self, key_name: str):
        """Guarda acción de tecla especial."""
        action = {
            "type": "key",
            "timestamp": datetime.now().isoformat(),
            "key_code": key_name,
            "selector": None,
            "position": None
        }
        self.actions.append(action)
        logger.info(f"⌨️ Tecla registrada: {key_name}")
    
    def _get_selector_type(self, selector: Dict) -> str:
        """Retorna tipo de selector para logging."""
        if not selector: return "NONE"
        if "automation_id" in selector:
            return "AUTOMATION_ID"
        elif "name" in selector and "control_type" in selector:
            return "NAME+CONTROLTYPE"
        elif "class_name" in selector:
            return "CLASS_NAME"
        elif "position" in selector:
            return "POSITION"
        return "UNKNOWN"
    
    def save(self, filename: str) -> str:
        """Guarda grabación a JSON."""
        # Use absolute path relative to this file to ensure it goes to rpa_framework/recordings
        base_dir = Path(__file__).resolve().parent.parent
        output_dir = base_dir / "recordings"
        output_dir.mkdir(exist_ok=True)
        
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        
        output_path = output_dir / filename
        
        # Calcular estadísticas
        start_time = datetime.fromisoformat(self.actions[0]["timestamp"]) if self.actions else datetime.now()
        end_time = datetime.fromisoformat(self.actions[-1]["timestamp"]) if self.actions else datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Obtener resolución de pantalla
        import ctypes
        try:
            user32 = ctypes.windll.user32
            screen_res = {"width": user32.GetSystemMetrics(0), "height": user32.GetSystemMetrics(1)}
        except:
            screen_res = {"width": 0, "height": 0}

        # Guardar
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "screen_resolution": screen_res,
                    "total_actions": len(self.actions),
                    "total_actions_optimized": len(self.actions),
                    "duration_seconds": duration,
                    "optimization_stats": {
                        "removed_count": 0,
                        "consolidated_count": 0
                    }
                },
                "actions": self.actions
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Guardado: {output_path}")
        return str(output_path)

class RecorderGUI:
    """GUI simple para grabación."""
    
    def __init__(self, config: dict):
        self.config = config
        self.recorder = RPARecorder(config)
    
    def run(self):
        """Inicia GUI (tkinter)."""
        try:
            import tkinter as tk
            from tkinter import simpledialog, messagebox
            
            root = tk.Tk()
            root.title("🎬 RPA Recorder v2")
            root.geometry("300x150")
            root.attributes('-topmost', True)
            
            self.status_var = tk.StringVar(value="READY")
            self.count_var = tk.StringVar(value="0")
            
            tk.Label(root, textvariable=self.status_var, font=("Arial", 14)).pack(pady=10)
            tk.Label(root, text="Acciones:", font=("Arial", 12)).pack()
            tk.Label(root, textvariable=self.count_var, font=("Arial", 20, "bold")).pack()
            
            frame = tk.Frame(root)
            frame.pack(pady=10)
            
            tk.Button(frame, text="⏺ REC", command=self._record, width=10).pack(side=tk.LEFT, padx=5)
            tk.Button(frame, text="⏸ PAUSE", command=self._pause, width=10).pack(side=tk.LEFT, padx=5)
            tk.Button(frame, text="⏹ STOP", command=self._stop, width=10).pack(side=tk.LEFT, padx=5)
            
            self.root = root
            self._update_count()
            root.mainloop()
            
        except ImportError:
            logger.info("tkinter no disponible, modo CLI")
            self._run_cli()
    
    def _record(self):
        self.recorder.start()
        self.status_var.set("REC...")
        self._update_count()
    
    def _pause(self):
        self.status_var.set("PAUSED")
    
    def _stop(self):
        self.status_var.set("STOPPED")
        self.recorder.stop()
        
        import tkinter.simpledialog
        name = tkinter.simpledialog.askstring("Guardar", "Nombre de la grabación:")
        
        if name:
            self.recorder.save(name)
        
        self.root.quit()
        self.root.destroy()
    
    def _update_count(self):
        self.count_var.set(str(len(self.recorder.actions)))
        if self.status_var.get() == "REC...":
            self.root.after(500, self._update_count)
    
    def _run_cli(self):
        """Modo CLI sin GUI."""
        input("Presiona ENTER para iniciar grabación...")
        self.recorder.start()
        print("Grabando... (presiona Ctrl+C para detener)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.recorder.stop()
            name = input("Nombre de la grabación: ")
            self.recorder.save(name)
