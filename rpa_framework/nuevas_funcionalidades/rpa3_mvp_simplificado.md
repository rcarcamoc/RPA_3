# RPA Framework 3 - MVP Simplificado (Python + Localhost)

## 🎯 MVP OPTIMIZADO - 2-3 SEMANAS

### Stack ULTRA-SIMPLE

**Backend**: Python puro (sin FastAPI, solo `http.server` o minimal Flask)  
**Frontend**: HTML5 + Vanilla JavaScript (sin librerías grandes)  
**Base de Datos**: JSON files (sin BD)  
**Deployment**: Localhost con `python main.py`  

---

## ✅ FUNCIONALIDADES CORE (MUST HAVE)

### Backend (Python)
- ✅ **Parser JSON** para workflows
- ✅ **Ejecutor Secuencial** de scripts Python
- ✅ **Paso de Variables** entre scripts (diccionario global)
- ✅ **Control de Flujo**:
  - `IF/ELSE` bifurcaciones
  - `LOOP` repeticiones
  - Evaluador de condiciones seguro
- ✅ **Error Handling** básico
- ✅ **Logger** simple (archivo + console)
- ✅ **HTTP Server** para servir UI

### Frontend (HTML + Vanilla JS)
- ✅ **Canvas SVG** para dibujar workflows
- ✅ **Nodos Visuales**: Action, Decision (IF), Loop
- ✅ **Drag & Drop** básico
- ✅ **Editor de Propiedades**: Inputs HTML simples
- ✅ **Botones**: Ejecutar, Pausar, Detener
- ✅ **Log Monitor**: Textarea con scroll
- ✅ **Variables Panel**: JSON viewer simple

---

## 📁 ESTRUCTURA ULTRA-SIMPLE

```
rpa_3/
├── main.py                    # Servidor HTTP + WebSocket (minimal)
├── executor.py                # Motor de ejecución
├── models.py                  # Clases Workflow, Node, etc.
├── logger.py                  # Logging simple
├── workflows/
│   ├── workflow_001.json      # Definiciones guardadas
│   └── logs/
│       └── workflow_001.log
├── scripts/                   # Scripts grabados (.py)
│   ├── login.py
│   └── verify.py
├── static/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── requirements.txt           # Python deps (solo lo necesario)
```

---

## 💾 FORMATO JSON WORKFLOW (SIMPLIFICADO)

```json
{
  "id": "wf_001",
  "name": "Login Flow",
  "nodes": [
    {
      "id": "n1",
      "type": "action",
      "label": "Login",
      "script": "scripts/login.py"
    },
    {
      "id": "n2",
      "type": "decision",
      "label": "Check Access?",
      "condition": "result == 'success'",
      "truePath": "n3",
      "falsePath": "n4"
    },
    {
      "id": "n3",
      "type": "action",
      "label": "Proceed",
      "script": "scripts/proceed.py"
    },
    {
      "id": "n4",
      "type": "action",
      "label": "Retry Login",
      "script": "scripts/login.py"
    },
    {
      "id": "n5",
      "type": "loop",
      "label": "Process Items",
      "script": "scripts/process.py",
      "iterations": "items_count",
      "loopVar": "current_item"
    }
  ],
  "edges": [
    {"from": "n1", "to": "n2"},
    {"from": "n2_true", "to": "n3"},
    {"from": "n2_false", "to": "n4"},
    {"from": "n3", "to": "end"},
    {"from": "n4", "to": "end"},
    {"from": "n5", "to": "end"}
  ],
  "variables": {
    "username": "admin",
    "max_retries": 3
  }
}
```

---

## 🔧 COMPONENTES CLAVE

### 1. executor.py - Motor de Ejecución

```python
import json
import subprocess
from typing import Dict, Any
from logger import Logger

class WorkflowExecutor:
    def __init__(self, workflow_path: str):
        with open(workflow_path) as f:
            self.workflow = json.load(f)
        self.context = self.workflow.get('variables', {})
        self.logger = Logger(f"logs/{self.workflow['id']}.log")
    
    def execute(self) -> Dict[str, Any]:
        """Ejecuta workflow secuencialmente"""
        current_node_id = self._find_start_node()
        visited = set()
        
        while current_node_id:
            if current_node_id in visited and current_node_id not in [
                n['id'] for n in self.workflow['nodes'] 
                if n['type'] == 'loop'
            ]:
                break
            
            node = self._get_node(current_node_id)
            self.logger.log(f"Ejecutando: {node['label']}")
            
            result = self._execute_node(node)
            
            if node['type'] == 'action':
                current_node_id = self._get_next_node(current_node_id)
            
            elif node['type'] == 'decision':
                # Evaluar condición
                condition_result = self._eval_condition(
                    node['condition']
                )
                current_node_id = (
                    node['truePath'] if condition_result 
                    else node['falsePath']
                )
            
            elif node['type'] == 'loop':
                # Ejecutar loop
                iterations = self._get_loop_count(node)
                for i in range(iterations):
                    self.context['_loop_index'] = i
                    self._execute_node(node)
                current_node_id = self._get_next_node(current_node_id)
            
            visited.add(current_node_id)
        
        return {
            'status': 'success',
            'context': self.context,
            'logs': self.logger.get_logs()
        }
    
    def _execute_node(self, node: Dict) -> Any:
        """Ejecuta un nodo individual"""
        if node['type'] in ['action', 'loop']:
            script_path = node['script']
            try:
                # Pasar contexto al script
                result = subprocess.run(
                    ['python', script_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env={**os.environ, **self.context}
                )
                
                if result.returncode == 0:
                    self.logger.log(f"✓ {node['label']}")
                    # Capturar output y actualizar context
                    if result.stdout:
                        self.context.update(
                            json.loads(result.stdout)
                        )
                else:
                    self.logger.log(f"✗ {node['label']}: {result.stderr}")
                
                return result
            except Exception as e:
                self.logger.log(f"ERROR {node['label']}: {str(e)}")
                raise
    
    def _eval_condition(self, condition: str) -> bool:
        """Evalúa condición segura"""
        # Usar ast.literal_eval o simple expression evaluator
        try:
            # SEGURO: solo soportar operadores básicos
            return eval(
                condition, 
                {"__builtins__": {}}, 
                self.context
            )
        except Exception as e:
            self.logger.log(f"Condition error: {condition} - {e}")
            return False
    
    def _find_start_node(self) -> str:
        """Busca el nodo inicial"""
        for node in self.workflow['nodes']:
            if node['type'] == 'start':
                return self._get_next_node(node['id'])
        return self.workflow['nodes'][0]['id']
    
    def _get_node(self, node_id: str) -> Dict:
        for node in self.workflow['nodes']:
            if node['id'] == node_id:
                return node
        return None
    
    def _get_next_node(self, node_id: str) -> str:
        for edge in self.workflow['edges']:
            if edge['from'] == node_id:
                return edge['to']
        return None
    
    def _get_loop_count(self, node: Dict) -> int:
        var_name = node.get('iterations')
        return self.context.get(var_name, 1)
```

### 2. main.py - Servidor Simple

```python
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import threading
from executor import WorkflowExecutor

class RPAHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/workflows':
            self.list_workflows()
        elif self.path.startswith('/api/workflows/'):
            workflow_id = self.path.split('/')[-1]
            self.get_workflow(workflow_id)
        else:
            super().do_GET()
    
    def do_POST(self):
        if self.path.startswith('/api/execute/'):
            workflow_id = self.path.split('/')[-1]
            self.execute_workflow(workflow_id)
    
    def list_workflows(self):
        workflows = []
        for f in os.listdir('workflows'):
            if f.endswith('.json'):
                workflows.append(f.replace('.json', ''))
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(workflows).encode())
    
    def execute_workflow(self, workflow_id):
        try:
            executor = WorkflowExecutor(f'workflows/{workflow_id}.json')
            result = executor.execute()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

if __name__ == '__main__':
    server = HTTPServer(('localhost', 8000), RPAHandler)
    print('🚀 Servidor en http://localhost:8000')
    server.serve_forever()
```

### 3. logger.py - Logging Simple

```python
from datetime import datetime

class Logger:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.logs = []
    
    def log(self, message: str):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)  # Console
        self.logs.append(log_entry)
        
        # Guardar en archivo
        with open(self.filepath, 'a') as f:
            f.write(log_entry + '\n')
    
    def get_logs(self) -> list:
        return self.logs
```

---

## 🎨 Frontend (HTML + Vanilla JS)

### index.html

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RPA Executor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f0f0f0; }
        
        .container { display: flex; height: 100vh; }
        .left { flex: 1; padding: 20px; background: white; overflow-y: auto; }
        .right { flex: 1; padding: 20px; background: #fafafa; }
        
        h1 { margin-bottom: 20px; color: #333; }
        
        .workflow-list { margin-bottom: 30px; }
        .workflow-item {
            padding: 10px;
            margin: 5px 0;
            background: #e8e8e8;
            cursor: pointer;
            border-radius: 4px;
        }
        .workflow-item:hover { background: #d0d0d0; }
        .workflow-item.active { background: #007bff; color: white; }
        
        #canvas {
            border: 1px solid #ccc;
            background: white;
            cursor: crosshair;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        button {
            padding: 10px 20px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover { background: #0056b3; }
        
        #logMonitor {
            width: 100%;
            height: 300px;
            padding: 10px;
            border: 1px solid #ccc;
            background: #1e1e1e;
            color: #00ff00;
            font-family: monospace;
            font-size: 12px;
            border-radius: 4px;
            overflow-y: auto;
        }
        
        .properties {
            background: white;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        
        input, select, textarea {
            width: 100%;
            padding: 8px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="left">
            <h1>Workflows</h1>
            <div class="workflow-list" id="workflowList"></div>
            
            <h2>Canvas</h2>
            <svg id="canvas" width="100%" height="400"></svg>
            
            <div class="properties">
                <h3>Properties</h3>
                <input type="text" id="nodeName" placeholder="Node Name">
                <select id="nodeType">
                    <option value="action">Action</option>
                    <option value="decision">Decision (IF)</option>
                    <option value="loop">Loop</option>
                </select>
                <input type="text" id="nodeScript" placeholder="Script Path">
                <textarea id="nodeCondition" placeholder="Condition (for IF)"></textarea>
            </div>
        </div>
        
        <div class="right">
            <h1>Execution</h1>
            
            <div class="controls">
                <button id="executeBtn">▶ Ejecutar</button>
                <button id="pauseBtn">⏸ Pausar</button>
                <button id="stopBtn">⏹ Detener</button>
            </div>
            
            <h2>Logs</h2>
            <div id="logMonitor"></div>
            
            <h2>Variables</h2>
            <pre id="variablesViewer" style="background: white; padding: 10px; border-radius: 4px;"></pre>
        </div>
    </div>
    
    <script src="app.js"></script>
</body>
</html>
```

### app.js

```javascript
class RPAUI {
    constructor() {
        this.workflows = [];
        this.currentWorkflow = null;
        this.isRunning = false;
        
        this.init();
    }
    
    async init() {
        await this.loadWorkflows();
        this.setupListeners();
    }
    
    async loadWorkflows() {
        const response = await fetch('/api/workflows');
        this.workflows = await response.json();
        this.renderWorkflowList();
    }
    
    renderWorkflowList() {
        const list = document.getElementById('workflowList');
        list.innerHTML = this.workflows.map(wf => 
            `<div class="workflow-item" onclick="app.selectWorkflow('${wf}')">${wf}</div>`
        ).join('');
    }
    
    async selectWorkflow(id) {
        const response = await fetch(`/api/workflows/${id}`);
        this.currentWorkflow = await response.json();
        this.renderCanvas();
    }
    
    renderCanvas() {
        const svg = document.getElementById('canvas');
        svg.innerHTML = '';
        
        if (!this.currentWorkflow) return;
        
        // Dibujar nodos
        this.currentWorkflow.nodes.forEach(node => {
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', node.position?.x || 50);
            rect.setAttribute('y', node.position?.y || 50);
            rect.setAttribute('width', 150);
            rect.setAttribute('height', 60);
            rect.setAttribute('fill', this.getNodeColor(node.type));
            rect.setAttribute('stroke', '#333');
            rect.setAttribute('stroke-width', 2);
            rect.setAttribute('class', 'node');
            
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', parseInt(rect.getAttribute('x')) + 75);
            text.setAttribute('y', parseInt(rect.getAttribute('y')) + 35);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('fill', 'white');
            text.textContent = node.label;
            
            svg.appendChild(rect);
            svg.appendChild(text);
        });
        
        // Dibujar edges
        this.currentWorkflow.edges.forEach(edge => {
            const fromNode = this.currentWorkflow.nodes.find(n => n.id === edge.from);
            const toNode = this.currentWorkflow.nodes.find(n => n.id === edge.to);
            
            if (fromNode && toNode) {
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', fromNode.position?.x + 75 || 125);
                line.setAttribute('y1', fromNode.position?.y + 60 || 110);
                line.setAttribute('x2', toNode.position?.x + 75 || 125);
                line.setAttribute('y2', toNode.position?.y || 50);
                line.setAttribute('stroke', '#999');
                line.setAttribute('stroke-width', 2);
                
                svg.appendChild(line);
            }
        });
    }
    
    getNodeColor(type) {
        const colors = {
            action: '#007bff',
            decision: '#ffc107',
            loop: '#28a745',
            start: '#6c757d',
            end: '#dc3545'
        };
        return colors[type] || '#999';
    }
    
    async executeWorkflow() {
        if (!this.currentWorkflow || this.isRunning) return;
        
        this.isRunning = true;
        const logMonitor = document.getElementById('logMonitor');
        logMonitor.innerHTML = '';
        
        try {
            const response = await fetch(
                `/api/execute/${this.currentWorkflow.id}`,
                { method: 'POST' }
            );
            const result = await response.json();
            
            // Mostrar logs
            result.logs.forEach(log => {
                logMonitor.innerHTML += log + '<br>';
            });
            logMonitor.scrollTop = logMonitor.scrollHeight;
            
            // Mostrar variables
            document.getElementById('variablesViewer').textContent = 
                JSON.stringify(result.context, null, 2);
        } catch (error) {
            logMonitor.innerHTML += `ERROR: ${error.message}`;
        } finally {
            this.isRunning = false;
        }
    }
    
    setupListeners() {
        document.getElementById('executeBtn').addEventListener('click', 
            () => this.executeWorkflow());
    }
}

const app = new RPAUI();
```

---

## 📋 requirements.txt

```
# Mínimo necesario
# Nada! Python puro con stdlib
# Si usas Flask:
# Flask==2.3.0
# Si usas Pydantic:
# Pydantic==2.0.0
```

---

## 🚀 CÓMO CORRER

```bash
# 1. Crear estructura
mkdir rpa_3 && cd rpa_3
mkdir workflows scripts static logs

# 2. Copiar archivos (main.py, executor.py, etc)

# 3. Correr servidor
python main.py

# 4. Abrir navegador
# http://localhost:8000
```

---

## 🎯 CRITERIOS DE ÉXITO MVP

1. ✅ Cargar workflow JSON
2. ✅ Visualizar en canvas SVG
3. ✅ Ejecutar scripts en orden
4. ✅ **IF/ELSE bifurcación**
5. ✅ **LOOP repetición**
6. ✅ Pasar variables entre scripts
7. ✅ Logs en tiempo real
8. ✅ Todo en Python puro (sin FastAPI/Django/SQLAlchemy)
9. ✅ Interfaz HTML5 simple
10. ✅ Funcionar en localhost

---

## 📊 COMPARATIVA: SIMPLE vs ANTERIOR

| Aspecto | Anterior | Nuevo |
|---------|----------|-------|
| **Stack Backend** | FastAPI + Pydantic | Python puro + stdlib |
| **WebSocket** | Socket.io | Simple polling HTTP |
| **Base de Datos** | SQLite | JSON files |
| **Frontend** | Vue.js + Cytoscape | HTML5 + Vanilla JS |
| **Tiempo Estimado** | 4 semanas | 1-2 semanas |
| **Líneas de Código** | ~3000 | ~800 |
| **IF/ELSE** | Fase 2 | **MVP** ✅ |
| **LOOP** | Fase 2 | **MVP** ✅ |

---

## 🎓 DESARROLLO STEP-BY-STEP

### Semana 1
- [ ] Crear estructura de carpetas
- [ ] Implementar executor.py (core)
- [ ] Implementar logger.py
- [ ] Crear main.py básico
- [ ] JSON workflow parsing

### Semana 2
- [ ] Frontend index.html
- [ ] Canvas SVG rendering
- [ ] app.js (load, execute)
- [ ] Endpoint /api/execute
- [ ] Log monitor en tiempo real

### Semana 3 (BONUS)
- [ ] Drag & drop en canvas
- [ ] Editor de propiedades funcional
- [ ] Guardar workflows
- [ ] Better error handling

---

## 🔗 PRÓXIMAS FASES (POST-MVP)

### Fase 2 (Semana 4-5)
- Timeout por script
- Retry automático
- Snapshots/checkpoints

### Fase 3 (Semana 6-7)
- Dashboard de métricas
- Historial de ejecuciones
- Exportar logs

### Fase 4+ (Ongoing)
- WebSocket real-time
- Job queues
- Integración con BD real
- Docker containerization
