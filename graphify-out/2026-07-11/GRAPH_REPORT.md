# Graph Report - .  (2026-07-11)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2141 nodes · 3744 edges · 158 communities (137 shown, 21 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 572 edges (avg confidence: 0.63)
- Token cost: 9,188 input · 1,767 output

## Graph Freshness
- Built from commit: `6bc8f91e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Telegram Bot Service
- Module and Script Generator
- OCR Diagnostic Search
- Doctor Database Search
- PACS Automation Workflow
- Doctor Search Testing
- Workflow Command Pattern
- LLM UI Panel
- Action Execution Framework
- OCR Action Library
- RIS Automation Workflow
- Doctor Database Connector
- OCR Engine Integration
- OCR Pattern Matching
- AI Pathology Detection
- Workflow Node Models
- Script Debugger Worker
- Immutable Action Executor
- Structured OCR Search
- Automated Workflow Execution
- Workflow Editor UI
- RPA Visual Feedback
- Document Viewer Automation
- Workflow Canvas Widgets
- Doctor Matcher Service
- OCR Code Generator
- Debugger Overlay UI
- Clipboard Text Automation
- Word Toolbar Automation
- Node Properties Panel
- RPA Input Recorder
- Web Automation Scripting
- Enhanced Structured Search
- Node Palette UI
- Python Script Generator
- Web Replay System
- Selenium Web Recorder
- Exam Search Automation
- Web Automation Controller
- Nested Workflow Nodes
- Operations Control Panel
- SharePoint Data Sync
- Adjusted OCR Search
- Nemotron OCR Verification
- Nemotron Table Search
- Pathology Report Generator
- Dashboard Analytics Panel
- Robust Click Automation
- PDF Doctor Extractor
- Workflow Logging System
- Workflow Serialization
- OCR Status Updater
- OCR Configuration Panel
- Critical Pathology Automation
- Main GUI Application
- Web Recording Stats
- Python Script Optimizer
- Error Handling Service
- Structured Search Normalization
- Script Debugging Panel
- Browser Recording Worker
- Syntax Highlighting UI
- Patient Search Automation
- Visual OCR Verification
- Visual Similarity Verification
- Web Record Panel
- Workflow Utility Nodes
- API Key Validator
- Word Toolbar Actions
- Robust RPA Execution
- Click and Sort Automation
- PACS User Login
- Recording Replay Panel
- Workflow Test Suite
- Recorder GUI Tool
- VPN Connectivity Monitor
- Carestream Viewer Automation
- Pathology Automation Script
- RIS Startup Verification
- Dynamic RIS Verification
- Dashboard Data Loading
- Mock Automation Feedback
- System Configuration Manager
- Generic Recording Automation
- Non-Critical Pathology Automation
- Report Recording Automation
- KSY Automation Script
- Pending Task Automation
- Windows Element Selector
- PACS Application Manager
- Workflow Edge UI
- Combobox Click Test
- Recording Player Setup
- Selector Strategy Pattern
- Mouse Movement Simulator
- Recording Control Panel
- RIS Window Management
- Action List Optimizer
- RTF Clipboard Utilities
- OpenRouter Model Checker
- LLM Model Validation
- Database Connection Management
- System Health Monitoring
- Execution Decorators
- Pathology Text Processing
- AI Pathology Search
- Database Record Creation
- Reference Image Capture
- Code Step Highlighting
- Project Structure Setup
- OCR Viewer Diagnostics
- GUI Worker Termination
- Generic Type Definitions
- Workflow Validation Logic
- Generic Type Definitions
- Generic Type Definitions
- Data Table Handling
- Core Execution Engine
- Qt Graphics Ellipse
- Qt Graphics Path
- Qt Graphics Rectangle
- Qt Graphics View
- Qt Coordinate Point
- Qt Thread Management
- Qt Widget Component

## God Nodes (most connected - your core abstractions)
1. `ActionExecutor` - 73 edges
2. `Action` - 64 edges
3. `OCREngine` - 61 edges
4. `VisualFeedback` - 55 edges
5. `WorkflowPanelV2` - 43 edges
6. `handle_error_and_exit()` - 41 edges
7. `setup_logging()` - 35 edges
8. `ActionType` - 34 edges
9. `DebugOverlay` - 31 edges
10. `Node` - 30 edges

## Surprising Connections (you probably didn't know these)
- `PatologiaCriticaConCierreOkAutomation` --uses--> `Action`  [INFERRED]
  debug_output.py → rpa_framework/core/action.py
- `PatologiaCriticaConCierreOkAutomation` --uses--> `ActionType`  [INFERRED]
  debug_output.py → rpa_framework/core/action.py
- `PatologiaCriticaConCierreOkAutomation` --uses--> `ActionExecutor`  [INFERRED]
  debug_output.py → rpa_framework/core/executor.py
- `debug_ocr_variants()` --calls--> `OCREngine`  [INFERRED]
  debug_tep.py → rpa_framework/ocr/engine.py
- `test_ocr()` --calls--> `OCREngine`  [INFERRED]
  eval_ocr.py → rpa_framework/ocr/engine.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **RPA Workflow Node Types** — rpa_framework_workflows_readme_action_node, rpa_framework_workflows_readme_decision_node, rpa_framework_workflows_readme_loop_node, rpa_framework_core_database_node [EXTRACTED 0.90]

## Communities (158 total, 21 thin omitted)

### Community 0 - "Telegram Bot Service"
Cohesion: 0.07
Nodes (52): get_last_update_id(), monitor_stop_signal(), Ejecuta la validación y actualización diaria de modelos LLM en segundo plano., Monitorea si la GUI solicita detener la ejecución., rehabilitar_ultimo_registro(), run_llm_daily_checker(), run_workflow_headless(), save_last_update_id() (+44 more)

### Community 1 - "Module and Script Generator"
Cohesion: 0.06
Nodes (36): ModuleGenerator, Path, Generador de módulos., Genera módulo independiente sin dependencias externas., Genera módulo independiente., QuickScriptGenerator, Generador de scripts rápidos., Genera script ejecutable. (+28 more)

### Community 2 - "OCR Diagnostic Search"
Cohesion: 0.07
Nodes (29): Diagnóstico final: simula exactamente lo que hace busqueda_triple_text_only.py s, BusquedaTextOnly, main(), Guarda imagen marcando el punto de clic con cruceta, círculo y coordenadas., Actualiza el estado a Error en la base de datos., Actualiza el campo coordenada en la base de datos., Busca en ris.sinonimos si existe alguna coincidencia para este examen/OCR., Guarda un nuevo registro en ris.sinonimos. (+21 more)

### Community 3 - "Doctor Database Search"
Cohesion: 0.07
Nodes (23): BuscadorBaseDatos, BuscadorDoctorSelenium, espera_con_countdown(), main(), Intenta resaltar visualmente el elemento usando VisualFeedback, Busca el último vínculo de doctor (patrón 'Folio / Nombre') en la tabla y le hac, Verifica si la tabla muestra el mensaje de 'Sin resultados'.         Retorna Tru, Cierra el navegador (solo si fue abierto por este módulo) (+15 more)

### Community 4 - "PACS Automation Workflow"
Cohesion: 0.08
Nodes (16): Automation1, main(), Automatización generada: 1, Actualiza el estado en la BD, Obtiene la patología detectada de la BD., Valida si el texto OCR coincide semánticamente con el objetivo usando LLM., Busca y enfoca la ventana de Carestream Vue PACS., Detiene la ejecución con un error y actualiza la BD. (+8 more)

### Community 5 - "Doctor Search Testing"
Cohesion: 0.08
Nodes (21): BuscadorBaseDatosTest, BuscadorDoctorSeleniumTest, main(), pedir_link_usuario(), Actualiza doctor y credenciales con datos dummy,         ya que el usuario saltó, Muestra un popup simple con Tkinter para no depender de la consola, Función principal (Modo Prueba), Se conecta al navegador y abre el PDF ingresado manualmente por el usuario. (+13 more)

### Community 6 - "Workflow Command Pattern"
Cohesion: 0.09
Nodes (16): QUndoCommand, Database Node, Edge, Workflow Executor, AddNodeCommand, ConnectionCommand, DeleteNodeCommand, ModifyPropertyCommand (+8 more)

### Community 7 - "LLM UI Panel"
Cohesion: 0.10
Nodes (15): QObject, QTableWidgetItem, AutoReplaceSignals, AutoReplaceWorker, LLMPanel, QThread, QWidget, Panel de mantenimiento de modelos LLM. (+7 more)

### Community 8 - "Action Execution Framework"
Cohesion: 0.13
Nodes (9): ActionType, Enum, Dataclass Action - Inmutable., log_execution_time(), ActionExecutor - Ejecuta acciones con retry., Decorator para loguear tiempo., RecordingPlayer - Reproduce grabación., Logging estructurado. (+1 more)

### Community 9 - "OCR Action Library"
Cohesion: 0.08
Nodes (17): OCRActions, ndarray, Busca texto y hace click en él.                  Args:             search_ter, Acciones de alto nivel basadas en OCR.          Integra Engine + Matcher para, Double-click en texto encontrado., Right-click en texto encontrado., Busca texto, hace triple-click para seleccionar.                  Args:, Busca, selecciona y copia texto.                  Args:             search_te (+9 more)

### Community 10 - "RIS Automation Workflow"
Cohesion: 0.09
Nodes (16): Automation1, main(), Automatización generada: 1, Actualiza el estado en la BD, Obtiene la patología detectada de la BD., Valida si el texto OCR coincide semánticamente con el objetivo usando LLM., Busca y enfoca la ventana de Carestream Vue PACS., Intenta traer el RIS al frente (Carestream o Philips). No es error si falla. (+8 more)

### Community 11 - "Doctor Database Connector"
Cohesion: 0.09
Nodes (19): BuscadorBaseDatos, BuscadorDoctorSelenium, espera_con_countdown(), main(), Intenta resaltar visualmente el elemento usando VisualFeedback, Busca el primer vínculo de doctor (patrón 'Folio / Nombre') en la tabla y le hac, Verifica si la tabla muestra el mensaje de 'Sin resultados'.         Retorna Tr, Extrae nombre de médico de la tabla dinámica del RIS     usando Selenium y cone (+11 more)

### Community 12 - "OCR Engine Integration"
Cohesion: 0.09
Nodes (19): debug_ocr_variants(), test_ocr(), OCREngine, Image, ndarray, Extrae texto con ubicación (bounding boxes).                  Args:, Redimensiona la imagen si excede las dimensiones máximas.         Ayuda a reduc, Extracción con EasyOCR (+11 more)

### Community 13 - "OCR Pattern Matching"
Cohesion: 0.07
Nodes (20): Inicializar acciones OCR.                  Args:             ocr_engine: Inst, OCRMatcher, Calcular similitud fuzzy entre dos términos.                  Usa múltiples al, Motor de búsqueda y matching para resultados OCR.          Soporta:     - Bús, Busca por patrón regex.                  Útil para:         - Emails: r'[\\w\, Busca múltiples términos a la vez.                  Args:             text_li, Busca texto más cercano a un punto de referencia.                  Útil para c, Inicializar matcher.                  Args:             threshold: Umbral mín (+12 more)

### Community 14 - "AI Pathology Detection"
Cohesion: 0.09
Nodes (28): actualizar_registro_acciones(), analizar_diagnosticos(), _buscar_en_lista_normalizado(), cargar_datos(), conectar_bd(), consultar_llm_patologia(), _consultar_modelo_llm(), detectar_patologia() (+20 more)

### Community 15 - "Workflow Node Models"
Cohesion: 0.11
Nodes (22): AnnotationNode, Any, Nodo de anotación/comentario para documentación, ActionNode, DecisionNode, LoopNode, Node, Nodo de decisión (IF/ELSE) (+14 more)

### Community 16 - "Script Debugger Worker"
Cohesion: 0.09
Nodes (15): DebugWorker, QThread, QThread que ejecuta un script RPA paso a paso.      Señales:         script_r, Avanzar al siguiente paso., Retroceder un paso: reinicia el proceso desde el inicio         y avanza automá, Reiniciar desde el paso 1., Activar/desactivar ejecución continua (▶ Ejecutar)., Activar/desactivar modo paso a paso automático (⏯). (+7 more)

### Community 17 - "Immutable Action Executor"
Cohesion: 0.13
Nodes (14): Action, Acción inmutable con metadatos completos., ActionExecutor, Doble Click con fallback., Sostiene el clic durante un tiempo (clic largo)., Type con selector o foco., Ejecuta combinación de teclas., Ejecuta acciones con retry y validación. (+6 more)

### Community 18 - "Structured OCR Search"
Cohesion: 0.12
Nodes (11): BusquedaEstructurada, BusquedaNemotronTabla, main(), datetime, ndarray, Normaliza texto: minúsculas, sin acentos, soloc alfanumérico y espacios simples., Agrupa textos por proximidad Y., Aplica preprocesamiento optimizado para OCR. (+3 more)

### Community 19 - "Automated Workflow Execution"
Cohesion: 0.10
Nodes (13): Automation1, main(), Automatización generada: 1, Actualiza el estado en la BD, Obtiene la patología detectada de la BD., Valida si el texto OCR coincide semánticamente con el objetivo usando LLM., Normaliza texto para comparación., Agrupa bloques de texto OCR en líneas coherentes. (+5 more)

### Community 20 - "Workflow Editor UI"
Cohesion: 0.12
Nodes (9): LogWindow, QWidget, Workflow Editor V2 - Diseño Moderno (3 Paneles)     Izquierda: Paleta | Centro:, Called when worker finished (success or error), Handle link creation from Canvas, Append a message to the log widget with color formatting, Ventana flotante para mostrar el log, Handle link deletion from Canvas (+1 more)

### Community 21 - "RPA Visual Feedback"
Cohesion: 0.08
Nodes (11): execute_clicks(), Provee feedback visual en pantalla para acciones de RPA.     - Resaltado de cli, Muestra un mensaje flotante (overlay) en la parte superior de la pantalla., Muestra un mensaje que permanece hasta que se llama a hide_persistent_message., Oculta un mensaje persistente por su nombre., Muestra una cuenta regresiva visual. Bloqueante visualmente (en su hilo), pero n, Reemplazo visual para time.sleep.         Muestra countdown y bloquea el hilo a, Muestra un diálogo enriquecido cuando falla la búsqueda OCR/LLM.         Presen (+3 more)

### Community 22 - "Document Viewer Automation"
Cohesion: 0.11
Nodes (27): activar_ventana_carestream(), _buscar_frase_en_lineas(), buscar_por_imagen_template(), buscar_texto_en_pantalla(), capturar_pantalla(), db_update(), enviar_alerta_todos(), execute() (+19 more)

### Community 23 - "Workflow Canvas Widgets"
Cohesion: 0.10
Nodes (17): EdgeGraphicsItem, NodeGraphicsItem, QGraphicsPathItem, QGraphicsRectItem, QGraphicsView, QPointF, Widgets personalizados para la interfaz de workflows del RPA Framework 3.  Est, Override para dibujar flecha (+9 more)

### Community 24 - "Doctor Matcher Service"
Cohesion: 0.09
Nodes (15): Logger, create_test_data(), DoctorMatcher, Carga todos los médicos en caché en memoria (incluyendo Integra credentials)., Normaliza un nombre de médico.                  - Minúsculas         - Quita, Calcula similitud entre dos strings.                  Usa RapidFuzz si está di, Busca un médico por nombre (OCR u otro texto).                  Estrategia:, Retorna lista de todos los médicos en caché (incluyendo credenciales Integra). (+7 more)

### Community 25 - "OCR Code Generator"
Cohesion: 0.10
Nodes (14): OCRCodeGenerator, Generador de código Python para acciones OCR.          Produce módulos ejecuta, Generar módulo para double click., Inicializar generador.                  Args:             engine: Motor OCR a, Generar módulo para click derecho., Generar módulo para buscar y copiar texto., Retorna el fragmento de código para tracking de BD., Generar módulo para seleccionar texto. (+6 more)

### Community 26 - "Debugger Overlay UI"
Cohesion: 0.16
Nodes (8): QDialog, DebugOverlay, ▶ Ejecutar: modo continuo sin pausa., ⏯ Paso a Paso: avance automático con delay., ⏭ Siguiente paso manual., 🔄 Reiniciar desde el paso 1., 💾 Guardar cambios y reiniciar desde el paso 1., Ventana flotante de depuración.      Parámetros:         script_path: ruta al

### Community 27 - "Clipboard Text Automation"
Cohesion: 0.12
Nodes (18): automatizar_buscar_toolbar(), buscar_bloque_toolbar(), enviar_alerta_todos(), humanized_click(), main(), Coloca contenido RTF y texto plano en el portapapeles., Automatización generada: test1, Actualiza el estado en la BD (+10 more)

### Community 28 - "Word Toolbar Automation"
Cohesion: 0.13
Nodes (19): automatizar_buscar_toolbar(), buscar_bloque_toolbar(), ejecutar_cierra_visor(), enviar_alerta_todos(), guardar_debug_screenshot(), humanized_click(), main(), Mueve el ratón a (x,y), hace una pausa (hover) y realiza el clic (sostenido o no (+11 more)

### Community 29 - "Node Properties Panel"
Cohesion: 0.11
Nodes (10): PropertiesPanel, QWidget, Panel de Propiedades para editar nodos.     Se muestra solo cuando hay un nodo, Muestra u oculta campos de loop según el tipo, Muestra u oculta campos de comando según el tipo, Conecta todos los widgets de entrada al trigger de autoguardado, Reinicia el timer de autoguardado, Carga los datos de un nodo en el formulario (+2 more)

### Community 30 - "RPA Input Recorder"
Cohesion: 0.12
Nodes (11): Captura typing y actualiza modificadores., Actualiza estado de modificadores al soltar., Detecta si es una combinación de teclas importante., Guarda una combinación de teclas., Captura acciones con selectores inteligentes., Obtiene el contenido del portapapeles., Guarda acción de typing usando contexto del último click., Guarda acción de tecla especial. (+3 more)

### Community 31 - "Web Automation Scripting"
Cohesion: 0.13
Nodes (12): main(), Auto-generated Web Automation Script Generated: 2025-12-30T09:27:43.927192 Tot, Updates database state on script completion or error, Configures and starts the browser with fast port detection, Finds an element by XPath with CSS fallback, Intenta resaltar visualmente el elemento usando VisualFeedback, Saves a screenshot from base64, Main execution entry point (+4 more)

### Community 32 - "Enhanced Structured Search"
Cohesion: 0.14
Nodes (11): BusquedaEstructurada, main(), Normaliza texto: minúsculas, sin acentos, soloc alfanumérico y espacios simples., Convierte a formato título (Primera letra mayúscula de cada palabra)., Calcula similitud entre dos strings (0-1)., Agrupa textos por proximidad Y., Aplica preprocesamiento optimizado para OCR., Ejecuta OCR con múltiples configuraciones y combina resultados. (+3 more)

### Community 33 - "Node Palette UI"
Cohesion: 0.16
Nodes (12): NodeCard, QWidget, Tarjeta de nodo arrastrable para la paleta, get_all_nodes(), NodeDefinition, Return flat list of all nodes, Definition of a node type for the palette, NodePalette (+4 more)

### Community 34 - "Python Script Generator"
Cohesion: 0.12
Nodes (11): Path, Genera scripts Python autosuficientes para reproducir acciones UI., Args:             actions: Lista de acciones grabadas             module_name:, Genera el script Python ejecutable., Genera el código para ejecutar cada acción., Genera código para acción de click., Genera código para acción de typing., Genera código para acción de tecla especial. (+3 more)

### Community 35 - "Web Replay System"
Cohesion: 0.13
Nodes (8): Reproduce grabaciones web capturadas con WebRecorder., Muestra un indicador visual en el navegador del paso actual., WebReplayer, OCRInitWorker, QThread, Worker para inicializar OCR en segundo plano., Worker para reproducción sin bloquear UI., ReplayWorker

### Community 36 - "Selenium Web Recorder"
Cohesion: 0.13
Nodes (9): Captures web actions using Selenium, Executes script safely, handling unexpected alerts., Starts Chrome browser (Attaches to Port 9222 or Launches new), Monitoring thread to capture actions continuously, Captures actions from the browser, Creates a WebAction object from captured data, Captures a square area around the coordinates, Adds action to the list (+1 more)

### Community 37 - "Exam Search Automation"
Cohesion: 0.20
Nodes (6): BusquedaPorExamenHecho, main(), Preprocesa una franja de fila para OCR., OCR completo sobre una franja de imagen., Usa Tesseract image_to_data para encontrar bounding boxes de palabras         qu, Recorta una franja horizontal de row_height px centrada en y_center.

### Community 38 - "Web Automation Controller"
Cohesion: 0.13
Nodes (11): main(), Auto-generated Web Automation Script Generated: 2026-01-01T18:05:43.911047 Tot, Configures and starts the browser with fast port detection, Finds an element by XPath with CSS fallback, Intenta resaltar visualmente el elemento usando VisualFeedback, Saves a screenshot from base64, Main execution entry point, Auto-generated Web Automation Class (+3 more)

### Community 39 - "Nested Workflow Nodes"
Cohesion: 0.15
Nodes (7): Any, Nodo que ejecuta otro workflow anidado, Convierte el workflow a diccionario para serialización, Crea un workflow desde un diccionario, Convierte el nodo a diccionario para serialización, Crea un nodo desde un diccionario, WorkflowNode

### Community 40 - "Operations Control Panel"
Cohesion: 0.14
Nodes (6): OperacionesPanel, QWidget, Muestra u oculta campos según el modo de loop seleccionado., Chequea si el servicio de Telegram está ejecutando un flujo mediante el archivo, Detiene la ejecución actual del worker local o del servicio en background., Panel personalizado con botones de operación solicitados.

### Community 41 - "SharePoint Data Sync"
Cohesion: 0.15
Nodes (19): _descargar_con_adfs_cookies(), _descargar_con_graph_api(), _descargar_con_sp_token(), descargar_excel_sharepoint(), _encode_sharing_url(), leer_medicos_excel(), main(), _normalizar_nombre() (+11 more)

### Community 42 - "Adjusted OCR Search"
Cohesion: 0.17
Nodes (7): BusquedaAjustada, main(), ndarray, Devuelve datos estructurados de OCR (cajas)., Obtiene un recorte de 20px de alto centrado en y_center., Consulta al LLM si el texto/imagen coincide con el diagnóstico., Obtiene diagnóstico y fecha desde la base de datos.

### Community 43 - "Nemotron OCR Verification"
Cohesion: 0.17
Nodes (7): BusquedaAjustada, main(), ndarray, Devuelve datos estructurados de OCR (cajas)., Obtiene un recorte de 20px de alto centrado en y_center., Consulta al LLM si el texto/imagen coincide con el diagnóstico., Obtiene diagnóstico y fecha desde la base de datos.

### Community 44 - "Nemotron Table Search"
Cohesion: 0.15
Nodes (12): BusquedaNemotronTabla, main(), datetime, ndarray, Captura la región especificada de la pantalla.                  Returns:, Codifica imagen OpenCV a base64 para enviar a OpenRouter.                  Arg, Construye prompt especializado en terminología médica para Nemotron., Realiza llamada a Nemotron via OpenRouter API.                  Args: (+4 more)

### Community 45 - "Pathology Report Generator"
Cohesion: 0.16
Nodes (19): actualizar_registro_acciones(), analizar_diagnosticos(), cargar_datos(), conectar_bd(), detectar_patologia(), generar_reporte(), main(), normalizar_texto() (+11 more)

### Community 46 - "Dashboard Analytics Panel"
Cohesion: 0.14
Nodes (11): main(), Test script for the new dashboard panel, ChartWidget, DashboardPanel, QWidget, Plot a bar chart from a dictionary, Plot a pie chart from a dictionary, Panel with execution statistics from registro_acciones table (+3 more)

### Community 47 - "Robust Click Automation"
Cohesion: 0.13
Nodes (11): main(), Ejecuta un clic resolviendo primero las coordenadas si es un selector., Conecta a la aplicación objetivo de forma robusta., Ejecuta todas las acciones grabadas., Feedback visual integrado para ser independiente del framework., Punto de entrada principal., Automatización generada: shotta, Actualiza el estado en la BD (+3 more)

### Community 48 - "PDF Doctor Extractor"
Cohesion: 0.17
Nodes (8): BuscadorBaseDatosPDF, ExtractorPDFDoctor, main(), Conecta al navegador Chrome existente en el puerto debug, Busca una pestaña que parezca ser un PDF (blob: o .pdf),         descarga el co, Clase para interactuar con la base de datos de RIS, Actualiza el estado de la ejecución en la base de datos, Actualiza numero_documento, diagnostico, examen, url y fecha_agendada en registr

### Community 49 - "Workflow Logging System"
Cohesion: 0.14
Nodes (8): Logger simple para el sistema de workflows.  Proporciona logging tanto a conso, Logger simple para workflows, Inicializa el logger.                  Args:             filepath: Ruta al ar, Registra un mensaje.                  Args:             message: Mensaje a re, Devuelve todos los logs registrados, Limpia los logs en memoria, Devuelve los últimos N logs.                  Args:             count: Número, WorkflowLogger

### Community 50 - "Workflow Serialization"
Cohesion: 0.13
Nodes (11): Workflow completo con nodos y conexiones, Obtiene un nodo por su ID, Obtiene el ID del siguiente nodo conectado, Obtiene el nodo de inicio, Guarda el workflow en un archivo JSON, Workflow, ConsoleNoiseFilter, main() (+3 more)

### Community 51 - "OCR Status Updater"
Cohesion: 0.15
Nodes (11): ActualizaEstadoAutomation, humanized_click(), main(), Busca la palabra 'Aprobado' en una franja de 20px de altura en la coordenada Y d, Conecta a la aplicación objetivo de forma robusta., Ejecuta todas las acciones grabadas., Punto de entrada principal., Realiza un movimiento de mouse humanizado hacia (x, y) y hace click u opcionalme (+3 more)

### Community 52 - "OCR Configuration Panel"
Cohesion: 0.16
Nodes (6): OCRPanel, QWidget, Tab para funcionalidades OCR en la GUI (PyQt6)., Habilitar/deshabilitar controles dependientes de init., Evento al mostrar la pestaña: Auto-iniciar OCR si es necesario., Guardar el código generado en un archivo .py

### Community 53 - "Critical Pathology Automation"
Cohesion: 0.17
Nodes (10): main(), PatologiaCriticaConCierreOkAutomation, Conecta a la aplicación objetivo., Ejecuta todas las acciones grabadas., Punto de entrada principal., Automatización generada: patologia_critica,_con_cierre_ok, Actualiza el estado en la BD, Obtiene la patología detectada de la BD para el registro en proceso. (+2 more)

### Community 54 - "Main GUI Application"
Cohesion: 0.18
Nodes (8): ConsoleNoiseFilter, main(), MainWindow, QMainWindow, cleanup_old_logs(), PeriodicCleanup, Elimina archivos de imagen (.png, .jpg, .jpeg) en la carpeta log      y subcarpe, Clase para manejar la limpieza periódica alineada con el reloj.

### Community 55 - "Web Recording Stats"
Cohesion: 0.16
Nodes (8): ElementInfo, Any, Captured element information, # IMPORTANT: When using debuggerAddress, most other options cause 'invalid argum, Starts recording actions, Structure to store a browser action, RecordingStats, WebAction

### Community 56 - "Python Script Optimizer"
Cohesion: 0.18
Nodes (8): PythonScriptGenerator, Generates Python scripts from captured actions, Generates the complete script, Generates the action code with smart optimization, Checks if action functionality targets a Select2 search input, Generates robust code for Select2 interaction, Converts an action to Python code, Main automation class

### Community 57 - "Error Handling Service"
Cohesion: 0.17
Nodes (14): execute_ocr_click_0(), Acción OCR: Click en texto 'estado'          Busca el texto 'estado' en la pan, _consultar_registro(), _formatear_mensaje(), _get_telegram(), handle_error_and_exit(), _marcar_error(), Genera el texto del mensaje Telegram con formato HTML. (+6 more)

### Community 58 - "Structured Search Normalization"
Cohesion: 0.18
Nodes (8): BusquedaEstructurada, main(), Normaliza texto: minúsculas, sin acentos, soloc alfanumérico y espacios simples., Convierte a formato título (Primera letra mayúscula de cada palabra)., Calcula similitud entre dos strings (0-1)., Agrupa textos por proximidad Y., Ejecuta búsqueda estructurada en 3 pasos., Obtiene diagnóstico y fecha desde la base de datos.

### Community 59 - "Script Debugging Panel"
Cohesion: 0.18
Nodes (8): extract_steps_from_script(), Parsea el script y devuelve una lista de pasos como:         (linea_inicio, lin, DebugPanel, QWidget, Carga la lista de scripts .py disponibles., Actualiza la info cuando se selecciona un script., Panel de selección y lanzamiento del depurador de scripts., Lanza el DebugOverlay para el script seleccionado.

### Community 60 - "Browser Recording Worker"
Cohesion: 0.14
Nodes (6): BrowserWorker, FloatingControlWindow, QThread, Thread to handle browser startup to avoid blocking UI, Starts browser and shows floating window, Floating window to control recording (PyQt6 impl)

### Community 61 - "Syntax Highlighting UI"
Cohesion: 0.14
Nodes (7): QFrame, QSyntaxHighlighter, QTextDocument, PythonHighlighter, Resaltado de sintaxis Python básico., Conecta las señales del worker a los slots del overlay., Carga el código fuente en el editor.

### Community 62 - "Patient Search Automation"
Cohesion: 0.19
Nodes (9): BusquedaPacienteAutomation, main(), Conecta a la aplicación objetivo., Ejecuta todas las acciones grabadas., Punto de entrada principal., Automatización generada: busqueda_paciente, Actualiza el estado en la BD, Actualiza la BD con el error, envía Telegram y detiene la ejecución. (+1 more)

### Community 63 - "Visual OCR Verification"
Cohesion: 0.19
Nodes (8): main(), Verifica si el proceso está en ejecución., Toma captura de la región y la compara con la referencia vía OCR., Automatización: verifica_inicio (Versión 3 Visual OCR), Extrae el texto de la imagen de referencia una sola vez., Actualiza el estado en la BD, Busca y enfoca la ventana del RIS., VerificaInicioVisualOCR

### Community 64 - "Visual Similarity Verification"
Cohesion: 0.19
Nodes (8): main(), Verifica si el proceso está en ejecución., Toma captura de la región y la compara estructuralmente con la referencia., Automatización: verifica_inicio (Versión 4 Similitud Visual), Carga la imagen de referencia en escala de grises., Actualiza el estado en la BD, Busca y enfoca la ventana del RIS., VerificaInicioSimilitud

### Community 65 - "Web Record Panel"
Cohesion: 0.17
Nodes (4): QWidget, Main Panel for Web Recorder, Executes the last generated script for validation, WebRecordPanel

### Community 66 - "Workflow Utility Nodes"
Cohesion: 0.19
Nodes (8): Nodo de anotación para workflows RPA Framework 3.  Este módulo define el Annot, DelayNode, Any, Nodo para pausar la ejecución por un tiempo determinado, NodeType, Enum, Modelos para el sistema de workflows RPA Framework 3.  Este módulo define las, Tipos de nodos soportados

### Community 67 - "API Key Validator"
Cohesion: 0.20
Nodes (9): enviar_alerta_todos(), KeyUpdateWindow, main(), Verifica si la API Key es válida haciendo una consulta a OpenRouter., Actualiza la clave en el archivo .env., test_api_key(), update_env_key(), enviar_alerta_todos() (+1 more)

### Community 68 - "Word Toolbar Actions"
Cohesion: 0.21
Nodes (13): automatizar_buscar_toolbar(), buscar_bloque_toolbar(), enviar_alerta_todos(), humanized_click(), obtener_info_bloque(), pegar_texto_todas_las_tecnicas(), Realiza una acción en el bloque de barra encontrado.          Args:         b, Intenta pegar texto usando 3 técnicas distintas para asegurar robustez. (+5 more)

### Community 69 - "Robust RPA Execution"
Cohesion: 0.18
Nodes (7): CriticaAutomation, Asegura el foco del elemento antes de ejecutar la acción., Ejecuta los movimientos automatizados de forma robusta., Automatización simplificada: critica, Mueve, resalta con círculo rojo y hace clic sostenido., Conecta a la aplicación de forma robusta., VisualFeedbackLocal

### Community 70 - "Click and Sort Automation"
Cohesion: 0.22
Nodes (8): ClicYOrdenarAutomation, main(), Conecta a la aplicación objetivo., Ejecuta todas las acciones grabadas., Punto de entrada principal., Automatización generada: clic_y_ordenar, Actualiza el estado en la BD, Actualiza la BD con el error y detiene la ejecución inmediatamente.

### Community 71 - "PACS User Login"
Cohesion: 0.21
Nodes (8): IngresaUserPacsAutomation, main(), Ejecuta todas las acciones grabadas., Punto de entrada principal., Automatización generada: ingresa_user_pacs, Actualiza el estado en la BD, Obtiene las credenciales de la BD, Conecta a la aplicación objetivo (Carestream Vue PACS).

### Community 72 - "Recording Replay Panel"
Cohesion: 0.21
Nodes (6): QListWidgetItem, QWidget, Carga lista de grabaciones desde el directorio principal recursivamente., Panel para reproducir., Elimina la grabación seleccionada físicamente., ReplayPanel

### Community 73 - "Workflow Test Suite"
Cohesion: 0.20
Nodes (9): Carga un workflow desde un archivo JSON, Ejecuta el workflow loop.json con las opciones avanzadas configuradas en el pane, main(), Test script para validar el WorkflowExecutor.  Este script carga y ejecuta el, Ejecuta todos los tests, Prueba la carga de un workflow desde JSON, Prueba la ejecución del workflow, test_workflow_execution() (+1 more)

### Community 74 - "Recorder GUI Tool"
Cohesion: 0.23
Nodes (4): Guarda grabación a JSON., GUI simple para grabación., Inicia GUI (tkinter)., RecorderGUI

### Community 75 - "VPN Connectivity Monitor"
Cohesion: 0.27
Nodes (11): abrir_globalprotect(), db_update(), enviar_alerta_todos(), handle_error_and_exit(), main(), mostrar_popup_vpn(), Verifica si la VPN de Palo Alto está activa buscando una interfaz      con IP e, Inicia la aplicación GlobalProtect de Palo Alto. (+3 more)

### Community 76 - "Carestream Viewer Automation"
Cohesion: 0.24
Nodes (11): activar_ventana_carestream(), buscar_imagen_visor(), db_update(), enviar_alerta_todos(), execute(), humanized_click(), Busca la imagen en la pantalla usando MULTI-SCALE MATCHING y DOBLE CONFIRMACIÓN., Mueve el raton, destaca la zona y hace clic sostenido. (+3 more)

### Community 77 - "Pathology Automation Script"
Cohesion: 0.21
Nodes (8): main(), PatologiaCritica, Punto de entrada principal., Automatización generada: patologia_critica_(sin_guardar), Actualiza el estado en la BD, Conecta a la aplicación objetivo., Ejecuta todas las acciones grabadas., SinGuardar

### Community 78 - "RIS Startup Verification"
Cohesion: 0.23
Nodes (7): main(), Punto de entrada principal., Automatización: verifica_inicio, Actualiza el estado en la BD, Intenta traer 'Carestream RIS' al frente. No es error si falla., Busca el patrón de inicio en pantalla con reintentos., VerificaInicioAutomation

### Community 79 - "Dynamic RIS Verification"
Cohesion: 0.23
Nodes (7): main(), Punto de entrada principal., Automatización: verifica_inicio (Versión 2 Dinámica), Actualiza el estado en la BD, Intenta traer el RIS al frente (Carestream o Philips). No es error si falla., Busca el programa en ejecución comprobando el estado de su ventana principal., VerificaInicioAutomationV2

### Community 80 - "Dashboard Data Loading"
Cohesion: 0.18
Nodes (6): Plot a line chart for temporal data, Get database connection, Set date filters to today and reload, Load data from database and update UI, Update UI when no data is available, Update the card value

### Community 81 - "Mock Automation Feedback"
Cohesion: 0.23
Nodes (3): MockAutomation, Mueve, resalta con círculo rojo y hace clic sostenido., VisualFeedbackLocal

### Community 82 - "System Configuration Manager"
Cohesion: 0.18
Nodes (10): get_directory(), get_gui_config(), get_ocr_config(), Obtener configuración OCR actual, Obtener configuración GUI actual, Obtener ruta de un directorio, Validar que engine es soportado, Validar que idioma es soportado (+2 more)

### Community 83 - "Generic Recording Automation"
Cohesion: 0.24
Nodes (7): Grabacion1Automation, main(), Automatización generada: grabacion1, Punto de entrada principal., Actualiza el estado en la BD, Conecta a la aplicación objetivo., Ejecuta todas las acciones grabadas.

### Community 84 - "Non-Critical Pathology Automation"
Cohesion: 0.24
Nodes (7): GrabacionPatologiaNoCriticaAutomation, main(), Punto de entrada principal., Automatización generada: grabacion_patologia_no_critica, Actualiza el estado en la BD, Conecta a la aplicación objetivo., Ejecuta todas las acciones grabadas.

### Community 85 - "Report Recording Automation"
Cohesion: 0.24
Nodes (7): GrabainformeAutomation, main(), Punto de entrada principal., Automatización generada: grabainforme, Actualiza el estado en la BD, Conecta a la aplicación objetivo., Ejecuta todas las acciones grabadas.

### Community 86 - "KSY Automation Script"
Cohesion: 0.24
Nodes (7): KsyAutomation, main(), Punto de entrada principal., Automatización generada: ksy, Actualiza el estado en la BD, Conecta a la aplicación objetivo., Ejecuta todas las acciones grabadas.

### Community 87 - "Pending Task Automation"
Cohesion: 0.24
Nodes (7): main(), PendingAutomation, Punto de entrada principal., Automatización generada: pending, Actualiza el estado en la BD, Conecta a la aplicación objetivo., Ejecuta todas las acciones grabadas.

### Community 88 - "Windows Element Selector"
Cohesion: 0.20
Nodes (5): Construye selector priorizado con validación de calidad., Busca elemento con retry, usando contexto de app si existe., Encuentra elementos con fallback chain y retry., Extrae propiedades de elemento en (x, y) buscando el mejor candidato y su contex, WindowsSelector

### Community 89 - "PACS Application Manager"
Cohesion: 0.31
Nodes (7): abrir_vue_pacs(), cerrar_todos_carestream(), debug_listar_ventanas(), main(), Script RPA: Cierra TODOS los programas Carestream + Abre Vue PACS limpio - Care, Lista TODAS las ventanas Carestream., Cierra TODOS los programas Carestream (ventanas y procesos).

### Community 90 - "Workflow Edge UI"
Cohesion: 0.22
Nodes (4): InsertNodeButton, QGraphicsEllipseItem, Insert Node Button for Edge - allows clicking on connections to insert intermedi, + button that appears on edges when hovering

### Community 91 - "Combobox Click Test"
Cohesion: 0.33
Nodes (5): humanized_click(), main(), Mueve, resalta con círculo rojo y hace clic sostenido., setup_app(), VisualFeedbackLocal

### Community 92 - "Recording Player Setup"
Cohesion: 0.29
Nodes (4): Reproduce grabación con validación., Conecta a ventana objetivo., Ejecuta todas las acciones., RecordingPlayer

### Community 93 - "Selector Strategy Pattern"
Cohesion: 0.25
Nodes (3): WindowsSelector - Búsqueda con fallback chain., Strategy pattern para selectores., SelectorStrategy

### Community 94 - "Mouse Movement Simulator"
Cohesion: 0.38
Nodes (6): iniciar_simulacion(), mostrar_cuenta_atras(), mover_mouse_aleatoriamente(), Mueve el mouse a una posición aleatoria dentro de los límites de la pantalla., Muestra un temporizador regresivo en la consola., Bucle principal de la simulación.

### Community 96 - "RIS Window Management"
Cohesion: 0.17
Nodes (6): Application, Conecta a la aplicación objetivo de forma robusta., Conecta a la aplicación objetivo de forma robusta., Intenta traer el RIS al frente (Carestream o Philips). No es error si falla., test_enfoque_ventana(), list_pacs()

### Community 97 - "Action List Optimizer"
Cohesion: 0.33
Nodes (4): ActionOptimizer, ActionOptimizer - Limpia acciones., Optimiza lista de acciones., Optimiza acciones (limpieza, consolidación).

### Community 98 - "RTF Clipboard Utilities"
Cohesion: 0.33
Nodes (5): Coloca texto plano en el portapapeles de forma robusta., Coloca contenido RTF y texto plano en el portapapeles., Procesa el texto usando pegado directo en formato RTF para un formato absoluto (, set_clipboard_rtf(), set_clipboard_text()

### Community 99 - "OpenRouter Model Checker"
Cohesion: 0.47
Nodes (5): get_available_models(), main(), Obtiene todos los modelos disponibles en OpenRouter., Hace una llamada mínima de prueba al modelo., test_model_call()

### Community 100 - "LLM Model Validation"
Cohesion: 0.47
Nodes (5): check_model(), main(), Verifica si el modelo está activo en OpenRouter., Actualiza la lista BASE_LLM_MODELS en llm_config.py., update_config_file()

### Community 101 - "Database Connection Management"
Cohesion: 0.50
Nodes (4): check_connection(), launch_wamp(), Intenta ejecutar WampManager con permisos de administrador., Intenta conectar a MySQL. Si falla, inicia WAMP y reintenta cada 10 segundos

### Community 102 - "System Health Monitoring"
Cohesion: 0.40
Nodes (3): Verifica CPU, RAM, disco., Monitorea salud del sistema., SystemMonitor

### Community 104 - "Pathology Text Processing"
Cohesion: 0.83
Nodes (3): detectar_patologia(), normalizar_texto(), tiene_negacion()

### Community 106 - "AI Pathology Search"
Cohesion: 0.67
Nodes (3): OPENROUTER_API_KEY, Busqueda Triple Text Only, Detecta Patologia IA

## Knowledge Gaps
- **7 isolated node(s):** `Busqueda Triple Text Only`, `Detecta Patologia IA`, `Database Node`, `Workflow Validator`, `Action Node` (+2 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OCREngine` connect `OCR Engine Integration` to `OCR Diagnostic Search`, `PACS Automation Workflow`, `Action Execution Framework`, `OCR Action Library`, `RIS Automation Workflow`, `OCR Pattern Matching`, `Structured OCR Search`, `Automated Workflow Execution`, `RPA Visual Feedback`, `Enhanced Structured Search`, `Web Replay System`, `Exam Search Automation`, `Adjusted OCR Search`, `Nemotron OCR Verification`, `Error Handling Service`, `Structured Search Normalization`, `Visual OCR Verification`, `Click and Sort Automation`, `Mock Automation Feedback`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `Main GUI Application` to `Web Record Panel`, `LLM UI Panel`, `Recording Replay Panel`, `Dashboard Analytics Panel`, `OCR Configuration Panel`, `Workflow Editor UI`, `Script Debugging Panel`, `Recording Control Panel`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `VisualFeedback` connect `RPA Visual Feedback` to `OCR Diagnostic Search`, `Doctor Database Search`, `Action Execution Framework`, `OCR Action Library`, `Doctor Database Connector`, `OCR Pattern Matching`, `Immutable Action Executor`, `Clipboard Text Automation`, `Word Toolbar Automation`, `RPA Input Recorder`, `Web Automation Scripting`, `Exam Search Automation`, `Web Automation Controller`, `OCR Status Updater`, `Error Handling Service`, `Patient Search Automation`, `Visual OCR Verification`, `Visual Similarity Verification`, `PACS Application Manager`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Are the 52 inferred relationships involving `ActionExecutor` (e.g. with `PatologiaCriticaConCierreOkAutomation` and `.run()`) actually correct?**
  _`ActionExecutor` has 52 INFERRED edges - model-reasoned connections that need verification._
- **Are the 43 inferred relationships involving `Action` (e.g. with `PatologiaCriticaConCierreOkAutomation` and `.run()`) actually correct?**
  _`Action` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 40 inferred relationships involving `OCREngine` (e.g. with `debug_ocr_variants()` and `test_ocr()`) actually correct?**
  _`OCREngine` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `VisualFeedback` (e.g. with `ActionExecutor` and `.execute()`) actually correct?**
  _`VisualFeedback` has 25 INFERRED edges - model-reasoned connections that need verification._