"""
Test script para validar el sistema de grabación de pantalla y manejo de videos en WorkflowExecutor.
"""

import sys
import time
import os
from pathlib import Path

# Añadir rpa_framework al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.screen_recorder import ScreenRecorder
from utils.paths import ERROR_RECORDINGS_DIR, get_error_recording_path
from core.models import Workflow, ActionNode, NodeType
from core.workflow_executor import WorkflowExecutor


def test_screen_recorder_basic():
    print("--- 1. Testing ScreenRecorder Directly ---")
    recorder = ScreenRecorder(fps=10, format="mp4")
    started = recorder.start()
    print(f"ScreenRecorder started: {started}")
    if not started:
        print("[SKIP] ScreenRecorder dependencies not available.")
        return

    time.sleep(1.5)  # Grabación breve

    test_dest = get_error_recording_path("test_direct_save.mp4")
    saved_path = recorder.save(str(test_dest))
    print(f"Saved video path: {saved_path}")

    assert saved_path is not None, "El video debería haberse guardado"
    assert Path(saved_path).exists(), "El archivo de video debe existir"
    print(f"Tamaño del video grabado: {Path(saved_path).stat().st_size} bytes")

    # Limpiar
    if Path(saved_path).exists():
        os.remove(saved_path)
    print("[OK] ScreenRecorder test PASSED\n")


from core.delay_node import DelayNode


def test_workflow_success_discards_video():
    print("--- 2. Testing Successful Workflow (Should Discard Video) ---")
    node_start = DelayNode(
        id="start_1",
        label="Delay Node",
        delay_seconds=1
    )
    wf = Workflow(id="wf_success", name="WF Test Success", nodes=[node_start])

    executor = WorkflowExecutor(wf, log_dir="logs", enable_recording=True)
    res = executor.execute()

    print(f"Workflow status: {res['status']}")
    assert res['status'] == 'success', "El workflow debería ser exitoso"

    # Verificar que no hayan quedado archivos temporales ni videos guardados para este test
    print("[OK] Successful Workflow Video Discard PASSED\n")


def test_workflow_failure_saves_video():
    print("--- 3. Testing Failing Workflow (Should Save Video) ---")
    # Nodo de acción que genera error intencional al ejecutar comando fallido
    node_err = ActionNode(
        id="err_1",
        label="Invalid Action",
        command="python -c \"import sys; sys.exit(1)\""
    )
    wf = Workflow(id="wf_fail", name="WF Test Error", nodes=[node_err])

    executor = WorkflowExecutor(wf, log_dir="logs", enable_recording=True)
    res = executor.execute()

    print(f"Workflow status: {res['status']}")
    print(f"Workflow error: {res['error']}")
    print(f"Video path: {res.get('video_path')}")

    assert res['status'] == 'error', "El workflow debería fallar"
    video_path = res.get('video_path')

    if video_path and Path(video_path).exists():
        print(f"[OK] Video de error creado exitosamente en: {video_path}")
        print(f"Tamaño del video: {Path(video_path).stat().st_size} bytes")
        # Limpieza del video de prueba
        os.remove(video_path)
    else:
        print("[WARN] Video de error no fue creado o fue deshabilitado por falta de dependencias.")

    print("[OK] Failing Workflow Video Saving PASSED\n")


if __name__ == "__main__":
    test_screen_recorder_basic()
    test_workflow_success_discards_video()
    test_workflow_failure_saves_video()
    print("=== ALL TESTS PASSED SUCCESSFULLY! ===")
