# FICHA TÉCNICA: REQUERIMIENTOS, ARQUITECTURA Y PUESTA A PUNTO RPA

**Automatización Operacional & Triage RIS-PACS | RPA Framework v3 | Confidencial**  
*Versión 2.0 (Actualizada con Guía de Instalación y Aprovisionamiento para Infraestructura / TI)*

---

## 1. Propósito y Modelo Operacional

El bot es un agente desatendido desarrollado en Python para ejecutar de forma autónoma el ciclo de correlación y apertura de estudios entre el portal web RIS y la aplicación de escritorio Carestream Vue PACS, integrando un clasificador clínico con Inteligencia Artificial (Exacto ➔ Fuzzy ➔ Cascada LLM) para detección temprana de patologías críticas.

| Modalidad | Ritmo Operativo | Ventana Diaria | Aporte Principal |
| :--- | :--- | :--- | :--- |
| **Operador Humano** | 30-40 casos/h (pico) | 8 h / turno (~220 casos) | Flexibilidad cognitiva; afectado por fatiga, pausas y rotación de turnos. |
| **Bot RPA (Fase 1)** | 8-10 casos/h (sostenido) | 24 h continuas (~220 casos) | Cero error de digitación; cobertura nocturna/festiva y alerta crítica inmediata. |

---

## 2. Requerimientos Técnicos Mínimos de Infraestructura

> [!IMPORTANT]
> **CRÍTICO:** Al requerir visión artificial (OCR) sobre Carestream PACS, el sistema necesita renderizado de interfaz activo. No puede operar como servicio *headless* tradicional sin pantalla interactiva.

| Componente | Especificación Mínima Requerida | Justificación Técnica |
| :--- | :--- | :--- |
| **Sistema Operativo** | Windows 10 / 11 Pro (64-bit) o Windows Server con GUI | Soporte nativo para cliente Carestream PACS, PyWinAuto y UI Automation. |
| **CPU / Procesador** | 4 vCPU (consumo base 5%, picos de 35%) | Procesamiento OCR local (Tesseract / OpenCV) y validación visual. |
| **Memoria RAM** | 8 GB RAM (16 GB recomendado) | 1.5 GB huella del bot + consumo de Carestream PACS y navegador Chrome. |
| **Almacenamiento** | 80 GB SSD (disponible >15 GB) | Sistema base, dependencias Python y rotación anual de capturas/logs. |
| **Resolución de Pantalla** | **1920 × 1080 a 100% de escala (DPI) (Fija)** | **Mandatorio:** Coordenadas de interfaz y OCR calibradas para Full HD. |
| **Sesión de Consola** | Sesión interactiva activa 24/7 sin bloqueo | Sin suspensión ni salvapantallas; *Autologon* configurado. |

---

## 3. Conectividad, Aplicaciones y Accesos

* **Túnel VPN Corporativo:** Conexión estable hacia la intranet de RIS/PACS con latencia recomendada <50 ms. Incluye script de auto-reconexión y monitoreo continuo.
* **Base de Datos MySQL:** Instancia local o en red de bajísima latencia (<5 ms) con esquema `ris` para control de cola, trazabilidad y banco de sinónimos.
* **Salida HTTPS (Puerto 443):** Habilitada hacia endpoints de IA médica en la nube (Cloud LLM) y hacia la API de Telegram (`api.telegram.org`) para despacho de incidentes.
* **Cuentas de Acceso:** 1 usuario activo en portal web RIS (descarga de PDF) y 1 usuario con licencia activa en cliente de escritorio PACS.

---

## 4. Seguridad de la Información y Cumplimiento Normativo

* **Minimización de Datos (Leyes 19.628 / 20.584 / 21.719):** Solo se envían a la IA fragmentos de texto diagnóstico (ej. *"aneurisma disecante"*). Nunca se transmiten nombres, RUT ni fichas clínicas completas.
* **Aislamiento de Secretos:** Credenciales de RIS, PACS y tokens residen fuera del código fuente en variables de entorno seguras (`.env`).
* **Auditoría y Supervisión:** Registro detallado por estudio en MySQL. Discrepancias generan captura de pantalla remitida vía Telegram.

---

## 5. Gestión de Riesgos y Hoja de Ruta (Roadmap)

| Riesgo Identificado | Impacto Operacional | Mecanismo de Mitigación |
| :--- | :--- | :--- |
| **Bloqueo de pantalla por GPO** | Detención inmediata del OCR visual | Exclusión de directiva GPO en VM; configuración de sesión interactiva. |
| **Actualización GUI PACS/RIS** | Descalibración de clics y selectores | Monitoreo de incidentes con alerta Telegram y ajuste modular de selectores. |
| **Ambigüedad en texto clínico** | Clasificación clínica no concluyente | Verificación en 3 capas (Exacto/Fuzzy/LLM) y derivación inmediata a médico. |

* **Fases:** [Fase 1 Actual] Estabilización, validación clínica y cobertura 24/7 (8-10 casos/h) ➔ [Fase 2] Optimización de pausas y OCR a 15-20 casos/h ➔ [Fase 3] Escalado multinstancia (2-3 VMs: 45-60 casos/h).

---

## 6. Preparación y Puesta a Punto de la Máquina (Guía de Instalación para TI)

Para dejar la máquina (física o virtual) completamente instalada y lista para producción, el área de Infraestructura / TI debe ejecutar las siguientes acciones organizadas en 5 pasos correlativos:

```
┌────────────────────────────────────────────────────────────────────────┐
│             CHECKLIST DE PREPARACIÓN DE MÁQUINA (TI / OPS)             │
└────────────────────────────────────────────────────────────────────────┘
  [Paso 1] Windows & Pantalla ──► 1920x1080 @ 100% escala + Sin bloqueo/GPO
  [Paso 2] Runtime Base       ──► Python 64-bit + Visual C++ + Tesseract OCR
  [Paso 3] Software Clínico   ──► Carestream PACS (mp.exe) + Chrome + VPN activa
  [Paso 4] Datos & Código     ──► MySQL (schema 'ris') + Carpeta C:\Desarrollo\RPA_3
  [Paso 5] Arranque Autónomo  ──► Autologon en Windows + Tarea Programada de inicio
```

### Paso 1: Configuración del Sistema Operativo y Entorno Gráfico (Mandatorio)
1. **Resolución y Escala de Fuentes:**
   * Configurar resolución fija en **1920 × 1080** píxeles.
   * Escala de texto y aplicaciones fijada estrictamente en **100%** (sin ampliación del 125% o 150%).
2. **Desactivar Bloqueo de Pantalla y Suspensión:**
   * En Panel de Control ➔ Opciones de Energía:
     * Apagar pantalla: **Nunca**.
     * Estado de suspensión: **Nunca**.
   * Protector de pantalla (*Screensaver*): **Ninguno** (desactivado).
   * **Exclusión de Directivas de Dominio (GPO):** Excluir la cuenta de servicio o la máquina de directivas corporativas de bloqueo automático por inactividad (*Interactive logon: Machine inactivity limit*).
3. **Inicio de Sesión Automático (*Autologon*):**
   * Configurar inicio de sesión automático mediante la herramienta oficial *Sysinternals Autologon* de Microsoft (o vía Registro en `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon`), de manera que el sistema inicie sesión en el escritorio interactivo inmediatamente tras cualquier reinicio o corte de energía.

---

### Paso 2: Instalación de Componentes Base y Runtimes
1. **Python 64-bit (Versión 3.11, 3.12 o 3.13):**
   * Descargar el instalador oficial de 64 bits.
   * Marcar la casilla **"Add python.exe to PATH"** durante la instalación.
2. **Microsoft Visual C++ Redistributable (x64):**
   * Instalar el paquete *Visual C++ 2015–2022 Redistributable (x64)* (indispensable para librerías de visión artificial como OpenCV, PyWinAuto y PaddleOCR).
3. **Tesseract OCR (Windows x64):**
   * Instalar el binario oficial de Tesseract en `C:\Program Files\Tesseract-OCR`.
   * Incluir durante la instalación el paquete de idioma español (`spa.traineddata`).
   * Añadir `C:\Program Files\Tesseract-OCR` a la variable de entorno `PATH` del sistema.

---

### Paso 3: Aplicativos Clínicos y Accesos de Red
1. **Google Chrome:**
   * Instalar navegador Chrome actualizado (utilizado por el módulo de extracción web del RIS).
2. **Cliente Carestream Vue PACS:**
   * Instalar aplicativo de escritorio de PACS (`mp.exe`).
   * Verificar conectividad a los servidores DICOM / PACS institucionales.
   * Validar inicio de sesión correcto con credenciales habilitadas.
3. **Cliente VPN Corporativo:**
   * Configurar software de VPN (ej. FortiClient, Cisco AnyConnect o VPN nativa) con credenciales persistentes y auto-conexión al iniciar sesión.
   * Comprobar ping y latencia (<50 ms) hacia los servidores de RIS y PACS.
4. **Reglas de Firewall / Proxy:**
   * Permitir tráfico de salida en puerto **443 (HTTPS)** hacia:
     * `api.telegram.org` (alertas a supervisores y streaming).
     * Endpoints de inferencia LLM en la nube (`openrouter.ai`, `nvidia.com`).
   * Puerto **3306** hacia el servidor de base de datos MySQL (si es remoto).

---

### Paso 4: Base de Datos y Despliegue del Proyecto
1. **Servidor MySQL:**
   * Contar con MySQL Server 8.0/9.0 activo (local o en red de <5 ms de latencia).
   * Crear la base de datos `ris` con codificación `utf8mb4`:
     ```sql
     CREATE DATABASE IF NOT EXISTS ris CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
     ```
2. **Estructura del Proyecto en Disco:**
   * Clonar o copiar el repositorio en la ruta estándar: `C:\Desarrollo\RPA_3`.
3. **Entorno Virtual de Python:**
   * Abrir una consola PowerShell o CMD como administrador y ejecutar:
     ```cmd
     cd C:\Desarrollo\RPA_3
     python -m venv venv
     .\venv\Scripts\pip install --upgrade pip
     .\venv\Scripts\pip install -r requirements.txt
     ```
4. **Archivo de Configuración de Entorno (`.env`):**
   * Crear el archivo `C:\Desarrollo\RPA_3\.env` a partir de `.env.example` y completar los tokens:
     ```env
     TELEGRAM_BOT_TOKEN=tu_token_aqui
     OPENROUTER_API_KEY=tu_api_key_aqui
     TELEGRAM_API_ID=tu_api_id
     TELEGRAM_API_HASH=tu_api_hash
     ```

---

### Paso 5: Automatización de Inicio y Resiliencia
1. **Creación de la Tarea Programada de Windows:**
   * Hacer clic derecho y seleccionar **"Ejecutar como Administrador"** sobre el archivo:  
     `C:\Desarrollo\RPA_3\Crear_Tarea_Programada.bat`
   * Este script registra la tarea `RPA_Servicio_Notificaciones_Telegram`, que asegura:
     * Inicio automático al arrancar Windows (*At Startup / At Logon*).
     * Reintentos automáticos en caso de cierre accidental (3 reintentos en intervalos de 1 minuto).
     * Política de instancia única (*IgnoreNew*) para evitar procesos duplicados.
2. **Prueba de Humo (Validación Final):**
   * Reiniciar la máquina virtual.
   * Verificar que Windows inicie sesión solo en el escritorio sin solicitar contraseña.
   * Comprobar que la ventana del servicio RPA se abra automáticamente y envíe el mensaje de inicialización al canal de Telegram.

---

### Checklist Rápido de Entrega (Para el Técnico de TI)

| # | Tarea de Verificación | Estado |
| :---: | :--- | :---: |
| 1 | Resolución 1920×1080 fijada y escala en 100% | [ ] |
| 2 | Opciones de energía en "Nunca apagar" / Protector de pantalla desactivado | [ ] |
| 3 | Autologon configurado (inicia sesión directo al reiniciar) | [ ] |
| 4 | Python 64-bit instalado con PATH habilitado | [ ] |
| 5 | Visual C++ Redistributable (x64) instalado | [ ] |
| 6 | Tesseract OCR instalado con paquete `spa` en PATH | [ ] |
| 7 | Carestream PACS y Chrome instalados y probados | [ ] |
| 8 | VPN corporativa conectada y con auto-conexión | [ ] |
| 9 | MySQL con base de datos `ris` accesible | [ ] |
| 10 | Entorno virtual `venv` creado con `pip install -r requirements.txt` | [ ] |
| 11 | Archivo `.env` configurado con credenciales y tokens | [ ] |
| 12 | Tarea programada registrada con `Crear_Tarea_Programada.bat` | [ ] |
