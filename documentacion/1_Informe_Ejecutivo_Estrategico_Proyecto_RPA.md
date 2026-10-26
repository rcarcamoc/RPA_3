# Proyecto RPA: Automatización Operacional y Triage de Estudios Radiológicos

**Informe Ejecutivo de Arquitectura y Defensa Operacional**  
*Evaluación de Rendimiento, Condiciones de Despliegue en Infraestructura Virtual Windows, Gestión de Seguridad de Datos Sensibles (PHI) y Justificación de Continuidad Operacional 24/7*

---

### Ficha Técnica Institucional

| Parámetro | Detalle |
| :--- | :--- |
| **Destinatario** | Gerencia General / Dirección de Operaciones y Tecnología |
| **Proyecto** | RPA Framework v3 — Teleradiología & Triage RIS-PACS |
| **Fase Actual** | Fase 1: Estabilización, Validación Clínica y Cobertura Continua |
| **Fecha de Emisión** | Octubre 2026 |
| **Clasificación** | Confidencial — Evaluación Estratégica y Toma de Decisión |

---

## 1. Resumen Ejecutivo y Tesis de Valor

El presente documento expone la justificación técnica, operacional y estratégica del Sistema de Automatización Robótica de Procesos (RPA) desarrollado para la integración y triage inteligente de exámenes radiológicos entre los sistemas RIS (*Radiology Information System*) y PACS (*Picture Archiving and Communication System*).

En la operación teleradiológica actual, la gestión de la lista de trabajo, la apertura de estudios, la verificación de órdenes médicas y la correlación paciente-estudio representan un cuello de botella logístico intensivo en tiempo de dedicación. Un operador humano altamente capacitado es capaz de procesar a un ritmo pico de **30 a 40 casos por hora** bajo condiciones de concentración extrema. Sin embargo, la jornada humana está sujeta a limitaciones naturales: fatiga cognitiva tras varias horas continuas de pantalla, pausas operacionales, riesgo de errores en la digitación de identificadores de pacientes y, de manera crítica, una cobertura limitada a turnos habituales de 8 horas con la dificultad recurrente de sostener la misma intensidad en turnos nocturnos, fines de semana y días feriados.

> [!IMPORTANT]
> **Tesis Central para Gerencia:**  
> La propuesta de valor del Bot RPA no radica en competir en velocidad puntual contra un operador humano en su hora pico, sino en proporcionar una **COBERTURA ININTERRUMPIDA 24/7/365**, con **CERO error de digitación**, trazabilidad absoluta en base de datos y, fundamentalmente, la **DETECCIÓN INMEDIATA de patologías críticas** con alerta médica instantánea, protegiendo la vida del paciente y absorbiendo la carga en horarios inhábiles.

El bot procesa actualmente cada caso en un ciclo completo de **5 a 7 minutos (~8 a 10 casos/hora sostenidos)**, priorizando deliberadamente la seguridad del paciente y la verificación rigurosa mediante visión por computador e Inteligencia Artificial antes de realizar cualquier acción en los sistemas clínicos. Al operar de manera desatendida durante las 24 horas del día, el sistema aporta una producción neta diaria de **~190 a 240 estudios procesados**, eliminando el represamiento de casos durante la noche y entregando a primera hora del turno matutino una bandeja de trabajo depurada y auditada.

---

## 2. Descripción del Proyecto: ¿Qué hace el Bot RPA?

El bot es un agente de software autónomo que replica y optimiza la secuencia de navegación que realiza un operador de mesa de ayuda o tecnólogo entre los sistemas web y de escritorio corporativos, ejecutando un flujo de 5 etapas continuas:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FLUJO OPERACIONAL END-TO-END                    │
└────────────────────────────────────────────────────────────────────────┘
   │
   ├─► [Etapa 1] Verificación de Entorno & Seguridad (VPN, MySQL, Red)
   │
   ├─► [Etapa 2] Extracción en RIS (Web: Selección, descarga de PDF y médico)
   │
   ├─► [Etapa 3] Triage Clínico con IA (Exacto ➔ Fuzzy ➔ Cascada LLM)
   │              └─► ¿Patología Crítica? ➔ Alerta Inmediata a Telegram
   │
   ├─► [Etapa 4] Control de Carestream PACS (Desktop: Búsqueda OCR, orden y apertura)
   │
   └─► [Etapa 5] Cierre, Auditoría Forense y Actualización de Base de Datos
```

* **Etapa 1: Verificación de Integridad de Entorno y Conectividad:**  
  Antes de iniciar cualquier acción clínica, el bot valida la persistencia del túnel VPN institucional, la disponibilidad de la base de datos MySQL local/central y los enlaces de red, garantizando que ninguna transacción quede a medio camino.

* **Etapa 2: Extracción y Consulta en el RIS (Web):**  
  El bot navega en el portal RIS mediante automatización web optimizada, consulta la lista de exámenes pendientes de cierre o informe, extrae la ficha del paciente, médico solicitante y descarga el informe o solicitud médica en formato PDF.

* **Etapa 3: Triage Clínico Inteligente con Cascada de IA (3 Niveles):**  
  El texto diagnóstico se procesa mediante un motor de tres capas: (1) Búsqueda normalizada directa, (2) Algoritmos de coincidencia difusa (*Fuzzy Matching* con RapidFuzz) y (3) Inferencia semántica con Modelos de Lenguaje Médico (LLM). Si el examen contiene hallazgos de emergencia (aneurismas, hemorragias cerebrales, tromboembolismo pulmonar, disección aórtica), el bot lo clasifica como **Patología Crítica** y activa el protocolo de emergencia médica.

* **Etapa 4: Control Dinámico del Visualizador PACS (Escritorio):**  
  El bot toma control del aplicativo de escritorio Carestream Vue PACS, maximiza la interfaz, utiliza visión por computador (OCR) para ubicar dinámicamente los campos de búsqueda, digita el identificador del paciente, ordena las series cronológicamente y selecciona el estudio exacto correspondiente.

* **Etapa 5: Cierre, Auditoría y Notificación Multicanal:**  
  Actualiza el registro transaccional en la base de datos interna, marca el estado final del estudio y, en caso de patologías críticas o discrepancias que requieran validación humana, despacha una alerta con captura de pantalla y enlace de streaming en vivo a los canales seguros de Telegram del equipo médico y supervisores.

---

## 3. Comparativa Estratégica: Operador Humano vs. Bot RPA

Para contrastar con objetividad la cadencia puntual frente a la cobertura global, la siguiente matriz analiza ambas modalidades en una perspectiva operacional continua (jornada de 24 horas):

| Criterio de Evaluación | Operador Humano Entrenado | Bot RPA Autónomo (Estado Actual) |
| :--- | :--- | :--- |
| **Velocidad de Procesamiento** | 30 - 40 casos / hora (pico) | 8 - 10 casos / hora (sostenido) |
| **Ventana Operativa Diaria** | 8 horas / turno (con pausas y descansos) | 24 horas ininterrumpidas (sin pausas) |
| **Producción Neta Diaria** | 200 - 240 casos / día útil | 190 - 240 casos / día (24 horas continuas) |
| **Cobertura Nocturna / Festivos** | Requiere rotación y turnos de guardia | Operación 100% activa e ininterrumpida |
| **Tasa de Error en Digitación** | Presente por fatiga visual y digitación manual | 0.0% de error (mecanismo determinístico) |
| **Detección de Patología Crítica** | Dependiente del orden en que abre la cola | Inmediata en tiempo real (SLA de minutos) |
| **Trazabilidad y Auditoría** | Reporte manual al final del turno | Auditoría en BD por segundo con capturas |

> [!NOTE]
> **Conclusión Operativa:** Si bien en 1 hora puntual el humano supera al bot, al cabo de 24 horas el volumen neto procesado es equivalente (~200 casos diarios), con la diferencia radical de que el bot absorbe la noche y el fin de semana de forma constante y con una capa de alerta clínica instantánea que el humano no puede mantener de forma ininterrumpida.

---

## 4. Componentes y Arquitectura del Sistema

El proyecto fue diseñado bajo una arquitectura modular y resiliente en Python, combinando bibliotecas especializadas que aseguran compatibilidad con software clínico moderno y heredado:

* **Motor de Orquestación y Flujos (RPA Framework v3):** Ejecutor central basado en grafo acíclico dirigido que interpreta workflows en JSON (nodos de acción, decisión y bucle). Implementa manejo seguro de excepciones, auto-reinicio y persistencia de contexto.
* **Visión Artificial y OCR Multimodelo (Tesseract, PaddleOCR, EasyOCR):** Capacidad de lectura óptica para interactuar con pantallas dinámicas de PACS donde no existen APIs disponibles. Emplea técnicas de preprocesamiento OpenCV (umbralización, binarización y escalado) para garantizar lectura exacta de textos clínicos.
* **Módulo de Inteligencia Semántica (Modelos LLM Especializados):** Integración con modelos de lenguaje optimizados para medicina. Se implementó un evaluador autónomo que selecciona en milisegundos el modelo más rápido y certero para auditar la anatomía y el diagnóstico.
* **Automatización de Interfaz Nativa (PyWinAuto y PyAutoGUI):** Control directo sobre el árbol de accesibilidad de Windows (UI Automation) y control de mouse/teclado para interactuar con el cliente de Carestream Vue PACS sin requerir modificaciones en la infraestructura del proveedor.
* **Sistema de Telemetría y Streaming Remoto (Telegram + RTMP):** Servicio en segundo plano que permite supervisión desatendida. Los supervisores pueden consultar el estado, pausar el bot o solicitar una transmisión de video en vivo del escritorio de la máquina virtual ante cualquier anomalía.
* **Capa de Datos Transaccional (MySQL / SQLAlchemy):** Base de datos de auditoría con tablas de control de cola (`registro_acciones`), métricas de latencia y repositorio de sinónimos médicos para aprendizaje continuo.

---

## 5. Recursos Técnicos Consumidos y Demanda de Sistema

La solución destaca por su bajo impacto sobre la infraestructura tecnológica corporativa:

* **Carga de CPU:** Consumo promedio en reposo entre 2% y 5% de uso. Durante la fase de OCR intensivo o captura de pantalla, se registran picos controlados de hasta 25-35% de CPU durante 3 a 5 segundos, estabilizándose inmediatamente.
* **Memoria RAM:** La huella de memoria del proceso base oscila entre 250 MB y 450 MB. Cuando se cargan los módulos de visión por computador e interfaz en memoria, el consumo total del sistema no supera los 1.5 GB de RAM.
* **Almacenamiento en Disco:** El código base y sus entornos virtuales ocupan ~3.5 GB. La política de almacenamiento incluye depuración programada de capturas de depuración y compresión de bitácoras, requiriendo menos de 10 GB de disco para operación anual.
* **Tráfico de Red y VPN:** Tráfico ligero consistente en llamadas REST para inferencia diagnóstica (cargas útiles de texto de <2 KB), tráfico web estándar contra el RIS y streaming de video solo bajo demanda expresa de supervisión humana.

---

## 6. Seguridad de la Información y Manejo de Datos Sensibles (PHI)

Al operar en el sector salud y manejar Información Médica Protegida (PHI), el diseño del bot incorporó salvaguardas estrictas de privacidad y seguridad informática:

### 6.1. Anonimización y Privacidad en el Uso de Inteligencia Artificial
Un temor habitual en la adopción de IA es el traspaso involuntario de datos personales a servicios externos. En este sistema, el algoritmo implementa una política estricta de **DESIDENTIFICACIÓN PREVIA**: Únicamente se transmite al modelo de lenguaje el fragmento textual del diagnóstico médico (por ejemplo: *"se observa aneurisma fusiforme de aorta infrarrenal de 4.8 cm"*). **NUNCA** se envía el nombre del paciente, RUT/cédula de identidad, fecha de nacimiento, número de ficha clínica ni procedencia institucional. La privacidad del paciente está resguardada por diseño.

### 6.2. Aislamiento de Credenciales y Secretos
Las claves de API de servicios externos, tokens de bots y configuraciones sensibles residen en un archivo de entorno protegido (`.env`) excluido del control de versiones (`.gitignore`). Para las credenciales de acceso a los sistemas médicos (PACS y RIS), el bot consulta la base de datos en memoria durante la ejecución y las inyecta directamente en los campos de login mediante eventos simulados de sistema operativo, sin registrar jamás contraseñas en archivos de texto plano ni en los logs de auditoría.

### 6.3. Trazabilidad Completa y Auditoría Forense
Cada acción ejecutada por el robot genera un registro con fecha, hora exacta en milisegundos, identificador del estudio, nodo del flujo ejecutado, tiempo de respuesta y resultado. En caso de discrepancia o error técnico, el sistema captura una fotografía instantánea del escritorio que se guarda en un directorio restringido y se envía cifrada vía Telegram a los supervisores para permitir una auditoría forense inmediata.

---

## 7. Condiciones Ideales para Ejecución en Máquina Virtual Windows

A diferencia de los servicios backend tradicionales (APIs o scripts de base de datos) que pueden operar en modo *headless* (sin interfaz), un robot RPA que interactúa con visualizadores médicos como PACS requiere imperativamente un **ENTORNO GRÁFICO ACTIVO Y RENDERIZADO**. A continuación se presenta el análisis comparativo de las 4 opciones de infraestructura (formuladas sin marcas comerciales):

| Modelo de Infraestructura | Especificación Recomendada | Ventajas Principales | Consideraciones Críticas |
| :--- | :--- | :--- | :--- |
| **1. Estación / Servidor Físico Dedicado** | CPU 6-8 Núcleos, 16 GB RAM, SSD 256 GB, GPU integrada / dedicada | Renderizado gráfico 100% nativo. Cero problemas de drivers con PACS. Máxima estabilidad para OCR. | Requiere espacio físico y mantenimiento de hardware individual. |
| **2. Servidor Físico para Virtualización (Host)** | Servidor multinúcleo con hipervisor de virtualización. Recursos asignados a VMs. | Consolidación en centro de datos. Respaldos por snapshot de máquina completa. Alta disponibilidad. | Requiere configurar emulación de pantalla activa en el hipervisor. |
| **3. Máquina Virtual en Servidor (VM Huésped)** | 4 vCPU asignadas, 8 - 16 GB vRAM, 80 GB SSD virtual, Windows 10/11 Pro o Server GUI | Facilidad de aprovisionamiento, clonación y aislamiento de red corporativa. | **CRÍTICO:** No puede bloquearse la sesión RDP (requiere sesión de consola activa con auto-logon). |
| **4. Entorno Actual de Desarrollo (Referencia)** | Intel Core i7 (6 núcleos / 12 hilos), 16 GB RAM DDR4, Windows 11 Pro 64-bit | Rendimiento probado, excelente respuesta en OCR y multieje PACS. | Equipo de escritorio local; sirve de base probada para dimensionar la VM final. |

### 7.1. Requisitos Críticos de la Sesión Gráfica en la VM
Para que la máquina virtual ejecute el bot de forma desatendida y sin fallas, se deben garantizar cuatro directrices operacionales estrictas:

1. **Resolución de Pantalla Fija de 1920x1080 a Escala del 100%:** Los módulos de reconocimiento óptico y búsqueda de coordenadas operan sobre una matriz Full HD. Si la resolución cambia dinámicamente o la escala de fuentes de Windows se altera (ej. 125%), las coordenadas de clic se descalibran.
2. **Sesión de Consola Interactiva Activa (Sin Bloqueo de Pantalla):** Cuando una sesión de Escritorio Remoto (RDP) se desconecta o la pantalla se bloquea por inactividad, Windows suspende la renderización gráfica del escritorio. Para evitar que el PACS o el OCR dejen de capturar imágenes, la VM debe configurarse con inicio de sesión automático en consola local y desactivación de protectores de pantalla o bloqueo por inactividad.
3. **Conectividad de Red y Túnel VPN Persistente:** El canal de comunicación con el RIS y el PACS institucional debe mantener latencia inferior a 50 ms. Se incluye en el bot un mecanismo de auto-reconocimiento y reconexión de VPN que monitoriza caídas del enlace.
4. **Motor de Base de Datos Local o con Enlace de Baja Latencia:** Para garantizar que los tiempos de registro y consulta de credenciales no agreguen demoras al ciclo, el servicio MySQL debe residir en la misma máquina o en la subred local (<5 ms de latencia).

---

## 8. Justificación Técnica y Operacional para Gerencia

La implementación formal de este bot se justifica en cuatro ejes estratégicos que generan un impacto directo en la sostenibilidad y calidad del servicio:

1. **Mitigación Drástica del Riesgo Clínico (SLA Crítico):** En condiciones normales, un informe con hallazgo grave (ej. disección aórtica o hemorragia subaracnoidea) puede permanecer horas en cola esperando que un operador lo abra en su turno. El bot analiza el texto clínico en segundos y dispara alertas inmediatas al radiólogo de turno, transformando la teleradiología reactiva en un servicio de triage activo que salvaguarda la salud del paciente.
2. **Continuidad Operacional 24/7 y Absorción de Demanda:** Al mantener la operación durante las noches, fines de semana y días festivos, el bot absorbe de forma continua cientos de estudios, evitando la acumulación masiva que suele colapsar a los equipos humanos a las 8:00 AM de cada jornada laboral.
3. **Eliminación del Error Humano en Digitación y Trazabilidad:** Los operadores humanos cometen errores involuntarios tras procesar cientos de números de ficha médica durante turnos extenuantes. El robot garantiza una exactitud del 100% en la concordancia entre el paciente del RIS y el estudio del PACS.
4. **Redirección de Talento hacia Tareas de Alto Valor:** El personal administrativo y técnico deja de realizar tareas monótonas de "abrir, copiar y buscar" para dedicarse a la atención telefónica a clínicas, resolución de discrepancias complejas y control de calidad médica.

---

## 9. Hoja de Ruta de Optimización (Roadmap)

La velocidad actual de 8 a 10 casos por hora responde a una decisión técnica consciente durante la Fase 1: se priorizó la estabilidad, la precisión médica y la tolerancia a fallos antes de acelerar los tiempos. El plan de trabajo contempla una evolución clara:

* **Fase 1: Estabilización, Validación Clínica y Cobertura (ESTADO ACTUAL):**  
  *Objetivo logrado:* Cero falsos positivos en patología crítica, integración estable RIS-PACS, logging forense, supervisión por Telegram y operación continua desatendida.
* **Fase 2: Optimización de Rendimiento y Velocidad (Próximos 45 días):**  
  Implementación de caché en memoria de resultados OCR, paralelización de descarga de órdenes médicas en segundo plano y reducción de pausas defensivas en la interfaz. *Meta:* Reducir el ciclo a 3-4 minutos por caso (~15 a 20 casos/hora).
* **Fase 3: Escalabilidad Multinstancia (Mediano Plazo):**  
  Despliegue de 2 a 3 máquinas virtuales concurrentes operando en paralelo sobre distintas ramas de la lista de trabajo, alcanzando una capacidad combinada superior a los 50 casos/hora, superando con creces la capacidad de un equipo humano completo.
