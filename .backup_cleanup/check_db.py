import mysql.connector

try:
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='ris'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT id, coordenada, estado, ultimo_nodo FROM ris.registro_acciones WHERE estado = 'En Proceso'")
    rows = cursor.fetchall()
    print("Found rows in 'En Proceso':")
    for row in rows:
        print(row)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
