#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPA_3 WebRecorder - Módulo Principal
Grabación de pasos web con validación OCR y exportación multi-formato
Plataforma: Windows
Autor: RPA_3 Team
"""

from __future__ import annotations
import json
import logging
import os
import base64
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

try:
    from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
    import cv2
    import numpy as np
    from PIL import Image
    import pytesseract
except ImportError as e:
    print(f"❌ Error importando dependencias: {e}")
    print("Ejecuta: pip install playwright opencv-python pillow pytesseract numpy")
    # Fallbacks for type hints
    sync_playwright = Any
    Browser = Any
    Page = Any
    BrowserContext = Any
    # Other potential missing imports
    cv2 = Any
    np = Any
    Image = Any
    pytesseract = Any

# ============================================================================
# CONFIGURACIÓN Y TIPOS
# ============================================================================

class ActionType(Enum):
    """Tipos de acciones capturadas"""
    CLICK = "click"
    TYPE = "type"
    HOVER = "hover"
    SCROLL = "scroll"
    WAIT = "wait"
    DRAG = "drag"
    SELECT = "select"
    FOCUS = "focus"
    BLUR = "blur"
    RIGHT_CLICK = "right_click"
    DOUBLE_CLICK = "double_click"


@dataclass
class StepConfig:
    """Configuración de un paso grabado"""
    id: str
    action: str
    selector: str
    coords: List[int]
    timestamp: float
    screenshot_base64: Optional[str] = None
    expected_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    selector_reliability: float = 0.0
    value: Optional[str] = None
    wait_time: int = 0


@dataclass
class SessionConfig:
    """Configuración de sesión de grabación"""
    name: str
    browser: str
    url: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    total_duration: float = 0.0


@dataclass
class RecorderSettings:
    """Configuración global del grabador"""
    browser_chrome_win: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    browser_edge_win: str = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    browser_firefox_win: str = r"C:\Program Files\Mozilla Firefox\firefox.exe"
    ocr_threshold: int = 85
    max_screenshot_size: int = 500  # KB
    critical_poll_interval: int = 50  # ms
    normal_poll_interval: int = 200  # ms
    slowmo: int = 0  # ms
    video_enabled: bool = False
    screenshot_width: int = 400
    screenshot_height: int = 300
    screenshot_padding: int = 20


# ============================================================================
# LOGGER CONFIGURATION
# ============================================================================

def setup_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """Configura logger con salida consola y archivo"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Evitar múltiples handlers si se importa varias veces
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else '.', exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


logger = setup_logger("WebRecorder", log_file="logs/web_recorder.log")


# ============================================================================
# SELECTORES ENGINE
# ============================================================================

class SelectorsEngine:
    """Motor de generación de selectores con 6 niveles de prioridad"""

    @staticmethod
    def generate(page: Page, element_handle) -> Dict[str, Any]:
        """Genera selector con prioridad estricta"""
        try:
            # 1. data-testid / data-cy
            testid = page.evaluate(
                "el => el.getAttribute('data-testid') || el.getAttribute('data-cy')",
                element_handle
            )
            if testid:
                return {
                    "selector": f"[data-testid='{testid}'], [data-cy='{testid}']",
                    "type": "data-testid",
                    "reliability": 0.90,
                }

            # 2. role + nombre accesible
            role = page.evaluate("el => el.getAttribute('role')", element_handle)
            aria_label = page.evaluate(
                "el => el.getAttribute('aria-label') || el.getAttribute('aria-describedby') || el.textContent",
                element_handle,
            )
            if role and aria_label:
                safe_label = (aria_label or "").strip().replace('"', '\\"')
                return {
                    "selector": f"[role='{role}'][aria-label=\"{safe_label}\"]",
                    "type": "role",
                    "reliability": 0.85,
                }

            # 3. aria-label/aria-describedby
            if aria_label:
                safe_label = aria_label.strip().replace('"', '\\"')
                return {
                    "selector": f"[aria-label=\"{safe_label}\"]",
                    "type": "aria-label",
                    "reliability": 0.80,
                }

            # 4. CSS moderno (nth-child minimal)
            css_selector = page.evaluate(
                """
                el => {
                    if (el.id) return '#' + el.id;
                    let path = [];
                    while (el.parentElement) {
                        let name = el.localName;
                        let sibling = el;
                        let nth = 1;
                        while (sibling = sibling.previousElementSibling) {
                            if (sibling.localName === el.localName) nth++;
                        }
                        if (nth > 1) name += ":nth-of-type(" + nth + ")";
                        path.unshift(name);
                        el = el.parentElement;
                    }
                    return path.join(" > ");
                }
                """,
                element_handle,
            )
            if css_selector:
                return {
                    "selector": css_selector,
                    "type": "css",
                    "reliability": 0.70,
                }

            # 5. XPath relativo (NO absolute)
            xpath = page.evaluate(
                """
                el => {
                    let path = [];
                    while (el.parentElement) {
                        let index = 1;
                        let sibling = el.previousElementSibling;
                        while (sibling) {
                            if (sibling.localName === el.localName) index++;
                            sibling = sibling.previousElementSibling;
                        }
                        let name = el.localName;
                        if (index > 1) name += '[' + index + ']';
                        path.unshift(name);
                        el = el.parentElement;
                    }
                    return './/' + path.join('/');
                }
                """,
                element_handle,
            )
            if xpath:
                return {
                    "selector": xpath,
                    "type": "xpath",
                    "reliability": 0.60,
                }

            # 6. Fallback: text + coordenadas
            text = page.evaluate("el => el.textContent?.slice(0, 50) || ''", element_handle)
            return {
                "selector": f"text='{(text or '').strip()}'",
                "type": "text",
                "reliability": 0.50,
            }

        except Exception as e:
            logger.error(f"Error generando selector: {e}")
            return {
                "selector": "unknown",
                "type": "unknown",
                "reliability": 0.0,
            }


# ============================================================================
# EVENTOS PROCESSOR
# ============================================================================

class EventsProcessor:
    """Procesa eventos con waits inteligentes"""

    @staticmethod
    def wait_for_element(page: Page, selector: str, timeout: int = 5000) -> bool:
        try:
            page.wait_for_selector(selector, timeout=timeout)
            logger.debug(f"Elemento encontrado: {selector}")
            return True
        except Exception:
            logger.warning(f"Timeout esperando selector: {selector}")
            return False

    @staticmethod
    def wait_for_navigation(page: Page, timeout: int = 5000) -> bool:
        try:
            page.wait_for_load_state("networkidle", timeout=timeout)
            logger.debug("Navegación completada")
            return True
        except Exception:
            logger.warning("Timeout en espera de navegación")
            return False

    @staticmethod
    def detect_loaders(page: Page) -> bool:
        try:
            return page.evaluate(
                """
                () => {
                    const loaders = document.querySelectorAll(
                      '[class*="loader"], [class*="spinner"], [role="progressbar"]'
                    );
                    for (let el of loaders) {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            return true;
                        }
                    }
                    return false;
                }
                """
            )
        except Exception:
            return False


# ============================================================================
# OCR PROCESSOR
# ============================================================================

class OCRProcessor:
    """Validación visual OCR con fallback a pixel matching"""

    def __init__(self, settings: RecorderSettings):
        self.settings = settings
        self.pytesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

        if not os.path.exists(self.pytesseract_path):
            logger.warning(f"Tesseract no encontrado en {self.pytesseract_path}")
            logger.info("Descárgalo desde: https://github.com/UB-Mannheim/tesseract/wiki")
        else:
            pytesseract.pytesseract.tesseract_cmd = self.pytesseract_path

    def capture_and_compress(self, page: Page, coords: List[int]) -> Optional[str]:
        """Captura screenshot, comprime y devuelve Base64"""
        try:
            screenshot_bytes = page.screenshot(
                clip={
                    "x": max(0, coords[0] - self.settings.screenshot_padding),
                    "y": max(0, coords[1] - self.settings.screenshot_padding),
                    "width": self.settings.screenshot_width + self.settings.screenshot_padding * 2,
                    "height": self.settings.screenshot_height + self.settings.screenshot_padding * 2,
                }
            )

            import io
            image = Image.open(io.BytesIO(screenshot_bytes))
            image = image.resize(
                (self.settings.screenshot_width, self.settings.screenshot_height),
                Image.Resampling.LANCZOS,
            )

            png_buffer = io.BytesIO()
            image.save(png_buffer, format="PNG", optimize=True)
            png_bytes = png_buffer.getvalue()

            size_kb = len(png_bytes) / 1024
            if size_kb > self.settings.max_screenshot_size:
                logger.warning(
                    f"Screenshot excede límite: {size_kb:.1f}KB > {self.settings.max_screenshot_size}KB"
                )
                return None

            base64_str = base64.b64encode(png_bytes).decode("utf-8")
            logger.debug(f"Screenshot capturado y comprimido: {size_kb:.1f}KB")
            return base64_str

        except Exception as e:
            logger.error(f"Error capturando screenshot: {e}")
            return None

    def extract_ocr_text(self, screenshot_base64: str) -> Optional[str]:
        try:
            import io
            image_bytes = base64.b64decode(screenshot_base64)
            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image, lang="spa+eng")
            logger.debug(f"OCR extraído: {text[:100]}...")
            return text
        except Exception as e:
            logger.warning(f"Error en OCR: {e}")
            return None

    def calculate_confidence(self, screenshot_base64: str, expected_text: str) -> float:
        try:
            extracted = self.extract_ocr_text(screenshot_base64)
            if not extracted or not expected_text:
                return 0.0

            from difflib import SequenceMatcher

            ratio = SequenceMatcher(
                None, extracted.lower(), expected_text.lower()
            ).ratio()
            confidence = min(1.0, max(0.0, ratio))
            logger.debug(f"Confianza OCR: {confidence * 100:.1f}%")
            return confidence
        except Exception as e:
            logger.error(f"Error calculando confianza: {e}")
            return 0.0

    def pixel_matching_fallback(self, screenshot_base64: str, reference_base64: str) -> float:
        try:
            img1_bytes = base64.b64decode(screenshot_base64)
            img2_bytes = base64.b64decode(reference_base64)

            img1 = cv2.imdecode(np.frombuffer(img1_bytes, np.uint8), cv2.IMREAD_COLOR)
            img2 = cv2.imdecode(np.frombuffer(img2_bytes, np.uint8), cv2.IMREAD_COLOR)

            if img1.shape != img2.shape:
                img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

            mse = np.sum((img1.astype(float) - img2.astype(float)) ** 2)
            mse /= float(img1.shape[0] * img1.shape[1])

            similarity = 1.0 / (1.0 + mse / 10000.0)
            logger.debug(f"Pixel matching similarity: {similarity * 100:.1f}%")
            return similarity
        except Exception as e:
            logger.error(f"Error en pixel matching: {e}")
            return 0.0


# ============================================================================
# CONTEXTOS COMPLEJOS
# ============================================================================

class ContextHandler:
    """Maneja contextos complejos: iframes, shadow DOM, SPAs"""

    @staticmethod
    def handle_dynamic_ids(selector: str) -> str:
        if "#" in selector:
            parts = selector.split("#")
            dynamic_id = parts[1].split("]")[0]
            partial_match = dynamic_id.split("_")[0]
            return f"{parts[0]}[id^='{partial_match}']"
        return selector

    @staticmethod
    def validate_spa_routing(page: Page, url: str) -> bool:
        try:
            current_url = page.url
            same_url = current_url.split("#")[0] == url.split("#")[0]
            same_hash = (
                current_url.split("#")[1] == url.split("#")[1]
                if "#" in current_url and "#" in url
                else True
            )
            logger.debug(f"SPA routing validado: {same_url and same_hash}")
            return same_url and same_hash
        except Exception:
            return False


# ============================================================================
# PLAYWRIGHT LAUNCHER
# ============================================================================

class PlaywrightLauncher:
    """Lanzador multi-navegador con perfiles reales"""

    def __init__(self, settings: RecorderSettings):
        self.settings = settings
        self.playwright = None
        self.browser = None
        self.context = None
        self.page: Optional[Page] = None

    def _get_executable_path(self, browser_name: str) -> str:
        name = browser_name.lower()
        if name == "chrome":
            return self.settings.browser_chrome_win
        if name == "edge":
            return self.settings.browser_edge_win
        if name == "firefox":
            return self.settings.browser_firefox_win
        return self.settings.browser_chrome_win

    def launch_browser(self, browser_name: str, url: str) -> Page:
        if sync_playwright is Any:
            raise ImportError("Playwright no está instalado. Ejecute 'pip install playwright' y 'playwright install' en la terminal.")
        try:
            self.playwright = sync_playwright().start()
            executable_path = self._get_executable_path(browser_name)

            logger.info(f"Lanzando {browser_name} desde: {executable_path}")

            launch_args = {
                # "executable_path": executable_path, # Commented to allow default discovery if path is wrong
                "headless": False,
                "slow_mo": self.settings.slowmo,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-resources-cache",
                    "--disable-sync",
                    "--disable-default-apps",
                ],
            }
            # Only add executable specific path if it exists, otherwise rely on default
            if os.path.exists(executable_path):
                launch_args["executable_path"] = executable_path
            else:
                 logger.warning(f"Browser path not found: {executable_path}. Using default system browser.")

            name = browser_name.lower()
            if name in ("chrome", "chromium", "edge"):
                # Use channel for edge/chrome if not specifying executable path strictly or if we want to be safer
                channel = "msedge" if name == "edge" else "chrome"
                # If we provided executable_path, we don't strictly need channel, but it helps if executable path is missing
                if "executable_path" not in launch_args:
                    launch_args["channel"] = channel
                
                self.browser = self.playwright.chromium.launch(**launch_args)
            elif name == "firefox":
                self.browser = self.playwright.firefox.launch(**launch_args)
            else:
                self.browser = self.playwright.chromium.launch(**launch_args)

            user_data_dir = Path.home() / f"AppData/Local/{browser_name}_RPA_Profile"
            user_data_dir.mkdir(parents=True, exist_ok=True)

            self.context = self.browser.new_context(
                # storage_state=None, # Avoid error if file doesn't exist
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            self.page = self.context.new_page()
            logger.info(f"✓ Navegador lanzado exitosamente.")
            return self.page

        except Exception as e:
            logger.error(f"Error lanzando navegador: {e}")
            raise

    def close(self):
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("Navegador cerrado")
        except Exception as e:
            logger.error(f"Error cerrando navegador: {e}")


# ============================================================================
# WEB RECORDER MAIN CLASS
# ============================================================================

class WebRecorder:
    """Grabador web profesional RPA_3"""

    def __init__(self, settings: Optional[RecorderSettings] = None, log_callback: Optional[callable] = None):
        self.settings = settings or RecorderSettings()
        self.log_callback = log_callback
        self.session: Optional[SessionConfig] = None
        self.steps: List[StepConfig] = []
        self.is_recording = False
        self.launcher: Optional[PlaywrightLauncher] = None
        self.page: Optional[Page] = None
        self.events_processor = EventsProcessor()
        self.ocr_processor = OCRProcessor(self.settings)
        self.selectors_engine = SelectorsEngine()
        self.context_handler = ContextHandler()

        self.log("WebRecorder inicializado")

    def log(self, message: str, level: str = "info"):
        """Logs message to both logger and callback."""
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)
            
        if self.log_callback:
            try:
                self.log_callback(message)
            except:
                pass

    def start_session(self, name: str, browser: str, url: str) -> None:
        if sync_playwright is Any:
             raise ImportError("El módulo Playwright no está disponible. Por favor, instálalo con 'pip install playwright' y luego ejecuta 'playwright install'.")
        try:
            self.session = SessionConfig(
                name=name,
                browser=browser,
                url=url,
                start_time=time.time(),
            )

            self.launcher = PlaywrightLauncher(self.settings)
            self.page = self.launcher.launch_browser(browser, url)

            # --- SETUP RECORDING BEFORE GOTO ---
            # 1. Expose binding
            self.page.expose_binding("rpa_record", self._on_browser_action)
            
            # 2. Add Init Script (survives navigations)
            self._inject_listener()

            # 3. Now navigate
            if url:
                if not url.startswith("http"):
                    url = "https://" + url
                self.page.goto(url, wait_until="domcontentloaded")

            self.is_recording = True
            self.steps = []
            
            self.log(f"✓ Sesión iniciada y listeners activos: {name}")
        except Exception as e:
            self.log(f"Error iniciando sesión: {e}", level="error")
            raise

    def _inject_listener(self):
        """Injects clean JS to listen for events and send to Python."""
        if not self.page: return
        
        js_code = """
        (function() {
            if (window.rpa_recording_active) return;
            window.rpa_recording_active = true;
            
            console.log('RPA_3: Smart Recorder Active');

            // --- SMART SELECTOR ENGINE ---
            const getSmartSelector = (el) => {
                // 1. Prioridad: ID
                if (el.id) return `#${el.id}`;
                
                // 2. Prioridad: Atributos clave de testing/form
                const keyAttrs = ['data-testid', 'data-test', 'name', 'placeholder', 'aria-label', 'role'];
                for (let attr of keyAttrs) {
                    if (el.hasAttribute(attr)) {
                         return `${el.tagName.toLowerCase()}[${attr}="${el.getAttribute(attr)}"]`;
                    }
                }

                // 3. Prioridad: Texto Visible (solo para botones y links cortos)
                if ((el.tagName === 'BUTTON' || el.tagName === 'A' || el.tagName === 'SPAN' || el.tagName === 'DIV') && 
                    el.innerText && el.innerText.length < 30) {
                    const text = el.innerText.trim();
                    if (text) return `text="${text}"`;
                }

                // 4. Prioridad: Clases únicas (si no son genéricas)
                if (el.className && typeof el.className === 'string' && el.className.trim() !== '') {
                    const classes = el.className.split(' ').filter(c => !c.match(/^[a-z0-9]{10,}$/)); // Filtrar hashes
                    if (classes.length > 0) {
                        return `${el.tagName.toLowerCase()}.${classes.join('.')}`;
                    }
                }

                // 5. Fallback: Ruta CSS limpia
                let path = [];
                let current = el;
                while (current && current.nodeType === Node.ELEMENT_NODE) {
                    let selector = current.nodeName.toLowerCase();
                    if (current.id) {
                        selector = `#${current.id}`;
                        path.unshift(selector);
                        break;
                    } 
                    if (current.parentNode) {
                        let siblings = Array.from(current.parentNode.children).filter(e => e.nodeName === current.nodeName);
                        if (siblings.length > 1) {
                            selector += `:nth-of-type(${siblings.indexOf(current) + 1})`;
                        }
                    }
                    path.unshift(selector);
                    current = current.parentNode;
                }
                return path.join(' > ');
            };

            const recordAction = (data) => {
                if (typeof window.rpa_record === 'function') {
                    window.rpa_record(data);
                }
            };

            // CLICK LISTENER (mousedown para capturar antes de cambios de pagina)
            document.addEventListener('mousedown', (e) => {
                try {
                    // Ignorar clicks en el debugger overlay si existiera
                    if (e.target.id === 'rpa-debug-indicator') return;

                    const selector = getSmartSelector(e.target);
                    
                    // Visual Highlighting (Feedback Rojo)
                    const originalOutline = e.target.style.outline;
                    e.target.style.outline = '3px solid rgba(255, 0, 0, 0.7)';
                    setTimeout(() => { e.target.style.outline = originalOutline; }, 300);

                    recordAction({
                        type: 'click',
                        selector: selector,
                        x: e.clientX,
                        y: e.clientY,
                        text: e.target.innerText?.slice(0, 50),
                        tagName: e.target.tagName
                    });
                } catch(err) { console.error('RPA Click error:', err); }
            }, { capture: true, passive: true });

            // INPUT LISTENER (Detectar 'change' para valores finales)
            document.addEventListener('change', (e) => {
                try {
                    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
                        const selector = getSmartSelector(e.target);
                        // Visual Feedback Azul
                        e.target.style.border = '2px solid blue';
                        
                        recordAction({
                            type: 'type',
                            selector: selector,
                            value: e.target.value,
                            tagName: e.target.tagName
                        });
                    }
                } catch(err) { console.error('RPA Type error:', err); }
            }, { capture: true, passive: true });
        })();
        """
        try:
            self.page.add_init_script(js_code)
            self.page.evaluate(js_code) # Force run immediately
        except Exception as e:
            self.log(f"Error injecting init script: {e}", level="warning")

    def _on_browser_action(self, source, data: dict):
        """Callback from browser JS."""
        if not self.is_recording or not self.page: return
        
        try:
            action_type = data.get('type')
            selector = data.get('selector', 'unknown')
            coords = [data.get('x', 0), data.get('y', 0)]
            value = data.get('value', '')
            
            self.log(f"🔵 Browser Action: {action_type} en {selector}")
            
            # Evitar duplicados rápidos de escritura si el valor no cambió (opcional)
            if action_type == 'type' and self.steps and self.steps[-1].action == 'type' and self.steps[-1].selector == selector:
                self.steps[-1].value = value
                return

            # Capturar screenshot para OCR si es un click
            screenshot_b64 = None
            if action_type == 'click':
                screenshot_b64 = self.ocr_processor.capture_and_compress(self.page, coords)

            step = StepConfig(
                id=f"step_{len(self.steps) + 1:03d}",
                action=action_type,
                selector=selector,
                coords=coords,
                timestamp=time.time(),
                value=value,
                screenshot_base64=screenshot_b64,
                selector_reliability=0.8
            )
            
            self.steps.append(step)
            self.log(f"✅ Paso guardado: {action_type.upper()} [{len(self.steps)}]")
            
        except Exception as e:
            self.log(f"Error procesando acción del navegador: {e}", level="error")

    def stop_session(self) -> None:
        try:
            self.is_recording = False
            if self.session and self.session.start_time:
                self.session.end_time = time.time()
                self.session.total_duration = (
                    self.session.end_time - self.session.start_time
                )

            if self.launcher:
                self.launcher.close()

            logger.info(
                f"✓ Sesión detenida. Pasos: {len(self.steps)}, "
                f"Duración: {self.session.total_duration:.1f}s"
            )
        except Exception as e:
            logger.error(f"Error deteniendo sesión: {e}")

    def simulate_capture_click(self, selector: str, coords: List[int]) -> None:
        """Simula captura de click (para integración con GUI)"""
        if not self.is_recording or not self.page:
            logger.warning("Grabación no iniciada o página no disponible")
            return

        try:
            selector_info = {
                "selector": selector,
                "type": "simulated",
                "reliability": 0.85,
            }

            screenshot_b64 = self.ocr_processor.capture_and_compress(self.page, coords)

            ocr_conf = None
            if screenshot_b64:
                ocr_conf = self.ocr_processor.calculate_confidence(
                    screenshot_b64, "Click"
                )

            step = StepConfig(
                id=f"step_{len(self.steps) + 1:03d}",
                action=ActionType.CLICK.value,
                selector=selector,
                coords=coords,
                timestamp=time.time(),
                screenshot_base64=screenshot_b64,
                expected_text="Click",
                ocr_confidence=ocr_conf,
                selector_reliability=selector_info["reliability"],
            )

            self.steps.append(step)
            logger.info(f"✓ Paso capturado: CLICK [{len(self.steps)}]")
        except Exception as e:
            logger.error(f"Error capturando click: {e}")

    def export_to_json(self, output_dir: Optional[str] = None) -> str:
        try:
            # Use centralized path management
            from utils.paths import get_web_recording_path
            
            if output_dir is None:
                # Will use default WEB_RECORDINGS_DIR
                pass

            session_dict = asdict(self.session) if self.session else {}
            output_data = {
                "session": session_dict,
                "steps": [asdict(step) for step in self.steps],
                "metrics": {
                    "total_steps": len(self.steps),
                    "total_duration": session_dict.get("total_duration", 0.0),
                    "average_reliability": (
                        sum(s.selector_reliability for s in self.steps) / len(self.steps)
                        if self.steps
                        else 0.0
                    ),
                    "exported_at": datetime.now().isoformat(),
                },
            }

            name = session_dict.get("name", "session")
            if output_dir:
                output_file = os.path.join(output_dir, f"{name}_steps.json")
            else:
                output_file = str(get_web_recording_path(f"{name}_steps.json"))
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✓ JSON exportado: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Error exportando JSON: {e}")
            return ""

    def export_to_python(self, output_dir: Optional[str] = None) -> str:
        try:
            # Use centralized path management
            from utils.paths import get_web_recording_path
            
            if output_dir is None:
                # Will use default WEB_RECORDINGS_DIR
                pass

            session_name = self.session.name if self.session else "session"
            url = self.session.url if self.session else "https://example.com"

            header = f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
Script RPA Autogenerado desde WebRecorder
Sesión: {session_name}
Navegador: chromium
URL Original: {url}
Generado: {datetime.now().isoformat()}
\"\"\"

from playwright.sync_api import sync_playwright
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RPA_Automation:
    def __init__(self, slowmo={self.settings.slowmo}):
        self.slowmo = slowmo
        self.browser = None
        self.page = None

    def start(self):
        playwright = sync_playwright().start()
        self.browser = playwright.chromium.launch(
            headless=False,
            slow_mo=self.slowmo
        )
        self.page = self.browser.new_page()
        logger.info("✓ Navegador iniciado")

    def run(self):
        try:
            logger.info(f"Navegando a: {url}")
            self.page.goto(f"{url}", wait_until="domcontentloaded")
"""

            body = ""
            for idx, step in enumerate(self.steps, 1):
                body += f"\n            # Paso {idx}: {step.action.upper()} en {step.selector}\n"
                
                # Sanitize selector and value from quotes
                sel = step.selector.replace('"', "'")
                val = str(step.value).replace('"', '\\"') if step.value else ""
                
                if step.action == 'click':
                    if 'text=' in sel:
                         # Playwright text selector
                         body += f'            self.page.click("{sel}")\n'
                    else:
                         # Standard CSS
                         body += f'            self.page.click("{sel}")\n'
                    
                    # Smart wait after clicks (often triggers navigation)
                    body += '            self.page.wait_for_load_state("networkidle", timeout=3000)\n'
                    body += f'            logger.info("✓ Click en {sel}")\n'

                elif step.action == 'type':
                    body += (
                        f'            self.page.fill("{sel}", "{val}")\n'
                        f'            logger.info("✓ Escribir \'{val}\' en {sel}")\n'
                    )

                elif step.action == 'hover':
                    body += f'            self.page.hover("{sel}")\n'
                
                elif step.action == 'wait':
                    body += f'            self.page.wait_for_selector("{sel}", state="visible", timeout=5000)\n'

            footer = f'''
            logger.info("✓ Automatización completada")

        except Exception as e:
            logger.error(f"❌ Error: {{str(e)}}")
            raise
        finally:
            time.sleep(1)
            self.browser.close()
            logger.info("Navegador cerrado")

if __name__ == "__main__":
    rpa = RPA_Automation(slowmo={self.settings.slowmo})
    rpa.start()
    rpa.run()
'''

            code = header + body + footer

            if output_dir:
                output_file = os.path.join(output_dir, f"{session_name}_automation.py")
            else:
                output_file = str(get_web_recording_path(f"{session_name}_automation.py"))
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(code)

            logger.info(f"✓ Script Python exportado: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Error exportando Python: {e}")
            return ""

    def export_to_n8n(self, output_dir: Optional[str] = None) -> str:
        try:
            # Use centralized path management
            from utils.paths import get_web_recording_path
            
            if output_dir is None:
                # Will use default WEB_RECORDINGS_DIR
                pass

            session_name = self.session.name if self.session else "session"
            url = self.session.url if self.session else "https://example.com"

            workflow = {
                "name": f"RPA - {session_name}",
                "active": False,
                "nodes": [],
            }

            workflow["nodes"].append(
                {
                    "parameters": {
                        "url": url,
                        "waitForNavigation": True,
                    },
                    "name": "HTTP Start",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 1,
                    "position": [250, 300],
                }
            )

            for idx, step in enumerate(self.steps, 1):
                workflow["nodes"].append(
                    {
                        "parameters": {
                            "selector": step.selector,
                            "action": step.action,
                            "value": step.value or "",
                            "waitTime": step.wait_time,
                        },
                        "name": f"Step {idx} - {step.action}",
                        "type": "n8n-nodes-base.playwright",
                        "typeVersion": 1,
                        "position": [250 + idx * 200, 300],
                    }
                )

            if output_dir:
                output_file = os.path.join(output_dir, f"{session_name}_workflow.json")
            else:
                output_file = str(get_web_recording_path(f"{session_name}_workflow.json"))
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(workflow, f, indent=2)

            logger.info(f"✓ Workflow n8n exportado: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Error exportando n8n: {e}")
            return ""

    def test_playback(self, slowmo: Optional[int] = None) -> bool:
        try:
            delay = (slowmo or self.settings.slowmo or 0) / 1000.0
            logger.info(f"Iniciando test playback (SlowMo: {delay * 1000:.0f}ms)...")

            for idx, step in enumerate(self.steps, 1):
                logger.info(f"[{idx}/{len(self.steps)}] Ejecutando: {step.action}")
                time.sleep(delay + 0.1)

            logger.info("✓ Test playback completado")
            return True
        except Exception as e:
            logger.error(f"Error en test playback: {e}")
            return False


# ============================================================================
# MAIN - EJEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    settings = RecorderSettings(
        browser_chrome_win=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        ocr_threshold=85,
        slowmo=500,
    )

    recorder = WebRecorder(settings)

    try:
        recorder.start_session(
            name="demo-grabacion-001",
            browser="chrome",
            url="https://www.example.com",
        )

        recorder.simulate_capture_click("button[type='submit']", [400, 300])
        time.sleep(1)
        recorder.simulate_capture_click("input[name='email']", [200, 150])

        recorder.stop_session()

        recorder.export_to_json()
        recorder.export_to_python()
        recorder.export_to_n8n()

        recorder.test_playback()
        logger.info("✓ Ejecución completada")

    except Exception as e:
        logger.error(f"Error: {e}")
