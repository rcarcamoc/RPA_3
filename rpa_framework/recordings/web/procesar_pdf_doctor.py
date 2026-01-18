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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Silenciar logs ruidosos
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('pypdf').setLevel(logging.WARNING)

logger = logging.getLogger('PDFExtractor')
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
        self.script_name = "procesar_pdf_doctor"
        
    def _get_conn(self):
        return mysql.connector.connect(**self.config)

    def db_update_tracking(self, status='En Proceso'):
        """Actualiza el estado de la ejecución en la base de datos"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            # El usuario pide: update = fecha hora actual, ultimo_nodo = nombre .py, [estado = error si aplica]
            if status == 'error':
                query = """
                UPDATE registro_acciones 
                SET `update` = NOW(), ultimo_nodo = %s, estado = %s 
                WHERE estado = 'En Proceso'
                """
                cursor.execute(query, (self.script_name, status))
            else:
                query = """
                UPDATE registro_acciones 
                SET `update` = NOW(), ultimo_nodo = %s
                WHERE estado = 'En Proceso'
                """
                cursor.execute(query, (self.script_name,))
            
            conn.commit()
            print(f"[DB] Tracking actualizado: {self.script_name} ({status})")
        except Exception as e:
            print(f"[ERROR] Error de tracking BD: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()

    def actualizar_datos_pdf(self, numero_documento, diagnostico, fecha_agendada=None):
        """Actualiza numero_documento, diagnostico y fecha_agendada en registro_acciones"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            query = """
            UPDATE registro_acciones 
            SET numero_documento = %s, diagnostico = %s, fecha_agendada = %s, `update` = NOW(), ultimo_nodo = %s
            WHERE estado = 'En Proceso'
            """
            cursor.execute(query, (numero_documento, diagnostico, fecha_agendada, self.script_name))
            conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Error al guardar datos PDF en BD: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()

class ExtractorPDFDoctor:
    def __init__(self, port=9222):
        self.port = port
        self.driver = None
        self.temp_pdf_path = os.path.join(tempfile.gettempdir(), "temp_downloaded_rpa.pdf")

    def conectar(self):
        """Conecta al navegador Chrome existente en el puerto debug"""
        try:
            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.port}")
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_script_timeout(30)
            logger.info("Conectado al navegador correctamente.")
        except Exception as e:
            logger.error(f"Error al conectar con navegador: {e}")
            raise

    def procesar_pestana_pdf(self):
        """
        Busca una pestaña que parezca ser un PDF (blob: o .pdf),
        descarga el contenido y extrae los datos solicitados.
        PROTEGE la ventana cuyo título comienza con 'RIS'.
        """
        try:
            handles = self.driver.window_handles
            ris_handle = None
            pdf_handle = None
            
            logger.info(f"Analizando {len(handles)} pestañas abiertas...")

            # 1. Identificar ventanas (Recorremos para encontrar la RIS y el PDF)
            for h in handles:
                try:
                    self.driver.switch_to.window(h)
                    time.sleep(0.5) 
                    title = self.driver.title
                    url = self.driver.current_url
                    
                    logger.info(f"Ventana [{h[-4:]}]: Titulo='{title}' | URL='{url[:50]}...'")

                    # Identificar ventana Principal (RIS)
                    # Usamos .upper() para evitar problemas de case, aunque el usuario dijo "RIS"
                    if title and title.strip().upper().startswith("RIS"):
                        ris_handle = h
                        logger.info("-> MARCADA COMO PRINCIPAL (NO CERRAR)")
                        continue # Pasamos a la siguiente, esta no es el PDF
                    
                    # Identificar candidato PDF (si no es la RIS)
                    if url and ("blob:" in url or ".pdf" in url.lower() or "print" in url.lower()):
                         pdf_handle = h
                         logger.info("-> MARCADA COMO PDF (POR URL)")

                except Exception as e:
                    logger.warning(f"Error inspeccionando ventana {h}: {e}")

            # Si no encontramos un PDF explícito por URL, asumimos que es cualquier ventana que NO sea la RIS
            if not pdf_handle:
                for h in reversed(handles):
                    if h != ris_handle:
                        pdf_handle = h
                        logger.info(f"-> Asumiendo ventana PDF por descarte: {h[-4:]}")
                        break
            
            # Validación final de objetivos
            if ris_handle and len(handles) == 1:
                 logger.warning("Solo está abierta la ventana RIS. No hay PDF para procesar.")
                 return None
            
            target_handle = pdf_handle if pdf_handle else (handles[-1] if handles else None)
            
            if not target_handle:
                logger.warning("No se pudo determinar qué ventana procesar.")
                return None

            if target_handle == ris_handle:
                logger.warning("La ventana objetivo resultó ser la RIS. Abortando cierre para protegerla.")
                # Podríamos intentar extraer datos igual, pero sin cerrar
            
            # 2. Procesar (Cambiamos al target si no estamos ahí)
            self.driver.switch_to.window(target_handle)
            current_url = self.driver.current_url
            
            if not current_url or current_url == "about:blank":
                logger.warning("URL vacía o about:blank en ventana objetivo.")
                return None

            extracted_data = None
            if self.descargar_pdf(current_url):
                 extracted_data = self.extraer_datos()
                 
                 # 3. Cerrar PDF (Solo si NO es la RIS y NO es la única)
                 if target_handle != ris_handle and len(self.driver.window_handles) > 1:
                     logger.info("Cerrando pestaña del PDF...")
                     self.driver.close()
                 else:
                     logger.info("No se cerrará la ventana (Es la RIS o la única abierta).")

            # 4. Asegurar foco en RIS al terminar
            if ris_handle:
                try:
                    self.driver.switch_to.window(ris_handle)
                    logger.info("Foco retornado a ventana RIS.")
                except:
                    logger.warning("No se pudo volver a la ventana RIS (¿cerrada?).")
            elif len(self.driver.window_handles) > 0:
                 self.driver.switch_to.window(self.driver.window_handles[0])

            return extracted_data

        except Exception as e:
            logger.error(f"Error en el proceso de PDF: {e}")
            return None

    def descargar_pdf(self, url):
        try:
            if url.startswith("blob:"):
                return self.descargar_blob(url)

            session = requests.Session()
            for cookie in self.driver.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
            
            headers = {"User-Agent": self.driver.execute_script("return navigator.userAgent;")}
            response = session.get(url, headers=headers, stream=True, verify=False)
            response.raise_for_status()

            with open(self.temp_pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Fallo descarga HTTP: {e}")
            return False

    def descargar_blob(self, blob_url):
        try:
            script = """
                var uri = arguments[0];
                var callback = arguments[1];
                var xhr = new XMLHttpRequest();
                xhr.open('GET', uri, true);
                xhr.responseType = 'blob';
                xhr.onload = function(e) {
                    if (this.status == 200) {
                        var blob = this.response;
                        var reader = new FileReader();
                        reader.readAsDataURL(blob);
                        reader.onloadend = function() { callback(reader.result); }
                    } else { callback(null); }
                };
                xhr.onerror = function() { callback(null); };
                xhr.send();
            """
            result = self.driver.execute_async_script(script, blob_url)
            if result:
                 header, encoded = result.split(",", 1)
                 data = base64.b64decode(encoded)
                 with open(self.temp_pdf_path, 'wb') as f:
                     f.write(data)
                 return True
            return False
        except Exception as e:
            logger.error(f"Fallo descarga Blob: {e}")
            return False

    def extraer_datos(self):
        try:
            text_content = ""
            with open(self.temp_pdf_path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    text_content += page.extract_text() + "\n"
            
            # 1. Número de Documento
            match_doc = re.search(r'Número de documento\s*[:\.]?\s*([\d\-]+)', text_content, re.IGNORECASE)
            doc_number = match_doc.group(1) if match_doc else "NO ENCONTRADO"
            
            # 2. Cuerpo (Diagnóstico)
            pattern_body = r'N[úu]mero de ficha.*?\n(.*?)(?=Atentamente|\Z)'
            match_body = re.search(pattern_body, text_content, re.DOTALL | re.IGNORECASE)
            
            diagnostico = "NO ENCONTRADO"
            if match_body:
                diagnostico = match_body.group(1).strip()
                # Limpieza solicitada por el usuario
                limpiar = [
                    r"Integramédica",
                    r"Fecha Examen:.*?\n",
                    r"Tiempo Cero:.*?\n",
                    r"Fecha informe:.*?\n",
                    r"Powered by TCPDF \(www\.tcpdf\.org\)"
                ]
                for p in limpiar:
                    diagnostico = re.sub(p, "", diagnostico, flags=re.IGNORECASE | re.MULTILINE)
                
                diagnostico = diagnostico.strip()

            # 3. Fecha Examen
            # Formato en PDF: "Fecha Examen: 22-12-2025 08:19:33"
            match_fecha = re.search(r'Fecha Examen:\s*(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})', text_content, re.IGNORECASE)
            fecha_examen_raw = match_fecha.group(1) if match_fecha else None
            fecha_agendada_sql = None
            
            if fecha_examen_raw:
                try:
                    # Convertir dd-mm-yyyy hh:mm:ss -> yyyy-mm-dd hh:mm:ss
                    dt = datetime.strptime(fecha_examen_raw, "%d-%m-%Y %H:%M:%S")
                    fecha_agendada_sql = dt.strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"Fecha Examen capturada (fecha_agendada): {fecha_agendada_sql}")
                except Exception as e:
                    logger.warning(f"Error al formatear fecha: {e}")

            return {
                "numero_documento": doc_number,
                "diagnostico": diagnostico,
                "fecha_agendada": fecha_agendada_sql
            }

        except Exception as e:
            logger.error(f"Error en extracción: {e}")
            return None

def main():
    bd = BuscadorBaseDatosPDF()
    extractor = ExtractorPDFDoctor()
    
    try:
        # 1. Inicio Tracking
        bd.db_update_tracking(status='En Proceso')
        
        # 2. Conectar y extraer
        extractor.conectar()
        resultados = extractor.procesar_pestana_pdf()
        
        if resultados:
            print(f"Doc: {resultados['numero_documento']}")
            # 3. Guardar en BD
            bd.actualizar_datos_pdf(
                numero_documento=resultados['numero_documento'],
                diagnostico=resultados['diagnostico'],
                fecha_agendada=resultados.get('fecha_agendada')
            )
            # 4. Fin Tracking (Éxito)
            bd.db_update_tracking(status='Completado')
            print("✓ Proceso PDF finalizado con éxito.")
        else:
            print("✗ No se pudieron obtener datos del PDF.")
            bd.db_update_tracking(status='error')

    except Exception as e:
        logger.error(f"Error fatal: {e}")
        bd.db_update_tracking(status='error')
    finally:
        # Aquí se podría liberar el driver si no se usa más, pero usualmente 
        # en estos scripts RIS se deja abierto el navegador.
        pass

if __name__ == "__main__":
    main()
