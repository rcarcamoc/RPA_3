import mysql.connector
from datetime import datetime, timedelta
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
cursor = conn.cursor(dictionary=True)
seven_days_ago = datetime(2026, 10, 22) - timedelta(days=7)

print(f"Buscando desde: {seven_days_ago}")

cursor.execute('''
    SELECT estado, COUNT(*) as cnt
    FROM ris.registro_acciones
    WHERE inicio >= %s
    GROUP BY estado
''', (seven_days_ago,))
print('\n=== TODOS LOS ESTADOS ULTIMOS 7 DIAS ===')
for r in cursor.fetchall():
    print(r)

cursor.execute('''
    SELECT estado, ultimo_nodo, observacion, COUNT(*) as cnt
    FROM ris.registro_acciones
    WHERE inicio >= %s AND (LOWER(estado) LIKE '%error%' OR estado = 'error')
    GROUP BY estado, ultimo_nodo, observacion
    ORDER BY cnt DESC
''', (seven_days_ago,))

rows = cursor.fetchall()
total_errors = sum(r['cnt'] for r in rows)
print(f'\n=== ERRORES ULTIMOS 7 DIAS (Total errores: {total_errors}) ===')
for r in rows:
    nodo = r['ultimo_nodo']
    est = r['estado']
    cnt = r['cnt']
    obs = (r['observacion'] or '')[:120].replace('\n', ' ')
    print(f"[{cnt} veces] Nodo: {nodo} | Estado: {est} | Obs: {obs}")

# Detalle específico de los de busqueda triple
cursor.execute('''
    SELECT id, inicio, numero_documento, examen, fecha_agendada, ultimo_nodo, observacion
    FROM ris.registro_acciones
    WHERE inicio >= %s AND (ultimo_nodo LIKE '%triple%' OR observacion LIKE '%triple%')
    ORDER BY id DESC
''', (seven_days_ago,))
triple_rows = cursor.fetchall()
print(f'\n=== CASOS ESPECIFICOS BUSQUEDA TRIPLE ULTIMOS 7 DIAS (Total: {len(triple_rows)}) ===')
for r in triple_rows:
    print(f"ID {r['id']} | Fecha: {r['inicio']} | Doc: {r['numero_documento']} | Examen: {r['examen']} | Nodo: {r['ultimo_nodo']}")
    print(f"   Obs: {r['observacion']}")

conn.close()
