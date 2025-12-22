from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class NodeDefinition:
    """Definition of a node type for the palette"""
    id: str  # Unique identifier (e.g., 'mysql_query', 'run_script')
    category: str
    icon: str  # Unicode or path to icon
    name: str
    description: str
    node_type_enum: str # Corresponding generic NodeType (e.g., 'database', 'action')
    fields: List[str]
    default_values: Dict[str, any] = field(default_factory=dict)

# Catalog of available nodes
NODE_CATALOG = {
    'Ejecuta un programa': [
         NodeDefinition(
            id='run_python_script',
            category='Ejecuta un programa',
            icon='🐍',
            name='Python Script',
            description='Ejecuta un script de Python',
            node_type_enum='action',
            fields=['script'],
            default_values={}
        ),
         NodeDefinition(
            id='run_command',
            category='Ejecuta un programa',
            icon='💻',
            name='System Command',
            description='Ejecuta un comando del sistema (cmd/powershell)',
            node_type_enum='action',
            fields=['script'], # Assuming we reuse script field for now or add a new one distinct for commands if needed
            default_values={'script': 'echo "Hello"'}
        ),
    ],
    'Database': [
        NodeDefinition(
            id='mysql_query',
            category='Database',
            icon='🗄',
            name='MySQL Query',
            description='Ejecuta consultas en MySQL',
            node_type_enum='database',
            fields=['host', 'port', 'user', 'password', 'database', 'query', 'operation', 'result_var'],
            default_values={'port': 3306, 'host': 'localhost', 'operation': 'SELECT'}
        ),
        # Placeholder for other DBs if implemented later
    ],
    'Control Flow': [
        NodeDefinition(
            id='if_condition',
            category='Control Flow',
            icon='◆',
            name='If / Else',
            description='Bifurcación condicional',
            node_type_enum='decision',
            fields=['condition', 'true_path', 'false_path'],
            default_values={'condition': 'x > 0'}
        ),
        NodeDefinition(
            id='loop_node',
            category='Control Flow',
            icon='↻',
            name='Loop',
            description='Repetir acciones',
            node_type_enum='loop',
            fields=['iterations', 'script'],
            default_values={'iterations': '1'}
        ),
    ],
    'Transform': [
        # Mapping to generic 'action' for now, but conceptually distinct
         NodeDefinition(
            id='json_parse',
            category='Transform',
            icon='﹛﹜',
            name='JSON Parse',
            description='Parsea un string JSON',
            node_type_enum='action',
            fields=['script'],
            default_values={'script': '# Transform logic here'}
        ),
    ],
    'Integrations': [
        # Placeholders mapping to generic 'action' or specialized nodes if available
         NodeDefinition(
            id='http_request',
            category='Integrations',
            icon='🌐',
            name='HTTP Request',
            description='Realiza una petición HTTP',
            node_type_enum='action', # Currently reusing action, ideally distinct type
            fields=['script'],
            default_values={'script': '# requests.get("...")'}
        ),
    ],
    'Documentation': [
        NodeDefinition(
            id='annotation',
            category='Documentation',
            icon='📝',
            name='Nota / Comentario',
            description='Agrega notas al workflow',
            node_type_enum='annotation',
            fields=['text', 'color'],
            default_values={'text': 'Nueva nota', 'color': '#ffffcc'}
        )
    ]
}

def get_all_nodes() -> List[NodeDefinition]:
    """Return flat list of all nodes"""
    all_nodes = []
    for cat_nodes in NODE_CATALOG.values():
        all_nodes.extend(cat_nodes)
    return all_nodes
