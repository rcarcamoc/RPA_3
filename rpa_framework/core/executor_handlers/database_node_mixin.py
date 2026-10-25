"""
Mixin para ejecución de nodos de base de datos (DatabaseNode: SELECT, INSERT, UPDATE, DELETE).
"""

from typing import Optional
import mysql.connector
from mysql.connector import Error as MySQLError


class DatabaseNodeMixin:
    """Mixin para ejecutar DatabaseNode sobre MySQL e inyectar resultados en el contexto."""

    def _execute_database(self, node) -> Optional[str]:
        """
        Ejecuta un nodo de base de datos.
        
        Args:
            node: DatabaseNode a ejecutar
            
        Returns:
            ID del siguiente nodo
        """
        from core.database_node import DatabaseNode
        
        if not isinstance(node, DatabaseNode):
            self.logger.log(f"❌ Nodo no es DatabaseNode: {node.id}")
            return self.workflow.get_next_node(node.id)
        
        self.logger.log(f"🗄️ Ejecutando nodo DB: {node.label}")
        self.logger.log(f"   Operación: {node.operation}")
        self.logger.log(f"   Host: {node.host}:{node.port}")
        self.logger.log(f"   Database: {node.database}")
        
        connection = None
        try:
            # Conectar a MySQL
            connection = mysql.connector.connect(
                host=node.host,
                port=node.port,
                user=node.user,
                password=node.password,
                database=node.database
            )
            
            if connection.is_connected():
                self.logger.log(f"✅ Conectado a MySQL")
                
                cursor = connection.cursor(dictionary=True)
                
                # Reemplazar variables en la query
                query = node.query
                for var_name, var_value in self.context.items():
                    placeholder = f"{{{var_name}}}"
                    if placeholder in query:
                        # Escapar valores para prevenir SQL injection
                        if isinstance(var_value, str):
                            var_value = var_value.replace("'", "''")
                            query = query.replace(placeholder, f"'{var_value}'")
                        else:
                            query = query.replace(placeholder, str(var_value))
                
                self.logger.log(f"   Query: {query[:100]}...")
                
                # Ejecutar query
                cursor.execute(query)
                
                if node.operation.upper() == "SELECT":
                    # Para SELECT, obtener resultados
                    results = cursor.fetchall()
                    
                    # Inyectar resultados en contexto
                    if results:
                        if len(results) == 1:
                            # Un solo resultado: dict
                            self.context[node.result_var] = results[0]
                            self.logger.log(f"✅ Resultado guardado en '{node.result_var}': {results[0]}")
                        else:
                            # Múltiples resultados: lista de dicts
                            self.context[node.result_var] = results
                            self.logger.log(f"✅ {len(results)} resultados guardados en '{node.result_var}'")
                    else:
                        self.context[node.result_var] = None
                        self.logger.log(f"⚠️ No se encontraron resultados")
                else:
                    # Para INSERT/UPDATE/DELETE, hacer commit
                    connection.commit()
                    affected_rows = cursor.rowcount
                    self.logger.log(f"✅ {node.operation} ejecutado. Filas afectadas: {affected_rows}")
                    self.context[node.result_var] = {"affected_rows": affected_rows}
                
                cursor.close()
                
        except MySQLError as e:
            error_msg = f"Error MySQL: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.context[node.result_var] = {"error": str(e)}
            
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise e
            
        except Exception as e:
            error_msg = f"Error ejecutando DB: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.context[node.result_var] = {"error": str(e)}
            
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise e
            
        finally:
            if connection and connection.is_connected():
                connection.close()
                self.logger.log(f"🔌 Conexión cerrada")
        
        return self.workflow.get_next_node(node.id)
