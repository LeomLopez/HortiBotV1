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
def insertar_producto(nombre, cantidad, tipo, fecha_producto, unidade, grupo, contenedor=None):
    """
    Consolida movimientos idénticos en 'movimientos' y actualiza 'stock_actual'.
    - 'movimientos': guarda histórico consolidado (no borra nada).
    - 'stock_actual': refleja el estado actual y elimina cuando cantidad <= 0.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Normalización
    if nombre: nombre = nombre.lower()
    if tipo: tipo = tipo.lower()
    if unidade: unidade = unidade.lower()
    if grupo: grupo = grupo.upper()

    # Manejo contenedor
    if grupo == "CON":
        if not contenedor:
            raise ValueError("Debe indicar contenedor (C1, C2 o C3) para congelados.")
        contenedor = contenedor.upper()
    else:
        contenedor = "N/A"

    # Determinar signo (entrada suma, salida/descarte resta en stock_actual)
    signo = 1 if tipo == "entrada" else -1

    # 1. Movimientos: Consolidar por clave única
    cursor.execute("""
        INSERT INTO movimientos (nombre, cantidad, tipo, fecha_producto, unidade, grupo, contenedor)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (nombre, tipo, fecha_producto, unidade, grupo, contenedor)
        DO UPDATE SET cantidad = movimientos.cantidad + EXCLUDED.cantidad;
    """, (nombre, cantidad, tipo, fecha_producto, unidade, grupo, contenedor))

    # 2. Stock actual: Actualizar y limpiar si cantidad <= 0
    cursor.execute("""
        INSERT INTO stock_actual (nombre, unidade, grupo, fecha_producto, contenedor, cantidad)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (nombre, unidade, grupo, fecha_producto, contenedor)
        DO UPDATE SET cantidad = stock_actual.cantidad + EXCLUDED.cantidad * %s;
    """, (nombre, unidade, grupo, fecha_producto, contenedor, cantidad, signo))

    cursor.execute("DELETE FROM stock_actual WHERE cantidad <= 0;")

    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ Producto '{nombre}' ({tipo}) registrado con éxito.")

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

from datetime import datetime

def obtener_stock_actual(grupo=None, nombre=None):
    """
    Devuelve el stock actual filtrado por grupo o nombre,
    ignorando productos vencidos.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT nombre, cantidad, unidade, grupo, fecha_producto, contenedor
        FROM stock_actual
        WHERE cantidad > 0 AND fecha_producto >= %s
    """
    params = [datetime.now().date()]

    if grupo:
        query += " AND grupo = %s"
        params.append(grupo.upper())
    if nombre:
        query += " AND nombre = %s"
        params.append(nombre.lower())

    query += " ORDER BY grupo, fecha_producto"

    cursor.execute(query, params)
    resultado = cursor.fetchall()

    cursor.close()
    conn.close()

    return resultado

