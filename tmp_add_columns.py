import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ris"
}

def add_columns():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check if columns exist first or just try to add them
        try:
            cursor.execute("ALTER TABLE registro_acciones ADD COLUMN fecha_hora_envio DATETIME;")
            print("Added fecha_hora_envio")
        except Exception as e:
            print("Column fecha_hora_envio might already exist:", e)

        try:
            cursor.execute("ALTER TABLE registro_acciones ADD COLUMN estado_notificacion VARCHAR(50);")
            print("Added estado_notificacion")
        except Exception as e:
            print("Column estado_notificacion might already exist:", e)

        try:
            cursor.execute("ALTER TABLE registro_acciones ADD COLUMN fecha_actualizacion_notificacion DATETIME;")
            print("Added fecha_actualizacion_notificacion")
        except Exception as e:
            print("Column fecha_actualizacion_notificacion might already exist:", e)

        conn.commit()
        
        # describe the table to verify
        cursor.execute("DESCRIBE registro_acciones;")
        for row in cursor.fetchall():
            print(row[0], row[1])
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_columns()
