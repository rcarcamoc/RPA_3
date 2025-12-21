# Plan de Continuidad - RPA Framework 3

Este documento ha sido generado para facilitar el traspaso del proyecto al siguiente equipo de desarrollo. Resume lo logrado hasta la fecha y establece las prioridades para las próximas etapas.

---

## ✅ Logros Técnicos Principales

### 1. Motor de Workflows (Backend)
- **Core Engine**: Implementado en `core/workflow_executor.py`. Soporta ejecución secuencial, condicionales (`DECISION`) y bucles (`LOOP`).
- **Paso de Variables**: Los scripts se comunican via JSON en `stdout`, actualizando un contexto compartido en tiempo real.
- **Logger Enterprise**: Sistema robusto que escribe en consola, archivo de log y buffer para la UI simultáneamente.
- **Validación de Integridad**: Motor que detecta ciclos infinitos, nodos huerfanos, y configuraciones incompletas antes de la ejecución.

### 2. Interfaz Gráfica (PyQt6)
- **Editor Visual**: Canvas interactivo basado en `QGraphicsView` con soporte para drag-and-drop de nodos.
- **Gestión de Conexiones**: Sistema para crear conexiones visualmente y "split" de edges (insertar nodos en medio de una conexión existente).
- **Undo/Redo System**: Soporte completo para deshacer y rehacer cambios en el flujo usando `QUndoStack`.
- **Navegación Avanzada**: Implementado zoom suave (hacia el cursor) y paneo del canvas con el botón central del mouse.
- **Iconografía Estándar**: Uso de `QStyle.StandardPixmap` para una interfaz profesional y reconocible.

---

## 📂 Estado de la Estructura
```
rpa_framework/
├── core/                 # Lógica de modelos, ejecutor y validador
├── ui/                   # Widgets, Canvas y Comandos Undo/Redo
├── workflows/            # Archivos .json de flujos y logs de ejecución
├── scripts/              # Repositorio de scripts Python para los nodos
└── CONTINUITY_PLAN.md    # Este documento
```

---

## 🚀 Hoja de Ruta Priorizada

### 🔴 PRIORIDAD ALTA: Estabilidad y Estructura
#### 1. Refactorización de Arquitectura
- **Problema**: `main_gui_simple.py` supera las 1000 líneas.
- **Tarea**: Desacoplar el archivo en módulos (`tabs/`, `widgets/`, `utils/`). Es crítico realizar esto **antes** de seguir agregando funcionalidades para evitar deuda técnica técnica.

#### 2. Unificación de Estructura de Grabaciones
- **Tarea**: Centralizar toda la salida de los grabadores (py, json, meta) en una única estructura de carpetas organizada.
- **Impacto**: Asegura que todas las pestañas de la GUI lean de la misma fuente de verdad y facilita el despliegue del software.

### 🟡 PRIORIDAD MEDIA: Funcionalidad Core
#### 3. Nodo de Base de Datos (MySQL)
- **Tarea**: Implementar un nodo especializado en operaciones SQL (CRUD).
- **Alcance**: Definición de conexión al servidor y inyección automática de resultados de `SELECT` en las variables del workflow.

### 🟢 PRIORIDAD BAJA: UX y Pulido
#### 4. Rediseño del Editor de Nodos
- **Tarea**: Hacer el panel de propiedades dinámico (solo campos relevantes por tipo) e iconografía mejorada para zoom y tipos de nodo.

#### 5. Facilidad de Edición
- **Portapapeles**: Implementar Copy/Paste (`Ctrl+C` / `Ctrl+V`).
- **Alineación Inteligente**: `Snap-to-grid`.

---

## 🛠️ Notas para el Equipo
- El sistema de Undo/Redo es extensible. Si agregas una nueva funcionalidad que afecte al modelo, crea un comando en `ui/workflow_commands.py`.
- La validación se encuentra en `core/validator.py`. Añade nuevas reglas allí para mantener el código limpio.
- Todos los scripts de ejemplo se encuentran en `scripts/` para referencia.

---
**Generado por Antigravity (Advanced Agentic Coding - Google DeepMind)** 
*Fecha: 21 de Diciembre de 2024*
