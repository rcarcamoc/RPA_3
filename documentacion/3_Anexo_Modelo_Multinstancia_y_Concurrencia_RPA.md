# Anexo Técnico-Operacional de Escalabilidad

**Modelo de Operación Multinstancia: Múltiples Sesiones y Asignación de Casos Sin Conflicto**  
*Diseño conceptual de integración para ejecutar 2 o más robots en paralelo (servidores o PCs virtuales) garantizando aislamiento de escritorio y prevención absoluta de colisiones*

---

### Ficha Resumen del Anexo

| Campo | Definición |
| :--- | :--- |
| **Objetivo del Anexo** | Definir cómo escalar de 1 robot a múltiples robots concurrentes para multiplicar la capacidad diaria sin riesgos operacionales. |
| **Pregunta Crítica 1 (Sesiones)** | ¿Cómo pueden trabajar múltiples bots al mismo tiempo sin interferir entre sí con la pantalla, el mouse o los programas abiertos? |
| **Pregunta Crítica 2 (Casos)** | ¿Cómo se identifican las máquinas para garantizar que dos bots jamás tomen, abran o cierren el mismo examen médico? |
| **Evolución Reciente del Proyecto** | Incorporación de arquitectura modular, nuevo gestor reactivo del RIS y triage de incidentes directo en Telegram (Addendum / Ya Ingresado). |

---

## 1. El Desafío de Trabajar con Múltiples Sesiones en RPA

A diferencia de los sistemas tradicionales que operan mediante servicios "invisibles" de fondo, los robots RPA interactúan con aplicaciones médicas complejas (como el visualizador Carestream Vue PACS y el portal RIS) simulando exactamente las acciones de una persona: mueven el puntero del mouse, hacen clics en coordenadas específicas, leen texto en pantalla mediante visión óptica (OCR) y presionan teclas.

Por esta razón, dos robots **NO pueden convivir en el mismo escritorio de Windows** al mismo tiempo, ya que competirían por el cursor y las ventanas en primer plano, provocando fallos inmediatos. Para trabajar en paralelo, la solución conceptual es muy sencilla:

> [!NOTE]
> **Principio de Aislamiento de Escritorio:**  
> Cada robot debe disponer de su propia "oficina digital" independiente (su propia sesión de Windows). En términos prácticos, es exactamente igual a tener a dos o tres tecnólogos trabajando cada uno en su propio computador, compartiendo la misma base de datos central de exámenes pero sin interferir en la pantalla del otro.

### 1.1. Las Dos Vías de Despliegue de Múltiples Sesiones
Existen dos alternativas sencillas para habilitar estas sesiones independientes, sin requerir una reingeniería compleja de servidores:

* **Opción A: Múltiples Máquinas Virtuales en Servidores:**  
  Se configuran 2 o más Máquinas Virtuales dentro de la infraestructura de centro de datos. Cada VM tiene su propio sistema operativo Windows, su propia resolución fija (1920x1080) y ejecuta su propia instancia del robot. Las VMs están aisladas entre sí y se conectan a la red clínica vía VPN corporativa.
* **Opción B: Múltiples Máquinas Virtuales en un Mismo PC Físico:**  
  En un único computador físico de buen rendimiento (por ejemplo, una estación de trabajo con procesador de 8 o más núcleos y 32 a 64 GB de RAM), se pueden ejecutar 2 o 3 máquinas virtuales locales mediante software de virtualización estándar de escritorio. El computador físico actúa como "anfitrión", mientras que dentro de él conviven 2 o 3 "pantallas virtuales" totalmente independientes donde cada bot trabaja a toda velocidad sin que ninguno toque el mouse ni la pantalla del computador principal.

---

## 2. Coordinación y Prevención de Duplicidad: ¿Cómo evitan tomar el mismo caso?

El punto más crítico para la seguridad operacional es garantizar que dos máquinas jamás abran simultáneamente al mismo paciente ni dupliquen un cierre en el PACS. Para resolver esto de forma infalible y sin tecnicismos engorrosos, el modelo implementa tres mecanismos coordinados:

```
               ┌────────────────────────────────────────────────────────┐
               │    BASE DE DATOS CENTRAL (MySQL / Control de Cola)     │
               │   • Semáforo de asignación instantánea ("Asiento cine") │
               │   • Bloqueo atómico: Excluye casos tomados en ms       │
               │   • Vigilante (Watchdog): Libera casos colgados (>12m) │
               └───────────────▲────────────────────────▲───────────────┘
                               │                        │
               ┌───────────────┴────────┐      ┌────────┴───────────────┐
               │    BOT-01 (Sesión 1)   │      │    BOT-02 (Sesión 2)   │
               │  • Windows 1080p       │      │  • Windows 1080p       │
               │  • RIS Chrome propio   │      │  • RIS Chrome propio   │
               │  • Carestream PACS #1  │      │  • Carestream PACS #2  │
               └───────────────┬────────┘      └────────┬───────────────┘
                               │                        │
                               ▼                        ▼
               ┌────────────────────────────────────────────────────────┐
               │         CANAL CENTRAL DE TELEGRAM (Supervisión)        │
               │  • Alertas con "Gafete": [BOT-01] vs [BOT-02]          │
               │  • Botones interactivos: "Gestionado", "Addendum", etc.│
               └────────────────────────────────────────────────────────┘
```

### 2.1. El "Gafete Digital" (Identificador Único por Máquina)
Cada máquina o sesión virtual posee una credencial de identidad única e irrepetible (por ejemplo: `BOT-01`, `BOT-02`, `BOT-03`). Desde que enciende hasta que termina cada ciclo, el robot estampa su firma digital en cada transacción de la base de datos y en las alertas de Telegram (ejemplo: *"Caso #8450 tomado por BOT-02"*). Esto permite a los supervisores saber en tiempo real qué máquina está atendiendo a cada paciente.

### 2.2. El "Semáforo de Asignación" (Reserva Atómica en Base de Datos)
El sistema funciona exactamente igual a una boletería digital de cine o aerolínea: cuando una persona selecciona una butaca, esa butaca queda bloqueada instantáneamente en rojo para todos los demás compradores, incluso si dos personas hicieron clic en la misma milésima de segundo.

En el bot RPA, este proceso se realiza en la base de datos central en tres pasos automáticos:
1. **Paso 1: Consulta de Casos Libres:** El `BOT-01` consulta la cola de estudios pendientes y localiza el siguiente examen sin asignar.
2. **Paso 2: Reserva Inmediata (*Lock*):** Antes de tocar el PACS o descargar el PDF, el `BOT-01` actualiza el registro en la base de datos marcándolo: `Estado: En Proceso | Asignado a: BOT-01 | Hora: 10:15:32`.
3. **Paso 3: Exclusión Automática para Otros Bots:** Si el `BOT-02` consulta la lista en ese mismo instante, la base de datos le oculta automáticamente el caso tomado por el `BOT-01` y le entrega de inmediato el siguiente caso disponible. Es matemáticamente imposible que dos bots tomen el mismo examen.

### 2.3. Mecanismo de Seguridad ante Caídas (Watchdog de Casos Colgados)
¿Qué ocurre si la máquina virtual del `BOT-01` sufre un corte de energía o pierde la conexión a internet en pleno proceso? Para evitar que el paciente quede bloqueado indefinidamente, el sistema cuenta con un **"Vigilante Automático"** (*Watchdog*): si un caso permanece en estado `En Proceso` por más de 12 minutos sin registrar actividad, el sistema asume que la máquina falló, libera automáticamente el examen de vuelta a la lista de pendientes y notifica por Telegram para que el `BOT-02` lo tome de inmediato.

| Modelo de Asignación | ¿Cómo se distribuyen los casos? | Ventaja Principal para la Operación |
| :--- | :--- | :--- |
| **1. Cola Central Inteligente (Recomendado)** | Los bots acuden a una única lista compartida y toman el siguiente caso libre mediante reserva atómica. | Máxima eficiencia. Si un bot termina rápido un caso simple, toma el siguiente sin esperar al otro. |
| **2. Reparto por Criterio / Segmentación** | BOT-01 atiende únicamente exámenes de TAC y BOT-02 atiende Resonancias (o por centros médicos / sedes). | Orden operativo total. Especialización de colas según prioridad clínica o convenio institucional. |
| **3. Turnos Alternos (Paridad)** | BOT-01 toma casos con identificador par y BOT-02 casos con identificador impar. | Independencia matemática absoluta sin riesgo alguno de solapamiento. |

---

## 3. Situación Actual del Proyecto: Mejoras Recientes que Viabilizan la Multinstancia

Al revisar el estado del código y los avances completados en los últimos días de octubre 2026, el proyecto incorporó transformaciones estructurales que facilitan de forma inmediata la puesta en marcha de múltiples máquinas concurrentes:

* **Modularización Integral de Arquitectura:** El código monolítico previo fue desacoplado en módulos especializados e independientes (`triple_search`, `telegram_bot`, `executor_handlers`, `reporting`). Esto significa que múltiples procesos pueden ejecutar las mismas librerías de forma compartida sin generar bloqueos de archivos en el sistema operativo.
* **Nuevo Flujo Optimizado de Extracción RIS (`obtener_datos_ris_optimizado.py`):** Se incorporó un gestor que reutiliza la sesión abierta de Chrome (evitando el ciclo constante de abrir/cerrar navegador), realiza filtrado instantáneo por selector inteligente y extrae médico y PDF en una sola pasada reactiva. Esto reduce drásticamente el tiempo de consulta y deja la cola lista para que varias máquinas la consuman a alta velocidad.
* **Supervisión y Gestión Interactiva de Incidentes vía Telegram:** Se crearon botones de acción en tiempo real dentro de Telegram (`Gestionado ✅`, `Addendum` o `Ya Ingresado`). Cada máquina reporta a un canal unificado indicando su nombre, permitiendo que un solo supervisor controle 2 o 3 robots desde su teléfono móvil.
* **Motor Autónomo de Calificación de Inteligencia Artificial (Auto-Ranking LLM):** El sistema cuenta ahora con un evaluador automático en segundo plano que valida cada 6 horas la disponibilidad y latencia de los modelos de IA médicos. Las distintas máquinas virtuales comparten este ranking optimizado sin necesidad de que cada una gaste tiempo realizando pruebas redundantes.

---

## 4. Impacto Operacional: ¿Cuánto rinde un esquema multinstancia?

Con el modelo actual de 1 máquina individual, el bot produce **~200 casos diarios** en 24 horas continuas (ritmo de 8-10 casos/hora). Al integrar 2 o 3 sesiones concurrentes, el impacto sobre la operación de teleradiología escala de forma directa y lineal:

| Configuración Operacional | Velocidad Combinada | Producción Diaria (24h) | Equivalencia en Personal Humano |
| :--- | :---: | :---: | :--- |
| **1 Máquina (Estado Actual)** | 8 - 10 casos / hora | **190 - 240 casos / día** | Equivale a 1 turno diurno completo sin pausas |
| **2 Máquinas Concurrentes** | 16 - 20 casos / hora | **380 - 480 casos / día** | **Supera a 2 turnos humanos de 8 horas** |
| **3 Máquinas Concurrentes** | 24 - 30 casos / hora | **570 - 720 casos / día** | **Equivale a un equipo completo de 3 operadores 24/7** |

> [!TIP]
> **Conclusión Operacional:** Con solo 2 máquinas virtuales trabajando en paralelo, el sistema procesa hasta 480 casos diarios con alerta crítica inmediata las 24 horas del día. Esto supera la capacidad total de un equipo de 2 operadores humanos dedicados, eliminando por completo la acumulación de exámenes nocturnos y la fatiga propia de turnos extendidos.

---

## 5. Pasos Concretos para Implementar la Multinstancia

Para llevar a cabo esta expansión, el plan de acción no requiere modificaciones estructurales en los sistemas médicos ni desarrollos complejos adicionales:

1. **Habilitación de Entornos:** Aprovisionar las 2 o 3 sesiones Windows independientes (ya sea en servidor de centro de datos o como 2 VMs en un PC anfitrión potente) con resolución fija de 1920x1080.
2. **Asignación de Identidades:** Configurar en cada máquina su archivo de configuración con su identificador único (`BOT-01`, `BOT-02`).
3. **Conexión a la Base de Datos Compartida:** Apuntar todas las máquinas a la misma base de datos central de control que ya implementa el bloqueo atómico de casos.
4. **Canal Unificado de Telegram:** Vincular las máquinas al mismo canal de supervisión de Telegram para que el equipo de operaciones reciba todas las alertas y estadísticas consolidadas en una sola pantalla.
