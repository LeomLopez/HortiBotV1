import psycopg2
from config.config import DATABASE_URL

# ----------------------------
# Conexión a la base de datos
# ----------------------------
def get_db_connection():
    try:
        print("🔗 Conectando con la base de datos...")
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ Error al conectar con la base de datos: {e}")
        return None


# ----------------------------
# Crear tabla (si no existe)
# ----------------------------
def crear_tablas_productos():
    """
    Crea la tabla de movimientos si no existe, con la estructura necesaria.
    """
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
            unidade VARCHAR(50),
            grupo VARCHAR(50),
            fecha_movimiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(nombre, tipo, fecha_producto, unidade, grupo)
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Tabla 'movimientos' creada o ya existente.")


# ----------------------------
# Insertar producto / movimiento
# ----------------------------
def insertar_producto(nombre, cantidad, tipo, fecha_producto, unidade, grupo):
    """
    Inserta o actualiza un movimiento (entrada, salida, descarte, devolución).
    Suma cantidades si ya existe el mismo registro.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Normalizar datos
    nombre = nombre.lower()
    tipo = tipo.lower()
    unidade = unidade.lower()
    grupo = grupo.upper()  # En mayúsculas para coincidir con GRUPOS_MAP

    cursor.execute("""
        INSERT INTO movimientos (nombre, cantidad, tipo, fecha_producto, unidade, grupo)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (nombre, tipo, fecha_producto, unidade, grupo)
        DO UPDATE SET cantidad = movimientos.cantidad + EXCLUDED.cantidad;
    """, (nombre, cantidad, tipo, fecha_producto, unidade, grupo))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ Producto '{nombre}' ({grupo}) actualizado/inserido com sucesso.")


# ----------------------------
# Obtener productos
# ----------------------------
def obtener_productos(nombre=None):
    """
    Devuelve todos los movimientos registrados.
    Si se pasa nombre, filtra por producto.
    Retorna: id, nombre, cantidad, tipo, fecha_producto, unidade, grupo, fecha_movimiento
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if nombre:
        cursor.execute("""
            SELECT id, nombre, cantidad, tipo, fecha_producto, unidade, grupo, fecha_movimiento
            FROM movimientos
            WHERE nombre = %s
            ORDER BY fecha_producto ASC
        """, (nombre,))
    else:
        cursor.execute("""
            SELECT id, nombre, cantidad, tipo, fecha_producto, unidade, grupo, fecha_movimiento
            FROM movimientos
            ORDER BY fecha_producto ASC
        """)

    productos = cursor.fetchall()
    cursor.close()
    conn.close()

    return productos

