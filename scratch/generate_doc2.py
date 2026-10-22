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

def create_document_2():
    doc = Document()
    
    # Márgenes compactos ejecutivos (0.8 pulgadas / ~2.0 cm)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)
        
        # Encabezado y Pie
        header = section.header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run("DOSSIER EJECUTIVO | PROYECTO RPA: TRIAGE RADIOLÓGICO 24/7")
        hrun.font.name = "Calibri"
        hrun.font.size = Pt(8.5)
        hrun.font.color.rgb = RGBColor(140, 150, 160)
        
        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        frun1 = fp.add_run("Resumen para Toma de Decisión Gerencial")
        frun1.font.name = "Calibri"
        frun1.font.size = Pt(8.5)
        frun1.font.color.rgb = RGBColor(140, 150, 160)
        
        frun2 = fp.add_run("\t\tUso Exclusivo Dirección & Operaciones")
        frun2.font.name = "Calibri"
        frun2.font.size = Pt(8.5)
        frun2.font.color.rgb = RGBColor(140, 150, 160)

    # Colores corporativos
    C_NAVY = RGBColor(27, 54, 93)      # #1B365D
    C_SLATE = RGBColor(70, 90, 115)    # #465A73
    C_BODY = RGBColor(40, 45, 55)      # #282D37
    C_CYAN = RGBColor(0, 120, 180)     # Destacados

    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(13.5)
        run.font.bold = True
        run.font.color.rgb = C_NAVY
        return p

    def add_body(text, bold_prefix=None):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.font.name = "Calibri"
            rb.font.size = Pt(9.5)
            rb.font.bold = True
            rb.font.color.rgb = C_BODY
        r = p.add_run(text)
        r.font.name = "Calibri"
        r.font.size = Pt(9.5)
        r.font.color.rgb = C_BODY
        return p

    # ENCABEZADO PRINCIPAL DE PRIMERA PÁGINA
    p_header = doc.add_paragraph()
    p_header.paragraph_format.space_before = Pt(0)
    p_header.paragraph_format.space_after = Pt(2)
    r_tag = p_header.add_run("DOCUMENTO DE DECISIÓN GERENCIAL (BRIEFING ESTRATÉGICO)")
    r_tag.font.name = "Calibri"
    r_tag.font.size = Pt(10)
    r_tag.font.bold = True
    r_tag.font.color.rgb = C_CYAN

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(6)
    r_main = p_title.add_run("Proyecto RPA: Automatización Operacional y Triage de Estudios Radiológicos")
    r_main.font.name = "Calibri"
    r_main.font.size = Pt(18)
    r_main.font.bold = True
    r_main.font.color.rgb = C_NAVY

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(12)
    r_sub = p_sub.add_run("Justificación de Rendimiento 24/7, Mitigación de Riesgo Clínico y Requisitos de Infraestructura Virtual")
    r_sub.font.name = "Calibri"
    r_sub.font.size = Pt(11)
    r_sub.font.color.rgb = C_SLATE

    # TABLA RESUMEN EJECUTIVO (ONE-PAGER SUMMARY)
    tbl_brief = doc.add_table(rows=4, cols=2)
    tbl_brief.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_brief.autofit = False

    brief_items = [
        ("Desafío Operacional:", "Volumen creciente de exámenes entre RIS y PACS, alta carga de turnos nocturnos y riesgo de demoras en la detección de patologías clínicas graves."),
        ("Solución RPA Implementada:", "Robot autónomo 24/7 que extrae estudios del RIS, analiza diagnósticos con IA (3 niveles) para alertas críticas y gestiona la apertura en el PACS."),
        ("Eje de Rentabilidad:", "No busca superar al humano en velocidad punta (30-40 casos/h en pico diurno), sino aportar 24 horas continuas (~200 casos/día) sin horas extras ni fatiga."),
        ("Solicitud a Gerencia:", "Habilitación formal de una Máquina Virtual Windows con sesión gráfica activa para paso a producción en horario continuo.")
    ]

    for i, (k, v) in enumerate(brief_items):
        c0 = tbl_brief.cell(i, 0)
        c1 = tbl_brief.cell(i, 1)
        c0.width = Inches(2.2)
        c1.width = Inches(4.7)
        set_cell_background(c0, "F1F5F9")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, top=70, bottom=70, left=100, right=100)
        set_cell_margins(c1, top=70, bottom=70, left=100, right=100)
        
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(k)
        r0.font.name = "Calibri"
        r0.font.bold = True
        r0.font.size = Pt(9)
        r0.font.color.rgb = C_NAVY
        
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        r1 = p1.add_run(v)
        r1.font.name = "Calibri"
        r1.font.size = Pt(9)
        r1.font.color.rgb = C_BODY

    set_table_borders(tbl_brief, color="CBD5E1")

    # SECCIÓN 1: MATRIZ DE RENDIMIENTO
    add_h1("1. El Factor Eficiencia: Humano en Pico vs. Robot en Cobertura 24/7")

    add_body(
        "Un operador entrenado alcanza una cadencia de 30 a 40 casos por hora bajo máxima concentración. No obstante, esa velocidad "
        "solo es sostenible durante lapsos acotados y en horario hábil. La siguiente tabla demuestra por qué el bot representa una ventaja "
        "neta en el balance global de la operación:"
    )

    tbl_kpi = doc.add_table(rows=6, cols=4)
    tbl_kpi.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_kpi.autofit = False

    kpi_data = [
        ("Métrica Operacional", "Operador Humano", "Bot RPA (Actual)", "Bot RPA (Fase 2)"),
        ("Velocidad Puntual", "30 - 40 casos/h", "8 - 10 casos/h", "15 - 20 casos/h"),
        ("Horas Activas al Día", "8 horas (1 turno)", "24 horas continuas", "24 horas continuas"),
        ("Producción Diaria Total", "~200 - 240 casos", "~190 - 240 casos", "~360 - 450 casos"),
        ("Costo Marginal Nocturno", "Horas extras / guardias", "$0 (costo plano)", "$0 (costo plano)"),
        ("Alerta Patología Crítica", "Manual según orden en cola", "Inmediata (<2 min)", "Inmediata (<2 min)")
    ]

    for r_idx, row in enumerate(kpi_data):
        for c_idx, val in enumerate(row):
            cell = tbl_kpi.cell(r_idx, c_idx)
            cell.width = Inches(1.72)
            set_cell_margins(cell, top=80, bottom=80, left=90, right=90)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            
            if r_idx == 0:
                set_cell_background(cell, "1B365D")
                run = p.add_run(val)
                run.font.name = "Calibri"
                run.font.bold = True
                run.font.size = Pt(8.5)
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

    set_table_borders(tbl_kpi, color="CBD5E1")

    add_callout(
        doc,
        "Ventaja Clave: El robot absorbe el flujo continuo nocturno y de fines de semana. Evita que el turno de la mañana inicie "
        "con una cola desbordada de estudios y asegura que los pacientes graves sean identificados en minutos, no en horas.",
        "IMPACTO DIRECTO"
    )

    # SECCIÓN 2: REQUISITOS DE INFRAESTRUCTURA (SIN MARCAS)
    add_h1("2. Infraestructura: Opciones y Condiciones Ideales en Máquina Virtual")

    add_body(
        "Para ejecutar la automatización desatendida, se contrastaron las opciones de hardware e infraestructura de forma vendor-agnostic:"
    )

    tbl_vm = doc.add_table(rows=5, cols=3)
    tbl_vm.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_vm.autofit = False

    vm_data = [
        ("Opción de Infraestructura", "Especificación Clave", "Diagnóstico Operacional"),
        ("A. Servidor Físico Dedicado", "CPU 6-8 cores, 16 GB RAM, SSD, GPU", "Excelente renderizado gráfico nativo. Requiere equipo físico en rack."),
        ("B. Servidor de Virtualización (Host)", "Plataforma de hipervisor en datacenter", "Óptima gobernanza, backups automáticos y monitoreo centralizado."),
        ("C. Máquina Virtual en Servidor (VM)", "4 vCPU, 8-16 GB vRAM, Win 10/11 Pro GUI", "RECOMENDADA: Balance ideal entre aislamiento, costo y facilidad de despliegue."),
        ("D. Entorno Actual (Desarrollo)", "Intel i7, 16 GB RAM, Win 11 Pro 64-bit", "Demostró alta fluidez; sirve de estándar para dimensionar la VM final.")
    ]

    for r_idx, row in enumerate(vm_data):
        for c_idx, val in enumerate(row):
            cell = tbl_vm.cell(r_idx, c_idx)
            cell.width = Inches(2.3)
            set_cell_margins(cell, top=80, bottom=80, left=90, right=90)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            
            if r_idx == 0:
                set_cell_background(cell, "1B365D")
                run = p.add_run(val)
                run.font.name = "Calibri"
                run.font.bold = True
                run.font.size = Pt(8.5)
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

    set_table_borders(tbl_vm, color="CBD5E1")

    add_body(
        "Condición Técnica Indispensable: La Máquina Virtual Windows debe mantener una SESIÓN DE CONSOLA ACTIVA (resolución fija de 1920x1080 al 100% de escala) "
        "sin bloqueo de pantalla ni suspensión por inactividad, ya que los motores de OCR y el visor PACS dependen de la renderización gráfica activa del sistema operativo."
    )

    # SECCIÓN 3: SEGURIDAD Y PRIVACIDAD DE DATOS (PHI)
    add_h1("3. Seguridad, Credenciales y Privacidad del Paciente (PHI)")

    add_body(
        "Cumplimiento médico estricto:", bold_prefix="• Desidentificación en IA: "
    )
    add_body(
        "Al consultar modelos de lenguaje para clasificar diagnósticos, NUNCA se transmiten datos personales (nombre, RUT, fecha de nacimiento o ficha médica). "
        "Solo se remite el texto clínico estricto (ej. 'sospecha de TEP masivo'), garantizando pleno apego a la legislación de protección de datos de salud."
    )
    add_body(
        "Credenciales protegidas:", bold_prefix="• Gestión Segura de Accesos: "
    )
    add_body(
        "Las claves de API y accesos residen en variables de entorno cifradas (.env). Las credenciales de usuarios médicos en PACS/RIS se inyectan en memoria sin quedar expuestas en logs."
    )
    add_body(
        "Auditoría forense en tiempo real:", bold_prefix="• Trazabilidad y Control: "
    )
    add_body(
        "Cada acción queda sellada con marca de tiempo en la base de datos MySQL, permitiendo auditorías de calidad en cualquier momento."
    )

    # SECCIÓN 4: COSTOS Y DECISIÓN FINAL
    add_h1("4. Estructura de Costos y Próximos Pasos para Gerencia")

    add_body(
        "Inversión en Software:", bold_prefix="• Costo de Licencias: "
    )
    add_body(
        "$0 USD. El framework fue desarrollado sobre componentes de código abierto en Python (PyQt, OpenCV, Tesseract, MySQL)."
    )
    add_body(
        "Consumo de IA:", bold_prefix="• Gasto Operacional Mensual: "
    )
    add_body(
        "Menor a $3 USD mensuales para un volumen de 6.000 estudios analizados (fracciones de centavo por consulta)."
    )
    add_body(
        "Ahorro Inmediato:", bold_prefix="• Retorno Operativo (ROI): "
    )
    add_body(
        "Absorbe ~6.000 casos mensuales sin incurrir en horas extras nocturnas o de fin de semana, con un SLA de detección de patología crítica inferior a 2 minutos."
    )

    add_callout(
        doc,
        "Decisión Solicitada a Gerencia:\n"
        "1. Aprobar la asignación formal de una Máquina Virtual Windows (4 vCPU, 8-16 GB RAM, resolución 1080p).\n"
        "2. Autorizar el inicio de pruebas operacionales en turno nocturno supervisado vía Telegram.\n"
        "3. Respaldar la Fase 2 de optimización de velocidad para alcanzar paridad humana de ciclo.",
        "ACCIONES REQUERIDAS"
    )

    # Guardar documento
    output_path = r"c:\Desarrollo\RPA_3\documentacion\2_Dossier_Ejecutivo_Briefing_Proyecto_RPA.docx"
    doc.save(output_path)
    print(f"Documento 2 generado exitosamente en: {output_path}")

if __name__ == "__main__":
    create_document_2()
