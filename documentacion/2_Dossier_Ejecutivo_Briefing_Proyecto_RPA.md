# Dossier Ejecutivo | Proyecto RPA: Triage Radiológico 24/7

**Documento de Decisión Gerencial (Briefing Estratégico)**  
*Justificación de Rendimiento 24/7, Mitigación de Riesgo Clínico y Requisitos de Infraestructura Virtual*

---

### Resumen Ejecutivo de Decisión

| Dimensión | Resumen para Directorio |
| :--- | :--- |
| **Desafío Operacional** | Volumen creciente de exámenes entre RIS y PACS, alta carga de turnos nocturnos y riesgo de demoras en la detección de patologías clínicas graves. |
| **Solución RPA Implementada** | Robot autónomo 24/7 que extrae estudios del RIS, analiza diagnósticos con IA (3 niveles) para alertas críticas y gestiona la apertura en el PACS. |
| **Eje de Valor Operacional** | No busca superar al humano en velocidad punta (30-40 casos/h en pico diurno), sino aportar 24 horas continuas (~200 casos/día) con estabilidad y sin pausas. |
| **Solicitud a Gerencia** | Habilitación formal de una Máquina Virtual Windows con sesión gráfica activa para paso a producción en horario continuo. |

---

## 1. El Factor Eficiencia: Humano en Pico vs. Robot en Cobertura 24/7

Un operador entrenado alcanza una cadencia de 30 a 40 casos por hora bajo máxima concentración. No obstante, esa velocidad solo es sostenible durante lapsos acotados y en horario hábil. La siguiente tabla demuestra por qué el bot representa una ventaja neta en el balance global de la operación:

| Métrica Operacional | Operador Humano | Bot RPA (Actual) | Bot RPA (Fase 2) |
| :--- | :--- | :--- | :--- |
| **Velocidad Puntual** | 30 - 40 casos / hora | 8 - 10 casos / hora | 15 - 20 casos / hora |
| **Horas Activas al Día** | 8 horas (1 turno laboral) | 24 horas continuas | 24 horas continuas |
| **Producción Diaria Total** | ~200 - 240 casos / día | ~190 - 240 casos / día | ~360 - 450 casos / día |
| **Cobertura Nocturna / Feriados** | Dependiente de turnos de guardia | 100% activa e ininterrumpida | 100% activa e ininterrumpida |
| **Alerta Patología Crítica** | Manual según orden en cola | Inmediata (<2 min) | Inmediata (<2 min) |

> [!TIP]
> **Impacto Directo:** El robot absorbe el flujo continuo nocturno y de fines de semana. Evita que el turno de la mañana inicie con una cola desbordada de estudios y asegura que los pacientes graves sean identificados en minutos, no en horas.

---

## 2. Infraestructura: Opciones y Condiciones Ideales en Máquina Virtual

Para ejecutar la automatización desatendida, se contrastaron las opciones de hardware e infraestructura de forma *vendor-agnostic*:

| Opción de Infraestructura | Especificación Clave | Diagnóstico Operacional |
| :--- | :--- | :--- |
| **A. Servidor Físico Dedicado** | CPU 6-8 cores, 16 GB RAM, SSD, GPU | Excelente renderizado gráfico nativo. Requiere equipo físico en rack. |
| **B. Servidor de Virtualización (Host)** | Plataforma de hipervisor en datacenter | Óptima gobernanza, backups automáticos y monitoreo centralizado. |
| **C. Máquina Virtual en Servidor (VM)** | 4 vCPU, 8-16 GB vRAM, Win 10/11 Pro GUI | **RECOMENDADA:** Balance ideal entre aislamiento y facilidad de despliegue. |
| **D. Entorno Actual (Desarrollo)** | Intel i7, 16 GB RAM, Win 11 Pro 64-bit | Demostró alta fluidez; sirve de estándar para dimensionar la VM final. |

> [!WARNING]
> **Condición Técnica Indispensable:** La Máquina Virtual Windows debe mantener una **SESIÓN DE CONSOLA ACTIVA** (resolución fija de 1920x1080 al 100% de escala) sin bloqueo de pantalla ni suspensión por inactividad, ya que los motores de OCR y el visor PACS dependen de la renderización gráfica activa del sistema operativo.

---

## 3. Seguridad, Credenciales y Privacidad del Paciente (PHI)

* **Desidentificación en IA (Cumplimiento Estricto):** Al consultar modelos de lenguaje para clasificar diagnósticos, **NUNCA** se transmiten datos personales (nombre, RUT, fecha de nacimiento o ficha médica). Solo se remite el texto clínico estricto (ej. *"sospecha de TEP masivo"*), garantizando pleno apego a la legislación de protección de datos de salud.
* **Gestión Segura de Accesos:** Las claves de API y accesos residen en variables de entorno cifradas (`.env`). Las credenciales de usuarios médicos en PACS/RIS se inyectan en memoria sin quedar expuestas en logs.
* **Trazabilidad Forense:** Cada acción queda sellada con marca de tiempo en la base de datos MySQL, permitiendo auditorías de calidad en cualquier momento.

---

## 4. Impacto en la Operación y Próximos Pasos para Gerencia

* **Absorción de Demanda:** Permite procesar de manera regular y desatendida **~6.000 casos mensuales** sin pausas, manteniendo la cola de trabajo al día.
* **Alerta Médica Temprana:** Proporciona un SLA de detección y notificación de patología crítica **inferior a 2 minutos**, transformando un proceso administrativo en un filtro preventivo de salud.
* **Reasignación de Horas Humanas:** Libera al equipo humano de la carga monótona de transcribir y buscar, permitiéndoles concentrarse en la atención directa y en la resolución de discrepancias complejas.

> [!IMPORTANT]
> **Decisión Solicitada a Gerencia:**  
> 1. Aprobar la asignación formal de una Máquina Virtual Windows (4 vCPU, 8-16 GB RAM, resolución 1080p fija).  
> 2. Autorizar el inicio de pruebas operacionales en turno nocturno supervisado vía Telegram.  
> 3. Respaldar la Fase 2 de optimización de velocidad para alcanzar paridad humana de ciclo.
