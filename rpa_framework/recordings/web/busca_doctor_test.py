import time
import sys
import os
import logging
import mysql.connector
import tkinter as tk
from tkinter import simpledialog
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

# Agregando para telegram_manager
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils.telegram_manager import enviar_alerta_todos

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BuscadorDoctorSeleniumTest:
    """
    Se conecta al navegador y abre el PDF ingresado manualmente por el usuario.
    """
    
    def __init__(self, usar_navegador_existente: bool = True):
        self.driver: Optional[webdriver.Chrome] = None
        self.usar_navegador_existente = usar_navegador_existente
        
    def conectar_navegador(self):
        """Conecta al navegador existente"""
        try:
            logger.info("Conectando al navegador existente en puerto 9222...")
            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = webdriver.Chrome(options=options)
            logger.info("✓ Conectado al navegador existente")
        except Exception as e:
            logger.error(f"✗ Error al conectar al navegador: {e}")
            raise
    
    def abrir_link_pdf(self, link: str):
        """Abre el link en una nueva pestaña (simulando el comportamiento de click)"""
        try:
            logger.info(f"Abriendo el link en una nueva pestaña: {link}")
            self.driver.execute_script("window.open(arguments[0], '_blank');", link)
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"✗ Error al abrir el link del PDF: {e}")
            return False

    def cerrar(self):
        if self.driver and not self.usar_navegador_existente:
            try:
                self.driver.quit()
                logger.info("✓ Navegador cerrado")
            except:
                pass


# Desactivar logs innecesarios
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


class BuscadorBaseDatosTest:
    """Clase para actualizar tracking localmente"""
    
    def __init__(self, host="localhost", user="root", password="", database="ris"):
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database
        }
        self.script_name = "busca_doctor_test"
        
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

    def actualizar_registro_acciones(self, doctor_detectado, usuario, clave):
        """
        Actualiza doctor y credenciales con datos dummy,
        ya que el usuario saltó la búsqueda visual.
        """
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
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
            if conn and conn.is_connected():
                conn.close()


def pedir_link_usuario():
    """Muestra un popup simple con Tkinter para no depender de la consola"""
    root = tk.Tk()
    root.withdraw() # ocultar ventana principal
    # Mostramos ventana al frente
    root.attributes('-topmost', True)
    link = simpledialog.askstring("Ingreso PDF", "Ingrese el link (URL) del PDF a procesar:", parent=root)
    root.destroy()
    return link


def main():
    """Función principal (Modo Prueba)"""
    logger.setLevel(logging.ERROR)
    bd = BuscadorBaseDatosTest()
    
    try:
        # 1. Iniciar tracking
        bd.db_update_tracking(status='En Proceso')
        
        # 2. Obtener nombre del navegador (para estar listos)
        buscador = BuscadorDoctorSeleniumTest(usar_navegador_existente=True)
        buscador.conectar_navegador()
        
        # 3. Pedir el link al usuario mediante un input/dialog
        print("Esperando que el usuario ingrese la URL del PDF...")
        link_pdf = pedir_link_usuario()
        
        if not link_pdf or not link_pdf.strip():
            print("Operación cancelada o link vacío.")
            bd.db_update_tracking(status='error')
            sys.exit(1)
            
        print(f"URL Ingresada: {link_pdf}")
            
        # 4. Enviar dummy a BD para que el workflow pueda seguir sin crashear
        print("Actualizando registro_acciones con datos de prueba...")
        bd.actualizar_registro_acciones(
            doctor_detectado="Doctor Prueba",
            usuario="user_prueba",
            clave="pass_prueba"
        )
        
        # 5. Abrir la URL directamente en el navegador actual
        print(f"[ACTION] Abriendo URL en nueva pestaña...")
        buscador.abrir_link_pdf(link_pdf.strip())
        
        print("✓ Script de prueba finalizado. Pasando al siguiente flujo.")

    except Exception as e:
        bd.db_update_tracking(status='error')
        import traceback
        traceback.print_exc()
        try:
            enviar_alerta_todos(f"❌ <b>Error Crítico en el script: busca_doctor_test</b>\\nExcepción:\\n<code>{str(e)}</code>")
        except:
            pass
        sys.exit(1)
    
    finally:
        try:
            if 'buscador' in locals():
                buscador.cerrar()
        except:
            pass


if __name__ == "__main__":
    main()
