"""
Script: busca_doctor_ultima_v2.py
Versión optimizada de busca_doctor_ultima.py:
- Soporta target_id explícito (VAR_TARGET_ID) para permitir ejecución concurrente en pipeline sin pisar otros registros.
- Tiempos de espera optimizados.
- Sin ventanas flotantes ni interrupciones visuales en modo background.
"""

import time
import sys
import os
import re
import logging
from typing import Optional
from difflib import SequenceMatcher

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
try:
    from utils.telegram_manager import enviar_alerta_todos
except ImportError:
    enviar_alerta_todos = None

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BuscadorDoctorSeleniumV2:
    def __init__(self, target_id=None, background=False):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.target_id = target_id or os.environ.get("VAR_TARGET_ID")
        self.background = background
        self.script_name = "busca_doctor_ultima_v2"
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }

    def _get_conn(self):
        if not HAS_MYSQL:
            return None
        return mysql.connector.connect(**self.db_config)

    def conectar_navegador(self):
        try:
            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 8)
            logger.info("✓ Conectado a Chrome en puerto 9222")
        except Exception as e:
            logger.error(f"✗ Error al conectar al navegador: {e}")
            raise

    def extraer_ultimo_medico(self) -> Optional[str]:
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
            rows = self.driver.find_elements(By.XPATH, "//tbody/tr")
            
            for row in reversed(rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    txt = cells[1].text.strip() if len(cells) >= 2 else row.text.strip()
                    if not txt:
                        continue
                    
                    match = re.search(r'(\d{6,})\s*/\s*([^/]+)', txt)
                    if match:
                        nombre_raw = match.group(2).strip().replace('\n', ' ').replace('\r', ' ')
                        nombre_raw = re.sub(r'\s+', ' ', nombre_raw)
                        
                        cortes = ["Integram", "Clínica", "Clinica", "Hospital", "Centro", "Sanatorio"]
                        for corte in cortes:
                            match_corte = re.search(re.escape(corte), nombre_raw, re.IGNORECASE)
                            if match_corte:
                                nombre_raw = nombre_raw[:match_corte.start()].strip()
                                
                        if len(nombre_raw) > 2:
                            return nombre_raw.rstrip('.')
                except Exception:
                    continue
            return None
        except Exception as e:
            logger.error(f"Error extrayendo médico: {e}")
            return None

    def click_vinculo_doctor(self) -> bool:
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table#turbogrid tbody tr") or self.driver.find_elements(By.XPATH, "//tbody/tr")
            
            for row in reversed(rows):
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:
                    txt = cells[1].text.strip()
                    if re.search(r'\d{6,}\s*/\s*[^/]+', txt):
                        try:
                            link = cells[1].find_element(By.TAG_NAME, "a")
                            link_url = link.get_attribute("href")
                            logger.info(f"✓ Clic en vínculo médico: {txt} | URL: {link_url}")
                            
                            # Clic vía JS directo sin necesidad de scroll ni foco del SO
                            self.driver.execute_script("arguments[0].click();", link)
                            time.sleep(0.8)
                            return True
                        except Exception as e:
                            logger.warning(f"Error haciendo click: {e}")
            return False
        except Exception as e:
            logger.error(f"Error click_vinculo_doctor: {e}")
            return False

    @staticmethod
    def calcular_similitud_medico(nombre_web: str, nombre_bd: str) -> float:
        """
        Calcula similitud inteligente entre el nombre extraído de la web/PDF y el nombre en la BD.
        Utiliza:
        1. Normalización de tildes y eliminación de títulos honoríficos (Dr., Dra., MD, Radiólogo).
        2. Token Set Ratio: valida si los tokens de la BD forman parte del nombre web o viceversa.
        3. Token Sort Ratio: tolera orden invertido de nombres/apellidos.
        4. SequenceMatcher: evalúa proximidad secuencial de apoyo.
        """
        import unicodedata
        try:
            from rapidfuzz import fuzz
        except ImportError:
            try:
                from fuzzywuzzy import fuzz
            except ImportError:
                fuzz = None

        def _norm(t):
            if not t:
                return ""
            t = t.lower()
            t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
            t = re.sub(r'\b(?:dr|dra|md|radiologo|medico)\b\.?', '', t)
            t = re.sub(r'[^a-z0-9\s]', ' ', t)
            return re.sub(r'\s+', ' ', t).strip()

        w = _norm(nombre_web)
        b = _norm(nombre_bd)
        if not w or not b:
            return 0.0

        if w == b:
            return 1.0

        seq = SequenceMatcher(None, w, b).ratio()

        if fuzz:
            t_set = fuzz.token_set_ratio(w, b) / 100.0
            t_sort = fuzz.token_sort_ratio(w, b) / 100.0
            score = (t_set * 0.60) + (t_sort * 0.25) + (seq * 0.15)
            return score
        else:
            tokens_w = set(w.split())
            tokens_b = set(b.split())
            overlap = len(tokens_w.intersection(tokens_b))
            token_ratio = overlap / max(len(tokens_b), 1)
            return (token_ratio * 0.70) + (seq * 0.30)

    def buscar_medico_en_bd(self, nombre_medico_web: str):
        if not HAS_MYSQL:
            return None, 0.0
        try:
            conn = self._get_conn()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT nombre_completo, usuario_integra, clave_integra FROM medicos WHERE estado = 'Activo' OR estado IS NULL")
            medicos = cursor.fetchall()
            conn.close()

            mejor_match = None
            mejor_score = 0.0

            for m in medicos:
                nom = m.get('nombre_completo', '')
                if not nom:
                    continue
                score = self.calcular_similitud_medico(nombre_medico_web, nom)
                if score > mejor_score:
                    mejor_score = score
                    mejor_match = m

            return mejor_match, mejor_score
        except Exception as e:
            logger.error(f"Error buscando médico en BD: {e}")
            return None, 0.0

    def actualizar_registro_acciones(self, doctor_detectado, usuario, clave):
        if not HAS_MYSQL:
            return False
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            if self.target_id:
                query = """
                UPDATE registro_acciones 
                SET doctor_detectado = %s, User = %s, Pass = %s, ultimo_nodo = %s, `update` = NOW()
                WHERE id = %s
                """
                cursor.execute(query, (doctor_detectado, usuario, clave, self.script_name, self.target_id))
            else:
                query = """
                UPDATE registro_acciones 
                SET doctor_detectado = %s, User = %s, Pass = %s, ultimo_nodo = %s, `update` = NOW()
                WHERE estado = 'En Proceso'
                """
                cursor.execute(query, (doctor_detectado, usuario, clave, self.script_name))
                
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error actualizando registro_acciones: {e}")
            return False

    def verificar_sin_resultados(self) -> bool:
        """Verifica si la tabla muestra 'Sin resultados'."""
        try:
            xpath = "//td[contains(text(), 'Sin resultados')]"
            if self.driver.find_elements(By.XPATH, xpath):
                return True
            return False
        except Exception:
            return False

    def registrar_sin_resultados(self):
        """Actualiza el estado a 'sin registros para trabajar'."""
        if not HAS_MYSQL:
            return
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            if self.target_id:
                query = """
                UPDATE registro_acciones 
                SET estado = 'sin registros para trabajar', ultimo_nodo = %s, `update` = NOW()
                WHERE id = %s
                """
                cursor.execute(query, (self.script_name, self.target_id))
            else:
                query = """
                UPDATE registro_acciones 
                SET estado = 'sin registros para trabajar', ultimo_nodo = %s, `update` = NOW()
                WHERE estado = 'En Proceso'
                """
                cursor.execute(query, (self.script_name,))
            conn.commit()
            conn.close()
            logger.info("[DB] Estado actualizado a: 'sin registros para trabajar'")
        except Exception as e:
            logger.error(f"Error registrando sin resultados en BD: {e}")

    def run(self) -> int:
        self.conectar_navegador()
        
        if self.verificar_sin_resultados():
            logger.info("ℹ️ Se detectó 'Sin resultados' en la tabla. Registrando en BD...")
            self.registrar_sin_resultados()
            return 2

        nombre_medico = self.extraer_ultimo_medico()
        if not nombre_medico:
            logger.warning("No se detectó ningún médico en la lista. Registrando en BD...")
            self.registrar_sin_resultados()
            return 2

        logger.info(f"Médico Web detectado: {nombre_medico}")
        medico_bd, score = self.buscar_medico_en_bd(nombre_medico)
        
        user = medico_bd['usuario_integra'] if medico_bd else "desconocido"
        clave = medico_bd['clave_integra'] if medico_bd else "desconocido"
        logger.info(f"Coincidencia BD: {medico_bd['nombre_completo'] if medico_bd else 'N/A'} ({score*100:.1f}%) -> Usuario: {user}")

        self.actualizar_registro_acciones(nombre_medico, user, clave)
        self.click_vinculo_doctor()
        return 0


def main():
    target_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("VAR_TARGET_ID")
    background = os.environ.get("VAR_RIS_BACKGROUND", "0") == "1"
    buscador = BuscadorDoctorSeleniumV2(target_id=target_id, background=background)
    try:
        ret = buscador.run()
    except Exception as e:
        logger.error(f"Excepción en buscador doctor V2: {e}")
        ret = 1

    if ret == 0:
        sys.exit(0)
    elif ret == 2:
        logger.info("Fin de ejecución por falta de registros (código 2).")
        if not background:
            try:
                from recordings.web.busca_doctor_ultima import espera_con_countdown
                espera_con_countdown(300, "Sin registros para trabajar.\nReintentando en:")
            except Exception:
                time.sleep(300)
        else:
            time.sleep(300)
        sys.exit(2)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
