#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script RPA Autogenerado desde WebRecorder
Sesión: demo_web
Navegador: chromium
URL Original: https://www.google.com
Generado: 2025-12-23T06:39:08.966404
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
    def __init__(self, slowmo=500):
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
            logger.info(f"Navegando a: https://www.google.com")
            self.page.goto(f"https://www.google.com", wait_until="domcontentloaded")

            logger.info("✓ Automatización completada")

        except Exception as e:
            logger.error(f"❌ Error: {str(e)}")
            raise
        finally:
            time.sleep(1)
            self.browser.close()
            logger.info("Navegador cerrado")

if __name__ == "__main__":
    rpa = RPA_Automation(slowmo=500)
    rpa.start()
    rpa.run()
