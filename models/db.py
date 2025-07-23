import psycopg2
from config.config import DATABASE_URL

def get_db_connection():
    try:
        print("🔗Conectando con la base de datos...")
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ Error al conectar con la base de datos: {e}")
        return None
    
def crear_tablas_productos():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(255) NOT NULL,
        precio DECIMAL(10, 2),
        cantidad INT NOT NULL,
        tipo VARCHAR(50) NOT NULL,
        fecha_producto DATE NOT NULL,
        UNIQUE(nombre, tipo, fecha_producto));
""")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Tablas de movimientos creadas o ya existen.")
    
    
    
def insertar_producto(nombre, cantidad, tipo, fecha_producto, unidad="kg"):
    conn = get_db_connection()
    cursor = conn.cursor()
    nombre = nombre.lower()
    tipo = tipo.lower()
    unidad = unidad.lower()
    cursor.execute("""
        INSERT INTO movimientos (nombre, cantidad, tipo, fecha_producto, unidade)
        VALUES (%s, %s, %s, %s, %s);
    """, (nombre, cantidad, tipo, fecha_producto, unidad))
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ Produto '{nombre}' inserido com sucesso.")

    
    
def obtener_productos(nombre=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if nombre:
        cursor.execute("""
                SELECT * FROM movimientos WHERE nombre ILIKE %s;
        """, (f"%{nombre}%",))
    else:
        cursor.execute("SELECT * FROM movimientos ORDER BY fecha_producto DESC;")
        
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados
