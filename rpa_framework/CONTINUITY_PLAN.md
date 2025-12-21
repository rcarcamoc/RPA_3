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

## 🚀 Próximas Tareas Prioritarias

### 1. Unificación de Estructura de Grabaciones
> [!IMPORTANT]
> **Problema**: Actualmente las grabaciones y scripts están dispersos en varias carpetas (`scripts/`, `recordings/`, `quick_scripts/`).
- **Tarea**: Centralizar toda la salida de los grabadores (py, json, meta) en una única estructura de carpetas ordenada dentro del framework.
- **Alcance**: Modificar `main_gui_simple.py` y todos los módulos de grabación para que escriban en esta carpeta central.
- **Vista**: Asegurar que todas las listas de selección de la GUI lean exclusivamente de esta nueva estructura unificada.

### 2. Rediseño del Editor de Nodos
- **Visualización Dinámica**: El editor de la derecha debe ser contextual. Si es un nodo `ACTION`, solo muestra el campo `Script`. Si es `DECISION`, muestra `Condición`, etc.
- **Iconografía de Nodos**: Agregar iconos representativos a los tipos de nodo en el dropdown y en el panel de propiedades.
- **Mejora de Iconos de Zoom**: Reemplazar los caracteres Unicode de acercar/alejar por iconos más descriptivos o botones con mejor feedback visual.

### 3. Integración con Bases de Datos (MySQL)
- **Nuevo Nodo de Consulta**: Implementar un tipo de nodo especializado en operaciones SQL.
- **Operaciones**: Soporte para `SELECT`, `INSERT`, `UPDATE` y `DELETE`.
- **Configuración**: Crear un diálogo o sección en propiedades para definir la conexión (Host, User, Pass, DB, Port).
- **Manejo de Resultados**: Los datos de un `SELECT` deben inyectarse automáticamente en el contexto de variables del workflow para que nodos posteriores puedan usarlos.

### 4. Pendientes de Edición de Flujo
- **Portapapeles**: Implementar Copy/Paste (`Ctrl+C` / `Ctrl+V`) para nodos individuales o grupos de nodos.
- **Alineación Inteligente**: Implementar `Snap-to-grid` para que los nodos se alineen automáticamente al ser soltados en el canvas.

### 5. Refactorización de Arquitectura
- **Desacoplamiento de main_gui_simple.py**: El archivo principal ha superado las 1000 líneas. Se recomienda dividirlo en módulos más pequeños (ej. `tabs/`, `widgets/`, `utils/`) para facilitar el mantenimiento y la extensibilidad por parte de otros equipos.

---

## 🛠️ Notas para el Equipo
- El sistema de Undo/Redo es extensible. Si agregas una nueva funcionalidad que afecte al modelo, crea un comando en `ui/workflow_commands.py`.
- La validación se encuentra en `core/validator.py`. Añade nuevas reglas allí para mantener el código limpio.
- Todos los scripts de ejemplo se encuentran en `scripts/` para referencia.

---
**Generado por Antigravity (Advanced Agentic Coding - Google DeepMind)** 
*Fecha: 21 de Diciembre de 2024*
