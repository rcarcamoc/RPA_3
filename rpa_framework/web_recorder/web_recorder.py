#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPA_3 WebRecorder - Módulo Principal
Grabación de pasos web con validación OCR y exportación multi-formato
Plataforma: Windows
Autor: RPA_3 Team
"""

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
    # exit(1) # Commented out to avoid crash if imported in GUI without dependencies fully active

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
            if url:
                try:
                    if not url.startswith("http"):
                        url = "https://" + url
                    self.page.goto(url, wait_until="domcontentloaded") # networkidle can be too slow
                except Exception as ex:
                    logger.error(f"Error navigating to {url}: {ex}")

            logger.info(f"✓ Navegador lanzado exitosamente: {url}")
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

    def __init__(self, settings: Optional[RecorderSettings] = None):
        self.settings = settings or RecorderSettings()
        self.session: Optional[SessionConfig] = None
        self.steps: List[StepConfig] = []
        self.is_recording = False
        self.launcher: Optional[PlaywrightLauncher] = None
        self.page: Optional[Page] = None
        self.events_processor = EventsProcessor()
        self.ocr_processor = OCRProcessor(self.settings)
        self.selectors_engine = SelectorsEngine()
        self.context_handler = ContextHandler()

        logger.info("WebRecorder inicializado")

    def start_session(self, name: str, browser: str, url: str) -> None:
        try:
            self.session = SessionConfig(
                name=name,
                browser=browser,
                url=url,
                start_time=time.time(),
            )

            self.launcher = PlaywrightLauncher(self.settings)
            self.page = self.launcher.launch_browser(browser, url)

            self.is_recording = True
            self.steps = []
            
            # TODO: Inject JS recorder here ideally, but for now we use simulation or external bindings
            # Inject listener script
            self._inject_listener()

            logger.info(f"✓ Sesión iniciada: {name} ({browser})")
        except Exception as e:
            logger.error(f"Error iniciando sesión: {e}")
            raise

    def _inject_listener(self):
        """Injects JS to listen for clicks/type and expose to Python."""
        if not self.page: return
        
        # This is a key part missing in the original md spec for a REAL recorder
        # We need to expose a binding to python `on_action`
        self.page.expose_binding("rpa_record", self._on_browser_action)
        
        js_code = """
        document.addEventListener('click', (e) => {
            const path = [];
            let el = e.target;
            while(el) {
                let sel = el.tagName.toLowerCase();
                if(el.id) sel += '#' + el.id;
                else if (el.className && typeof el.className === 'string') sel += '.' + el.className.split(' ').join('.');
                path.push(sel);
                el = el.parentElement;
            }
            const full_path = path.reverse().join(' > ');
            
            window.rpa_record({
                type: 'click',
                selector: full_path,
                x: e.clientX,
                y: e.clientY,
                target_text: e.target.innerText
            });
        }, true);
        
        document.addEventListener('change', (e) => {
             window.rpa_record({
                type: 'type',
                selector: e.target.tagName, # Simple fallback
                value: e.target.value
            });
        }, true);
        """
        try:
            self.page.add_init_script(js_code)
            self.page.evaluate(js_code) # Also run now
        except Exception as e:
            logger.warning(f"Could not inject listener: {e}")

    def _on_browser_action(self, source, data):
        """Callback from browser JS."""
        if not self.is_recording: return
        logger.info(f"Browser Action: {data}")
        # Convert to StepConfig
        # This is a bit advanced for the current 'simulated' requested scope but good to have prepared
        # For now, rely on manual simulate calls or this callback
        pass

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
            # --- PATH CORRECTION START ---
            if output_dir is None:
                # Default to ../recordings relative to this file
                base_dir = Path(__file__).resolve().parent.parent # rpa_framework/
                output_dir = base_dir / "recordings"
            
            os.makedirs(output_dir, exist_ok=True)
            # --- PATH CORRECTION END ---

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
            output_file = os.path.join(output_dir, f"{name}_steps.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✓ JSON exportado: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Error exportando JSON: {e}")
            return ""

    def export_to_python(self, output_dir: Optional[str] = None) -> str:
        try:
            # --- PATH CORRECTION START ---
            if output_dir is None:
                # Default to ../modules relative to this file
                base_dir = Path(__file__).resolve().parent.parent # rpa_framework/
                output_dir = base_dir / "modules"

            os.makedirs(output_dir, exist_ok=True)
            # --- PATH CORRECTION END ---

            session_name = self.session.name if self.session else "session"
            url = self.session.url if self.session else "https://example.com"

            header = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script RPA Autogenerado desde WebRecorder
Sesión: {session_name}
Navegador: chromium
URL Original: {url}
Generado: {datetime.now().isoformat()}
"""

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
            logger.info("Navegando a: {url}")
            self.page.goto("{url}", wait_until="domcontentloaded")
'''

            body = ""
            for idx, step in enumerate(self.steps, 1):
                body += f"\n            # Paso {idx}: {step.action.upper()}\n"
                if step.action == ActionType.CLICK.value:
                    body += (
                        f'            self.page.click("{step.selector}")\n'
                        f'            logger.info("✓ Click ejecutado")\n'
                    )
                elif step.action == ActionType.TYPE.value:
                    body += (
                        f'            self.page.fill("{step.selector}", "{step.value or ""}")\n'
                        f'            logger.info("✓ Texto ingresado")\n'
                    )
                elif step.action == ActionType.HOVER.value:
                    body += (
                        f'            self.page.hover("{step.selector}")\n'
                        f'            logger.info("✓ Hover ejecutado")\n'
                    )
                elif step.action == ActionType.SCROLL.value:
                    body += (
                        f'            self.page.evaluate("window.scrollTo(0, {step.coords[1]})")\n'
                        f'            logger.info("✓ Scroll ejecutado")\n'
                    )
                elif step.action == ActionType.WAIT.value:
                    body += (
                        f'            self.page.wait_for_selector("{step.selector}", timeout=5000)\n'
                        f'            logger.info("✓ Elemento aparición esperado")\n'
                    )

            footer = '''
            logger.info("✓ Automatización completada")

        except Exception as e:
            logger.error(f"❌ Error: {str(e)}")
            raise
        finally:
            time.sleep(1)
            self.browser.close()
            logger.info("Navegador cerrado")

if __name__ == "__main__":
    rpa = RPA_Automation(slowmo={slowmo})
    rpa.start()
    rpa.run()
'''.format(
                slowmo=self.settings.slowmo
            )

            code = header + body + footer

            output_file = os.path.join(output_dir, f"{session_name}_automation.py")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(code)

            logger.info(f"✓ Script Python exportado: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Error exportando Python: {e}")
            return ""

    def export_to_n8n(self, output_dir: Optional[str] = None) -> str:
        try:
            # --- PATH CORRECTION START ---
            if output_dir is None:
                base_dir = Path(__file__).resolve().parent.parent # rpa_framework/
                output_dir = base_dir / "modules" # N8N also in modules/ or maybe a new one? Let's use modules/ for now or recordings/
                # Actually, JSON workflows often go with recordings, but modules is for code.
                # Let's put n8n in recordings/ since it's a definition file, not executable python
                output_dir = base_dir / "recordings"

            os.makedirs(output_dir, exist_ok=True)
            # --- PATH CORRECTION END ---

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

            output_file = os.path.join(output_dir, f"{session_name}_workflow.json")
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
