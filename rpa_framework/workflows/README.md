# Workflow Engine - RPA Framework 3

Motor de ejecución de workflows visuales para automatización RPA.

## 🚀 Inicio Rápido

### Ejecutar la GUI
```bash
cd rpa_framework
python main_gui_simple.py
```

Ve a la pestaña **"Workflows"** para:
- Cargar workflows existentes
- Crear nuevos workflows
- Editar nodos y conexiones
- Ejecutar y monitorear en tiempo real

---

## 📁 Estructura

```
workflows/           # Archivos JSON de workflows
scripts/             # Scripts Python ejecutables
core/
  ├── models.py      # Modelos de datos (Node, Edge, Workflow)
  ├── workflow_executor.py  # Motor de ejecución
  └── logger.py      # Sistema de logging
ui/
  └── workflow_panel.py     # Panel PyQt6 integrado
```

---

## 📝 Formato de Workflow JSON

```json
{
  "id": "wf_mi_workflow",
  "name": "Mi Workflow",
  "description": "Descripción del workflow",
  "nodes": [...],
  "edges": [...],
  "variables": {"key": "value"}
}
```

### Tipos de Nodos

| Tipo | Descripción | Campos Especiales |
|------|-------------|-------------------|
| `start` | Nodo inicial | - |
| `end` | Nodo final | - |
| `action` | Ejecuta script Python | `script` |
| `decision` | IF/ELSE | `condition`, `truePath`, `falsePath` |
| `loop` | Iteración | `script`, `iterations`, `loopVar` |

### Ejemplo de Nodo ACTION
```json
{
  "id": "n1",
  "type": "action",
  "label": "Mi Acción",
  "script": "scripts/mi_script.py",
  "position": {"x": 200, "y": 100}
}
```

### Ejemplo de Nodo DECISION
```json
{
  "id": "n2",
  "type": "decision",
  "label": "¿Éxito?",
  "condition": "status == 'success'",
  "truePath": "n3",
  "falsePath": "n4",
  "position": {"x": 200, "y": 200}
}
```

### Ejemplo de Nodo LOOP
```json
{
  "id": "n5",
  "type": "loop",
  "label": "Procesar Items",
  "script": "scripts/process.py",
  "iterations": "item_count",
  "loopVar": "current_index",
  "position": {"x": 200, "y": 300}
}
```

---

## 📜 Creación de Scripts

Los scripts deben:
1. Leer variables de entorno (`os.environ`)
2. Imprimir JSON al final para actualizar contexto

### Plantilla Básica

```python
import json
import os

# Leer variables del workflow
valor = os.getenv('mi_variable', 'default')

# Tu lógica aquí
resultado = procesar(valor)

# Retornar resultado (última línea debe ser JSON)
print(json.dumps({
    "nueva_variable": resultado,
    "status": "success"
}))
```

### Variables Disponibles
- Todas las `variables` definidas en el workflow
- Variables creadas por nodos anteriores
- `_loop_index` dentro de LOOPs

---

## 🎮 Controles de la UI

### Panel de Workflows
- **+ Nuevo**: Crear workflow vacío
- **Guardar**: Persistir cambios
- **Ejecutar**: Iniciar ejecución
- **Detener**: Parar ejecución

### Canvas (Click Derecho)
- En nodo: Editar, Resaltar, Eliminar
- En vacío: Agregar ACTION/DECISION/LOOP

### Editor de Nodos
- Edita propiedades del nodo seleccionado
- Campos se habilitan según tipo
- "Aplicar" para confirmar cambios

---

## 📊 Workflows de Ejemplo

1. **wf_login_example.json** - Login con decisión IF/ELSE
2. **wf_data_processing.json** - Procesamiento con LOOP

---

## 🔧 Uso Programático

```python
from core.models import Workflow
from core.workflow_executor import WorkflowExecutor

# Cargar workflow
wf = Workflow.from_json("workflows/mi_workflow.json")

# Ejecutar
executor = WorkflowExecutor(wf)
result = executor.execute()

print(result['status'])      # success, error, stopped
print(result['context'])     # Variables finales
print(result['logs'])        # Lista de logs
```
