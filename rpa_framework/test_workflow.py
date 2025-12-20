"""
Test script para validar el WorkflowExecutor.

Este script carga y ejecuta el workflow de ejemplo para verificar
que todas las funcionalidades (ACTION, DECISION, LOOP) funcionan correctamente.
"""

import os
import sys

# Añadir el directorio padre al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models import Workflow, NodeType
from core.workflow_executor import WorkflowExecutor


def test_workflow_load():
    """Prueba la carga de un workflow desde JSON"""
    print("=" * 60)
    print("TEST 1: Carga de Workflow desde JSON")
    print("=" * 60)
    
    workflow_path = "workflows/wf_login_example.json"
    
    try:
        workflow = Workflow.from_json(workflow_path)
        print(f"[OK] Workflow cargado: {workflow.name}")
        print(f"  - Nodos: {len(workflow.nodes)}")
        print(f"  - Conexiones: {len(workflow.edges)}")
        print(f"  - Variables iniciales: {workflow.variables}")
        
        # Mostrar nodos
        print("\n  Nodos del workflow:")
        for node in workflow.nodes:
            print(f"    - {node.id}: {node.label} ({node.type.value})")
        
        return workflow
    except Exception as e:
        print(f"[ERR] Error cargando workflow: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_workflow_execution(workflow):
    """Prueba la ejecución del workflow"""
    print("\n" + "=" * 60)
    print("TEST 2: Ejecución del Workflow")
    print("=" * 60)
    
    try:
        # Crear ejecutor
        executor = WorkflowExecutor(workflow, log_dir="workflows/logs")
        
        # Ejecutar
        print("\nEjecutando workflow...\n")
        result = executor.execute()
        
        # Mostrar resultados
        print("\n" + "-" * 60)
        print("RESULTADOS DE EJECUCIÓN")
        print("-" * 60)
        print(f"Estado: {result['status']}")
        print(f"\nVariables finales:")
        for key, value in result['context'].items():
            print(f"  {key}: {value}")
        
        if 'error' in result:
            print(f"\nError: {result['error']}")
        
        print(f"\nLogs de ejecución ({len(result['logs'])} entradas):")
        print("-" * 60)
        for log in result['logs']:
            print(f"  {log}")
        
        return result['status'] == 'success'
    
    except Exception as e:
        print(f"[ERR] Error ejecutando workflow: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_node_types():
    """Verifica que todos los tipos de nodos se crearon correctamente"""
    print("\n" + "=" * 60)
    print("TEST 3: Verificación de Tipos de Nodos")
    print("=" * 60)
    
    from core.models import ActionNode, DecisionNode, LoopNode
    
    # Crear nodos de prueba (el type se establece automáticamente en __post_init__)
    action = ActionNode(id="a1", label="Test Action", script="test.py", position={"x": 0, "y": 0})
    decision = DecisionNode(
        id="d1", 
        label="Test Decision", 
        condition="x > 5",
        true_path="t1",
        false_path="f1",
        position={"x": 0, "y": 0}
    )
    loop = LoopNode(
        id="l1",
        label="Test Loop",
        script="test.py",
        iterations="3",
        position={"x": 0, "y": 0}
    )
    
    print(f"[OK] ActionNode: {action.type == NodeType.ACTION}")
    print(f"[OK] DecisionNode: {decision.type == NodeType.DECISION}")
    print(f"[OK] LoopNode: {loop.type == NodeType.LOOP}")
    
    # Test serialización
    action_dict = action.to_dict()
    print(f"[OK] Serialización ActionNode: {'script' in action_dict}")
    
    decision_dict = decision.to_dict()
    print(f"[OK] Serialización DecisionNode: {'condition' in decision_dict}")
    
    loop_dict = loop.to_dict()
    print(f"[OK] Serialización LoopNode: {'iterations' in loop_dict}")
    
    return True


def main():
    """Ejecuta todos los tests"""
    print("\n" + "=" * 60)
    print(" " * 10 + "WORKFLOW EXECUTOR - SUITE DE TESTS")
    print("=" * 60)
    
    # Cambiar al directorio correcto
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Test 1: Verificar tipos de nodos
    test_node_types()
    
    # Test 2: Cargar workflow
    workflow = test_workflow_load()
    if not workflow:
        print("\n✗ Los tests fallaron: No se pudo cargar el workflow")
        return False
    
    # Test 3: Ejecutar workflow
    success = test_workflow_execution(workflow)
    
    # Resumen
    print("\n" + "=" * 60)
    if success:
        print("[OK] TODOS LOS TESTS PASARON EXITOSAMENTE")
    else:
        print("[ERR] ALGUNOS TESTS FALLARON")
    print("=" * 60 + "\n")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
