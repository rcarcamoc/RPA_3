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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

# Agregar al path para uso global
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils.telegram_manager import enviar_alerta_todos

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

    def guardar_url_previa(self, url):
        """Guarda la URL del PDF anticipadamente en registro_acciones antes de abrirlo/descargarlo"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            query = """
            UPDATE registro_acciones 
            SET URL = %s, `update` = NOW(), ultimo_nodo = %s
            WHERE estado = 'En Proceso'
            """
            cursor.execute(query, (url, self.script_name))
            conn.commit()
            print(f"[DB] URL del PDF guardada anticipadamente: {url}")
            return True
        except Exception as e:
            print(f"[ERROR] Error al guardar URL anticipada en BD: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()

    def actualizar_datos_pdf(self, numero_documento, diagnostico, examen, url, fecha_agendada=None):
        """Actualiza numero_documento, diagnostico, examen, url y fecha_agendada en registro_acciones"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            query = """
            UPDATE registro_acciones 
            SET numero_documento = %s, diagnostico = %s, examen = %s, URL = %s, fecha_agendada = %s, `update` = NOW(), ultimo_nodo = %s
            WHERE estado = 'En Proceso'
            """
            cursor.execute(query, (numero_documento, diagnostico, examen, url, fecha_agendada, self.script_name))
            conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Error al guardar datos PDF en BD: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()

class ExtractorPDFDoctor:
    def __init__(self, port=9222, bd=None):
        self.port = port
        self.bd = bd
        self.driver = None
        self.ris_post_data = None
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

    def _extraer_datos_post_ris(self):
        """Extrae los campos de frmLista o del último link setExamenImg en la pestaña principal RIS."""
        try:
            script = """
                var res = {};
                var f = document.forms['frmLista'] || document.getElementById('frmLista');
                if (f) {
                    var inputs = f.querySelectorAll('input');
                    for (var i = 0; i < inputs.length; i++) {
                        if (inputs[i].name) res[inputs[i].name] = inputs[i].value;
                    }
                }
                if (!res.idExamen || res.idExamen === '-1') {
                    var links = document.querySelectorAll('a[href*="setExamenImg"]');
                    if (links.length > 0) {
                        var href = links[links.length - 1].getAttribute('href') || '';
                        var m = href.match(/setExamenImg\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\)/);
                        if (m) {
                            res.idExamen = m[1];
                            res.idAgenda = m[2];
                            res.idPaciente = m[3];
                            res.descargaInterna = '-1';
                        }
                    }
                }
                return res;
            """
            data = self.driver.execute_script(script)
            if isinstance(data, dict) and data.get("idExamen") and data.get("idExamen") != "-1":
                logger.info(f"Datos POST de RIS capturados: idExamen={data.get('idExamen')}, idPaciente={data.get('idPaciente')}")
                return data
        except Exception as e:
            logger.warning(f"No se pudieron extraer datos POST de frmLista: {e}")
        return None

    def procesar_pestana_pdf(self):
        """
        Busca una pestaña que parezca ser un PDF (blob:, .pdf o /atencion/pdf),
        descarga el contenido y extrae los datos solicitados.
        PROTEGE la ventana cuyo título comienza con 'RIS'.
        """
        ris_handle = None
        target_handle = None
        try:
            handles = self.driver.window_handles
            pdf_handle = None
            
            logger.info(f"Analizando {len(handles)} pestañas abiertas...")

            # 1. Identificar ventanas (Recorremos para encontrar la RIS y el PDF)
            for h in handles:
                try:
                    self.driver.switch_to.window(h)
                    time.sleep(0.5) 
                    title = self.driver.title
                    url = self.driver.current_url
                    
                    logger.info(f"Ventana [{h[-4:]}]: Titulo='{title}' | URL='{url}'")

                    # Identificar ventana Principal (RIS)
                    if title and title.strip().upper().startswith("RIS"):
                        ris_handle = h
                        logger.info("-> MARCADA COMO PRINCIPAL (NO CERRAR)")
                        self.ris_post_data = self._extraer_datos_post_ris()
                        continue # Pasamos a la siguiente, esta no es el PDF
                    
                    # Identificar candidato PDF (si no es la RIS)
                    if url and ("blob:" in url or ".pdf" in url.lower() or "/atencion/pdf" in url.lower() or "print" in url.lower()):
                         pdf_handle = h
                         logger.info(f"-> MARCADA COMO PDF (POR URL): {url}")

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
            
            # 2. Procesar (Cambiamos al target si no estamos ahí)
            self.driver.switch_to.window(target_handle)
            time.sleep(1.0)
            current_url = self.driver.current_url

            # Si está en /ris/atencion/pdf y aún no tiene título ni redirigió a .pdf, dar breve espera
            if current_url and "/ris/atencion/pdf" in current_url.lower():
                for _ in range(4):
                    if ".pdf" in (self.driver.current_url or "").lower() or ".pdf" in (self.driver.title or "").lower():
                        break
                    time.sleep(0.5)
                current_url = self.driver.current_url

            logger.info(f"Procesando PDF desde URL: {current_url}")
            
            if not current_url or current_url == "about:blank":
                logger.warning("URL vacía o about:blank en ventana objetivo.")
                return None

            # Guardar la URL en la base de datos ANTES de intentar abrir/descargar el PDF
            if self.bd and current_url:
                self.bd.guardar_url_previa(current_url)

            extracted_data = None
            try:
                if self.descargar_pdf(current_url):
                    extracted_data = self.extraer_datos()
                    if extracted_data:
                        extracted_data["url"] = current_url
            finally:
                # 3. Cerrar PDF siempre (Solo si NO es la RIS y NO es la única)
                try:
                    if target_handle != ris_handle and len(self.driver.window_handles) > 1:
                        self.driver.switch_to.window(target_handle)
                        logger.info("Cerrando pestaña del PDF...")
                        self.driver.close()
                    else:
                        logger.info("No se cerrará la ventana (Es la RIS o la única abierta).")
                except Exception as e_close:
                    logger.warning(f"No se pudo cerrar la pestaña del PDF: {e_close}")

                # 4. Asegurar foco en RIS al terminar
                if ris_handle:
                    try:
                        self.driver.switch_to.window(ris_handle)
                        logger.info("Foco retornado a ventana RIS.")
                    except Exception:
                        logger.warning("No se pudo volver a la ventana RIS (¿cerrada?).")
                elif len(self.driver.window_handles) > 0:
                    try:
                        self.driver.switch_to.window(self.driver.window_handles[0])
                    except Exception:
                        pass

            return extracted_data

        except Exception as e:
            logger.error(f"Error en el proceso de PDF: {e}")
            return None

    def descargar_pdf(self, url, max_retries=3, delay=2.0):
        """
        Descarga el PDF a self.temp_pdf_path con reintentos y validación de contenido.
        Verifica que el archivo no esté vacío y contenga encabezado válido (%PDF).
        Soporta tanto URLs directas (GET) como el endpoint dinámico /ris/atencion/pdf (POST).
        """
        # Limpiar archivo temporal previo si existe
        if os.path.exists(self.temp_pdf_path):
            try:
                os.remove(self.temp_pdf_path)
            except Exception:
                pass

        if url.startswith("blob:"):
            return self.descargar_blob(url)

        is_dynamic_pdf_endpoint = "/ris/atencion/pdf" in url.lower()

        for intento in range(1, max_retries + 1):
            try:
                logger.info(f"Descargando PDF (Intento {intento}/{max_retries}) desde: {url}")
                session = requests.Session()
                for cookie in self.driver.get_cookies():
                    session.cookies.set(cookie['name'], cookie['value'])
                
                headers = {
                    "User-Agent": self.driver.execute_script("return navigator.userAgent;"),
                    "Referer": "https://ris.chile.telemedicina.com/ris/atencion/lista",
                }

                # Si la URL es /ris/atencion/pdf y tenemos datos POST de frmLista, enviamos POST directamente
                if is_dynamic_pdf_endpoint and self.ris_post_data:
                    post_payload = dict(self.ris_post_data)
                    if session.cookies.get("csrf_ris"):
                        post_payload["csrf_ris"] = session.cookies.get("csrf_ris")
                    logger.info(f"Enviando petición POST a {url} para idExamen={post_payload.get('idExamen')}...")
                    response = session.post(url, data=post_payload, headers=headers, stream=True, verify=False, timeout=20)
                else:
                    response = session.get(url, headers=headers, stream=True, verify=False, timeout=20)

                response.raise_for_status()

                with open(self.temp_pdf_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                if os.path.exists(self.temp_pdf_path):
                    file_size = os.path.getsize(self.temp_pdf_path)
                    if file_size > 100:
                        with open(self.temp_pdf_path, 'rb') as f_chk:
                            header = f_chk.read(5)
                        if header.startswith(b'%PDF'):
                            logger.info(f"PDF descargado correctamente vía HTTP ({file_size} bytes).")
                            return True
                        else:
                            logger.warning(f"Descarga HTTP recibida ({file_size} bytes) pero sin encabezado %PDF válido.")
                            # Si falló por GET y tenemos datos POST de frmLista, probar POST inmediato
                            if not is_dynamic_pdf_endpoint and self.ris_post_data:
                                is_dynamic_pdf_endpoint = True
                    else:
                        logger.warning(f"Descarga HTTP devolvió archivo vacío o insuficiente ({file_size} bytes).")
            except Exception as e:
                logger.warning(f"Fallo en intento {intento} de descarga HTTP: {e}")

            if intento < max_retries:
                time.sleep(delay)

        # Fallback: descarga directa en contexto de sesión del navegador vía JS fetch
        logger.info("Intentando fallback de descarga mediante JS fetch en el navegador...")
        if self.descargar_via_browser_fetch(url):
            if os.path.exists(self.temp_pdf_path) and os.path.getsize(self.temp_pdf_path) > 100:
                with open(self.temp_pdf_path, 'rb') as f_chk:
                    if f_chk.read(5).startswith(b'%PDF'):
                        logger.info("PDF descargado correctamente mediante fallback JS fetch.")
                        return True

        logger.error(f"Fallo definitivo al descargar PDF tras {max_retries} intentos y fallback JS.")
        return False

    def descargar_via_browser_fetch(self, url):
        """Descarga el PDF ejecutando fetch con credenciales directamente en el contexto del navegador."""
        try:
            post_data = self.ris_post_data if ("/ris/atencion/pdf" in url.lower() and self.ris_post_data) else None
            script = """
                var uri = arguments[0];
                var postData = arguments[1];
                var callback = arguments[2];
                var opts = {credentials: 'include'};
                if (postData) {
                    opts.method = 'POST';
                    var params = new URLSearchParams();
                    for (var k in postData) {
                        if (Object.prototype.hasOwnProperty.call(postData, k)) {
                            params.append(k, postData[k]);
                        }
                    }
                    opts.body = params;
                }
                fetch(uri, opts)
                    .then(function(r) { return r.blob(); })
                    .then(function(blob) {
                        var reader = new FileReader();
                        reader.readAsDataURL(blob);
                        reader.onloadend = function() { callback(reader.result); };
                    })
                    .catch(function(e) { callback(null); });
            """
            result = self.driver.execute_async_script(script, url, post_data)
            if result and "," in result:
                header, encoded = result.split(",", 1)
                data = base64.b64decode(encoded)
                with open(self.temp_pdf_path, 'wb') as f:
                    f.write(data)
                return True
            return False
        except Exception as e:
            logger.warning(f"Fallo descarga vía fallback JS fetch: {e}")
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
                 if os.path.exists(self.temp_pdf_path) and os.path.getsize(self.temp_pdf_path) > 100:
                     return True
                 logger.warning("Blob descargado pero está vacío o es inválido.")
            return False
        except Exception as e:
            logger.error(f"Fallo descarga Blob: {e}")
            return False

    def extraer_datos(self):
        try:
            if not os.path.exists(self.temp_pdf_path) or os.path.getsize(self.temp_pdf_path) < 100:
                logger.error("El archivo temporal del PDF no existe o está vacío (menos de 100 bytes).")
                return None

            with open(self.temp_pdf_path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                pages_text = [page.extract_text() or "" for page in reader.pages]

            if not pages_text:
                logger.warning("El PDF no contiene texto extraíble.")
                return None

            # ── Utilidad: cortar el texto de una página antes de la firma ──────
            def cortar_antes_firma(texto):
                """Devuelve solo el texto anterior a 'Atentamente' (la firma).
                Funciona con cualquier nombre de radiólogo — no necesita hardcodear."""
                corte = re.search(r'Atentamente', texto, re.IGNORECASE)
                return texto[:corte.start()].strip() if corte else texto.strip()

            # ── Patrones de metadatos de encabezado (aplican a todas las páginas) ─
            PATRONES_META = [
                r"Integram[eé]dica\n?",
                r"Fecha Examen:\s*[\d\-]+\s+[\d:]+\n?",
                r"Tiempo Cero:\s*[\d\-]+\s+[\d:]+\n?",
                r"Fecha informe:\s*[\d\-]+\s+[\d:]+\n?",
                r"Fecha Adquisici[oó]n Ex\.\s*[\d\-]+\s+[\d:]+\n?",
                r"Fecha de Recepci[oó]n Ex\.\s*[\d\-]+\s+[\d:]+\n?",
                r"Fecha/hora del informe\s*[\d\-]+\s+[\d:]+\n?",
                r"Powered by TCPDF \(www\.tcpdf\.org\)\n?",
                r"Consecutivo \d+\s*\(.*?\)[^\n]*\n?",
                r"P[aá]gina \d+ [/de]+ \d+\n?",
            ]

            def limpiar_meta(texto):
                for p in PATRONES_META:
                    texto = re.sub(p, "", texto, flags=re.IGNORECASE)
                return texto.strip()

            # ── Página 1: extraer metadatos del paciente + primera parte del cuerpo ─
            pagina1 = pages_text[0]

            # 1. Número de documento
            match_doc = re.search(r'N[uú]mero de documento\s*[:\.]?\s*([\d\-]+)', pagina1, re.IGNORECASE)
            doc_number = match_doc.group(1) if match_doc else "NO ENCONTRADO"

            # 2. Fecha Examen o Fecha Adquisición Ex. (solo está en página 1)
            match_fecha = re.search(
                r'(?:Fecha Examen:|Fecha Adquisici[oó]n Ex\.)\s*(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})',
                pagina1,
                re.IGNORECASE
            )
            fecha_examen_raw = re.sub(r'\s+', ' ', match_fecha.group(1).strip()) if match_fecha else None
            fecha_agendada_sql = None
            if fecha_examen_raw:
                try:
                    dt = datetime.strptime(fecha_examen_raw, "%d-%m-%Y %H:%M:%S")
                    fecha_agendada_sql = dt.strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"Fecha Examen capturada: {fecha_agendada_sql}")
                except Exception as e:
                    logger.warning(f"Error al formatear fecha: {e}")

            # 3. Cuerpo de página 1: desde "Número de ficha" (o "Integramédica" / "Edad" en formato /atencion/pdf)
            match_inicio = (
                re.search(r'N[uú]mero de ficha[^\n]*\n', pagina1, re.IGNORECASE)
                or re.search(r'Integram[eé]dica[^\n]*\n', pagina1, re.IGNORECASE)
                or re.search(r'Edad\s+\d+\s*a[ñn]os[^\n]*\n', pagina1, re.IGNORECASE)
            )
            if not match_inicio:
                logger.warning("No se encontró 'Número de ficha' ni encabezado equivalente en página 1.")
                return None

            # Limpiar el encabezado (Integramédica, fechas) que aparece justo después
            # de "Número de ficha" y antes del contenido clínico real
            cuerpo_raw_p1 = limpiar_meta(pagina1[match_inicio.end():])
            cuerpo_p1 = cortar_antes_firma(cuerpo_raw_p1)

            # Campo examen = primera línea no vacía del cuerpo de página 1
            lineas_examen = [l.strip() for l in cuerpo_p1.splitlines() if l.strip()]
            examen = lineas_examen[0] if lineas_examen else "NO ENCONTRADO"

            # ── Páginas 2+: solo continuación del cuerpo, sin encabezado ni firma ─
            PATRONES_CABECERA_PACIENTE = [
                r"Continuaci[oó]n de informe paciente[^\n]*\n?",
                r"Nombre del paciente[^\n]*\n?",
                r"N[uú]mero de documento[^\n]*\n?",
                r"Edad\s+\d+\s*a[ñn]os[^\n]*\n?",
                r"Procedencia[^\n]*\n?",
                r"N[uú]mero de ficha[^\n]*\n?",
            ]
            continuaciones = []
            for texto_pag in pages_text[1:]:
                texto_limpio = texto_pag
                for p_cab in PATRONES_CABECERA_PACIENTE:
                    texto_limpio = re.sub(p_cab, "", texto_limpio, flags=re.IGNORECASE)
                # Limpiar metadatos (Powered by TCPDF, Página X de Y, etc.)
                texto_limpio = limpiar_meta(texto_limpio)
                # Cortar antes de la firma de esta página
                continuaciones.append(cortar_antes_firma(texto_limpio))

            # ── Fusionar todas las partes del cuerpo ──────────────────────────────
            partes = [cuerpo_p1] + continuaciones
            diagnostico = "\n\n".join(p for p in partes if p)

            # Normalizar saltos de línea y espacios
            diagnostico = re.sub(r'\n{3,}', '\n\n', diagnostico)
            diagnostico = "\n".join(line.rstrip() for line in diagnostico.splitlines())

            # Insertar salto de página (\f) antes de "Hallazgos:" (solo al inicio de línea) para el procesador Word
            diagnostico = re.sub(r'(?im)^(Hallazgos:)', r'\f\n\1', diagnostico)

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
    bd = BuscadorBaseDatosPDF()
    extractor = ExtractorPDFDoctor(bd=bd)
    
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
                examen=resultados['examen'],
                url=resultados['url'],
                fecha_agendada=resultados.get('fecha_agendada')
            )
            # 4. Fin Tracking (Éxito)
            bd.db_update_tracking(status='Completado')
            print("✓ Proceso PDF finalizado con éxito.")
        else:
            msg = "No se pudieron obtener datos del PDF."
            try:
                from utils.error_handler import handle_error_and_exit
            except ImportError:
                try:
                    from rpa_framework.utils.error_handler import handle_error_and_exit
                except ImportError:
                    handle_error_and_exit = None
            
            if handle_error_and_exit:
                handle_error_and_exit("procesar_pdf_doctor.py", msg)
            else:
                print(f"[ERROR] {msg}")
                sys.exit(1)

    except Exception as e:
        try:
            from utils.error_handler import handle_error_and_exit
        except ImportError:
            try:
                from rpa_framework.utils.error_handler import handle_error_and_exit
            except ImportError:
                handle_error_and_exit = None
        
        if handle_error_and_exit:
            handle_error_and_exit("procesar_pdf_doctor.py", str(e))
        else:
            logger.error(f"Error fatal: {e}")
            sys.exit(1)
    finally:
        # Aquí se podría liberar el driver si no se usa más, pero usualmente 
        # en estos scripts RIS se deja abierto el navegador.
        pass

if __name__ == "__main__":
    main()
