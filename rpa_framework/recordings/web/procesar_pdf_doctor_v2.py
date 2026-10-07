"""
Script: procesar_pdf_doctor_v2.py
Versión optimizada de procesar_pdf_doctor.py:
- Soporta target_id explícito (VAR_TARGET_ID) para ejecución en pipeline.
- Descarga y parseo resiliente de PDF sin requerir foco en el sistema operativo.
"""

import os
import re
import sys
import time
import logging
import requests
import urllib3
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PDFDoctorV2:
    def __init__(self, target_id=None):
        self.driver: Optional[webdriver.Chrome] = None
        self.target_id = target_id or os.environ.get("VAR_TARGET_ID")
        self.script_name = "procesar_pdf_doctor_v2"
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

    def conectar(self):
        options = ChromeOptions()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        self.driver = webdriver.Chrome(options=options)

    def obtener_url_pdf_y_cerrar_pestana(self) -> Tuple[Optional[str], Optional[str]]:
        """Busca la pestaña del PDF, extrae la URL y cierra la pestaña volviendo a la lista."""
        handles = self.driver.window_handles
        pdf_url = None
        main_handle = None
        pdf_handle = None

        for h in handles:
            self.driver.switch_to.window(h)
            url = self.driver.current_url
            if ".pdf" in url.lower() or "serve/firmadigital" in url.lower():
                pdf_url = url
                pdf_handle = h
            elif "ris/atencion/lista" in url:
                main_handle = h

        if pdf_handle:
            try:
                self.driver.switch_to.window(pdf_handle)
                self.driver.close()
                logger.info("✓ Pestaña del PDF cerrada exitosamente.")
            except Exception:
                pass

        if main_handle:
            try:
                self.driver.switch_to.window(main_handle)
            except Exception:
                pass

        return pdf_url

    def descargar_y_extraer_texto(self, pdf_url: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        """Descarga el PDF y extrae texto, fecha de examen y rut/documento."""
        # Obtener cookies de Selenium para la descarga autenticada
        session = requests.Session()
        for cookie in self.driver.get_cookies():
            session.cookies.set(cookie['name'], cookie['value'])

        resp = session.get(pdf_url, verify=False, timeout=15)
        resp.raise_for_status()

        tmp_pdf = Path.cwd() / "temp_examen.pdf"
        tmp_pdf.write_bytes(resp.content)

        texto_completo = ""
        if HAS_PDFPLUMBER:
            with pdfplumber.open(tmp_pdf) as pdf:
                for page in pdf.pages:
                    texto_completo += (page.extract_text() or "") + "\n"
        else:
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(tmp_pdf))
                for page in reader.pages:
                    texto_completo += (page.extract_text() or "") + "\n"
            except Exception:
                pass

        try:
            tmp_pdf.unlink(missing_ok=True)
        except Exception:
            pass

        # Extraer fecha
        fecha_examen = None
        match_fecha = re.search(r'Fecha\s*(?:Examen|Atención)?\s*[:]\s*(\d{2}[/-]\d{2}[/-]\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', texto_completo, re.I)
        if match_fecha:
            raw_f = match_fecha.group(1).replace('/', '-')
            try:
                # Normalizar a YYYY-MM-DD
                parts = raw_f.split()[0].split('-')
                if len(parts[0]) == 2: # DD-MM-YYYY
                    fecha_examen = f"{parts[2]}-{parts[1]}-{parts[0]}"
                else:
                    fecha_examen = raw_f.split()[0]
            except Exception:
                fecha_examen = raw_f

        # Extraer documento paciente
        doc_paciente = None
        match_doc = re.search(r'(?:RUT|DNI|Pasaporte|Doc\.?)\s*[:]\s*([0-9Kk.-]+)', texto_completo, re.I)
        if match_doc:
            doc_paciente = match_doc.group(1).strip()
        else:
            # Extraer de URL si contiene el patrón ID_RUT.pdf
            match_url_doc = re.search(r'_(\d{8,11})\.pdf', pdf_url)
            if match_url_doc:
                doc_paciente = match_url_doc.group(1)

        # Extraer nombre del examen
        examen_nombre = ""
        match_ex = re.search(r'(?:Examen|Estudio)\s*[:]\s*([^\n]+)', texto_completo, re.I)
        if match_ex:
            examen_nombre = match_ex.group(1).strip()

        return texto_completo.strip(), fecha_examen, doc_paciente, examen_nombre

    def actualizar_bd(self, doc, diag, examen, url, fecha):
        if not HAS_MYSQL:
            return False
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            if self.target_id:
                query = """
                UPDATE registro_acciones 
                SET numero_documento = %s, diagnostico = %s, examen = %s, URL = %s, fecha_agendada = %s, `update` = NOW(), ultimo_nodo = %s
                WHERE id = %s
                """
                cursor.execute(query, (doc, diag, examen, url, fecha, self.script_name, self.target_id))
            else:
                query = """
                UPDATE registro_acciones 
                SET numero_documento = %s, diagnostico = %s, examen = %s, URL = %s, fecha_agendada = %s, `update` = NOW(), ultimo_nodo = %s
                WHERE estado = 'En Proceso'
                """
                cursor.execute(query, (doc, diag, examen, url, fecha, self.script_name))
                
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error actualizando BD: {e}")
            return False

    def run(self):
        self.conectar()
        pdf_url = self.obtener_url_pdf_y_cerrar_pestana()
        if not pdf_url:
            logger.error("No se encontró pestaña de PDF activa.")
            return False

        logger.info(f"URL de PDF obtenida: {pdf_url}")
        texto, fecha, doc, examen = self.descargar_y_extraer_texto(pdf_url)
        logger.info(f"Fecha Examen: {fecha} | Doc Paciente: {doc}")
        
        self.actualizar_bd(doc, texto, examen, pdf_url, fecha)
        return True


def main():
    target_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("VAR_TARGET_ID")
    proc = PDFDoctorV2(target_id=target_id)
    if proc.run():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
