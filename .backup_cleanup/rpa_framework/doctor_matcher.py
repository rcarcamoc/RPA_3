#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Doctor Matcher Module - RPA_3 (Versión con Usuario Integra y Clave Integra)
Módulo de resolución y matching de nombres de médicos contra base de datos MySQL.

Características:
- Carga en memoria de médicos (fast lookup).
- Normalización de strings (tildes, mayúsculas, prefijos).
- Fuzzy matching con Levenshtein/Jaro-Winkler.
- Validación de coincidencias con umbrales configurables.
- **NUEVO: Retorna Usuario Integra y Clave Integra de cada médico encontrado**
- Logging integrado con RPA_3.

Autor: RPA_3 Doctor Resolver
Dependencias: mysql-connector-python, rapidfuzz (o difflib built-in)
Última actualización: 2025-12-19
"""

import mysql.connector
import re
import logging
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
from datetime import datetime

# Try to import rapidfuzz for better performance, fallback to difflib
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


class DoctorMatcher:
    """
    Clase para resolver y matchear nombres de médicos.
    
    Flujo:
    1. Conectarse a MySQL y cargar médicos en memoria.
    2. Normalizar OCR/texto entrada.
    3. Buscar coincidencia exacta o fuzzy.
    4. Retornar médico + score + credenciales Integra.
    """

    def __init__(self, 
                 db_host: str = "localhost",
                 db_user: str = "root",
                 db_password: str = "",
                 db_name: str = "rpa_db",
                 db_port: int = 3306,
                 logger: Optional[logging.Logger] = None):
        """
        Inicializa el matcher.
        
        Args:
            db_host: Host del servidor MySQL.
            db_user: Usuario MySQL.
            db_password: Contraseña MySQL.
            db_name: Nombre de la base de datos.
            db_port: Puerto MySQL.
            logger: Logger personalizado (opcional).
        """
        self.db_config = {
            'host': db_host,
            'user': db_user,
            'password': db_password,
            'database': db_name,
            'port': db_port
        }
        self.logger = logger or self._setup_logger()
        self.doctors_cache: Dict[str, Dict] = {}  # Caché en memoria
        self.connection = None
        self.is_connected = False

    def _setup_logger(self) -> logging.Logger:
        """Configura logger por defecto."""
        logger = logging.getLogger('DoctorMatcher')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - DoctorMatcher - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def connect(self) -> bool:
        """
        Conecta a la base de datos y carga médicos en caché.
        
        Returns:
            True si conecta exitosamente, False si falla.
        """
        try:
            self.connection = mysql.connector.connect(**self.db_config)
            self.is_connected = True
            self.logger.info(f"✓ Conectado a MySQL: {self.db_config['host']}:{self.db_config['port']}")
            
            # Cargar médicos en caché
            self._load_doctors_cache()
            return True
            
        except mysql.connector.Error as e:
            self.logger.error(f"✗ Error conectando a MySQL: {str(e)}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Cierra la conexión."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            self.is_connected = False
            self.logger.info("Desconectado de MySQL")

    def _load_doctors_cache(self):
        """Carga todos los médicos en caché en memoria (incluyendo Integra credentials)."""
        try:
            cursor = self.connection.cursor(dictionary=True)
            query = """
                SELECT id_medico, nombre_original, nombre_normalizado, 
                       especialidad, codigo, email, telefono,
                       usuario_integra, clave_integra
                FROM medicos
                WHERE activo = 1
                ORDER BY nombre_normalizado
            """
            cursor.execute(query)
            self.doctors_cache = {}
            
            for row in cursor.fetchall():
                normalized = row['nombre_normalizado']
                self.doctors_cache[normalized] = {
                    'id': row['id_medico'],
                    'nombre_original': row['nombre_original'],
                    'nombre_normalizado': normalized,
                    'especialidad': row['especialidad'],
                    'codigo': row['codigo'],
                    'email': row['email'],
                    'telefono': row['telefono'],
                    'usuario_integra': row.get('usuario_integra'),
                    'clave_integra': row.get('clave_integra')
                }
            
            cursor.close()
            self.logger.info(f"✓ {len(self.doctors_cache)} médicos cargados en caché")
            
        except mysql.connector.Error as e:
            self.logger.error(f"✗ Error cargando caché de médicos: {str(e)}")

    def normalize_name(self, name: str) -> str:
        """
        Normaliza un nombre de médico.
        
        - Minúsculas
        - Quita tildes (á→a, é→e, etc.)
        - Quita prefijos (Dr., Dra., Sr., Sra.)
        - Quita dobles espacios
        - Trim
        
        Args:
            name: Nombre a normalizar.
            
        Returns:
            Nombre normalizado.
        """
        if not name:
            return ""
        
        # Minúsculas
        normalized = name.lower().strip()
        
        # Quitar tildes
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ñ': 'n'
        }
        for accented, normal in replacements.items():
            normalized = normalized.replace(accented, normal)
        
        # Quitar prefijos comunes
        prefixes = [
            r'^dr\.\s+', r'^dra\.\s+',
            r'^sr\.\s+', r'^sra\.\s+',
            r'^prof\.\s+', r'^prof\s+'
        ]
        for prefix in prefixes:
            normalized = re.sub(prefix, '', normalized)
        
        # Dobles espacios → espacio simple
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized

    def _similarity_score(self, text1: str, text2: str) -> float:
        """
        Calcula similitud entre dos strings.
        
        Usa RapidFuzz si está disponible (más rápido), sino difflib.
        
        Args:
            text1: Primer string.
            text2: Segundo string.
            
        Returns:
            Score 0-100 (100 = coincidencia exacta).
        """
        if RAPIDFUZZ_AVAILABLE:
            # RapidFuzz es ~10x más rápido
            return fuzz.ratio(text1, text2)
        else:
            # Fallback a difflib
            return SequenceMatcher(None, text1, text2).ratio() * 100

    def match_doctor(self, 
                    ocr_text: str,
                    exact_threshold: float = 0.95,
                    fuzzy_threshold: float = 0.85) -> Tuple[Optional[Dict], float, str]:
        """
        Busca un médico por nombre (OCR u otro texto).
        
        Estrategia:
        1. Normalizar input.
        2. Buscar exacta en caché.
        3. Si no, buscar fuzzy contra todos los nombres.
        4. Retornar mejor coincidencia con score + credenciales Integra.
        
        Args:
            ocr_text: Texto OCR o nombre a resolver.
            exact_threshold: Umbral para coincidencia exacta (0-1). Default 0.95.
            fuzzy_threshold: Umbral para coincidencia fuzzy (0-1). Default 0.85.
            
        Returns:
            Tuple (doctor_dict, score, status_message)
            - doctor_dict: Dict con datos del médico (incluyendo usuario_integra y clave_integra) o None.
            - score: Similitud 0-100.
            - status_message: Mensaje descriptivo.
        """
        if not self.is_connected:
            return None, 0.0, "❌ Base de datos no conectada"
        
        if not ocr_text or not ocr_text.strip():
            return None, 0.0, "⚠️ Texto vacío"
        
        # Normalizar entrada
        normalized_input = self.normalize_name(ocr_text)
        
        if not normalized_input:
            return None, 0.0, "⚠️ Texto inválido después de normalización"
        
        # 1. Intentar búsqueda exacta primero (muy rápido)
        if normalized_input in self.doctors_cache:
            doctor = self.doctors_cache[normalized_input]
            return doctor, 100.0, f"✓ Coincidencia exacta: {doctor['nombre_original']}"
        
        # 2. Buscar fuzzy matching contra todos
        best_match = None
        best_score = 0.0
        
        for cached_name, doctor_data in self.doctors_cache.items():
            score = self._similarity_score(normalized_input, cached_name) / 100.0
            
            if score > best_score:
                best_score = score
                best_match = doctor_data
        
        # Evaluar si el score es aceptable
        if best_score >= exact_threshold:
            status = f"✓ Coincidencia muy probable: {best_match['nombre_original']} ({best_score*100:.1f}%)"
            return best_match, best_score * 100, status
        elif best_score >= fuzzy_threshold:
            status = f"⚠️ Coincidencia probable (revisar): {best_match['nombre_original']} ({best_score*100:.1f}%)"
            return best_match, best_score * 100, status
        else:
            status = f"❌ No se encontró coincidencia confiable. Mejor candidato: {best_match['nombre_original'] if best_match else 'N/A'} ({best_score*100:.1f}%)"
            return None, best_score * 100, status

    def get_all_doctors(self) -> List[Dict]:
        """Retorna lista de todos los médicos en caché (incluyendo credenciales Integra)."""
        return list(self.doctors_cache.values())

    def search_by_criteria(self, 
                          especialidad: Optional[str] = None,
                          codigo: Optional[str] = None,
                          usuario_integra: Optional[str] = None) -> List[Dict]:
        """
        Busca médicos por criterio (especialidad, código, usuario Integra, etc.).
        
        Args:
            especialidad: Especialidad a filtrar (substring).
            codigo: Código a filtrar (substring).
            usuario_integra: Usuario Integra a filtrar (substring).
            
        Returns:
            Lista de médicos que coinciden.
        """
        results = []
        
        for doctor in self.doctors_cache.values():
            match = True
            
            if especialidad and especialidad.lower() not in doctor['especialidad'].lower():
                match = False
            
            if codigo and codigo.lower() not in doctor['codigo'].lower():
                match = False
            
            if usuario_integra and usuario_integra.lower() not in (doctor.get('usuario_integra') or '').lower():
                match = False
            
            if match:
                results.append(doctor)
        
        return results

    def validate_and_update_cache(self) -> Tuple[bool, str]:
        """
        Recarga la caché desde la base de datos.
        Útil después de cambios en BD.
        
        Returns:
            Tuple (success, message).
        """
        try:
            if not self.is_connected:
                return False, "Base de datos no conectada"
            
            self._load_doctors_cache()
            return True, f"✓ Caché actualizada: {len(self.doctors_cache)} médicos"
            
        except Exception as e:
            return False, f"✗ Error actualizando caché: {str(e)}"


# ============================================================================
# FUNCIONES AUXILIARES PARA TESTING
# ============================================================================

def create_test_data(matcher: DoctorMatcher) -> bool:
    """
    Crea datos de prueba en la BD si no existen.
    
    Inserta 5 médicos de ejemplo para testing (datos de Integramedica).
    """
    try:
        cursor = matcher.connection.cursor()
        
        # Verificar si ya existen datos
        cursor.execute("SELECT COUNT(*) FROM medicos")
        count = cursor.fetchone()[0]
        
        if count > 0:
            matcher.logger.info(f"Base de datos ya contiene {count} médicos, saltando insert de prueba")
            return True
        
        # Datos de prueba (del archivo Integramedica)
        test_doctors = [
            ("Alejandra Zaninovic", "alejandra zaninovic", "Pediatría", "MED001", "alejandra@hospital.cl", "2-22223333", "azaninovicca", "alejandra"),
            ("Alexis Montilla", "alexis montilla", "Cardiología", "MED002", "alexis@hospital.cl", "2-22224444", "amontillava", "alexis"),
            ("Álvaro Trullenque", "alvaro trullenque", "Neurología", "MED003", "alvaro@hospital.cl", "2-22225555", "atrullenquesa", "alvaro"),
            ("Juan Errazuriz", "juan errazuriz", "Oftalmología", "MED004", "juan@hospital.cl", "2-22226666", "jerrazurizbu", "juan"),
            ("María Alejandra Loyola", "maria alejandra loyola", "Dermatología", "MED005", "maria@hospital.cl", "2-22227777", "mloyolamu", "maria"),
        ]
        
        for nombre_orig, nombre_norm, espec, cod, email, tel, user_integra, clave_integra in test_doctors:
            cursor.execute("""
                INSERT INTO medicos 
                (nombre_original, nombre_normalizado, especialidad, codigo, email, telefono, 
                 usuario_integra, clave_integra, activo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
            """, (nombre_orig, nombre_norm, espec, cod, email, tel, user_integra, clave_integra))
        
        matcher.connection.commit()
        matcher.logger.info(f"✓ {len(test_doctors)} médicos de prueba insertados (con credenciales Integra)")
        return True
        
    except Exception as e:
        matcher.logger.error(f"✗ Error creando datos de prueba: {str(e)}")
        return False


if __name__ == "__main__":
    # Testing local
    print("=" * 70)
    print("DOCTOR MATCHER - TEST LOCAL (CON INTEGRA CREDENTIALS)")
    print("=" * 70)
    
    matcher = DoctorMatcher(
        db_host="localhost",
        db_user="root",
        db_password="",
        db_name="rpa_db"
    )
    
    if matcher.connect():
        print("\n[TEST] Conexión exitosa ✓")
        
        # Crear datos de prueba si no existen
        create_test_data(matcher)
        
        # Test 1: Búsqueda exacta con credenciales
        print("\n[TEST 1] Búsqueda exacta (retorna Usuario Integra + Clave):")
        result, score, msg = matcher.match_doctor("Juan Errazuriz")
        print(f"  Input: 'Juan Errazuriz'")
        print(f"  {msg}")
        print(f"  Score: {score:.1f}%")
        if result:
            print(f"  ID: {result['id']}")
            print(f"  👤 Usuario Integra: {result['usuario_integra']}")
            print(f"  🔐 Clave Integra: {result['clave_integra']}")
        
        # Test 2: Búsqueda fuzzy
        print("\n[TEST 2] Búsqueda fuzzy (OCR imperfecto):")
        result, score, msg = matcher.match_doctor("Juan Errazuris")  # Error de tipeo
        print(f"  Input: 'Juan Errazuris' (con error)")
        print(f"  {msg}")
        print(f"  Score: {score:.1f}%")
        if result:
            print(f"  👤 Usuario Integra: {result['usuario_integra']}")
            print(f"  🔐 Clave Integra: {result['clave_integra']}")
        
        # Test 3: Búsqueda normalizando
        print("\n[TEST 3] Búsqueda con prefijo 'Dr.' (normalización):")
        result, score, msg = matcher.match_doctor("Dr. Alexis Montilla")
        print(f"  Input: 'Dr. Alexis Montilla'")
        print(f"  {msg}")
        if result:
            print(f"  👤 Usuario Integra: {result['usuario_integra']}")
            print(f"  🔐 Clave Integra: {result['clave_integra']}")
        
        # Test 4: Listar todos con credenciales
        print("\n[TEST 4] Listar médicos (con credenciales Integra):")
        all_doctors = matcher.get_all_doctors()
        for doc in all_doctors:
            print(f"  ✓ {doc['nombre_original']}")
            print(f"    └─ Usuario: {doc['usuario_integra']} | Clave: {doc['clave_integra']}")
        
        matcher.disconnect()
        print("\n✅ Tests completados exitosamente")
    else:
        print("✗ No se pudo conectar a la BD")
