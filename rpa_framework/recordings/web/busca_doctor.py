import time
import sys
from typing import Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
import logging
import mysql.connector
import re
from difflib import SequenceMatcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BuscadorDoctorSelenium:
    """
    Extrae nombre de médico de la tabla dinámica del RIS
    usando Selenium y conectándose al navegador existente.
    """
    
    def __init__(self, usar_navegador_existente: bool = True):
        """
        Inicializa el buscador de doctores.
        
        Args:
            usar_navegador_existente: Si True, se conecta al navegador en puerto 9222
                                     Si False, abre un nuevo navegador
        """
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.usar_navegador_existente = usar_navegador_existente
        
    def conectar_navegador(self):
        """Conecta al navegador existente o abre uno nuevo"""
        try:
            if self.usar_navegador_existente:
                logger.info("Conectando al navegador existente en puerto 9222...")
                options = ChromeOptions()
                options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                self.driver = webdriver.Chrome(options=options)
                logger.info("✓ Conectado al navegador existente")
            else:
                logger.info("Abriendo nuevo navegador...")
                options = ChromeOptions()
                options.add_argument("--start-maximized")
                self.driver = webdriver.Chrome(options=options)
                logger.info("✓ Navegador nuevo abierto")
            
            self.wait = WebDriverWait(self.driver, 10)
            
        except Exception as e:
            logger.error(f"✗ Error al conectar al navegador: {e}")
            raise
    
    def navegar_a_lista(self, url: str = "https://ris.chile.telemedicina.com/ris/atencion/lista"):
        """
        Navega a la página de lista de exámenes si no está ya allí.
        
        Args:
            url: URL de la página de lista
        """
        try:
            current_url = self.driver.current_url
            if url not in current_url:
                logger.info(f"Navegando a {url}...")
                self.driver.get(url)
                time.sleep(2)
            else:
                logger.info("Ya estamos en la página de lista")
        except Exception as e:
            logger.error(f"✗ Error al navegar: {e}")
            raise
    
    def extraer_primer_medico(self) -> Optional[str]:
        """
        Extrae el nombre del médico de la primera fila de datos.
        Busca en la segunda columna (índice 1) y parsea el contenido.
        
        Format esperado: 'Folio / Nombre Médico'
        Retorna: 'Nombre Médico'
        """
        try:
            logger.info("Esperando que cargue la tabla...")
            
            # Esperar a que aparezca la primera fila de datos
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr"))
            )
            
            # Pequeña pausa para asegurar carga
            time.sleep(1)
            
            # Estrategia final: Iterar filas y buscar patrón con Regex Flexible
            
            # Buscar en las primeras 50 filas para asegurar encontrar el dato real
            # incluso si hay headers o wrappers masivos antes.
            rows = self.driver.find_elements(By.XPATH, "//tbody/tr")
            
            for i, row in enumerate(rows[:50]):
                try:
                    # Intentamos obtener la celda específica si existe estructura
                    txt_to_search = ""
                    cells = row.find_elements(By.TAG_NAME, "td")
                    
                    if len(cells) >= 2:
                        txt_to_search = cells[1].text.strip()
                    else:
                        # Fallback: usar todo el texto de la fila
                        txt_to_search = row.text.strip()
                    
                    if not txt_to_search:
                        continue
                        
                    # Busca Folio (digitos) / Nombre
                    # Permitimos salto de línea en el nombre para capturarlo completo y luego limpiar
                    match = re.search(r'(\d{6,})\s*/\s*([^/]+)', txt_to_search)
                    
                    if match:
                        nombre_raw = match.group(2).strip()
                        
                        # Normalizar espacios: reemplazar explícitamente saltos de línea y luego espacios múltiples
                        nombre_raw = nombre_raw.replace('\n', ' ').replace('\r', ' ')
                        nombre_raw = re.sub(r'\s+', ' ', nombre_raw)
                        
                        # Heurística de limpieza: cortar si aparece "Integramedica", "Hospital", etc.
                        cortes = ["Integram", "Clínica", "Clinica", "Hospital", "Centro", "Sanatorio"]
                        for corte in cortes:
                            # Buscar case-insensitive
                            match_corte = re.search(re.escape(corte), nombre_raw, re.IGNORECASE)
                            if match_corte:
                                nombre_raw = nombre_raw[:match_corte.start()].strip()

                        # Validación mínima
                        if len(nombre_raw) > 2:
                             # Quitar puntos finales si quedaron
                             nombre_raw = nombre_raw.rstrip('.')
                             return nombre_raw

                except:
                    continue
            
            return None

            
        except Exception as e:
            logger.error(f"✗ Error al extraer dato: {e}")
            raise

        except Exception as e:
            logger.error(f"✗ Error al intentar hacer click en el doctor: {e}")
            return False

    def _visual_highlight(self, element):
        """Intenta resaltar visualmente el elemento usando VisualFeedback"""
        try:
             # Lazy import
            try:
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
                from rpa_framework.utils.visual_feedback import VisualFeedback
                vf = VisualFeedback()
            except ImportError:
                return

            # Calcular coordenadas de pantalla usando JS (aproximación)
            screen_rect = self.driver.execute_script("""
                var rect = arguments[0].getBoundingClientRect();
                var borderLeft = (window.outerWidth - window.innerWidth) / 2;
                var navHeight = window.outerHeight - window.innerHeight - borderLeft;
                return {
                    x: rect.left + window.screenX + borderLeft,
                    y: rect.top + window.screenY + navHeight,
                    width: rect.width,
                    height: rect.height
                };
            """, element)
            
            final_x = screen_rect['x'] + screen_rect['width']/2
            final_y = screen_rect['y'] + screen_rect['height']/2
             
            vf.highlight_click(final_x, final_y)
        except Exception:
            pass

    def click_vinculo_doctor(self) -> bool:
        """
        Busca el primer vínculo de doctor (patrón 'Folio / Nombre') en la tabla y le hace click.
        Este es un click dinámico que se adapta al id/nombre de cada caso.
        """
        try:
            logger.info("Buscando el vínculo del médico en la tabla...")
            # Esperar a que la tabla esté presente
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
            
            # Intentar usar el ID de tabla mencionado por el usuario o fallback genérico
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table#turbogrid tbody tr")
            if not rows:
                rows = self.driver.find_elements(By.XPATH, "//tbody/tr")
            
            for row in rows[:50]:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:
                    txt = cells[1].text.strip()
                    # Patrón: Folio (dígitos) / Nombre
                    if re.search(r'\d{6,}\s*/\s*[^/]+', txt):
                        try:
                            link = cells[1].find_element(By.TAG_NAME, "a")
                            logger.info(f"✓ Haciendo click en el vínculo: {txt}")
                            
                            # Asegurar visibilidad con Scroll
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
                            time.sleep(0.5)
                            
                            self._visual_highlight(link)
                            
                            # Intentar click estándar
                            link.click()
                            time.sleep(1.0) # Esperar a que reaccione la página
                            return True
                        except Exception as e:
                            logger.warning(f"Click estándar falló, intentando JS: {e}")
                            try:
                                link = cells[1].find_element(By.TAG_NAME, "a")
                                self._visual_highlight(link)
                                self.driver.execute_script("arguments[0].click();", link)
                                time.sleep(1.0)
                                return True
                            except:
                                pass
            
            logger.warning("No se encontró ningún vínculo de médico que coincida con el patrón.")
            return False
        except Exception as e:
            logger.error(f"✗ Error al intentar hacer click en el doctor: {e}")
            return False

    def verificar_sin_resultados(self) -> bool:
        """
        Verifica si la tabla muestra el mensaje de 'Sin resultados'.
        Retorna True si encuentra el mensaje.
        """
        try:
            logger.info("Verificando si existen resultados en la tabla...")
            # Esperar brevemente a que haya filas (o el mensaje)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
            
            # Buscar celda con texto 'Sin resultados'
            # El usuario indicó: <td align="center" colspan="7"> Sin resultados </td>
            xpath = "//td[contains(text(), 'Sin resultados')]"
            elementos = self.driver.find_elements(By.XPATH, xpath)
            
            if elementos:
                logger.info("Se detectó 'Sin resultados' en la tabla.")
                return True
            return False
        except Exception as e:
            # Si falla el wait o la búsqueda, asumimos que no es el caso de 'Sin resultados' explícito
            logger.warning(f"No se pudo verificar sin resultados (posiblemente hay datos o error): {e}")
            return False

    def cerrar(self):
        """Cierra el navegador (solo si fue abierto por este módulo)"""
        if self.driver and not self.usar_navegador_existente:
            try:
                self.driver.quit()
                logger.info("✓ Navegador cerrado")
            except:
                pass


# Desactivar logs innecesarios para esta ejecución limpia
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


class BuscadorBaseDatos:
    """Clase para buscar médicos en la base de datos local"""
    
    def __init__(self, host="localhost", user="root", password="", database="ris"):
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database
        }
        self.script_name = "busca_doctor"
        
    def _get_conn(self):
        return mysql.connector.connect(**self.config)

    def db_update_tracking(self, status='En Proceso'):
        """Actualiza el estado de la ejecución en la base de datos"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            query = """
            UPDATE registro_acciones 
            SET `update` = NOW(), ultimo_nodo = %s, estado = %s 
            WHERE estado = 'En Proceso'
            """
            cursor.execute(query, (self.script_name, status))
            conn.commit()
            print(f"[DB] Tracking actualizado: {self.script_name} ({status})")
        except Exception as e:
            print(f"[ERROR] Error de tracking BD: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()

    def buscar_credenciales(self, nombre_buscado):
        """
        Busca el nombre más parecido en la tabla medicos y retorna sus credenciales.
        """
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor(dictionary=True)
            
            # Obtener todos los médicos (nombre y credenciales)
            query = "SELECT nombre_completo, usuario_integra, clave_integra FROM medicos"
            cursor.execute(query)
            resultados = cursor.fetchall()
            
            if not resultados:
                print("La tabla de médicos está vacía.")
                return None
                
            # Búsqueda difusa (Fuzzy Matching)
            mejor_match = None
            mejor_ratio = 0.0
            
            nombre_buscado_norm = nombre_buscado.lower()
            
            for medico in resultados:
                nombre_bd = medico['nombre_completo']
                if not nombre_bd:
                    continue
                    
                nombre_bd_norm = nombre_bd.lower()
                
                # Calcular similitud
                ratio = SequenceMatcher(None, nombre_buscado_norm, nombre_bd_norm).ratio()
                
                # Guardar si es el mejor hasta ahora
                if ratio > mejor_ratio:
                    mejor_ratio = ratio
                    mejor_match = medico
            
            if mejor_ratio > 0.4: # Umbral permisivo
                return {
                    'nombre_encontrado': mejor_match['nombre_completo'],
                    'usuario': mejor_match['usuario_integra'],
                    'clave': mejor_match['clave_integra'],
                    'similitud': mejor_ratio
                }
            else:
                print(f"No se encontró coincidencia suficiente (Mejor: {mejor_ratio:.2f})")
                return None

        except Exception as e:
            print(f"Error en búsqueda BD: {e}")
            return None
        finally:
            if conn and conn.is_connected():
                conn.close()

    def actualizar_registro_acciones(self, doctor_detectado, usuario, clave):
        """
        Actualiza la tabla registro_acciones con los datos encontrados
        donde estado = 'En Proceso'.
        """
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Nota: 'User' y 'Pass' son columnas solicitadas.
            # Agregamos ultimo_nodo y fecha de update (usando NOW() de MySQL)
            query = """
            UPDATE registro_acciones 
            SET doctor_detectado = %s, User = %s, Pass = %s, ultimo_nodo = %s, `update` = NOW()
            WHERE estado = 'En Proceso'
            """
            
            val = (doctor_detectado, usuario, clave, self.script_name)
            cursor.execute(query, val)
            
            conn.commit()
            print(f"Update realizado correctamente: {cursor.rowcount} filas afectadas.")
            return True
            
        except Exception as e:
            print(f"Error al actualizar BD: {e}")
            return False
        finally:
                conn.close()

    def registrar_sin_resultados(self):
        """
        Actualiza el estado a 'sin registros para trabajar' cuando la tabla está vacía.
        """
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            query = """
            UPDATE registro_acciones 
            SET estado = 'sin registros para trabajar'
            WHERE estado = 'En Proceso'
            """
            cursor.execute(query)
            conn.commit()
            print("[DB] Estado actualizado a: 'sin registros para trabajar'")
        except Exception as e:
            print(f"[ERROR] Al registrar sin resultados: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()


def main():
    """Función principal"""
    # Silenciar logs del módulo principal también si se desea salida pura
    logger.setLevel(logging.ERROR)
    
    bd = BuscadorBaseDatos()
    
    try:
        # 1. Iniciar tracking
        bd.db_update_tracking(status='En Proceso')
        
        # 2. Obtener nombre del navegador
        buscador = BuscadorDoctorSelenium(usar_navegador_existente=True)
        buscador.conectar_navegador()
        buscador.navegar_a_lista()
        
        # Verificación solicitada antes de extraer
        if buscador.verificar_sin_resultados():
            bd.registrar_sin_resultados()
            print("Terminando script: Tabla sin resultados.")
            # Terminar con error en consola como solicitado (sys.exit(1))
            sys.exit("Script finalizado: Sin resultados para trabajar")

        nombre_medico = buscador.extraer_primer_medico()
        
        if nombre_medico:
            print(f"Médico Web: {nombre_medico}")
            
            # 3. Buscar en Base de Datos
            credenciales = bd.buscar_credenciales(nombre_medico)
            
            if credenciales:
                print("-" * 40)
                print(f"Coincidencia BD: {credenciales['nombre_encontrado']} ({credenciales['similitud']:.2%})")
                print(f"Usuario: {credenciales['usuario']}")
                print(f"Clave: {credenciales['clave']}")
                print("-" * 40)
                
                # 4. Actualizar tabla registro_acciones (éxito del nodo)
                print("Actualizando registro_acciones...")
                bd.actualizar_registro_acciones(
                    doctor_detectado=credenciales['nombre_encontrado'],
                    usuario=credenciales['usuario'],
                    clave=credenciales['clave']
                )
            else:
                print("No se encontraron credenciales en la BD para este médico.")
                # Si no hay credenciales, igual actualizamos el nodo
                bd.db_update_tracking(status='En Proceso')
            
            # 5. Click en el vínculo del médico (Nueva solicitud del usuario)
            # Esto se hace después de que la identificación y actualización en BD terminó.
            print(f"[ACTION] CLICK en el vínculo del médico: {nombre_medico}")
            buscador.click_vinculo_doctor()
            
        else:
            print("No encontrado en la web")
            bd.db_update_tracking(status='En Proceso')

    except Exception:
        # Tracking de error
        bd.db_update_tracking(status='error')
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            if 'buscador' in locals():
                buscador.cerrar()
        except:
            pass


if __name__ == "__main__":
    main()

