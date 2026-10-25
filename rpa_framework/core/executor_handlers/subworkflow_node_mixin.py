"""
Mixin para ejecución de sub-workflows anidados (WorkflowNode).
"""

from pathlib import Path
from typing import Optional
from core.models import Workflow, WorkflowNode


class SubworkflowNodeMixin:
    """Mixin para ejecutar nodos WorkflowNode (sub-workflows anidados)."""

    def _execute_workflow(self, node) -> Optional[str]:
        """
        Ejecuta un workflow anidado.
        """
        if not isinstance(node, WorkflowNode):
            self.logger.log(f"❌ Nodo no es WorkflowNode: {node.id}")
            return self.workflow.get_next_node(node.id)
            
        wf_path = node.workflow_path
        if not wf_path:
            self.logger.log("⚠️ Nodo Workflow sin ruta definida")
            return self.workflow.get_next_node(node.id)
            
        self.logger.log(f"🔄 Preparando ejecución de workflow anidado: {wf_path}")
        
        # Resolver ruta
        path_obj = Path(wf_path)
        if not path_obj.is_absolute():
            # Intentar en rpa_framework/workflows
            base_dir = Path("rpa_framework/workflows")
            if not base_dir.exists():
                 base_dir = Path("workflows")
            
            candidate = base_dir / wf_path
            # Si tiene extensión .json bien, sino probar agregandola
            if not candidate.exists() and not candidate.suffix:
                candidate = candidate.with_suffix(".json")
            
            if candidate.exists():
                path_obj = candidate
            else:
                # Fallback: intentar desde cwd
                path_obj = Path(wf_path).resolve()

        if not path_obj.exists():
             self.logger.log(f"❌ Archivo de workflow no encontrado: {path_obj}")
             if getattr(node, 'on_error', 'stop') == 'stop':
                 raise FileNotFoundError(f"Workflow no encontrado: {path_obj}")
             return self.workflow.get_next_node(node.id)
             
        try:
            # Cargar nested workflow
            nested_wf = Workflow.from_json(str(path_obj))
            
            # Inicializar variables con el contexto actual
            # (Sobreescribiendo las defaults del nested)
            nested_wf.variables.update(self.context)
            
            # Crear executor (usando la misma clase WorkflowExecutor del padre)
            nested_executor = self.__class__(nested_wf, self.logger.log_dir, is_sub_workflow=True)
            self.nested_executor = nested_executor
            
            # --- PATCH LOGGER ---
            # Para que los logs del hijo suban al padre (y a la UI)
            original_child_log = nested_executor.logger.log
            def bridged_log(msg, level="INFO"):
                prefix = f"   [WF:{nested_wf.name}]"
                self.logger.log(f"{prefix} {msg}", level)
            
            nested_executor.logger.log = bridged_log
            # --------------------
            
            self.logger.log(f"▶️ Iniciando sub-workflow: {nested_wf.name}")
            try:
                result = nested_executor.execute()
            finally:
                self.nested_executor = None
            
            status = result.get("status") if isinstance(result, dict) else "unknown"
            is_ext = self._external_stop or getattr(nested_executor, '_external_stop', False)
            if status == "no_records":
                self.logger.log("ℹ️ Sub-workflow finalizado sin registros para trabajar. Terminando flujo actual de forma limpia.")
                self.no_records_found = True
                self.should_stop = True
                return None
            elif status == "stopped" or self.should_stop:
                if is_ext:
                    self.logger.log("⏹️ Sub-workflow detenido por el usuario. Deteniendo padre.")
                    self.should_stop = True
                    self._external_stop = True
                else:
                    self.logger.log("⏹️ Sub-workflow detenido internamente.")
                    self.should_stop = True
                return None
            elif status == "error":
                if self.should_stop:
                    self.logger.log("⏹️ Sub-workflow cancelado por detención.")
                    return None
                self.logger.log(f"❌ Error en sub-workflow: {result.get('error')}")
                if getattr(node, 'on_error', 'stop') == 'stop':
                     raise RuntimeError(f"Fallo en sub-workflow: {result.get('error')}")
                else:
                     prefix = f"{self.workflow.name}_{nested_wf.name}"
                     self._save_and_send_error_video(f"Sub-workflow {nested_wf.name}: {result.get('error')}", custom_prefix=prefix)
                     if not self.should_stop:
                         self._restart_screen_recorder()
            else:
                self.logger.log(f"✅ Sub-workflow finalizado correctamente")
                # Actualizar contexto padre con resultados del hijo
                self.context.update(result.get("context", {}))
        
        except Exception as e:
            self.logger.log(f"❌ Error ejecutando nodo workflow: {e}")
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise e
            else:
                prefix = f"{self.workflow.name}_{node.label}"
                self._save_and_send_error_video(f"Excepción en sub-workflow {node.label}: {e}", custom_prefix=prefix)
                if not self.should_stop:
                    self._restart_screen_recorder()
                
        return self.workflow.get_next_node(node.id)
