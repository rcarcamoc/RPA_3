
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

try:
    from playwright.sync_api import sync_playwright, Browser, Page
except ImportError:
    sync_playwright = None

logger = logging.getLogger(__name__)

class WebReplayer:
    """Reproduce grabaciones web capturadas con WebRecorder."""
    
    def __init__(self, recording_source: Union[str, Dict], config: dict):
        self.config = config
        self.playwright = None
        self.browser = None
        self.page = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if isinstance(recording_source, dict):
            self.data = recording_source
        else:
            with open(recording_source, "r", encoding="utf-8") as f:
                self.data = json.load(f)
                
        self.steps = self.data.get("steps", [])
        self.session_info = self.data.get("session", {})

    def setup(self) -> bool:
        if sync_playwright is None:
            logger.error("Playwright no está instalado. No se puede reproducir la grabación web.")
            return False
            
        try:
            self.playwright = sync_playwright().start()
            browser_type = self.session_info.get("browser", "chrome").lower()
            
            launch_args = {
                "headless": False,
                "slow_mo": self.config.get("slowmo", 1000)
            }
            
            if browser_type == "firefox":
                self.browser = self.playwright.firefox.launch(**launch_args)
            else:
                self.browser = self.playwright.chromium.launch(**launch_args)
                
            self.page = self.browser.new_page()
            
            url = self.session_info.get("url")
            if url:
                logger.info(f"Navegando a la URL inicial: {url}")
                self.page.goto(url, wait_until="domcontentloaded")
                
            return True
        except Exception as e:
            logger.error(f"Error en setup de WebPlayer: {e}")
            return False

    def _highlight_and_indicator(self, selector: str, action: str, current: int, total: int):
        """Muestra un indicador visual en el navegador del paso actual."""
        try:
            # Script para resaltar el elemento y mostrar un tooltip de depuración
            script = """
            (sel, act, cur, tot) => {
                const el = document.querySelector(sel);
                
                // 1. Crear o actualizar el indicador de paso (top bar)
                let indicator = document.getElementById('rpa-debug-indicator');
                if (!indicator) {
                    indicator = document.createElement('div');
                    indicator.id = 'rpa-debug-indicator';
                    Object.assign(indicator.style, {
                        position: 'fixed', top: '10px', right: '10px',
                        padding: '10px 20px', backgroundColor: '#1e293b',
                        color: '#f8fafc', borderRadius: '8px', zIndex: '999999',
                        fontFamily: 'Consolas, monospace', fontSize: '14px',
                        boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                        border: '2px solid #3b82f6', transition: 'all 0.3s'
                    });
                    document.body.appendChild(indicator);
                }
                indicator.innerHTML = `🤖 <b>DEBUG RPA</b><br>Paso: ${cur}/${tot}<br>Acción: <span style="color:#60a5fa">${act.toUpperCase()}</span>`;

                // 2. Resaltar el elemento
                if (el) {
                    const originalOutline = el.style.outline;
                    el.style.outline = '4px solid #facc15';
                    el.style.outlineOffset = '2px';
                    el.scrollIntoView({behavior: 'smooth', block: 'center'});
                    
                    // Quitar resaltado después de un momento
                    setTimeout(() => { el.style.outline = originalOutline; }, 1500);
                }
            }
            """
            self.page.evaluate(script, selector, action, current, total)
            time.sleep(0.8) # Pausa para que el usuario humano vea el debug
        except Exception:
            pass

    def run(self) -> dict:
        if not self.setup():
            return {"status": "FAILED", "reason": "Setup de Playwright falló"}
            
        results = {
            "session_id": self.session_id,
            "status": "RUNNING",
            "total_actions": len(self.steps),
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        try:
            for idx, step in enumerate(self.steps, 1):
                action = step.get("action")
                selector = step.get("selector")
                value = step.get("value")
                
                logger.info(f"[{idx}/{results['total_actions']}] Debugging {action} en {selector}")
                
                # Efecto visual de depuración
                self._highlight_and_indicator(selector, action, idx, results['total_actions'])
                
                try:
                    if action == "click":
                        self.page.click(selector, timeout=5000)
                    elif action == "type":
                        self.page.fill(selector, value, timeout=5000)
                    elif action == "hover":
                        self.page.hover(selector, timeout=5000)
                    
                    results["completed"] += 1
                except Exception as e:
                    logger.warning(f"Error en paso {idx}: {e}")
                    results["failed"] += 1
                    results["errors"].append({"step": idx, "error": str(e)})
                    if self.config.get("stop_on_error", False):
                        break
            
            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
        except Exception as e:
            logger.error(f"Error durante la ejecución web: {e}")
            results["status"] = "FAILED"
            results["reason"] = str(e)
        finally:
            if self.browser:
                time.sleep(1)
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
                
        results["end_time"] = datetime.now().isoformat()
        return results
