-- ============================================================================
-- SCHEMA: Tabla de Médicos para Doctor Matcher (SOLO COLUMNAS DEL EXCEL)
-- Base de Datos: rpa_db
-- Versión: 2.1 (Simplificado - SOLO columnas del archivo Usuarios-Dres-Integramedica.xlsx)
-- ============================================================================

-- Crear base de datos si no existe
CREATE DATABASE IF NOT EXISTS rpa_db;
USE rpa_db;

-- ============================================================================
-- Tabla Principal: medicos (VERSIÓN 2.1 - SIMPLIFICADA)
-- Solo columnas que existen en el Excel
-- ============================================================================
CREATE TABLE IF NOT EXISTS medicos (
    id_medico INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID único del médico',
    nombre_original VARCHAR(255) NOT NULL COMMENT 'Nombre del médico (columna "Médico" del Excel)',
    nombre_normalizado VARCHAR(255) NOT NULL COMMENT 'Nombre normalizado (minúsculas, sin tildes)',
    usuario_integra VARCHAR(100) UNIQUE NOT NULL COMMENT 'Usuario para login Integra (columna "Usuario Integra" del Excel)',
    clave_integra VARCHAR(100) NOT NULL COMMENT 'Contraseña Integra (columna "Clave Integra" del Excel)',
    
    activo TINYINT(1) DEFAULT 1 COMMENT 'Médico activo (1=sí, 0=no)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Índices para búsqueda rápida
    KEY idx_nombre_normalizado (nombre_normalizado),
    KEY idx_usuario_integra (usuario_integra),
    KEY idx_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Registro maestro de médicos - SOLO columnas del Excel';

-- ============================================================================
-- Tabla Auxiliar: doctor_lookup_log
-- Registro de búsquedas (auditoría y estadísticas)
-- ============================================================================
CREATE TABLE IF NOT EXISTS doctor_lookup_log (
    id_log INT AUTO_INCREMENT PRIMARY KEY,
    texto_buscado VARCHAR(255) NOT NULL COMMENT 'Texto OCR/entrada',
    texto_normalizado VARCHAR(255) NOT NULL COMMENT 'Después de normalización',
    id_medico_encontrado INT COMMENT 'ID del médico encontrado',
    score_confianza DECIMAL(5,2) COMMENT 'Score de similitud (0-100)',
    tipo_busqueda ENUM('exacta', 'fuzzy', 'no_encontrada') COMMENT 'Tipo de búsqueda',
    usuario_integra_usado VARCHAR(100) COMMENT 'Usuario Integra retornado',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usuario VARCHAR(100) COMMENT 'Usuario que ejecutó búsqueda',
    
    KEY idx_timestamp (timestamp),
    KEY idx_id_medico (id_medico_encontrado),
    KEY idx_tipo_busqueda (tipo_busqueda),
    KEY idx_usuario_integra (usuario_integra_usado),
    FOREIGN KEY (id_medico_encontrado) REFERENCES medicos(id_medico) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Log de búsquedas para auditoría';

-- ============================================================================
-- SCRIPT DE MIGRACIÓN (Para tablas existentes)
-- Si ya tienes tabla medicos v2.0, ejecuta esto para simplificar
-- ============================================================================

/*
-- Opción 1: Borrar tabla anterior y usar esta (RECOMENDADO si es primera vez)
DROP TABLE IF EXISTS doctor_lookup_log;
DROP TABLE IF EXISTS medicos;
-- Luego ejecutar CREATE TABLE arriba

-- Opción 2: Si ya tienes datos v2.0 y quieres mantenerlos
-- (No se recomienda - mejor empezar limpio)
ALTER TABLE medicos 
DROP COLUMN IF EXISTS especialidad,
DROP COLUMN IF EXISTS codigo,
DROP COLUMN IF EXISTS email,
DROP COLUMN IF EXISTS telefono,
DROP COLUMN IF EXISTS consultorio,
DROP COLUMN IF EXISTS rut;
*/

-- ============================================================================
-- VISTAS ÚTILES
-- ============================================================================

-- Vista: Médicos activos con credenciales
CREATE OR REPLACE VIEW v_medicos_activos AS
SELECT 
    id_medico,
    nombre_original,
    nombre_normalizado,
    usuario_integra,
    clave_integra
FROM medicos
WHERE activo = 1
ORDER BY nombre_normalizado;

-- Vista: Estadísticas de búsquedas
CREATE OR REPLACE VIEW v_lookup_stats AS
SELECT 
    DATE(timestamp) as fecha,
    COUNT(*) as total_busquedas,
    SUM(CASE WHEN tipo_busqueda = 'exacta' THEN 1 ELSE 0 END) as exactas,
    SUM(CASE WHEN tipo_busqueda = 'fuzzy' THEN 1 ELSE 0 END) as fuzzy,
    SUM(CASE WHEN tipo_busqueda = 'no_encontrada' THEN 1 ELSE 0 END) as no_encontradas,
    AVG(score_confianza) as score_promedio,
    COUNT(DISTINCT usuario_integra_usado) as usuarios_unicos
FROM doctor_lookup_log
GROUP BY DATE(timestamp)
ORDER BY fecha DESC;

-- ============================================================================
-- PROCEDIMIENTO ALMACENADO: Buscar por Usuario Integra
-- ============================================================================

DELIMITER $$

CREATE PROCEDURE IF NOT EXISTS sp_buscar_por_usuario_integra(
    IN p_usuario_integra VARCHAR(100)
)
BEGIN
    SELECT 
        id_medico,
        nombre_original,
        usuario_integra,
        clave_integra
    FROM medicos
    WHERE usuario_integra = p_usuario_integra
    AND activo = 1
    LIMIT 1;
END$$

DELIMITER ;

-- ============================================================================
-- ÍNDICES ADICIONALES
-- ============================================================================

-- Índice de texto completo para búsquedas avanzadas
ALTER TABLE medicos ADD FULLTEXT INDEX ft_nombre (nombre_original, nombre_normalizado);

-- Índice compuesto para búsquedas frecuentes
CREATE INDEX idx_activo_nombre ON medicos(activo, nombre_normalizado);
CREATE INDEX idx_usuario_integra_activo ON medicos(usuario_integra, activo);
