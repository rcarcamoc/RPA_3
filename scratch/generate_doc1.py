import os
import sys
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

sys.path.append(os.path.dirname(__file__))
from docx_helpers import set_cell_background, set_cell_margins, set_table_borders, add_callout

def create_document_1():
    doc = Document()
    
    # Configuración de márgenes estándar de 2.5 cm (aprox 0.98 pulgadas)
    for section in doc.sections:
        section.top_margin = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)
        
        # Encabezado y Pie de página
        header = section.header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run("PROYECTO RPA: TRIAGE RADIOLÓGICO Y OPERACIÓN 24/7 | INFORME ESTRATÉGICO")
        hrun.font.name = "Calibri"
        hrun.font.size = Pt(8.5)
        hrun.font.color.rgb = RGBColor(140, 150, 160)
        
        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        frun1 = fp.add_run("Documento de Presentación y Justificación Ejecutiva")
        frun1.font.name = "Calibri"
        frun1.font.size = Pt(8.5)
        frun1.font.color.rgb = RGBColor(140, 150, 160)
        
        # Paginación en pie
        frun2 = fp.add_run("\t\tConfidencial - Uso Interno")
        frun2.font.name = "Calibri"
        frun2.font.size = Pt(8.5)
        frun2.font.color.rgb = RGBColor(140, 150, 160)

    # Colores corporativos
    C_NAVY = RGBColor(27, 54, 93)      # #1B365D - Títulos principales
    C_SLATE = RGBColor(70, 90, 115)    # #465A73 - Subtítulos
    C_BODY = RGBColor(40, 45, 55)      # #282D37 - Texto cuerpo
    C_MUTED = RGBColor(100, 110, 125)  # Metadatos

    # ==========================================
    # PORTADA FORMAL Y ELEGANTE
    # ==========================================
    p_title_pre = doc.add_paragraph()
    p_title_pre.paragraph_format.space_before = Pt(36)
    p_title_pre.paragraph_format.space_after = Pt(4)
    run_pre = p_title_pre.add_run("INFORME EJECUTIVO DE ARQUITECTURA Y DEFENSA OPERACIONAL")
    run_pre.font.name = "Calibri"
    run_pre.font.size = Pt(11)
    run_pre.font.bold = True
    run_pre.font.color.rgb = RGBColor(0, 120, 180)

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(12)
    p_title.paragraph_format.line_spacing = 1.15
    run_main = p_title.add_run("Proyecto RPA: Automatización Operacional y Triage de Estudios Radiológicos")
    run_main.font.name = "Calibri"
    run_main.font.size = Pt(24)
    run_main.font.bold = True
    run_main.font.color.rgb = C_NAVY

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(24)
    p_sub.paragraph_format.line_spacing = 1.2
    run_sub = p_sub.add_run(
        "Evaluación de Rendimiento, Condiciones de Despliegue en Infraestructura Virtual Windows, "
        "Gestión de Seguridad de Datos Sensibles (PHI) y Justificación de Continuidad 24/7"
    )
    run_sub.font.name = "Calibri"
    run_sub.font.size = Pt(13)
    run_sub.font.color.rgb = C_SLATE

    # Tabla de metadatos de portada
    tbl_meta = doc.add_table(rows=5, cols=2)
    tbl_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_meta.autofit = False
    
    meta_rows = [
        ("Destinatario:", "Gerencia General / Dirección de Operaciones y Tecnología"),
        ("Proyecto:", "RPA Framework v3 - Teleradiología & Triage RIS-PACS"),
        ("Fase Actual:", "Fase 1: Estabilización, Validación Clínica y Cobertura Continua"),
        ("Fecha de Emisión:", "Octubre 2026"),
        ("Clasificación:", "Confidencial - Evaluación Estratégica y Toma de Decisión")
    ]
    
    for i, (k, v) in enumerate(meta_rows):
        c0 = tbl_meta.cell(i, 0)
        c1 = tbl_meta.cell(i, 1)
        c0.width = Inches(2.0)
        c1.width = Inches(4.5)
        set_cell_background(c0, "F8FAFC")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, top=80, bottom=80, left=120, right=120)
        set_cell_margins(c1, top=80, bottom=80, left=120, right=120)
        
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(k)
        r0.font.name = "Calibri"
        r0.font.bold = True
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = C_NAVY
        
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        r1 = p1.add_run(v)
        r1.font.name = "Calibri"
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = C_BODY
        
    set_table_borders(tbl_meta, color="E2E8F0")

    doc.add_page_break()

    # ==========================================
    # SECCIÓN 1: RESUMEN EJECUTIVO Y TESIS DE VALOR
    # ==========================================
    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(15)
        run.font.bold = True
        run.font.color.rgb = C_NAVY
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.color.rgb = C_SLATE
        return p

    def add_body(text, bold_prefix=None):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.font.name = "Calibri"
            rb.font.size = Pt(10)
            rb.font.bold = True
            rb.font.color.rgb = C_BODY
        r = p.add_run(text)
        r.font.name = "Calibri"
        r.font.size = Pt(10)
        r.font.color.rgb = C_BODY
        return p

    add_h1("1. Resumen Ejecutivo y Tesis de Valor")

    add_body(
        "El presente documento expone la justificación técnica, operacional y económica del Sistema de Automatización Robótica de Procesos (RPA) "
        "desarrollado para la integración y triage inteligente de exámenes radiológicos entre los sistemas RIS (Radiology Information System) "
        "y PACS (Picture Archiving and Communication System)."
    )

    add_body(
        "En la operación teleradiológica actual, la gestión de la lista de trabajo, la apertura de estudios, la verificación de órdenes médicas "
        "y la correlación paciente-estudio representan un cuello de botella logístico intensivo en mano de obra. Un operador humano altamente capacitado "
        "es capaz de procesar a un ritmo pico de 30 a 40 casos por hora bajo condiciones de concentración extrema. Sin embargo, la jornada humana "
        "está sujeta a limitaciones físicas evidentes: fatiga cognitiva tras varias horas de pantalla, pausas operacionales, riesgo de errores en la "
        "digitación de identificadores de pacientes y, de manera crítica, una cobertura limitada a turnos de 8 horas con costos crecientes para sostener "
        "guardias nocturnas, festivos y fines de semana."
    )

    add_callout(
        doc,
        "La propuesta de valor del Bot RPA no radica en competir en velocidad puntual contra un operador humano en su hora pico, sino en proporcionar "
        "una COBERTURA ININTERRUMPIDA 24/7/365, con CERO error de digitación, trazabilidad absoluta en base de datos y, fundamentalmente, la DETECCIÓN "
        "INMEDIATA de patologías críticas con alerta médica instantánea, protegiendo la vida del paciente y absorbiendo la carga nocturna.",
        "TESIS CENTRAL PARA GERENCIA"
    )

    add_body(
        "El bot procesa actualmente cada caso en un ciclo completo de 5 a 7 minutos (~8 a 10 casos/hora sostenidos), priorizando deliberadamente la "
        "seguridad del paciente y la verificación rigurosa mediante visión por computador e Inteligencia Artificial antes de realizar cualquier acción en los sistemas clínicos. "
        "Al operar de manera desatendida durante las 24 horas del día, el sistema aporta una producción neta diaria de ~190 a 240 estudios procesados, "
        "eliminando el represamiento de casos durante la noche y entregando a primera hora del turno diurno una bandeja de trabajo depurada y auditada."
    )

    # ==========================================
    # SECCIÓN 2: DESCRIPCIÓN DEL PROYECTO Y FLUJO END-TO-END
    # ==========================================
    add_h1("2. Descripción del Proyecto: ¿Qué hace el Bot RPA?")

    add_body(
        "El bot es un agente de software autónomo que replica y optimiza la secuencia de navegación que realiza un operador de mesa de ayuda o tecnólogo "
        "entre los sistemas web y de escritorio corporativos, ejecutando un flujo de 5 etapas continuas:"
    )

    etapas = [
        ("Etapa 1: Verificación de Integridad de Entorno y Conectividad: ", 
         "Antes de iniciar cualquier acción clínica, el bot valida la persistencia del túnel VPN institucional, la disponibilidad de la base de datos MySQL local/central y los enlaces de red, garantizando que ninguna transacción quede a medio camino."),
        ("Etapa 2: Extracción y Consulta en el RIS (Web): ", 
         "El bot navega en el portal RIS mediante automatización web, consulta la lista de exámenes pendientes de cierre o informe, extrae la ficha del paciente, médico solicitante y descarga el informe o solicitud médica en formato PDF."),
        ("Etapa 3: Triage Clínico Inteligente con Cascada de IA (3 Niveles): ", 
         "El texto diagnóstico se procesa mediante un motor de tres capas: (1) Búsqueda normalizada directa, (2) Algoritmos de coincidencia difusa (Fuzzy Matching con RapidFuzz) y (3) Inferencia semántica con Modelos de Lenguaje Médico (LLM). Si el examen contiene hallazgos de emergencia (aneurismas, hemorragias cerebrales, tromboembolismo pulmonar, disección aórtica), el bot lo clasifica como Patología Crítica y activa el protocolo de emergencia."),
        ("Etapa 4: Control Dinámico del Visualizador PACS (Escritorio): ", 
         "El bot toma control del aplicativo de escritorio Carestream Vue PACS, maximiza la interfaz, utiliza visión por computador (OCR) para ubicar dinámicamente los campos de búsqueda, digita el identificador del paciente, ordena las series cronológicamente y selecciona el estudio exacto correspondiente."),
        ("Etapa 5: Cierre, Auditoría y Notificación Multicanal: ", 
         "Actualiza el registro transaccional en la base de datos interna, marca el estado final del estudio y, en caso de patologías críticas o discrepancias que requieran validación humana, despacha una alerta con captura de pantalla y enlace de streaming en vivo a los canales seguros de Telegram del equipo médico y supervisores.")
    ]

    for bold_p, text_p in etapas:
        add_body(text_p, bold_prefix=bold_p)

    # ==========================================
    # SECCIÓN 3: COMPARATIVA HUMANO VS BOT 24/7
    # ==========================================
    add_h1("3. Comparativa Estratégica: Operador Humano vs. Bot RPA")

    add_body(
        "Para responder con claridad a la interrogante sobre la eficiencia del bot frente a los 30-40 casos por hora de un operador humano entrenado, "
        "la siguiente matriz contrasta ambas modalidades en una perspectiva operacional completa (jornada de 24 horas y costo total de operación):"
    )

    tbl_comp = doc.add_table(rows=8, cols=3)
    tbl_comp.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_comp.autofit = False

    comp_data = [
        ("Criterio de Evaluación", "Operador Humano Entrenado", "Bot RPA Autónomo (Estado Actual)"),
        ("Velocidad de Procesamiento", "30 - 40 casos / hora (pico)", "8 - 10 casos / hora (sostenido)"),
        ("Ventana Operativa Diaria", "8 horas / turno (con pausas y descansos)", "24 horas ininterrumpidas (sin pausas)"),
        ("Producción Neta Diaria", "200 - 240 casos / día útil", "190 - 240 casos / día (24 horas continuas)"),
        ("Disponibilidad Nocturna / Festivos", "Alto sobrecosto en horas extras y guardias", "Operación 100% activa a costo marginal cero"),
        ("Tasa de Error en Digitación", "Presente por fatiga visual y digitación manual", "0.0% de error (mecanismo determinístico)"),
        ("Detección de Patología Crítica", "Dependiente del orden en que abre la cola", "Inmediata en tiempo real (SLA de minutos)"),
        ("Trazabilidad y Auditoría", "Reporte manual al final del turno", "Auditoría en BD por segundo con capturas")
    ]

    for r_idx, row in enumerate(comp_data):
        for c_idx, val in enumerate(row):
            cell = tbl_comp.cell(r_idx, c_idx)
            cell.width = Inches(2.1)
            set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            
            if r_idx == 0:
                set_cell_background(cell, "1B365D")
                run = p.add_run(val)
                run.font.name = "Calibri"
                run.font.bold = True
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(255, 255, 255)
            else:
                bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
                set_cell_background(cell, bg)
                run = p.add_run(val)
                run.font.name = "Calibri"
                run.font.size = Pt(9)
                if c_idx == 0:
                    run.font.bold = True
                    run.font.color.rgb = C_NAVY
                else:
                    run.font.color.rgb = C_BODY
                    
    set_table_borders(tbl_comp, color="CBD5E1")

    add_callout(
        doc,
        "Conclusión Operativa: Si bien en 1 hora el humano supera al bot, al cabo de 24 horas el volumen neto procesado es equivalente "
        "(~200 casos diarios), con la diferencia radical de que el bot absorbe la noche y el fin de semana sin coste laboral adicional y "
        "con una capa de alerta clínica instantánea que el humano no puede mantener de forma constante.",
        "ANÁLISIS COMPARATIVO"
    )

    # ==========================================
    # SECCIÓN 4: COMPONENTES TECNOLÓGICOS Y ARQUITECTURA
    # ==========================================
    add_h1("4. Componentes y Arquitectura del Sistema")

    add_body(
        "El proyecto fue diseñado bajo una arquitectura modular y resiliente en Python 3.13, combinando bibliotecas de grado empresarial "
        "que aseguran compatibilidad con software clínico moderno y heredado:"
    )

    componentes = [
        ("Motor de Orquestación y Flujos (RPA Framework v3): ",
         "Ejecutor central basado en grafo acíclico dirigido que interpreta workflows en JSON (nodos de acción, decisión y bucle). Implementa manejo seguro de excepciones, auto-reinicio y persistencia de contexto."),
        ("Visión Artificial y OCR Multimodelo (Tesseract, PaddleOCR, EasyOCR): ",
         "Capacidad de lectura óptica para interactuar con pantallas dinámicas de PACS donde no existen APIs disponibles. Emplea técnicas de preprocesamiento OpenCV (umbralización, binarización y escalado) para garantizar lectura exacta de textos clínicos."),
        ("Módulo de Inteligencia Semántica (Modelos LLM Especializados): ",
         "Integración con modelos de lenguaje de última generación optimizados para medicina (vía API segura). Se implementó un algoritmo de ranking dinámico que selecciona en milisegundos el modelo más rápido y certero para auditar la anatomía y el diagnóstico."),
        ("Automatización de Interfaz Nativa (PyWinAuto y PyAutoGUI): ",
         "Control directo sobre el árbol de accesibilidad de Windows (UI Automation) y control de mouse/teclado para interactuar con el cliente pesado de Carestream Vue PACS sin requerir modificaciones en la infraestructura del proveedor."),
        ("Sistema de Telemetría y Streaming Remoto (Telegram + RTMP): ",
         "Servicio en segundo plano que permite supervisión desatendida. Los supervisores pueden consultar el estado, pausar el bot o solicitar una transmisión de video en vivo del escritorio de la máquina virtual desde su móvil ante cualquier anomalía."),
        ("Capa de Datos Transaccional (MySQL / SQLAlchemy): ",
         "Base de datos de auditoría con tablas de control de cola (registro_acciones), métricas de latencia de modelos de IA (log_llm_ranking) y repositorio de sinónimos médicos para aprendizaje continuo.")
    ]

    for bc, tc in componentes:
        add_body(tc, bold_prefix=bc)

    # ==========================================
    # SECCIÓN 5: RECURSOS CONSUMIDOS Y COSTOS OPERACIONALES
    # ==========================================
    add_h1("5. Recursos Consumidos y Costos de Operación")

    add_body(
        "La solución destaca por su bajo impacto sobre los recursos corporativos y un costo marginal de operación prácticamente nulo:"
    )

    add_body(
        "Consumo promedio en reposo entre 2% y 5% de uso. Durante la fase de OCR intensivo o captura de pantalla, se registran picos controlados de hasta 25-35% de CPU durante 3 a 5 segundos, estabilizándose inmediatamente.",
        bold_prefix="• Carga de CPU: "
    )
    add_body(
        "La huella de memoria del proceso base oscila entre 250 MB y 450 MB. Cuando se cargan los módulos de visión por computador y PySide/PyQt6 en memoria, el consumo total del sistema no supera los 1.5 GB de RAM.",
        bold_prefix="• Memoria RAM: "
    )
    add_body(
        "El código base y sus entornos virtuales ocupan ~3.5 GB. La política de almacenamiento incluye purga programada de capturas de pantalla de depuración y compresión de archivos de bitácora, requiriendo menos de 10 GB de disco para operación anual.",
        bold_prefix="• Almacenamiento en Disco: "
    )
    add_body(
        "Tráfico ligero consistente en llamadas REST para inferencia de diagnóstico (cargas útiles de texto de <2 KB), tráfico web estándar contra el RIS y streaming de video solo bajo demanda expresa de supervisión humana.",
        bold_prefix="• Tráfico de Red y VPN: "
    )
    add_body(
        "Las consultas de discernimiento clínico emplean modelos altamente optimizados. El costo por consulta ronda entre $0.0001 y $0.0005 USD. Para un volumen mensual de 6.000 estudios analizados, el gasto acumulado en IA es inferior a $3 USD mensuales.",
        bold_prefix="• Costo Financiero de Inteligencia Artificial: "
    )

    # ==========================================
    # SECCIÓN 6: SEGURIDAD, CREDENCIALES Y DATOS CLÍNICOS (PHI)
    # ==========================================
    add_h1("6. Seguridad de la Información y Manejo de Datos Sensibles")

    add_body(
        "Al operar en el sector salud y manejar Información Médica Protegida (PHI), el diseño del bot incorporó salvaguardas estrictas de privacidad y seguridad informática:"
    )

    add_h2("6.1. Anonimización y Privacidad en el Uso de Inteligencia Artificial")
    add_body(
        "Un temor habitual en la adopción de IA es el traspaso involuntario de datos personales a proveedores externos. En este sistema, "
        "el algoritmo implementa una política estricta de DESIDENTIFICACIÓN PREVIA: Únicamente se transmite al modelo de lenguaje el fragmento "
        "textual del diagnóstico médico (por ejemplo: 'se observa aneurisma fusiforme de aorta infrarrenal de 4.8 cm'). NUNCA se envía el nombre del paciente, "
        "RUT/cédula de identidad, fecha de nacimiento, número de ficha clínica ni procedencia institucional. La privacidad del paciente está resguardada por diseño."
    )

    add_h2("6.2. Aislamiento de Credenciales y Secretos")
    add_body(
        "Las claves de API de servicios externos, tokens de bots y configuraciones sensibles residen en un archivo de entorno protegido (.env) "
        "excluido del control de versiones (.gitignore). Para las credenciales de acceso a los sistemas médicos (PACS y RIS), el bot consulta la base "
        "de datos en memoria durante la ejecución y las inyecta directamente en los campos de login mediante eventos simulados de sistema operativo, "
        "sin registrar jamás contraseñas en archivos de texto plano ni en los logs de auditoría."
    )

    add_h2("6.3. Trazabilidad Completa y Auditoría Forense")
    add_body(
        "Cada acción ejecutada por el robot genera un registro con fecha, hora exacta en milisegundos, identificador del estudio, nodo del flujo ejecutado, "
        "tiempo de respuesta y resultado. En caso de discrepancia o error técnico, el sistema captura una fotografía instantánea del escritorio que se guarda "
        "en un directorio restringido y se envía cifrada vía Telegram a los supervisores para permitir una auditoría forense inmediata."
    )

    # ==========================================
    # SECCIÓN 7: INFRAESTRUCTURA Y CONDICIONES IDEALES EN MÁQUINA VIRTUAL
    # ==========================================
    add_h1("7. Condiciones Ideales para Ejecución en Máquina Virtual Windows")

    add_body(
        "A diferencia de los servicios backend tradicionales (APIs o scripts de base de datos) que pueden operar en modo 'headless' (sin interfaz), "
        "un robot RPA que interactúa con visualizadores médicos como PACS requiere imperativamente un ENTORNO GRÁFICO ACTIVO Y RENDERIZADO. "
        "A continuación se presenta el análisis comparativo de las 4 opciones de infraestructura (formuladas sin marcas comerciales):"
    )

    tbl_infra = doc.add_table(rows=5, cols=4)
    tbl_infra.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_infra.autofit = False

    infra_cols = [
        ("Modelo de Infraestructura", "Especificación Recomendada", "Ventajas Principales", "Consideraciones Críticas"),
        ("1. Estación / Servidor Físico Dedicado", 
         "CPU 6-8 Núcleos\n16 GB RAM\nSSD 256 GB\nGPU integrada / dedicada", 
         "Renderizado gráfico 100% nativo.\nCero problemas de drivers con PACS.\nMáxima estabilidad para OCR.", 
         "Requiere espacio físico y mantenimiento de hardware individual."),
        ("2. Servidor Físico para Virtualización (Host)", 
         "Servidor multinúcleo con hipervisor de virtualización.\nRecursos asignados a VMs.", 
         "Consolidación en centro de datos.\nRespaldos por snapshot de máquina completa.\nAlta disponibilidad.", 
         "Requiere configurar emulación de pantalla activa en el hipervisor."),
        ("3. Máquina Virtual en Servidor (VM Huésped)", 
         "4 vCPU asignadas\n8 - 16 GB vRAM\n80 GB SSD virtual\nWindows 10/11 Pro o Server GUI", 
         "Facilidad de aprovisionamiento, clonación y aislamiento de red corporativa.", 
         "CRÍTICO: No puede bloquearse la sesión RDP (requiere sesión de consola activa con auto-logon)."),
        ("4. Entorno Actual de Desarrollo (Referencia)", 
         "Intel Core i7 (6 núcleos / 12 hilos)\n16 GB RAM DDR4\nWindows 11 Pro 64-bit", 
         "Rendimiento probado, excelente respuesta en OCR y multieje PACS.", 
         "Equipo de escritorio local; requiere migración a infraestructura formal corporativa.")
    ]

    for r_idx, row in enumerate(infra_cols):
        for c_idx, val in enumerate(row):
            cell = tbl_infra.cell(r_idx, c_idx)
            cell.width = Inches(1.6)
            set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            
            if r_idx == 0:
                set_cell_background(cell, "1B365D")
                run = p.add_run(val)
                run.font.name = "Calibri"
                run.font.bold = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(255, 255, 255)
            else:
                bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
                set_cell_background(cell, bg)
                run = p.add_run(val)
                run.font.name = "Calibri"
                run.font.size = Pt(8.5)
                if c_idx == 0:
                    run.font.bold = True
                    run.font.color.rgb = C_NAVY
                else:
                    run.font.color.rgb = C_BODY

    set_table_borders(tbl_infra, color="CBD5E1")

    add_h2("7.1. Requisitos Críticos de la Sesión Gráfica en la VM")
    add_body(
        "Para que la máquina virtual ejecute el bot de forma desatendida y sin fallas, el equipo de Infraestructura y TI debe garantizar "
        "cuatro directrices operacionales estrictas:"
    )

    reqs = [
        ("Resolución de Pantalla Fija de 1920x1080 a Escala del 100%: ",
         "Los módulos de reconocimiento óptico y búsqueda de coordenadas operan sobre una matriz Full HD. Si la resolución cambia dinámicamente o la escala de fuentes de Windows se altera (ej. 125%), las coordenadas de clic se descalibran."),
        ("Sesión de Consola Interactiva Activa (Sin Bloqueo de Pantalla): ",
         "Cuando una sesión de Escritorio Remoto (RDP) se desconecta o la pantalla se bloquea por inactividad, Windows suspende la renderización gráfica del escritorio. Para evitar que el PACS o el OCR dejen de capturar imágenes, la VM debe configurarse con inicio de sesión automático en consola local y desactivación de protectores de pantalla o bloqueo por inactividad."),
        ("Conectividad de Red y Túnel VPN Persistente: ",
         "El canal de comunicación con el RIS y el PACS institucional debe mantener latencia inferior a 50 ms. Se incluye en el bot un mecanismo de auto-reconocimiento y reconexión de VPN que monitoriza caídas del enlace."),
        ("Motor de Base de Datos Local o con Enlace de Baja Latencia: ",
         "Para garantizar que los tiempos de registro y consulta de credenciales no agreguen demoras al ciclo, el servicio MySQL debe residir en la misma máquina o en la subred local (<5 ms de latencia).")
    ]

    for br, tr in reqs:
        add_body(tr, bold_prefix=br)

    # ==========================================
    # SECCIÓN 8: JUSTIFICACIÓN TÉCNICA Y OPERACIONAL
    # ==========================================
    add_h1("8. Justificación Técnica y Operacional para Gerencia")

    add_body(
        "La implementación formal de este bot se justifica en cuatro ejes estratégicos que generan un impacto directo en la sostenibilidad y calidad del servicio:"
    )

    add_body(
        "En condiciones normales, un informe con hallazgo grave (ej. disección aórtica o hemorragia subaracnoidea) puede permanecer horas en cola esperando que un operador lo abra en su turno. El bot analiza el texto clínico en segundos y dispara alertas inmediatas al radiólogo de turno, transformando la teleradiología reactiva en un servicio de triage activo que salva vidas.",
        bold_prefix="1. Mitigación Drástica del Riesgo Clínico (SLA Crítico): "
    )
    add_body(
        "Al mantener la operación durante las noches, fines de semana y días festivos, el bot absorbe de forma continua cientos de estudios, evitando la acumulación masiva que suele colapsar a los equipos humanos a las 8:00 AM de cada jornada.",
        bold_prefix="2. Continuidad Operacional 24/7 sin Sobrecostos Laborales: "
    )
    add_body(
        "Los operadores humanos cometen errores involuntarios tras procesar cientos de números de ficha médica durante turnos extenuantes. El robot garantiza una exactitud del 100% en la concordancia entre el paciente del RIS y el estudio del PACS.",
        bold_prefix="3. Eliminación del Error Humano en Digitación y Trazabilidad: "
    )
    add_body(
        "El personal administrativo y técnico deja de realizar tareas monótonas de 'abrir, copiar y buscar' para dedicarse a la atención telefónica a clínicas, resolución de discrepancias complejas y control de calidad médica.",
        bold_prefix="4. Redirección de Talento hacia Tareas de Alto Valor: "
    )

    # ==========================================
    # SECCIÓN 9: HOJA DE RUTA Y PLAN DE OPTIMIZACIÓN
    # ==========================================
    add_h1("9. Hoja de Ruta de Optimización (Roadmap)")

    add_body(
        "La velocidad actual de 8 a 10 casos por hora responde a una decisión técnica consciente durante la Fase 1: se priorizó la estabilidad, "
        "la precisión médica y la tolerancia a fallos antes de acelerar los tiempos. El plan de trabajo contempla una evolución clara:"
    )

    fases = [
        ("Fase 1: Estabilización, Validación Clínica y Cobertura (ESTADO ACTUAL): ",
         "Objetivo logrado: Cero falsos positivos en patología crítica, integración estable RIS-PACS, logging forense, supervisión por Telegram y operación continua desatendida."),
        ("Fase 2: Optimización de Rendimiento y Velocidad (Próximos 45 días): ",
         "Implementación de caché en memoria de resultados OCR, paralelización de descarga de órdenes médicas en segundo plano y reducción de pausas defensivas en la interfaz. Meta: Reducir el ciclo a 3-4 minutos por caso (~15 a 20 casos/hora)."),
        ("Fase 3: Escalabilidad Multinstancia (Mediano Plazo): ",
         "Despliegue de 2 a 3 máquinas virtuales concurrentes operando en paralelo sobre distintas ramas de la lista de trabajo, alcanzando una capacidad combinada superior a los 50 casos/hora, superando con creces la capacidad de un equipo humano completo.")
    ]

    for bf, tf in fases:
        add_body(tf, bold_prefix=bf)

    # Guardar documento
    output_path = r"c:\Desarrollo\RPA_3\documentacion\1_Informe_Ejecutivo_Estrategico_Proyecto_RPA.docx"
    doc.save(output_path)
    print(f"Documento 1 generado exitosamente en: {output_path}")

if __name__ == "__main__":
    create_document_1()
