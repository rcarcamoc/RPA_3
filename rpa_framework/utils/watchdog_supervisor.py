# -*- coding: utf-8 -*-
"""
watchdog_supervisor.py
======================
Supervisor autónomo (Watchdog) para la detección y auto-recuperación de casos congelados.

Reglas de negocio:
1. Umbral de inactividad: Si un caso en 'ris.registro_acciones' permanece en estado 'En Proceso'
   por más de 12 minutos (>= 720 segundos), se considera congelado.
2. Acción de descongelación:
   - Notifica a Telegram.
   - Detiene la ejecución actual y liquida cualquier proceso huérfano de Python/RPA.
3. Enrutamiento inteligente:
   - Si el caso TIENE la información del examen completa (paciente, fecha agendada, examen/diagnóstico),
     se ejecuta ÚNICAMENTE la fase de PACS (workflows/pacs.json).
   - Si la información está INCOMPLETA (se trabó en fase RIS antes de la extracción), se marca el caso
     como 'Error' con su debida observación.
4. Continuidad operativa:
   - Al finalizar PACS (con éxito o fallo controlado) o al descartar el caso incompleto,
     el Watchdog reanuda automáticamente el bucle principal (loop.json) para que el bot
     siga gestionando los siguientes casos de la cola.
"""

import os
import sys
import time
import logging
import threading
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger("watchdog_supervisor")

DB_CONFIG = dict(
    host='localhost',
    user='root',
    password='',
    database='ris',
    connect_timeout=3
)

TIMEOUT_SECONDS = 720  # 12 minutos
CHECK_INTERVAL_SECONDS = 30  # Revisar cada 30 segundos
MAX_REINTENTOS_PACS = 2  # Reintentos automáticos para fase PACS

_watchdog_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_is_recovering = False
_recovering_lock = threading.Lock()

# Callbacks inyectados desde servicio_bot_telegram.py
_start_wf_callback: Optional[Callable[..., bool]] = None
_stop_wf_callback: Optional[Callable[..., Any]] = None
_is_running_callback: Optional[Callable[[], bool]] = None
_get_loop_params_callback: Optional[Callable[[], Dict[str, Any]]] = None


def is_watchdog_recovering() -> bool:
    """Retorna True si el Watchdog está en proceso activo de auto-recuperación."""
    return _is_recovering


def set_watchdog_callbacks(
    start_wf_func: Callable[..., bool],
    stop_wf_func: Callable[..., Any],
    is_running_func: Callable[[], bool],
    get_loop_params_func: Optional[Callable[[], Dict[str, Any]]] = None
):
    """Configura las funciones del orquestador necesarias para la auto-recuperación."""
    global _start_wf_callback, _stop_wf_callback, _is_running_callback, _get_loop_params_callback
    _start_wf_callback = start_wf_func
    _stop_wf_callback = stop_wf_func
    _is_running_callback = is_running_func
    _get_loop_params_callback = get_loop_params_func


def _notificar_telegram(mensaje: str, record_id: Optional[int] = None):
    """Envía una alerta formateada a todos los destinatarios de Telegram."""
    try:
        from utils.telegram_manager import enviar_alerta_todos
        enviar_alerta_todos(mensaje, record_id=record_id)
    except Exception as e:
        logger.error(f"[Watchdog] Error enviando alerta a Telegram: {e}")


def _kill_stuck_rpa_processes():
    """Elimina procesos hijos de Python colgados relacionados a RPA."""
    try:
        import psutil
        current_pid = os.getpid()
        targets = [
            'busqueda_triple', 'abre_pacs', 'ingresa_user_pacs',
            'busqueda_paciente', 'pega en word', 'actualiza_estado',
            'preparar_examen'
        ]
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.pid == current_pid:
                    continue
                name = (proc.info.get('name') or '').lower()
                if 'python' in name:
                    cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                    if any(t in cmdline for t in targets):
                        logger.warning(f"[Watchdog] Forzando cierre de subproceso RPA: PID {proc.pid} ({proc.name()})")
                        if sys.platform == "win32":
                            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=3)
                        proc.kill()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"[Watchdog] Error en limpieza de procesos: {e}")


def _wait_until_idle(timeout=25) -> bool:
    """Espera activamente a que el orquestador termine y libere cualquier workflow previo."""
    end_time = time.time() + timeout
    while time.time() < end_time:
        if _is_running_callback and not _is_running_callback():
            time.sleep(1.5)  # Margen para que hilos y sockets liberen
            return True
        time.sleep(0.5)

    # Si expiró el timeout, intentar verificar y resetear execution_state si quedó huérfano
    try:
        state_file = Path(__file__).resolve().parent.parent / "config" / "execution_state.json"
        if state_file.exists():
            import json
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get("is_running", False):
                logger.warning("[Watchdog] Forzando reseteo de execution_state.json tras timeout de espera.")
                from servicio_bot_telegram import set_execution_state
                set_execution_state(False)
    except Exception:
        pass

    time.sleep(1.0)
    return (_is_running_callback is None or not _is_running_callback())


def _retomar_bucle_principal():
    """Retoma el bucle principal de procesamiento de casos."""
    logger.info("[Watchdog] Retomando bucle principal...")
    
    # Esperar a que la ejecución previa (ej: pacs.json o cancelación) termine por completo
    _wait_until_idle(timeout=30)

    loop_params = None
    if _get_loop_params_callback:
        try:
            loop_params = _get_loop_params_callback()
        except Exception:
            pass

    if not loop_params:
        loop_params = {"tipo": "infinite", "valor": "9999"}

    if _start_wf_callback:
        iniciado = False
        for intento in range(5):
            if _start_wf_callback("loop.json", loop_params):
                iniciado = True
                _notificar_telegram(
                    "🚀 <b>WATCHDOG: Bucle principal retomado exitosamente.</b>\n"
                    f"Modo: <code>{loop_params.get('tipo', 'infinite')}</code>\n"
                    "El bot continúa gestionando la cola de casos."
                )
                break
            time.sleep(3)

        if not iniciado:
            _notificar_telegram(
                "⚠️ <b>WATCHDOG:</b> Se intentó retomar el bucle pero no se pudo iniciar automáticamente. "
                "Reanuda con /loop en Telegram."
            )


def _lanzar_pacs_con_reintentos(
    rec_id: int, 
    num_doc: str, 
    f_agendada: Any, 
    intento: int = 1, 
    max_intentos: int = MAX_REINTENTOS_PACS
):
    """
    Ejecuta la fase PACS para el caso especificado con auto-reintento tanto en el lanzamiento
    como si la ejecución de PACS finaliza sin éxito.
    """
    global _is_recovering
    logger.info(f"[Watchdog] Ejecutando fase PACS para #{rec_id} (Intento {intento}/{max_intentos})...")

    import mysql.connector

    # Actualizar BD a 'En Proceso' con timestamp fresco para evitar que el watchdog se dispare a sí mismo
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        obs_msg = f"Watchdog: Ejecutando fase PACS (intento {intento}/{max_intentos})"
        cur.execute("""
            UPDATE ris.registro_acciones
            SET estado = 'En Proceso',
                inicio = NOW(),
                observacion = %s,
                `update` = NOW()
            WHERE id = %s
        """, (obs_msg, rec_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e_db:
        logger.error(f"[Watchdog] Error actualizando BD para PACS (intento {intento}): {e_db}")

    def _on_pacs_finish(result):
        global _is_recovering
        time.sleep(3)
        try:
            conn_chk = mysql.connector.connect(**DB_CONFIG)
            cur_chk = conn_chk.cursor(dictionary=True)
            cur_chk.execute("SELECT estado, observacion FROM ris.registro_acciones WHERE id = %s", (rec_id,))
            row_chk = cur_chk.fetchone()
            cur_chk.close()
            conn_chk.close()

            est_final = str(row_chk.get('estado') or '').lower() if row_chk else ''
            # Estados exitosos del framework: 'terminado', 'aprobacion_pendiente', 'exitoso'
            es_exitoso = any(k in est_final for k in ['terminado', 'aprobacion_pendiente', 'exitoso'])

            if es_exitoso:
                _notificar_telegram(
                    f"✅ <b>WATCHDOG: Caso #{rec_id} completado con éxito en PACS.</b>\n"
                    f"▶️ Retomando bucle principal de casos...",
                    record_id=rec_id
                )
                _is_recovering = False
                _retomar_bucle_principal()
                return

            logger.warning(f"[Watchdog] Caso #{rec_id} finalizó sin éxito (estado: '{est_final}') en intento {intento}/{max_intentos}.")
            if intento < max_intentos:
                _notificar_telegram(
                    f"⚠️ <b>WATCHDOG: Caso #{rec_id} no completó PACS en intento {intento}/{max_intentos}.</b>\n"
                    f"🔄 <b>Reintentando fase PACS automáticamente (intento {intento + 1} de {max_intentos})...</b>",
                    record_id=rec_id
                )
                _kill_stuck_rpa_processes()
                _wait_until_idle(timeout=25)
                # Lanzar siguiente intento de PACS
                _lanzar_pacs_con_reintentos(rec_id, num_doc, f_agendada, intento=intento + 1, max_intentos=max_intentos)
            else:
                # Se agotaron los reintentos: marcar como Error para desbloquear la cola
                conn_err = mysql.connector.connect(**DB_CONFIG)
                cur_err = conn_err.cursor()
                cur_err.execute("""
                    UPDATE ris.registro_acciones
                    SET estado = 'Error',
                        observacion = 'Watchdog: Se agotaron los reintentos de PACS. Marcado como Error para continuar cola.',
                        `update` = NOW()
                    WHERE id = %s AND estado = 'En Proceso'
                """, (rec_id,))
                conn_err.commit()
                cur_err.close()
                conn_err.close()

                _notificar_telegram(
                    f"❌ <b>WATCHDOG: Caso #{rec_id} agotó los reintentos de PACS ({max_intentos}/{max_intentos}).</b>\n"
                    f"Marcado como Error para desatascar la cola.\n"
                    f"▶️ Retomando bucle principal de casos...",
                    record_id=rec_id
                )
                _is_recovering = False
                _retomar_bucle_principal()

        except Exception as e_pacs_chk:
            logger.error(f"[Watchdog] Error verificando resultado PACS: {e_pacs_chk}")
            _is_recovering = False
            _retomar_bucle_principal()

    if _start_wf_callback:
        success = False
        for sub_intento in range(1, 6):
            if _wait_until_idle(timeout=10):
                success = _start_wf_callback("pacs.json", on_finish_callback=_on_pacs_finish)
                if success:
                    logger.info(f"[Watchdog] pacs.json lanzado exitosamente para #{rec_id} (intento {intento}, sub-intento {sub_intento}).")
                    break
            logger.warning(f"[Watchdog] Esperando disponibilidad para pacs.json #{rec_id} (sub-intento {sub_intento}/5)...")
            time.sleep(3)

        if not success:
            logger.error(f"[Watchdog] No se pudo lanzar pacs.json para #{rec_id} en intento {intento}.")
            if intento < max_intentos:
                logger.info(f"[Watchdog] Reintentando preparación y lanzamiento de PACS para #{rec_id}...")
                _kill_stuck_rpa_processes()
                _wait_until_idle(timeout=20)
                _lanzar_pacs_con_reintentos(rec_id, num_doc, f_agendada, intento=intento + 1, max_intentos=max_intentos)
            else:
                try:
                    conn = mysql.connector.connect(**DB_CONFIG)
                    cur = conn.cursor()
                    cur.execute("""
                        UPDATE ris.registro_acciones
                        SET estado = 'Error',
                            observacion = 'Watchdog: No se pudo lanzar pacs.json tras reintentos.',
                            `update` = NOW()
                        WHERE id = %s
                    """, (rec_id,))
                    conn.commit()
                    cur.close()
                    conn.close()
                except Exception:
                    pass

                _notificar_telegram(
                    f"⚠️ <b>WATCHDOG: No se pudo lanzar pacs.json para el caso #{rec_id} tras varios intentos.</b>\n"
                    f"Se reanudará el bucle principal de casos.",
                    record_id=rec_id
                )
                _is_recovering = False
                _retomar_bucle_principal()
    else:
        _is_recovering = False
        _retomar_bucle_principal()


def _ejecutar_recuperacion(rec: Dict[str, Any]):
    """Ejecuta el protocolo de auto-recuperación para el registro estancado."""
    global _is_recovering
    rec_id = rec['id']
    mins = rec['mins_transcurridos']
    nodo = rec.get('ultimo_nodo') or 'Desconocido'
    exam_text = str(rec.get('examen') or '')
    
    # 1. Alerta de detección
    msg_alerta = (
        f"🚨 <b>WATCHDOG: Caso #{rec_id} congelado (>12 min)</b>\n\n"
        f"⏱️ <b>Tiempo transcurrido:</b> {mins} minutos\n"
        f"🩺 <b>Último nodo:</b> <code>{nodo}</code>\n"
        f"📋 <b>Examen:</b> <code>{exam_text[:60] if exam_text else 'N/A'}</code>\n\n"
        f"⚙️ <b>Acción:</b> Deteniendo procesos bloqueados y activando auto-recuperación..."
    )
    _notificar_telegram(msg_alerta, record_id=rec_id)

    # 2. Detener ejecución congelada
    if _stop_wf_callback:
        try:
            _stop_wf_callback(source=f"Watchdog Supervisor (>12 min, caso #{rec_id})")
        except Exception as e_stop:
            logger.error(f"[Watchdog] Error al detener ejecución: {e_stop}")

    _kill_stuck_rpa_processes()
    # Esperar activamente a que el proceso y loop anterior liberen completamente
    _wait_until_idle(timeout=25)

    # 3. Evaluar si la información del examen está completa
    num_doc = str(rec.get("numero_documento") or "").strip().replace("-", "")
    diag = str(rec.get("diagnostico") or "").strip()
    f_agendada = rec.get("fecha_agendada")
    exam = str(rec.get("examen") or "").strip()

    # Requisitos para correr únicamente PACS: paciente, fecha agendada y examen/diagnóstico
    info_completa = bool(num_doc and f_agendada and (exam or diag))

    if info_completa:
        # Caso A: Información completa -> Correr solo PACS con auto-reintento
        logger.info(f"[Watchdog] Caso #{rec_id} tiene info completa. Ejecutando exclusivamente PACS con auto-reintento...")
        _notificar_telegram(
            f"🩺 <b>WATCHDOG: Información de examen completa.</b>\n"
            f"Paciente: <code>{num_doc}</code> | Fecha: <code>{f_agendada}</code>\n\n"
            f"▶️ Ejecutando <b>únicamente la fase PACS</b> para el caso #{rec_id} (con auto-reintento)...",
            record_id=rec_id
        )
        _lanzar_pacs_con_reintentos(rec_id, num_doc, f_agendada, intento=1, max_intentos=MAX_REINTENTOS_PACS)

    else:
        # Caso B: Información incompleta -> Marcar error y reiniciar bucle
        logger.info(f"[Watchdog] Caso #{rec_id} tiene info incompleta. Marcando como Error...")
        _notificar_telegram(
            f"⚠️ <b>WATCHDOG: Información de examen incompleta.</b>\n"
            f"El caso #{rec_id} se congeló antes de extraer los datos de RIS.\n"
            f"Marcado como Error para desbloquear la cola. Retomando bucle principal...",
            record_id=rec_id
        )

        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute("""
                UPDATE ris.registro_acciones
                SET estado = 'Error',
                    observacion = 'Watchdog (>12 min): Datos de examen incompletos (fallo previo a extracción RIS).',
                    `update` = NOW()
                WHERE id = %s
            """, (rec_id,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e_db2:
            logger.error(f"[Watchdog] Error marcando caso incompleto como Error: {e_db2}")

        time.sleep(2)
        _is_recovering = False
        _retomar_bucle_principal()


def _watchdog_loop():
    """Bucle principal de supervisión cada CHECK_INTERVAL_SECONDS."""
    global _is_recovering
    logger.info("🛡️ [Watchdog] Supervisor de casos congelados iniciado (Umbral: 12 minutos).")

    while not _stop_event.is_set():
        try:
            time.sleep(CHECK_INTERVAL_SECONDS)
            if _stop_event.is_set():
                break

            with _recovering_lock:
                if _is_recovering:
                    continue

            # Consultar base de datos por caso 'En Proceso'
            import mysql.connector
            conn = mysql.connector.connect(**DB_CONFIG)
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT 
                    id, 
                    inicio, 
                    `update`,
                    TIMESTAMPDIFF(SECOND, COALESCE(`update`, inicio), NOW()) AS segs_inactividad,
                    TIMESTAMPDIFF(MINUTE, COALESCE(`update`, inicio), NOW()) AS mins_inactividad,
                    TIMESTAMPDIFF(SECOND, inicio, NOW()) AS segs_totales,
                    TIMESTAMPDIFF(MINUTE, inicio, NOW()) AS mins_totales,
                    numero_documento, 
                    diagnostico, 
                    fecha_agendada, 
                    examen, 
                    ultimo_nodo,
                    observacion
                FROM ris.registro_acciones
                WHERE estado = 'En Proceso'
                ORDER BY id DESC 
                LIMIT 1
            """)
            rec = cur.fetchone()
            cur.close()
            conn.close()

            if not rec:
                continue

            segs_inactividad = rec.get('segs_inactividad') or 0
            segs_totales = rec.get('segs_totales') or 0

            # Criterio de congelamiento:
            # 1. Inactividad en el nodo actual >= 12 minutos (TIMEOUT_SECONDS = 720s) -> congelamiento real
            # O
            # 2. Duración total del caso >= 20 minutos (1200s) -> tope máximo de seguridad por caso
            es_congelado = (segs_inactividad >= TIMEOUT_SECONDS) or (segs_totales >= 1200)

            if es_congelado:
                with _recovering_lock:
                    if _is_recovering:
                        continue
                    _is_recovering = True

                mins_reporte = rec.get('mins_inactividad') if segs_inactividad >= TIMEOUT_SECONDS else rec.get('mins_totales')
                rec['mins_transcurridos'] = mins_reporte
                logger.warning(
                    f"🚨 [Watchdog] CASO CONGELADO DETECTADO: ID #{rec['id']} lleva "
                    f"{mins_reporte} minutos sin avance. Iniciando auto-recuperación..."
                )
                
                # Ejecutar recuperación en hilo separado para no bloquear el loop del watchdog
                t_rec = threading.Thread(
                    target=_ejecutar_recuperacion, 
                    args=(rec,), 
                    daemon=True, 
                    name=f"WatchdogRecov_#{rec['id']}"
                )
                t_rec.start()

        except Exception as e:
            logger.debug(f"[Watchdog] Error en ciclo de supervisión: {e}")


def start_watchdog_supervisor(
    start_wf_func: Callable[..., bool],
    stop_wf_func: Callable[..., Any],
    is_running_func: Callable[[], bool],
    get_loop_params_func: Optional[Callable[[], Dict[str, Any]]] = None
):
    """Inicia el hilo supervisor del Watchdog en segundo plano."""
    global _watchdog_thread
    set_watchdog_callbacks(start_wf_func, stop_wf_func, is_running_func, get_loop_params_func)
    
    if _watchdog_thread and _watchdog_thread.is_alive():
        logger.info("[Watchdog] El supervisor ya está activo.")
        return

    _stop_event.clear()
    _watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True, name="WatchdogSupervisor")
    _watchdog_thread.start()
    logger.info("🛡️ [Watchdog] Hilo supervisor lanzado exitosamente.")


def stop_watchdog_supervisor():
    """Detiene el hilo supervisor del Watchdog."""
    _stop_event.set()
    logger.info("🛡️ [Watchdog] Supervisor detenido.")
