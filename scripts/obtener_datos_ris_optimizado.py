#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: obtener_datos_ris_optimizado.py
Descripción:
  Workflow optimizado de obtención de datos desde RIS en Chrome:
  1. Reutilización reactiva de sesión (evita logout/login repetitivo).
  2. Filtro inteligente con Select2 (selección instantánea vía jQuery o UI).
  3. Conteo de casos pendientes y registro en BD (idéntico a la función /casos de Telegram).
  4. Extracción en una sola pasada de médico y enlace a PDF (sin dobles recorridos de tabla).
  5. Descarga y extracción de datos del PDF con esperas reactivas y validación de integridad.
  6. Resiliencia ante latencia de red/servidor (Event-Driven Waits en vez de time.sleep ciegos).
  7. Medición y reporte de tiempos por cada etapa.
"""

import os
import sys
import time
import socket
import re
import io
import unicodedata
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

# Configurar codificación estándar
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Importar Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options as ChromeOptions
except ImportError:
    print("❌ Error: 'selenium' no está instalado en el entorno.")
    sys.exit(1)

# Importar MySQL
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False
    print("⚠️ Advertencia: 'mysql-connector-python' no disponible.")

# Importar Requests y PyPDF
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

# Importar Rapidfuzz / Fuzzy
try:
    from rapidfuzz import fuzz
    HAS_FUZZ = True
except ImportError:
    try:
        from fuzzywuzzy import fuzz
        HAS_FUZZ = True
    except ImportError:
        fuzz = None
        HAS_FUZZ = False

from difflib import SequenceMatcher

# Configuración de Base de Datos
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ris',
    'connect_timeout': 5
}

class GestorRISOptimizado:
    def __init__(self, port: int = 9222):
        self.port = port
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.ris_handle: Optional[str] = None
        self.metrics: Dict[str, float] = {}
        self.start_time: float = 0.0

    # -------------------------------------------------------------------------
    # 1. Base de datos
    # -------------------------------------------------------------------------
    def get_db(self):
        if not HAS_MYSQL:
            return None
        try:
            return mysql.connector.connect(**DB_CONFIG)
        except Exception as e:
            print(f"⚠️ Error conectando a BD: {e}", flush=True)
            return None

    def guardar_casos_pendientes(self, total: int, cliente: str = 'integramedica', obs: str = None):
        """Registra el conteo en la tabla casos_pendientes tal como /casos de Telegram"""
        conn = self.get_db()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS casos_pendientes (
                    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    fecha_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    cliente VARCHAR(100) DEFAULT 'integramedica',
                    total_pendientes INT NOT NULL DEFAULT 0,
                    observacion VARCHAR(500) NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cursor.execute("""
                INSERT INTO casos_pendientes (fecha_hora, cliente, total_pendientes, observacion)
                VALUES (NOW(), %s, %s, %s)
            """, (cliente, total, obs))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"[DB] Registrado en 'casos_pendientes': {total} registros.", flush=True)
        except Exception as e:
            print(f"⚠️ Error guardando casos_pendientes: {e}", flush=True)

    def actualizar_registro_acciones(self, doctor: str, usuario: str, clave: str, doc_paciente: str = None,
                                     diagnostico: str = None, examen: str = None, url: str = None, fecha_agendada: str = None):
        """Actualiza el caso 'En Proceso' en registro_acciones"""
        conn = self.get_db()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM registro_acciones WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO registro_acciones (inicio, `update`, ultimo_nodo, estado)
                    VALUES (NOW(), NOW(), 'obtener_datos_ris_opt', 'En Proceso')
                """)
                conn.commit()
                target_id = cursor.lastrowid
            else:
                target_id = row[0]

            query = """
                UPDATE registro_acciones 
                SET doctor_detectado = COALESCE(%s, doctor_detectado),
                    User = COALESCE(%s, User),
                    Pass = COALESCE(%s, Pass),
                    numero_documento = COALESCE(%s, numero_documento),
                    diagnostico = COALESCE(%s, diagnostico),
                    examen = COALESCE(%s, examen),
                    URL = COALESCE(%s, URL),
                    fecha_agendada = COALESCE(%s, fecha_agendada),
                    ultimo_nodo = 'obtener_datos_ris_opt',
                    `update` = NOW()
                WHERE id = %s
            """
            cursor.execute(query, (doctor, usuario, clave, doc_paciente, diagnostico, examen, url, fecha_agendada, target_id))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"[DB] Registro {target_id} actualizado exitosamente.", flush=True)
        except Exception as e:
            print(f"⚠️ Error actualizando registro_acciones: {e}", flush=True)

    # -------------------------------------------------------------------------
    # 2. Conexión a Navegador (Attach o Launch)
    # -------------------------------------------------------------------------
    def conectar_o_iniciar_chrome(self):
        t0 = time.time()
        is_port_open = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.4)
                if s.connect_ex(('127.0.0.1', self.port)) == 0:
                    is_port_open = True
        except Exception:
            pass

        if is_port_open:
            try:
                print(f"[CHROME] Puerto {self.port} detectado. Conectando a sesión activa...", flush=True)
                attach_options = ChromeOptions()
                attach_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.port}")
                self.driver = webdriver.Chrome(options=attach_options)
                print("✓ Conexión establecida a Chrome existente.", flush=True)
            except Exception as e:
                print(f"⚠️ No se pudo adjuntar al puerto {self.port}: {e}", flush=True)

        if not self.driver:
            print("[CHROME] Iniciando nueva instancia de Chrome con depuración remota...", flush=True)
            launch_options = ChromeOptions()
            launch_options.add_argument(f"--remote-debugging-port={self.port}")
            launch_options.add_argument("--no-sandbox")
            launch_options.add_argument("--disable-dev-shm-usage")
            launch_options.add_argument("--start-maximized")
            
            profile_path = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "RPA_Remote_Profile"
            launch_options.add_argument(f"--user-data-dir={profile_path}")
            launch_options.add_experimental_option("detach", True)
            
            self.driver = webdriver.Chrome(options=launch_options)
            print("✓ Nueva instancia de Chrome iniciada.", flush=True)

        self.wait = WebDriverWait(self.driver, 10, poll_frequency=0.2)
        self.ris_handle = self.driver.current_window_handle
        self.metrics['conexion_chrome'] = time.time() - t0

    # -------------------------------------------------------------------------
    # 3. Sesión Activa / Login Reactivo
    # -------------------------------------------------------------------------
    def asegurar_sesion_activa(self):
        t0 = time.time()
        url_actual = self.driver.current_url or ""
        print(f"[SESIÓN] URL actual: {url_actual}", flush=True)

        # Comprobar si ya estamos en la lista de atención con sesión válida
        if "ris/atencion/lista" in url_actual:
            try:
                # Comprobar si el formulario o botón buscar están disponibles
                if self.driver.find_elements(By.ID, "frm_buscar") or self.driver.find_elements(By.ID, "buscar"):
                    print("⚡ Sesión ya activa en 'Lista de Atención'. Omitiendo login.", flush=True)
                    self.metrics['sesion_verificacion'] = time.time() - t0
                    return
            except Exception:
                pass

        # Si no estamos en la lista o venimos de otra pestaña, navegar directo
        print("[SESIÓN] Navegando a https://ris.chile.telemedicina.com/ris/atencion/lista...", flush=True)
        self.driver.get('https://ris.chile.telemedicina.com/ris/atencion/lista')

        # Esperar a que la página reaccione (carga de lista o redirección a login)
        try:
            WebDriverWait(self.driver, 5, poll_frequency=0.2).until(
                lambda d: "login" in d.current_url.lower() or d.find_elements(By.ID, "frm_buscar") or d.find_elements(By.ID, "buscar")
            )
        except Exception:
            pass

        # Si fuimos redirigidos a pantalla de login
        if "login" in self.driver.current_url.lower() or self.driver.find_elements(By.ID, "user"):
            print("[SESIÓN] Sesión no activa. Realizando login formal...", flush=True)
            # Manejo de alerta inicial si existe
            try:
                WebDriverWait(self.driver, 1.5).until(EC.alert_is_present())
                self.driver.switch_to.alert.accept()
            except Exception:
                pass

            txt_user = self.wait.until(EC.element_to_be_clickable((By.ID, "user")))
            txt_user.clear()
            txt_user.send_keys("rbt.integra")

            txt_pass = self.wait.until(EC.element_to_be_clickable((By.ID, "pass")))
            txt_pass.clear()
            txt_pass.send_keys("Integramedica02!")

            btn = self.wait.until(EC.element_to_be_clickable((By.ID, "button")))
            btn.click()

            self.wait.until(lambda d: "atencion/lista" in d.current_url.lower() or "login" not in d.current_url.lower())
            if "atencion/lista" not in self.driver.current_url:
                self.driver.get('https://ris.chile.telemedicina.com/ris/atencion/lista')
            
            self.wait.until(EC.presence_of_element_located((By.ID, "frm_buscar")))
            print("✓ Login formal completado exitosamente.", flush=True)
        else:
            print("⚡ Sesión activa reutilizada exitosamente sin relogueo.", flush=True)

        self.metrics['sesion_verificacion'] = time.time() - t0

    # -------------------------------------------------------------------------
    # 4. Filtro y Búsqueda Reactiva
    # -------------------------------------------------------------------------
    def aplicar_filtros_y_buscar(self):
        t0 = time.time()
        print("[FILTROS] Comprobando filtros de búsqueda...", flush=True)

        # 1. Asegurar que los filtros extendidos estén desplegados (s2id_filtro_cliente visible)
        try:
            s2_visible = self.driver.execute_script("""
                var s = document.getElementById('s2id_filtro_cliente');
                return s && s.offsetParent !== null;
            """)
            if not s2_visible:
                print("[FILTROS] Desplegando filtros avanzados ('Mostrar Filtros')...", flush=True)
                mostrar_link = self.driver.find_elements(By.ID, "mostrar")
                if mostrar_link:
                    self.driver.execute_script("arguments[0].click();", mostrar_link[0])
                    WebDriverWait(self.driver, 5, poll_frequency=0.2).until(
                        lambda d: d.execute_script("var s = document.getElementById('s2id_filtro_cliente'); return s && s.offsetParent !== null;")
                    )
        except Exception as e:
            print(f"⚠️ Aviso al desplegar filtros: {e}", flush=True)

        # 2. Comprobar si Integramédica ya está seleccionado
        cliente_ya_seleccionado = False
        try:
            chosen = self.driver.find_elements(By.CSS_SELECTOR, "div#s2id_filtro_cliente span.select2-chosen")
            if chosen and "integra" in chosen[0].text.strip().lower():
                cliente_ya_seleccionado = True
        except Exception:
            pass

        if not cliente_ya_seleccionado:
            print("[FILTROS] Aplicando Integramédica en filtro de cliente...", flush=True)
            # Intentar primero asignación directa ultra-rápida vía jQuery/Select2
            asignado_jquery = self.driver.execute_script("""
                try {
                    if (typeof jQuery !== 'undefined') {
                        var sel = jQuery('#filtro_cliente');
                        if (sel.length) {
                            sel.val('INT-000').trigger('change');
                            return true;
                        }
                    }
                } catch(e) {}
                return false;
            """)

            if not asignado_jquery:
                # Fallback: abrir UI de Select2
                opener = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div#s2id_filtro_cliente a.select2-choice")))
                self.driver.execute_script("arguments[0].click();", opener)

                search_input = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#select2-drop input.select2-input")))
                search_input.clear()
                search_input.send_keys("integramedica")

                opcion = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#select2-drop ul.select2-results li")))
                self.driver.execute_script("arguments[0].click();", opcion)
            
            print("✓ Integramédica seleccionado.", flush=True)
        else:
            print("⚡ Integramédica ya estaba seleccionado. Omitiendo selección redundante.", flush=True)

        # 3. Checkbox 'examen validado' (value='7')
        try:
            chk_activado = self.driver.execute_script("""
                var chk = document.querySelector("input[name='estados[]'][value='7']");
                if (chk) {
                    if (!chk.checked) {
                        chk.click();
                        return 'marcado';
                    }
                    return 'ya_marcado';
                }
                return 'no_encontrado';
            """)
            if chk_activado == 'marcado':
                print("✓ Checkbox 'examen validado' activado.", flush=True)
            elif chk_activado == 'ya_marcado':
                print("⚡ Checkbox 'examen validado' ya estaba marcado.", flush=True)
        except Exception as e:
            print(f"⚠️ Aviso en checkbox: {e}", flush=True)

        # 4. Clic en 'Buscar estudios' y espera reactiva de resultados
        print("[FILTROS] Disparando búsqueda de estudios...", flush=True)
        self.driver.execute_script("""
            var btn = document.getElementById('buscar');
            if (btn) btn.click();
        """)

        # Esperar reactivamente a que la tabla cargue (o aparezca mensaje 'Sin resultados')
        try:
            WebDriverWait(self.driver, 8, poll_frequency=0.2).until(
                lambda d: "sin resultados" in (d.execute_script("return document.body.innerText || '';")).lower() or
                          len(d.find_elements(By.CSS_SELECTOR, "table#turbogrid tbody tr, tbody tr")) > 0
            )
        except Exception:
            pass

        self.metrics['filtros_y_busqueda'] = time.time() - t0

    # -------------------------------------------------------------------------
    # 5. Conteo de Casos Pendientes (función idéntica a /casos)
    # -------------------------------------------------------------------------
    def contar_casos_pendientes(self) -> int:
        t0 = time.time()
        print("[CONTEO] Analizando cantidad de casos pendientes...", flush=True)
        total = 0

        body_text = self.driver.execute_script("return document.body.innerText || '';")
        if "sin resultados" in body_text.lower():
            total = 0
            print("ℹ️ La tabla indica: 'Sin resultados'.", flush=True)
        else:
            m = re.search(r'Total de registros\s*=\s*(\d+)', body_text, re.IGNORECASE)
            if m:
                total = int(m.group(1))
            else:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table#turbogrid tbody tr, tbody tr")
                valid_rows = [r for r in rows if "sin resultados" not in r.text.lower()]
                total = len(valid_rows)

        # Guardar en base de datos tal como /casos
        obs = "Conteo en vivo ejecución optimizada" if total > 0 else "Sin registros en tabla"
        self.guardar_casos_pendientes(total=total, cliente='integramedica', obs=obs)
        self.metrics['conteo_pendientes'] = time.time() - t0
        return total

    # -------------------------------------------------------------------------
    # 6. Extracción Unificada de Médico y Enlace en una Sola Pasada
    # -------------------------------------------------------------------------
    def extraer_medico_y_enlace(self) -> Optional[Dict[str, Any]]:
        t0 = time.time()
        print("[EXTRACCIÓN] Buscando último médico y enlace a examen en tabla...", flush=True)
        
        rows = self.driver.find_elements(By.CSS_SELECTOR, "table#turbogrid tbody tr")
        if not rows:
            rows = self.driver.find_elements(By.XPATH, "//tbody/tr")

        for row in reversed(rows):
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                txt = cells[1].text.strip() if len(cells) >= 2 else row.text.strip()
                if not txt:
                    continue

                m = re.search(r'(\d{6,})\s*/\s*([^/]+)', txt)
                if not m:
                    continue

                folio = m.group(1).strip()
                nombre_raw = m.group(2).strip().replace('\n', ' ').replace('\r', ' ')
                nombre_raw = re.sub(r'\s+', ' ', nombre_raw)

                for corte in ["Integram", "Clínica", "Clinica", "Hospital", "Centro", "Sanatorio"]:
                    mc = re.search(re.escape(corte), nombre_raw, re.IGNORECASE)
                    if mc:
                        nombre_raw = nombre_raw[:mc.start()].strip()

                nombre_medico = nombre_raw.rstrip('.')
                if len(nombre_medico) <= 2:
                    continue

                link_elem = None
                link_url = ""
                try:
                    link_elem = cells[1].find_element(By.TAG_NAME, "a")
                    link_url = link_elem.get_attribute("href") or ""
                except Exception:
                    pass

                print(f"✓ Médico detectado: '{nombre_medico}' (Folio: {folio})", flush=True)
                print(f"✓ Enlace asociado: {link_url}", flush=True)

                self.metrics['extraccion_medico_dom'] = time.time() - t0
                return {
                    "folio": folio,
                    "medico": nombre_medico,
                    "link_element": link_elem,
                    "link_url": link_url
                }
            except Exception:
                continue

        self.metrics['extraccion_medico_dom'] = time.time() - t0
        return None

    # -------------------------------------------------------------------------
    # 7. Similitud y Búsqueda de Credenciales en BD
    # -------------------------------------------------------------------------
    @staticmethod
    def normalizar_texto(t: str) -> str:
        if not t:
            return ""
        t = t.lower()
        t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
        t = re.sub(r'\b(?:dr|dra|md|radiologo|medico)\b\.?', '', t)
        t = re.sub(r'[^a-z0-9\s]', ' ', t)
        return re.sub(r'\s+', ' ', t).strip()

    def calcular_similitud(self, web_name: str, db_name: str) -> float:
        w = self.normalizar_texto(web_name)
        b = self.normalizar_texto(db_name)
        if not w or not b:
            return 0.0
        if w == b:
            return 1.0

        seq = SequenceMatcher(None, w, b).ratio()
        if HAS_FUZZ and fuzz:
            t_set = fuzz.token_set_ratio(w, b) / 100.0
            t_sort = fuzz.token_sort_ratio(w, b) / 100.0
            return (t_set * 0.60) + (t_sort * 0.25) + (seq * 0.15)
        else:
            tokens_w = set(w.split())
            tokens_b = set(b.split())
            overlap = len(tokens_w.intersection(tokens_b))
            token_ratio = overlap / max(len(tokens_b), 1)
            return (token_ratio * 0.70) + (seq * 0.30)

    def buscar_credenciales_doctor(self, nombre_medico: str) -> Optional[Dict[str, Any]]:
        t0 = time.time()
        conn = self.get_db()
        if not conn:
            return None
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT nombre_completo, usuario_integra, clave_integra FROM medicos WHERE (estado = 'Activo' OR estado IS NULL)")
            medicos = cursor.fetchall()
            cursor.close()
            conn.close()

            mejor_match = None
            mejor_score = 0.0
            for med in medicos:
                score = self.calcular_similitud(nombre_medico, med['nombre_completo'])
                if score > mejor_score:
                    mejor_score = score
                    mejor_match = med

            self.metrics['busqueda_credenciales_bd'] = time.time() - t0
            if mejor_score >= 0.40 and mejor_match:
                print(f"✓ Match BD: '{mejor_match['nombre_completo']}' ({mejor_score:.1%}) -> Usuario: {mejor_match['usuario_integra']}", flush=True)
                return {
                    "nombre": mejor_match['nombre_completo'],
                    "usuario": mejor_match['usuario_integra'],
                    "clave": mejor_match['clave_integra'],
                    "score": mejor_score
                }
            else:
                print(f"⚠️ No hubo coincidencia suficiente en BD para '{nombre_medico}' (Mejor: {mejor_score:.1%})", flush=True)
                return None
        except Exception as e:
            print(f"⚠️ Error buscando credenciales: {e}", flush=True)
            self.metrics['busqueda_credenciales_bd'] = time.time() - t0
            return None

    # -------------------------------------------------------------------------
    # 8. Descarga Rápida de PDF y Extracción Clínica
    # -------------------------------------------------------------------------
    def procesar_pdf(self, link_element, link_url: str) -> Optional[Dict[str, Any]]:
        t0 = time.time()
        print("[PDF] Iniciando apertura y descarga reactiva de informe...", flush=True)

        handles_antes = set(self.driver.window_handles)

        # Clic en el enlace vía JS para abrir pestaña sin scroll
        self.driver.execute_script("arguments[0].click();", link_element)

        # Espera reactiva de nueva pestaña (sin sleep fijo)
        nueva_pestana = None
        try:
            WebDriverWait(self.driver, 6, poll_frequency=0.1).until(
                lambda d: len(d.window_handles) > len(handles_antes)
            )
            nueva_pestana = (set(self.driver.window_handles) - handles_antes).pop()
        except Exception:
            pass

        pdf_url_real = link_url
        if nueva_pestana:
            self.driver.switch_to.window(nueva_pestana)
            try:
                WebDriverWait(self.driver, 4, poll_frequency=0.2).until(
                    lambda d: d.current_url and d.current_url != "about:blank"
                )
                pdf_url_real = self.driver.current_url
            except Exception:
                pass

        print(f"[PDF] URL resuelta: {pdf_url_real}", flush=True)

        session = requests.Session()
        for c in self.driver.get_cookies():
            session.cookies.set(c['name'], c['value'])
        headers = {
            "User-Agent": self.driver.execute_script("return navigator.userAgent;"),
            "Referer": "https://ris.chile.telemedicina.com/ris/atencion/lista"
        }

        pdf_bytes = None
        for intento in range(1, 3):
            try:
                resp = session.get(pdf_url_real, headers=headers, verify=False, timeout=(4, 15))
                if resp.status_code == 200 and resp.content.startswith(b'%PDF') and len(resp.content) > 100:
                    pdf_bytes = resp.content
                    print(f"✓ PDF descargado exitosamente vía HTTP ({len(pdf_bytes)} bytes).", flush=True)
                    break
            except Exception as e:
                print(f"⚠️ Intento {intento} de descarga: {e}", flush=True)
                time.sleep(0.5)

        # Cerrar la pestaña del PDF de inmediato y volver al RIS
        if nueva_pestana and len(self.driver.window_handles) > 1:
            try:
                self.driver.close()
                self.driver.switch_to.window(self.ris_handle)
                print("✓ Pestaña del PDF cerrada; foco retornado al RIS.", flush=True)
            except Exception:
                pass

        if not pdf_bytes:
            print("❌ No se pudo descargar el PDF.", flush=True)
            self.metrics['procesamiento_pdf'] = time.time() - t0
            return None

        extracted = self.extraer_texto_pdf(pdf_bytes)
        if extracted:
            extracted['url'] = pdf_url_real
        self.metrics['procesamiento_pdf'] = time.time() - t0
        return extracted

    def extraer_texto_pdf(self, pdf_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Extrae datos clínicos del PDF usando la lógica exacta y probada de procesar_pdf_doctor.py:
        - Limpieza exhaustiva de encabezados y metadatos (Tiempo Cero, Fecha Examen, Powered by TCPDF, etc.)
        - Corte estricto antes de la firma ('Atentamente')
        - Soporte para informes multi-página
        - Inserción de salto de página (\f) antes de 'Hallazgos:' para el procesador Word
        """
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            pages_text = [page.extract_text() or "" for page in reader.pages]

            if not pages_text:
                print("⚠️ El PDF no contiene texto extraíble.", flush=True)
                return None

            # ── Utilidad: cortar el texto de una página antes de la firma ──────
            def cortar_antes_firma(texto):
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
                    print(f"✓ Fecha Examen capturada: {fecha_agendada_sql}", flush=True)
                except Exception as e:
                    print(f"⚠️ Error al formatear fecha: {e}", flush=True)

            # 3. Cuerpo de página 1: desde "Número de ficha" (o "Integramédica" / "Edad" en formato /atencion/pdf)
            match_inicio = (
                re.search(r'N[uú]mero de ficha[^\n]*\n', pagina1, re.IGNORECASE)
                or re.search(r'Integram[eé]dica[^\n]*\n', pagina1, re.IGNORECASE)
                or re.search(r'Edad\s+\d+\s*a[ñn]os[^\n]*\n', pagina1, re.IGNORECASE)
            )
            if not match_inicio:
                print("⚠️ No se encontró 'Número de ficha' ni encabezado equivalente en página 1.", flush=True)
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
                texto_limpio = limpiar_meta(texto_limpio)
                continuaciones.append(cortar_antes_firma(texto_limpio))

            # ── Fusionar todas las partes del cuerpo ──────────────────────────────
            partes = [cuerpo_p1] + continuaciones
            diagnostico = "\n\n".join(p for p in partes if p)

            # Normalizar saltos de línea y espacios
            diagnostico = re.sub(r'\n{3,}', '\n\n', diagnostico)
            diagnostico = "\n".join(line.rstrip() for line in diagnostico.splitlines())

            # Insertar salto de página (\f) antes de "Hallazgos:" para el procesador Word
            diagnostico = re.sub(r'(?im)^(Hallazgos:)', r'\f\n\1', diagnostico)

            print(f"✓ Datos clínicos extraídos: Doc={doc_number} | Examen='{examen}'", flush=True)
            return {
                "numero_documento": doc_number,
                "diagnostico": diagnostico,
                "examen": examen,
                "fecha_agendada": fecha_agendada_sql
            }

        except Exception as e:
            print(f"⚠️ Error parseando texto de PDF: {e}", flush=True)
            return None

    # -------------------------------------------------------------------------
    # 9. Ejecución Completa
    # -------------------------------------------------------------------------
    def ejecutar(self):
        self.start_time = time.time()
        print("\n" + "="*70, flush=True)
        print("🚀 INICIANDO EXTRACCIÓN OPTIMIZADA DE RIS", flush=True)
        print(f"⏰ Hora de inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print("="*70 + "\n", flush=True)

        try:
            # 1. Conexión o inicio Chrome
            self.conectar_o_iniciar_chrome()

            # 2. Sesión activa / Login reactivo
            self.asegurar_sesion_activa()

            # 3. Aplicar filtros
            self.aplicar_filtros_y_buscar()

            # 4. Conteo de casos pendientes (/casos)
            total_pendientes = self.contar_casos_pendientes()

            # Mostrar mensaje con formato idéntico a Telegram
            print("\n" + "─"*50, flush=True)
            print("📊 CONTEO DE CASOS PENDIENTES (Tipo /casos Telegram):", flush=True)
            print("🏢 Cliente: integramedica", flush=True)
            print(f"📅 Fecha y Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", flush=True)
            print(f"🔢 Total de registros pendientes: {total_pendientes}", flush=True)
            print("─"*50 + "\n", flush=True)

            if total_pendientes == 0:
                print("ℹ️ No hay casos pendientes para procesar en este momento.", flush=True)
            else:
                # 5. Extraer médico y enlace al informe
                caso = self.extraer_medico_y_enlace()
                if not caso:
                    print("⚠️ No se identificaron filas con formato 'Folio / Médico' válido.", flush=True)
                else:
                    # 6. Buscar credenciales
                    cred = self.buscar_credenciales_doctor(caso['medico'])
                    usr = cred['usuario'] if cred else ""
                    pwd = cred['clave'] if cred else ""
                    doc_nombre = cred['nombre'] if cred else caso['medico']

                    # 7. Procesar PDF
                    datos_pdf = None
                    if caso['link_element']:
                        datos_pdf = self.procesar_pdf(caso['link_element'], caso['link_url'])

                    # 8. Actualizar registro en BD
                    if datos_pdf:
                        self.actualizar_registro_acciones(
                            doctor=doc_nombre,
                            usuario=usr,
                            clave=pwd,
                            doc_paciente=datos_pdf.get('numero_documento'),
                            diagnostico=datos_pdf.get('diagnostico'),
                            examen=datos_pdf.get('examen'),
                            url=datos_pdf.get('url'),
                            fecha_agendada=datos_pdf.get('fecha_agendada')
                        )
                    elif cred:
                        self.actualizar_registro_acciones(doctor=doc_nombre, usuario=usr, clave=pwd)

            total_elapsed = time.time() - self.start_time

            # 9. Reporte detallado de métricas y velocidad
            print("\n" + "="*70, flush=True)
            print("⏱️ RESUMEN DE TIEMPOS Y RENDIMIENTO OPTIMIZADO", flush=True)
            print("="*70, flush=True)
            for k, v in self.metrics.items():
                print(f"  • {k.replace('_', ' ').capitalize():<30}: {v:.2f} s", flush=True)
            print("─"*70, flush=True)
            print(f"  ⚡ TIEMPO TOTAL DEL FLUJO RIS        : {total_elapsed:.2f} s", flush=True)
            print("="*70 + "\n", flush=True)

        except Exception as e:
            print(f"\n❌ Error durante la ejecución optimizada: {e}", flush=True)
            import traceback
            traceback.print_exc()

def main():
    gestor = GestorRISOptimizado(port=9222)
    gestor.ejecutar()

if __name__ == "__main__":
    main()
