import sys
import time
import os
import re
import tempfile
import logging
import base64
import requests
import pypdf
import mysql.connector
from datetime import datetime

# Agregar al path para uso global
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
try:
    from utils.telegram_manager import enviar_alerta_todos
except ImportError:
    def enviar_alerta_todos(msg):
        print(f"Alerta Telegram: {msg}")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Silenciar logs ruidosos
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('pypdf').setLevel(logging.WARNING)

logger = logging.getLogger('PDFExtractorURL')
logger.setLevel(logging.INFO)

class BuscadorBaseDatosPDF:
    """Clase para interactuar con la base de datos de RIS"""
    def __init__(self, host="localhost", user="root", password="", database="ris"):
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database
        }
        self.script_name = "procesar_pdf_doctor_url"
        self.id_registro = 1
        
    def _get_conn(self):
        return mysql.connector.connect(**self.config)

    def db_update_tracking(self, status='En Proceso'):
        """Actualiza el estado de la ejecución en la base de datos para el ID 1"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            if status == 'error':
                query = """
                UPDATE registro_acciones 
                SET `update` = NOW(), ultimo_nodo = %s, estado = %s 
                WHERE id = %s
                """
                cursor.execute(query, (self.script_name, status, self.id_registro))
            else:
                query = """
                UPDATE registro_acciones 
                SET `update` = NOW(), ultimo_nodo = %s
                WHERE id = %s
                """
                cursor.execute(query, (self.script_name, self.id_registro))
            
            conn.commit()
            print(f"[DB] Tracking actualizado (ID {self.id_registro}): {self.script_name} ({status})")
        except Exception as e:
            print(f"[ERROR] Error de tracking BD: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()

    def actualizar_datos_pdf(self, numero_documento, diagnostico, examen, url, fecha_agendada=None):
        """Actualiza numero_documento, diagnostico, examen, url y fecha_agendada en registro_acciones para el ID 1"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            query = """
            UPDATE registro_acciones 
            SET numero_documento = %s, diagnostico = %s, examen = %s, URL = %s, fecha_agendada = %s, `update` = NOW(), ultimo_nodo = %s
            WHERE id = %s
            """
            cursor.execute(query, (numero_documento, diagnostico, examen, url, fecha_agendada, self.script_name, self.id_registro))
            conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Error al guardar datos PDF en BD: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()

class ExtractorPDFDoctorURL:
    def __init__(self, port=9222):
        self.port = port
        self.driver = None
        self.temp_pdf_path = os.path.join(tempfile.gettempdir(), "temp_downloaded_rpa_url.pdf")

    def conectar(self):
        """Conecta al navegador Chrome existente en el puerto debug"""
        try:
            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.port}")
            self.driver = webdriver.Chrome(options=options)
            logger.info("Conectado al navegador correctamente para obtener cookies.")
        except Exception as e:
            logger.error(f"Error al conectar con navegador: {e}")
            raise

    def descargar_pdf(self, url):
        """Descarga el PDF usando cookies de la sesión activa o lo copia si es local"""
        try:
            if os.path.exists(url):
                logger.info(f"Usando archivo local: {url}")
                import shutil
                shutil.copy2(url, self.temp_pdf_path)
                logger.info(f"Archivo copiado a: {self.temp_pdf_path}")
                return True

            logger.info(f"Intentando descargar PDF desde: {url}")
            
            session = requests.Session()
            if self.driver:
                for cookie in self.driver.get_cookies():
                    session.cookies.set(cookie['name'], cookie['value'])
                headers = {"User-Agent": self.driver.execute_script("return navigator.userAgent;")}
            else:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

            response = session.get(url, headers=headers, stream=True, verify=False, timeout=30)
            response.raise_for_status()

            with open(self.temp_pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"PDF descargado con éxito en: {self.temp_pdf_path}")
            return True
        except Exception as e:
            logger.error(f"Fallo descarga/copia: {e}")
            return False

    def extraer_datos(self):
        try:
            pages_text = []
            with open(self.temp_pdf_path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                num_pages = len(reader.pages)
                logger.info(f"Procesando PDF con {num_pages} páginas.")
                for i, page in enumerate(reader.pages):
                    txt = page.extract_text()
                    if txt:
                        pages_text.append(txt)
            
            # Unimos todo el texto
            text_content = "\n".join(pages_text)
            
            # 1. Número de Documento
            match_doc = re.search(r'Número de documento\s*[:\.]?\s*([\d\-]+)', text_content, re.IGNORECASE)
            doc_number = match_doc.group(1) if match_doc else "NO ENCONTRADO"
            
            # 2. Cuerpo (Diagnóstico y Examen)
            # Para capturar TODO hasta el ÚLTIMO 'Atentamente', usamos una búsqueda manual o un regex codicioso
            # Primero buscamos el inicio
            start_search = re.search(r'N[úu]mero de ficha.*?\n', text_content, re.IGNORECASE)
            if start_search:
                start_index = start_search.end()
                # Buscamos la ULTIMA ocurrencia de 'Atentamente'
                # Buscamos 'Atentamente' pero de forma que capture la última
                last_atentamente = list(re.finditer(r'Atentamente', text_content, re.IGNORECASE))
                if last_atentamente:
                    end_index = last_atentamente[-1].start()
                else:
                    end_index = len(text_content)
                
                raw_diagnostico = text_content[start_index:end_index]
            else:
                raw_diagnostico = "NO ENCONTRADO"
            
            diagnostico = "NO ENCONTRADO"
            examen = "NO ENCONTRADO"
            
            if raw_diagnostico != "NO ENCONTRADO":
                # Limpieza de textos que se repiten en cada página
                limpiar = [
                    r"Integramédica",
                    r"Fecha Examen:.*?\n",
                    r"Tiempo Cero:.*?\n",
                    r"Fecha informe:.*?\n",
                    r"Powered by TCPDF \(www\.tcpdf\.org\)",
                    r"Página \d+ / \d+",
                    r"Página \d+ de \d+",
                    r"Consecutivo \d+ \(.*?\)",
                    r"Continuación de informe paciente.*?\n",
                    r"Atentamente\.?\s*MD Radiologo\s*\d+\.\d+\.\d+-\d+", # Limpiar bloques de firma intermedios si aparecen
                    r"Omar Enriquez Gutierrez",
                    r"MD Radiologo",
                    r"11\.842\.031-4",
                    r"Atentamente\.?"
                ]
                
                # Guardamos el segmento para el examen antes de limpiar excesivamente
                # El examen suele estar en la primera página
                texto_primera_pagina = pages_text[0] if pages_text else ""
                match_examen_pag1 = re.search(r'N[úu]mero de ficha.*?\n(.*?)(?=Atentamente|\Z)', texto_primera_pagina, re.DOTALL | re.IGNORECASE)
                segmento_examen = match_examen_pag1.group(1).strip() if match_examen_pag1 else raw_diagnostico.strip()

                diagnostico = raw_diagnostico
                
                for p in limpiar:
                    diagnostico = re.sub(p, "", diagnostico, flags=re.IGNORECASE | re.MULTILINE)
                    segmento_examen = re.sub(p, "", segmento_examen, flags=re.IGNORECASE | re.MULTILINE)
                
                diagnostico = diagnostico.strip()
                
                # Eliminar múltiples saltos de línea consecutivos (más de 2)
                diagnostico = re.sub(r'\n{3,}', '\n\n', diagnostico)
                # Limpiar espacios al final de cada línea
                diagnostico = "\n".join([line.rstrip() for line in diagnostico.splitlines()])
                
                # Para el campo 'examen', tomamos SOLO la primera fila
                lineas_examen = [l.strip() for l in segmento_examen.splitlines() if l.strip()]
                examen = lineas_examen[0] if lineas_examen else "NO ENCONTRADO"

            # 3. Fecha Examen
            match_fecha = re.search(r'Fecha Examen:\s*(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})', text_content, re.IGNORECASE)
            fecha_examen_raw = match_fecha.group(1) if match_fecha else None
            fecha_agendada_sql = None
            
            if fecha_examen_raw:
                try:
                    dt = datetime.strptime(fecha_examen_raw, "%d-%m-%Y %H:%M:%S")
                    fecha_agendada_sql = dt.strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"Fecha Examen capturada: {fecha_agendada_sql}")
                except Exception as e:
                    logger.warning(f"Error al formatear fecha: {e}")

            return {
                "numero_documento": doc_number,
                "diagnostico": diagnostico,
                "examen": examen,
                "fecha_agendada": fecha_agendada_sql
            }

        except Exception as e:
            logger.error(f"Error en extracción: {e}")
            return None

def main():
    pdf_url = r"c:\Desarrollo\RPA_3\rpa_framework\utils\pdf.pdf"
    
    bd = BuscadorBaseDatosPDF()
    extractor = ExtractorPDFDoctorURL()
    
    try:
        # 1. Inicio Tracking
        bd.db_update_tracking(status='En Proceso')
        
        # 2. Conectar al navegador para obtener sesión
        try:
            extractor.conectar()
        except:
            logger.warning("No se pudo conectar al navegador. Se intentará descarga directa (puede fallar si requiere login).")

        # 3. Descargar y extraer
        if extractor.descargar_pdf(pdf_url):
            resultados = extractor.extraer_datos()
            
            if resultados:
                resultados["url"] = pdf_url
                print(f"Doc: {resultados['numero_documento']}")
                
                # 4. Guardar en BD (Id 1 se maneja en la clase)
                bd.actualizar_datos_pdf(
                    numero_documento=resultados['numero_documento'],
                    diagnostico=resultados['diagnostico'],
                    examen=resultados['examen'],
                    url=resultados['url'],
                    fecha_agendada=resultados.get('fecha_agendada')
                )
                
                # 5. Fin Tracking (Éxito)
                bd.db_update_tracking(status='Completado')
                print("✓ Proceso PDF desde URL finalizado con éxito.")
            else:
                print("✗ No se pudieron extraer datos del PDF descargado.")
                bd.db_update_tracking(status='error')
                enviar_alerta_todos("⚠️ <b>Script: procesar_pdf_doctor_url</b>\nNo se pudieron extraer datos del PDF descargado.")
                sys.exit(1)
        else:
            print(f"✗ No se pudo descargar el PDF de la URL: {pdf_url}")
            bd.db_update_tracking(status='error')
            enviar_alerta_todos(f"⚠️ <b>Script: procesar_pdf_doctor_url</b>\nNo se pudo descargar el PDF desde la URL:\n{pdf_url}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error fatal: {e}")
        bd.db_update_tracking(status='error')
        enviar_alerta_todos(f"❌ <b>Error Crítico en el script: procesar_pdf_doctor_url</b>\nExcepción:\n<code>{str(e)}</code>")
        sys.exit(1)

if __name__ == "__main__":
    main()
