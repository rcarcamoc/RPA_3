import mysql.connector

try:
    conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
    cur = conn.cursor(dictionary=True)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_terminados,
            AVG(TIMESTAMPDIFF(SECOND, inicio, `update`)) as avg_segundos,
            MIN(TIMESTAMPDIFF(SECOND, inicio, `update`)) as min_segundos,
            MAX(TIMESTAMPDIFF(SECOND, inicio, `update`)) as max_segundos
        FROM registro_acciones 
        WHERE estado LIKE 'Terminado%' AND TIMESTAMPDIFF(SECOND, inicio, `update`) BETWEEN 10 AND 1200
    """)
    res = cur.fetchone()
    print("Métricas de Casos Terminado OK:")
    print(res)
    
    # Calcular promedio por hora
    if res and res['avg_segundos']:
        avg_s = float(res['avg_segundos'])
        casos_hora = 3600.0 / avg_s
        print(f"Tiempo promedio por caso: {avg_s:.1f} segundos ({avg_s/60.0:.2f} minutos)")
        print(f"Rendimiento proyectado: {casos_hora:.1f} casos por hora")
        print(f"Proyección en 24h continuas: {casos_hora * 24:.0f} casos por día")

    cur.execute("""
        SELECT estado, COUNT(*) as qty 
        FROM registro_acciones 
        GROUP BY estado
    """)
    print("\nDistribución global de estados:")
    for row in cur.fetchall():
        print(f" - {row['estado']}: {row['qty']}")

    conn.close()
except Exception as e:
    print("Error:", e)
