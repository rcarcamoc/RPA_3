# ANEXO COMPLEMENTARIO: PROCESO FUNCIONAL, REGLAS DE DECISIÓN Y GOBIERNO OPERACIONAL RPA

**Descripción Funcional Extremo a Extremo y Operación del Robot RPA (RIS – PACS)**  
*Documento complementario a la Ficha Técnica de Arquitectura (v2.0). Detalla el flujo funcional de negocio, evento de inicio, correlación clínica entre sistemas, reglas de decisión, manejo de excepciones y monitoreo para Tecnología y Seguridad.*

---

## 1. Descripción y Objetivo Funcional del Robot

El presente anexo complementa la documentación técnica de infraestructura previamente entregada, describiendo desde una perspectiva funcional y de negocio **qué actividades realiza el robot RPA de extremo a extremo**, cómo interactúa entre las plataformas clínicas y bajo qué criterios toma decisiones o solicita intervención humana.

El objetivo del robot es automatizar de forma continua (24/7) el proceso operativo de conciliación, triage preventivo y cierre documental de estudios radiológicos entre el portal web **RIS** (*Radiology Information System*) y el sistema visualizador de escritorio **Carestream Vue PACS** (*Picture Archiving and Communication System*). Su operación persigue tres propósitos de negocio:

* **Continuidad Operacional y Sincronización:** Procesar de manera constante la bandeja de estudios informados pendientes de sincronización, eliminando cuellos de botella en turnos nocturnos, fines de semana y festivos.
* **Triage Clínico Preventivo (Detección Temprana):** Identificar en tiempo real hallazgos médicos de urgencia o riesgo vital dentro de los informes clínicos para alertar de inmediato al equipo médico supervisor.
* **Integridad y Trazabilidad Clínica:** Garantizar cero errores de transcripción o asignación cruzada de pacientes mediante validaciones cruzadas obligatorias entre el RIS y el PACS antes de aprobar cualquier estudio.

---

## 2. Evento que da Inicio al Proceso

El proceso funcional opera bajo un esquema desatendido de monitoreo continuo sobre la lista de trabajo clínica, activándose mediante los siguientes eventos disparadores (*triggers*):

| Tipo de Evento Disparador | Condición de Activación Funcional | Comportamiento del Robot |
| :--- | :--- | :--- |
| **1. Evento Primario (De Negocio)** | Existencia de estudios pendientes en la lista de trabajo del portal web RIS (asociados al centro médico configurado). | Al detectar uno o más exámenes pendientes de gestión en la bandeja del RIS, el robot reserva el primer estudio disponible e inicia el flujo de correlación hacia el PACS. |
| **2. Evento de Ciclo Continuo (Polling Programado)** | Finalización del caso en curso o inicio automático del servicio operativo en la estación de trabajo. | El robot ejecuta ciclos sucesivos de consulta. Si al revisar el RIS la bandeja se encuentra sin estudios nuevos, registra el estado *"Sin registros para trabajar"*, entra en pausa controlada y vuelve a consultar en el siguiente ciclo. |
| **3. Activación o Pausa por Supervisión** | Instrucción operativa emitida por un supervisor autorizado a través del canal de control o consola de operaciones. | Permite iniciar, pausar o reanudar la ejecución del flujo de manera controlada ante ventanas de mantenimiento de los sistemas clínicos. |

---

## 3. Flujo Funcional Completo y Secuencia de Acciones Extremo a Extremo

Para cada estudio radiológico procesado, el robot ejecuta una secuencia estructurada de **8 etapas funcionales** que van desde la verificación inicial del entorno hasta el cierre auditado del examen:

| Etapa del Flujo | Sistema Involucrado | Qué hace el Robot (Acción Funcional) |
| :--- | :--- | :--- |
| **Etapa 1: Validación de Condiciones Operativas** | Entorno de Red, VPN y Base de Datos Local | Comprueba que el enlace seguro a la red clínica (VPN corporativa), la base de datos de control y los servicios de clasificación estén activos antes de interactuar con datos de pacientes. |
| **Etapa 2: Consulta y Filtrado de Lista de Trabajo** | Portal Web RIS | Accede al portal RIS, aplica los filtros de búsqueda institucionales y verifica la bandeja de atenciones para identificar exámenes pendientes de procesar. |
| **Etapa 3: Reserva y Extracción Documental** | Portal Web RIS + Base de Datos de Control | Selecciona el estudio pendiente, lo marca como *"En Proceso"* en la cola interna (evitando duplicidad), extrae los datos del médico informante y descarga el documento PDF de la orden/informe clínico. |
| **Etapa 4: Lectura Clínica y Clasificación (Triage)** | Motor de Reglas y Clasificación Clínica | Extrae del documento clínico el identificador del paciente, tipo de examen, fecha y diagnóstico. Evalúa el texto diagnóstico para determinar si existen hallazgos críticos que requieran notificación urgente. |
| **Etapa 5: Acceso y Búsqueda del Paciente en PACS** | Carestream Vue PACS (Escritorio) | Inicia sesión o activa la ventana de Carestream Vue PACS utilizando las credenciales correspondientes al médico informante asignado, accede al buscador e ingresa el identificador único del paciente. |
| **Etapa 6: Correlación y Selección del Estudio** | Carestream Vue PACS (Escritorio) | Ordena los estudios del paciente en la grilla del PACS y evalúa cuál de las filas corresponde exactamente al examen extraído del RIS, verificando concordancia anatómica, modalidad y fecha. |
| **Etapa 7: Transcripción del Informe y Aprobación** | Carestream Vue PACS (Visor de Informes) | Abre el estudio correlacionado, inserta el texto diagnóstico validado en el editor de informes del PACS, verifica que el contenido haya quedado íntegramente registrado y actualiza el estado del examen (ej. *"Aprobado"*). |
| **Etapa 8: Registro de Auditoría y Cierre de Ciclo** | Base de Datos de Control | Actualiza el registro del caso a estado *"Completado"*, almacena la marca de tiempo de término y libera el robot para tomar inmediatamente el siguiente estudio pendiente. |

> [!NOTE]
> **OPTIMIZACIÓN DE FLUJO (PRE-CARGA CONTROLADA):** Con el fin de optimizar los tiempos de ciclo sin afectar la precisión, mientras el robot ejecuta las acciones visuales en el PACS para el paciente actual (Etapas 5 a 7), puede pre-validar en segundo plano los datos del siguiente estudio en la cola del RIS, manteniendo siempre la estricta separación e integridad de cada registro.

---

## 4. Diagrama de Flujo Funcional Extremo a Extremo (BPMN)

El diagrama BPMN (incluido en alta resolución en `diagrama_flujo_funcional_rpa.png` e incrustado en el documento Word) ilustra el recorrido completo del proceso automatizado a través de sus cuatro carriles operacionales (**1. Portal Web RIS**, **2. Orquestador RPA & Motor IA**, **3. Sistema PACS** y **4. Supervisión y Alertas**), destacando los tres puntos principales de decisión (`¿Estudios Pendientes?`, `¿Hallazgo Crítico?` y `¿Estudio Válido?`).

---

## 5. Interacción y Mecanismo de Correlación entre RIS y PACS

Dado que el portal web RIS y la aplicación de escritorio Carestream Vue PACS operan como entornos independientes en la interfaz de usuario, el robot actúa como puente de integración funcional asegurando que la información extraída del RIS se aplique única y exclusivamente sobre el estudio correspondiente en el PACS.

La correlación unívoca entre ambos sistemas se realiza mediante cuatro llaves de validación sucesivas:

| Llave de Correlación | Origen (Portal Web RIS) | Destino (Carestream Vue PACS) | Objetivo de Control |
| :--- | :--- | :--- | :--- |
| **1. Identificador del Paciente (ID / Documento)** | Extraído desde la orden clínica y el documento PDF del estudio en el RIS. | Ingresado en el filtro de búsqueda de pacientes del PACS. | Aislar únicamente el historial de estudios perteneciente al paciente correcto, con cero error de digitación. |
| **2. Credencial del Médico Informante** | Nombre y folio del profesional radiólogo asignado al examen en la lista del RIS. | Homologado contra el catálogo interno de profesionales para autenticar la sesión en el PACS. | Asegurar que la apertura, transcripción y firma del estudio en el PACS quede registrada bajo el médico responsable. |
| **3. Denominación del Examen y Región Anatómica** | Descripción del examen informado en el RIS (ej. *"TAC de Tórax"*, *"RM Cerebral"*). | Contrastado contra las descripciones de estudios listadas en la grilla del paciente en el PACS. | Seleccionar el estudio correcto cuando un mismo paciente posee múltiples exámenes históricos o simultáneos. |
| **4. Concordancia Temporal y Estado en PACS** | Fecha de atención registrada en la orden del RIS. | Ordenamiento cronológico de la bandeja del PACS y verificación de estado elegible. | Impedir la modificación de estudios antiguos o exámenes que ya hayan sido cerrados previamente. |

---

## 6. Información Utilizada y Reglas de Clasificación y Decisión

### 6.1. Conjunto de Datos Utilizados por el Proceso
Para operar cada caso, el robot utiliza un conjunto acotado de datos operacionales y clínicos, aplicando el principio de minimización de datos:
* **Datos del Estudio (RIS):** Identificador/documento del paciente (utilizado exclusivamente en local para buscar en PACS), nombre del examen, fecha del estudio y texto del diagnóstico radiológico.
* **Datos del Profesional:** Nombre del médico informante y sus credenciales asociadas para la sesión de PACS.
* **Catálogos de Control Interno:** Diccionario institucional de patologías críticas, catálogo de equivalencias/sinónimos de nombres de exámenes y registro de estado de ejecución.

### 6.2. Reglas de Clasificación y Puntos de Decisión
Durante el flujo extremo a extremo, el robot aplica cuatro reglas de negocio estructuradas en tres niveles de verificación (coincidencia exacta, coincidencia por similitud/diccionario de sinónimos y evaluación semántica asistida por IA):

| Punto de Decisión | Regla de Evaluación Funcional | Criterio de Aprobación / Rechazo |
| :--- | :--- | :--- |
| **Regla 1: Elegibilidad de Cola (RIS)** | Evalúa si existen estudios pendientes en la lista de trabajo del RIS que no estén siendo procesados en otra sesión. | • **Con estudios libres:** Reserva el caso e inicia procesamiento.<br>• **Sin estudios:** Finaliza el ciclo sin error y aguarda la siguiente ventana. |
| **Regla 2: Homologación de Médico Informante** | Compara el nombre del médico extraído del RIS contra el padrón de profesionales habilitados en la base de datos. | • **Coincidencia validada:** Obtiene perfil de acceso para PACS.<br>• **Médico no registrado:** Detiene el caso y notifica a supervisión para actualización de catálogo. |
| **Regla 3: Triage de Patología Crítica** | Analiza únicamente el fragmento de texto diagnóstico (desidentificado) frente al catálogo de hallazgos críticos (ej. aneurisma, TEP, hemorragia aguda). | • **Hallazgo Crítico ("Sí"):** Activa alerta médica prioritaria e inmediata.<br>• **Sin Hallazgo Crítico ("No"):** Clasifica como flujo regular y continúa hacia el cierre en PACS. |
| **Regla 4: Concordancia de Estudio (RIS vs PACS)** | Verifica que el examen listado en la pantalla del PACS corresponda en anatomía, lateralidad y modalidad al examen del RIS. | • **Concordancia confirmada:** Abre el visor y transcribe el diagnóstico.<br>• **Ambigüedad o discrepancia:** Aborta el cierre automático para proteger la integridad clínica y escala el caso a un operador. |

---

## 7. Acciones que Ejecuta el RPA según cada Resultado

En función del resultado obtenido en las reglas de clasificación y correlación, el robot ejecuta caminos de acción determinísticos y claramente diferenciados:

| Escenario / Resultado de Evaluación | Acciones Ejecutadas en Sistemas (RIS / PACS / BD) | Notificación y Seguimiento Operacional |
| :--- | :--- | :--- |
| **Escenario A: Estudio Normal con Correlación Exitosa (Flujo Estándar)** | 1. Abre el examen correspondiente en PACS.<br>2. Inserta y valida el diagnóstico clínico en el informe.<br>3. Cambia el estado del estudio a *"Aprobado"* en PACS y cierra el visor.<br>4. Registra estado *"Completado"* en Base de Datos. | No requiere intervención humana. El avance queda registrado en la bitácora transaccional para métricas de producción. |
| **Escenario B: Estudio con Detección de Patología Crítica** | 1. Marca el registro en la Base de Datos con indicador de *"Patología Crítica = Sí"* y detalla el hallazgo identificado.<br>2. Continúa la apertura y gestión del estudio en PACS dando prioridad al trazado del caso. | Dispara una **Alerta Clínica Inmediata** al canal de supervisión médica indicando el hallazgo detectado para activar el protocolo asistencial de urgencia. |
| **Escenario C: Estudio Ya Ingresado o con Addendum Previo en PACS** | 1. Detecta en PACS que el estudio ya cuenta con informe previo o estado avanzado.<br>2. No sobrescribe la información existente.<br>3. Registra la condición en la Base de Datos. | Envía aviso al canal operativo con botones de clasificación rápida (*"Ya Ingresado"* / *"Addendum"* / *"Gestionado"*) para confirmación del supervisor. |
| **Escenario D: Discrepancia de Correlación (Paciente o Examen No Coincide)** | 1. Cancela de inmediato la escritura del informe en PACS.<br>2. Captura evidencia visual de la pantalla.<br>3. Marca el caso como *"Error / Pendiente de Revisión"* en BD y libera la interfaz. | Remite alerta con la captura de pantalla al equipo de soporte/operaciones para resolución manual asistida, pasando al siguiente caso de la cola. |
| **Escenario E: Bandeja de Trabajo Vacía en RIS** | 1. Cierra la consulta sin modificar registros clínicos.<br>2. Registra en bitácora *"Sin registros para trabajar"*. | El robot permanece en espera activa hasta el próximo ciclo programado de lectura. |

---

## 8. Tratamiento de Excepciones, Seguridad e Intervención Humana

### 8.1. Clasificación y Manejo de Excepciones
El diseño del robot distingue entre excepciones de negocio (clínicas/funcionales) y excepciones técnicas (de infraestructura o conectividad), asegurando que ningún fallo puntual detenga la operación general ni comprometa datos de pacientes:

* **Excepciones Funcionales o de Negocio:** Corresponden a situaciones donde los datos del estudio no permiten una automatización segura (ej. paciente sin imágenes cargadas en PACS, nombre de examen no homologable entre RIS y PACS, o médico informante nuevo no registrado). En estos casos, el robot aplica una política de **Fallo Seguro (*Fail-Safe*)**: nunca fuerza el guardado de un informe dudoso, documenta la discrepancia con una captura de la interfaz, notifica al operador humano y avanza con el siguiente paciente de la fila.
* **Excepciones Técnicas o de Sistema:** Corresponden a interrupciones momentáneas de red, caída del túnel VPN, lentitud en la carga del visor PACS o ventanas emergentes inesperadas del sistema operativo. El robot ejecuta primero protocolos automáticos de autocuración: reintentos controlados de lectura (hasta 3 intentos), reconexión automática de VPN y reinicio limpio del visor Carestream PACS. Si tras los reintentos la falla persiste, detiene de forma segura el ciclo y alerta al equipo técnico.

### 8.2. Protocolo de Intervención Humana (*Human-in-the-Loop*)
La intervención humana se gestiona de manera centralizada y ágil a través del sistema de notificaciones operativas (Telegram Corporativo) y el panel de control:
1. **Recepción de Alerta con Contexto:** Al recibir una alerta de excepción junto con la captura de pantalla del motivo, el operador revisa el caso puntual en el RIS/PACS.
2. **Resolución Interactiva:** El supervisor puede marcar directamente en la notificación el resultado de su revisión mediante botones interactivos (*"Gestionado"*, *"Addendum"* o *"Ya Ingresado"*), o bien solicitar la rehabilitación del registro para que el robot lo reprocese.
3. **Supervisión Remota No Intrusiva:** En caso de requerir inspección visual en tiempo real sobre la máquina virtual sin interrumpir la sesión gráfica del robot, el supervisor puede solicitar una transmisión en vivo de solo lectura o pausar el bot de forma remota.

### 8.3. Medidas de Seguridad Aplicadas Durante la Operación
* **Desidentificación y Minimización de Datos (PHI):** En estricto apego a la normativa de privacidad de datos de salud (Leyes 19.628, 20.584 y 21.719), cuando el motor consulta servicios de IA para clasificación semántica, filtra y envía exclusivamente el texto técnico del hallazgo médico, sin incluir jamás nombre, RUT, número de documento ni identificadores del paciente.
* **Resguardo de Credenciales:** Las contraseñas de acceso al RIS/PACS y llaves de conexión se mantienen cifradas o en variables de entorno protegidas fuera del código fuente, inyectándose en memoria únicamente al momento de autenticar la sesión.
* **Trazabilidad e Inmutabilidad de Bitácora:** Cada paso ejecutado, decisión tomada y excepción capturada queda registrada en la base de datos MySQL con fecha, hora exacta y resultado, permitiendo auditoría completa.

---

## 9. Resultado Esperado, Condición de Finalización y Procedimiento de Monitoreo

### 9.1. Resultado Esperado y Condiciones de Finalización del Proceso
El proceso automatizado cuenta con criterios claros de cierre tanto a nivel de cada estudio individual como a nivel del ciclo operativo completo:

| Nivel de Evaluación | Condición de Finalización Exitosa | Resultado Final Esperado en los Sistemas |
| :--- | :--- | :--- |
| **Finalización por Estudio Individual (Caso Clínico)** | El informe del RIS ha sido correlacionado en el PACS, el texto diagnóstico fue insertado y validado visualmente, y el estado en PACS cambió a *"Aprobado"*. | • **Carestream PACS:** Estudio informado y aprobado bajo el médico correspondiente.<br>• **Base de Datos RPA:** Registro en estado *"Completado"* con trazabilidad completa.<br>• **Canal Médico:** Alerta despachada si hubo patología crítica. |
| **Finalización por Excepción Controlada (Caso Derivado)** | Se detecta una discrepancia clínica o bloqueo tras agotar los reintentos automáticos. | • **Carestream PACS:** Estudio intacto (sin modificaciones parciales).<br>• **Base de Datos RPA:** Registro marcado en estado *"Error"* o *"Gestionado"* con detalle del motivo.<br>• **Operador Humano:** Notificado con captura de pantalla. |
| **Finalización de Ciclo de Cola (Bandeja RIS)** | El robot procesa la totalidad de los estudios pendientes en la lista de trabajo del RIS hasta que la consulta retorna cero registros pendientes. | • Bandeja RIS / PACS conciliada y al día.<br>• El robot cierra su ciclo actual limpiamente y queda en espera programada para el siguiente barrido. |

### 9.2. Procedimiento de Operación, Monitoreo, Soporte y Gestión de Incidentes
Para respaldar la continuidad operacional y facilitar la supervisión por parte de los equipos de Operaciones y Tecnología, el sistema incorpora el siguiente modelo de operación y soporte:
* **Operación Autónoma:** El robot inicia automáticamente con el sistema operativo mediante una tarea programada resiliente y opera en modalidad 24/7 sin requerir intervención manual para su arranque diario.
* **Monitoreo Continuo:** Los supervisores disponen de notificaciones automáticas en tiempo real ante cualquier anomalía, reportes de estado en base de datos (casos completados, tiempos de ciclo, alertas críticas emitidas) y verificación automática de salud de los servicios de clasificación.
* **Gestión de Incidentes y Soporte:** Ante cualquier incidente reportado (nivel 1: discrepancia de datos en un estudio; nivel 2: caída de conectividad VPN/red; nivel 3: actualización de interfaz de RIS o PACS), el flujo aísla la falla, notifica con evidencia visual al canal de soporte y permite retomar la operación inmediatamente tras la corrección sin pérdida de trazabilidad.
