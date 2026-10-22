# -*- coding: utf-8 -*-
import os
import sys
import json
import time
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "rpa_framework"))

from core.models import Workflow
from core.workflow_executor import WorkflowExecutor

def set_execution_state(is_running, workflow_name=""):
    state_file = root_dir / "tmp" / "execution_state.json"
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "is_running": is_running,
            "workflow_name": workflow_name,
            "updated_at": time.time()
        }
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error escribiendo execution_state: {e}")

def main():
    wf_path = root_dir / "rpa_framework" / "workflows" / "pacs.json"
    print(f"🚀 Iniciando ejecución de {wf_path}...")
    wf = Workflow.from_json(str(wf_path))
    set_execution_state(True, "pacs")
    try:
        executor = WorkflowExecutor(wf)
        result = executor.execute()
        print("🏁 Ejecución finalizada con resultado:", result)
        return result
    finally:
        set_execution_state(False)

if __name__ == "__main__":
    main()
