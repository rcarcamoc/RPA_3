"""
Consultas y actualizaciones sobre ris.registro_acciones, casos_pendientes y exportación de reportes Excel.
"""
import html
import threading

from utils.excel_generator import generar_excel_reporte
from utils.telegram_manager import (
    enviar_mensaje,
    editar_mensaje,
    enviar_documento,
    get_menu_ejecucion_markup,
    get_menu_revalidar_markup,
)


def rehabilitar_ultimo_registro():
    try:
        import mysql.connector
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }
        conn = mysql.connector.connect(**config, connect_timeout=5)
        cursor = conn.cursor()
        query = """
        UPDATE ris.registro_acciones 
        SET estado = 'En Proceso' 
        WHERE id = (SELECT max_id FROM (SELECT MAX(id) as max_id FROM ris.registro_acciones) as t)
        """
        cursor.execute(query)
        filas_afectadas = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return filas_afectadas > 0
    except Exception as e:
        print(f"Error rehabilitando registro: {e}")
        return False


def obtener_ultimos_errores(limite=5):
    """
    Obtiene los últimos N registros de ris.registro_acciones clasificados como 'Error'
    o 'error', con los campos mínimos requeridos y formateados de manera segura.
    """
    try:
        import mysql.connector
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }
        conn = mysql.connector.connect(**config, connect_timeout=5)
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT id, inicio, doctor_detectado, User, numero_documento, examen, estado, ultimo_nodo, observacion
        FROM ris.registro_acciones
        WHERE LOWER(estado) = 'error'
        ORDER BY id DESC
        LIMIT %s
        """
        cursor.execute(query, (limite,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        registros = []
        for r in rows:
            f_dt = r.get("inicio")
            fecha_str = f_dt.strftime("%d/%m/%Y %H:%M:%S") if hasattr(f_dt, "strftime") else (str(f_dt) if f_dt else "--")
            doc = r.get("numero_documento") or "--"
            examen = r.get("examen") or "--"
            medico = r.get("doctor_detectado") or r.get("User") or "--"
            registros.append({
                "id": r.get("id"),
                "inicio": fecha_str,
                "doctor": medico,
                "numero_documento": doc,
                "examen": examen,
                "ultimo_nodo": r.get("ultimo_nodo") or "--",
                "observacion": r.get("observacion") or ""
            })
        return registros
    except Exception as e:
        print(f"Error obteniendo últimos errores: {e}")
        return []


def marcar_registro_en_proceso(registro_id):
    """
    Marca el registro especificado con estado 'En Proceso' y actualiza fecha `update`.
    Si existía algún otro registro en 'En Proceso', lo pasa a 'Error' para evitar colisiones.
    Retorna (True, datos_registro) o (False, None).
    """
    try:
        import mysql.connector
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }
        conn = mysql.connector.connect(**config, connect_timeout=5)
        cursor = conn.cursor(dictionary=True)

        # 1. Desmarcar cualquier registro previo 'En Proceso'
        cursor.execute("""
            UPDATE ris.registro_acciones 
            SET estado = 'Error', observacion = 'Reemplazado por revalidación manual' 
            WHERE estado = 'En Proceso' AND id != %s
        """, (registro_id,))

        # 2. Actualizar el registro seleccionado a 'En Proceso'
        cursor.execute("""
            UPDATE ris.registro_acciones 
            SET estado = 'En Proceso', `update` = NOW() 
            WHERE id = %s
        """, (registro_id,))
        filas = cursor.rowcount
        conn.commit()

        # 3. Obtener los datos del registro actualizado
        cursor.execute("""
            SELECT id, inicio, doctor_detectado, User, numero_documento, examen, estado 
            FROM ris.registro_acciones 
            WHERE id = %s
        """, (registro_id,))
        reg = cursor.fetchone()
        cursor.close()
        conn.close()

        if filas > 0 and reg:
            f_dt = reg.get("inicio")
            fecha_str = f_dt.strftime("%d/%m/%Y %H:%M:%S") if hasattr(f_dt, "strftime") else (str(f_dt) if f_dt else "--")
            return True, {
                "id": reg.get("id"),
                "inicio": fecha_str,
                "doctor": reg.get("doctor_detectado") or reg.get("User") or "--",
                "numero_documento": reg.get("numero_documento") or "--",
                "examen": reg.get("examen") or "--"
            }
        return False, None
    except Exception as e:
        print(f"Error marcando registro en proceso: {e}")
        return False, None


def mostrar_menu_revalidar(chat_id, msg_id=None):
    """
    Presenta la lista de los últimos 5 registros con estado Error
    y el menú inline para seleccionar cuál debe quedar En Proceso.
    """
    errores = obtener_ultimos_errores(5)
    if not errores:
        texto = (
            "🔄 <b>Revalidar Registros</b>\n\n"
            "ℹ️ No se encontraron registros con estado <b>Error</b> en la base de datos."
        )
        if msg_id:
            editar_mensaje(chat_id, msg_id, texto, reply_markup=get_menu_ejecucion_markup())
        else:
            enviar_mensaje(chat_id, texto, reply_markup=get_menu_ejecucion_markup())
        return

    lineas = [
        "🔄 <b>Revalidar Registros con Error</b>\n",
        "Selecciona el registro que deseas poner <b>En Proceso</b> para que se ejecute en la próxima interacción:\n"
    ]

    for idx, reg in enumerate(errores, 1):
        lineas.append(
            f"<b>{idx}. Registro #{reg['id']}</b>\n"
            f"  🗓️ <b>Fecha/Hora Inicio:</b> <code>{html.escape(reg['inicio'])}</code>\n"
            f"  👨‍⚕️ <b>Doctor:</b> {html.escape(reg['doctor'])}\n"
            f"  📄 <b>N° Documento:</b> <code>{html.escape(reg['numero_documento'])}</code>\n"
            f"  🧪 <b>Examen:</b> {html.escape(reg['examen'])}\n"
        )

    mensaje_final = "\n".join(lineas)
    markup = get_menu_revalidar_markup(errores)

    if msg_id:
        editar_mensaje(chat_id, msg_id, mensaje_final, reply_markup=markup)
    else:
        enviar_mensaje(chat_id, mensaje_final, reply_markup=markup)


def obtener_ultimo_registro_casos_pendientes():
    """Consulta el último registro de la tabla casos_pendientes y devuelve el mensaje formateado."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=5)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM casos_pendientes ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return "ℹ️ No se encontraron registros en la tabla <b>casos_pendientes</b>."

        fecha_hora = row.get("fecha_hora")
        fecha_str = fecha_hora.strftime("%d/%m/%Y %H:%M:%S") if hasattr(fecha_hora, "strftime") else str(fecha_hora)
        total = row.get("total_pendientes", 0)
        cliente = row.get("cliente", "integramedica")
        obs = row.get("observacion")

        msg = "📊 <b>Conteo de Casos Pendientes</b>\n\n"
        msg += f"🏢 Cliente: <b>{cliente}</b>\n"
        msg += f"📅 Fecha y Hora: <b>{fecha_str}</b>\n"
        msg += f"🔢 Total de registros pendientes: <b>{total}</b>\n"
        if obs:
            msg += f"📝 Observación: <i>{obs}</i>\n"
        return msg
    except Exception as e:
        return f"❌ Error consultando casos pendientes: {e}"


def enviar_reporte_excel_por_periodo(chat_id, periodo):
    """Genera y envía el reporte Excel formateado a Telegram en segundo plano."""
    enviar_mensaje(chat_id, "⏳ <i>Generando archivo Excel del periodo seleccionado...</i>")

    def _worker():
        try:
            res = generar_excel_reporte(periodo)
            if not res.get("success"):
                err = res.get("error_msg", "Error desconocido")
                enviar_mensaje(chat_id, f"❌ Error generando el archivo Excel: {err}")
                return

            file_path = res["file_path"]
            nombre_periodo = res["nombre_periodo"]
            exitos = res["exitosos"]
            pendientes = res.get("pendientes_aprobacion", 0)
            addendums = res.get("addendums", 0)
            ya_ingresados = res.get("ya_ingresados", 0)
            completados_totales = res.get("completados_totales", exitos + pendientes + addendums + ya_ingresados)
            errores = res["errores"]
            errores_gest = res.get("errores_gestionados", 0)
            errores_pend = res.get("errores_pendientes", 0)
            proceso = res["en_proceso"]
            patologias = res["patologias_criticas"]
            tasa = res["tasa_exito"]
            total = res.get("total_casos", completados_totales + errores + proceso)

            err_detail = f" (Gestionados: {errores_gest} | Pendientes: {errores_pend})" if errores > 0 else ""
            pend_detail = f" (Gestionados: {res.get('pendientes_gestionados', 0)} | Pendientes: {res.get('pendientes_pendientes', 0)})" if pendientes > 0 else ""

            caption = (
                f"📊 <b>REPORTE EXCEL - ATRYS RPA</b>\n\n"
                f"📅 <b>Periodo:</b> {nombre_periodo}\n"
                f"🔢 <b>Total casos gestionados:</b> <b>{total}</b>\n\n"
                f"📋 <b>Desglose por Estado:</b>\n"
            )
            if completados_totales > 0:
                caption += f"• 🟢 <b>Exitosos (Total):</b> <b>{completados_totales}</b>\n"
                if exitos > 0:
                    caption += f"   ├ ✅ Completados 100%: <b>{exitos}</b>\n"
                if pendientes > 0:
                    caption += f"   ├ ⏳ Aprobación Pendiente: <b>{pendientes}</b>{pend_detail}\n"
                if addendums > 0:
                    caption += f"   ├ 📝 Addendum: <b>{addendums}</b>\n"
                if ya_ingresados > 0:
                    caption += f"   └ 🔁 Ya Ingresado: <b>{ya_ingresados}</b>\n"
            else:
                caption += "• 🟢 <b>Exitosos (Total):</b> <b>0</b>\n"

            caption += f"• ❌ <b>Con Incidencias:</b> <b>{errores}</b>{err_detail}\n"
            if proceso > 0:
                caption += f"• 🔄 <b>En Proceso:</b> <b>{proceso}</b>\n"

            caption += (
                f"\n📈 <b>Tasa de Efectividad:</b> <b>{tasa}</b>\n"
                f"🚨 <b>Patologías Críticas:</b> <b>{patologias}</b>\n\n"
                f"📁 <i>Archivo adjunto listo para consultar.</i>"
            )

            if not enviar_documento(chat_id, file_path, caption):
                enviar_mensaje(chat_id, f"⚠️ No se pudo enviar el archivo adjunto.\n\n{caption}")
        except Exception as e:
            enviar_mensaje(chat_id, f"❌ Error en la exportación Excel: {e}")

    threading.Thread(target=_worker, daemon=True, name="ExcelReportWorker").start()
