# -*- coding: utf-8 -*-
"""
db_and_synonyms_mixin.py — Operaciones de base de datos MySQL (ris.registro_acciones,
ris.sinonimos y ris.log_llm_ranking) para BusquedaTextOnly.
Extraído de busqueda_triple_text_only.py.
"""

import logging
from utils.llm_config import log_llm_result

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)


class TripleSearchDBMixin:
    """Mixin con operaciones de BD y diccionario de sinónimos clínicos para BusquedaTextOnly."""

    def update_db_error(self, error_message):
        """Actualiza el estado a Error en la base de datos."""
        if not HAS_MYSQL:
            logger.error("No hay driver de MySQL para actualizar error.")
            return

        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            
            query = """
            UPDATE ris.registro_acciones
            SET estado = 'Error'
            WHERE estado = 'En Proceso'
            LIMIT 1;
            """
            cursor.execute(query)
            conn.commit()
            conn.close()
            logger.info(f"Estado actualizado a 'Error' en BBDD: {error_message}")
        except Exception as e:
            logger.error(f"Error actualizando BBDD con error: {e}")

    def update_db_coordinate(self, coordinate_str):
        """Actualiza el campo coordenada en la base de datos."""
        if not HAS_MYSQL:
            logger.error("No hay driver de MySQL para actualizar coordenada.")
            return

        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            
            query = """
            UPDATE ris.registro_acciones
            SET coordenada = %s
            WHERE estado = 'En Proceso'
            LIMIT 1;
            """
            cursor.execute(query, (coordinate_str,))
            conn.commit()
            conn.close()
            logger.info(f"Coordenada '{coordinate_str}' actualizada en BBDD.")
        except Exception as e:
            logger.error(f"Error actualizando BBDD con coordenada: {e}")

    def buscar_sinonimo(self, examen: str, ocr_text: str) -> str:
        """
        Busca en ris.sinonimos si existe alguna coincidencia para este examen/OCR.
        Protegido contra subcadenas cortas: no utiliza INSTR si el término tiene menos de 8 caracteres.
        """
        if not HAS_MYSQL or not examen:
            return ''
        try:
            conn = mysql.connector.connect(
                host='localhost', user='root', password='', database='ris'
            )
            cursor = conn.cursor()
            # 1. Coincidencia exacta directa (máxima prioridad)
            cursor.execute("""
                SELECT Sugerencia FROM ris.sinonimos
                WHERE examen = %s OR Sugerencia = %s
                LIMIT 1
            """, (examen, examen))
            row = cursor.fetchone()
            if row and row[0]:
                conn.close()
                logger.info(f"✅ Sinónimo exacto encontrado en BD: '{row[0]}' para examen='{examen}'")
                return row[0]

            # 2. Coincidencia en OCR solo si ocr_text tiene al menos 8 caracteres
            if ocr_text and len(ocr_text.strip()) >= 8:
                cursor.execute("""
                    SELECT Sugerencia FROM ris.sinonimos
                    WHERE OCR != '' AND LENGTH(OCR) >= 8 AND INSTR(%s, OCR) > 0
                    LIMIT 1
                """, (ocr_text,))
                row = cursor.fetchone()
                if row and row[0]:
                    conn.close()
                    logger.info(f"✅ Sinónimo por OCR encontrado en BD: '{row[0]}'")
                    return row[0]

            conn.close()
            return ''
        except Exception as e:
            logger.warning(f"No se pudo consultar ris.sinonimos: {e}")
            return ''

    def guardar_sinonimo(self, examen: str, ocr_text: str, sugerencia: str, confianza: float = 1.0) -> None:
        """
        Guarda un nuevo registro en ris.sinonimos bajo estrictas reglas de admisión:
        1. Longitud mínima de OCR >= 12 caracteres (no abreviaturas breves como 'ECO').
        2. No guardar si confianza < 0.90.
        3. No guardar si falta examen o sugerencia.
        """
        if not HAS_MYSQL or not sugerencia or not ocr_text:
            return
        clean_ocr = ocr_text.strip()
        if len(clean_ocr) < 12:
            logger.warning(f"🛡️ [GUARDAR SINÓNIMO] Rechazado por longitud insuficiente ({len(clean_ocr)} < 12): '{clean_ocr}'")
            return
        if confianza < 0.90:
            logger.warning(f"🛡️ [GUARDAR SINÓNIMO] Rechazado por confianza insuficiente ({confianza:.2f} < 0.90)")
            return

        try:
            conn = mysql.connector.connect(
                host='localhost', user='root', password='', database='ris'
            )
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM ris.sinonimos WHERE examen = %s AND Sugerencia = %s LIMIT 1", (examen[:100], sugerencia[:100]))
            if cursor.fetchone():
                conn.close()
                return

            cursor.execute("""
                INSERT INTO ris.sinonimos (examen, OCR, Sugerencia)
                VALUES (%s, %s, %s)
            """, (examen[:100], clean_ocr[:100], sugerencia[:100]))
            conn.commit()
            conn.close()
            logger.info(f"💾 Sinónimo guardado de forma segura: examen='{examen}' | OCR='{clean_ocr}' | Sugerencia='{sugerencia}'")
        except Exception as e:
            logger.error(f"Error guardando sinónimo en BD: {e}")

    def log_llm_ranking(self, id_registro, modelo, target_buscado, texto_ocr, es_match, razonamiento, confianza, tiempo_ms, es_primer_intento=True):
        """Delega en la función centralizada log_llm_result de llm_config."""
        log_llm_result(
            modelo=modelo,
            es_match=es_match,
            confianza=confianza,
            tiempo_ms=tiempo_ms,
            razonamiento=razonamiento,
            target_buscado=target_buscado,
            texto_ocr=texto_ocr,
            id_registro=id_registro,
            es_primer_intento=es_primer_intento,
            contexto='busqueda_ocr',
        )
        logger.info(f"📊 Ranking log: {modelo} | Match={es_match} | {tiempo_ms}ms | primer={es_primer_intento}")

    def get_db_targets(self):
        """Obtiene ID, diagnóstico y fecha desde la base de datos."""
        if not HAS_MYSQL:
            logger.error("No hay driver de MySQL instalado.")
            return None, None, None

        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            
            query = """
            SELECT id, SUBSTRING_INDEX(diagnostico, '\n', 1) AS examen, date(fecha_agendada) as fecha
            FROM ris.registro_acciones
            WHERE estado = 'En Proceso'
            LIMIT 1;
            """
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()

            if result:
                id_registro = result[0]
                examen = result[1]
                fecha = result[2]
                logger.info(f"Target DB [ID:{id_registro}] - Diagnóstico: '{examen}', Fecha: '{fecha}'")
                return id_registro, examen, fecha
            else:
                logger.warning("No se encontraron registros 'En Proceso' en la BBDD.")
                return None, None, None
        except Exception as e:
            logger.error(f"Error consultando BBDD: {e}")
            return None, None, None
