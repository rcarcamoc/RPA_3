import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ris"
}

def add_column():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        try:
            cursor.execute("ALTER TABLE registro_acciones ADD COLUMN observacion VARCHAR(500);")
            print("Added observacion column")
        except Exception as e:
            print("Column observacion might already exist:", e)

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_column()
