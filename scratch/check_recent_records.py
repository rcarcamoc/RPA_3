import mysql.connector

try:
    conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
    cur = conn.cursor(dictionary=True)
    
    cur.execute("""
        SELECT 
            id, inicio, `update`,
            TIMESTAMPDIFF(SECOND, inicio, `update`) as seg,
            estado, ultimo_nodo
        FROM registro_acciones 
        ORDER BY id DESC 
        LIMIT 25
    """)
    rows = cur.fetchall()
    print("Últimos 25 registros:")
    for r in rows:
        print(f"ID #{r['id']} | Inicio: {r['inicio']} | Estado: {r['estado']} | Duracion: {r['seg']}s | Ultimo Nodo: {r['ultimo_nodo']}")

    conn.close()
except Exception as e:
    print("Error:", e)
