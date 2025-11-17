import psycopg2
from config.config import DATABASE_URL
from datetime import datetime

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


#Obtener producto especifico

def obtener_lote_stock_actual(nombre, grupo, fecha_producto, contenedor=None):
    """
    Devuelve el lote actual en stock_actual para:
    - nombre
    - grupo
    - fecha_producto
    - (contenedor si es CON)

    Retorna: (nombre, cantidad, unidade, grupo, fecha_producto, contenedor) o None
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT nombre, cantidad, unidade, grupo, fecha_producto, contenedor
        FROM stock_actual
        WHERE nombre = %s
          AND grupo = %s
          AND fecha_producto = %s
    """
    params = [
        (nombre or "").lower().strip(),
        (grupo or "").upper().strip(),
        fecha_producto,
    ]

    if grupo and grupo.upper().strip() == "CON":
        sql += " AND contenedor = %s"
        params.append((contenedor or "N/A").upper().strip())

    cursor.execute(sql, params)
    row = cursor.fetchone()

    cursor.close()
    conn.close()

    return row  # None si ya no existe el lote


def obtener_ultima_actualizacion(grupo=None):
    """
    Devuelve la fecha/hora de la última actualización del stock.
    Si grupo se pasa, filtra por ese grupo.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT MAX(fecha_movimiento) FROM movimientos WHERE 1=1"
    params = []

    if grupo:
        query += " AND grupo = %s"
        params.append(grupo.upper())

    cursor.execute(query, params)
    result = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return result


# db.py
def search_productos(conn, query, limit=50, grupo=None):
    """
    Busca por 1+ palabras en productos.nombre y devuelve producto + grupo (stock),
    ordenado por similaridad. Si 'grupo' viene, filtra por ese grupo.
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    tokens = [t for t in q.split() if t]
    where_parts = []
    params = []

    # Cada token debe aparecer en el nombre (AND)
    for t in tokens:
        where_parts.append("nombre_busqueda LIKE ('%' || unaccent(lower(%s)) || '%')")
        params.append(t)

    # (Opcional) filtro por grupo exacto si lo pasas (p. ej. 'secos')
    if grupo:
        where_parts.append("lower(grupo) = lower(%s)")
        params.append(grupo)

    where_sql = " AND ".join(where_parts) if where_parts else "TRUE"

    sql = f"""
        SELECT id, nombre, grupo, stock, unidad, vencimiento
        FROM productos
        WHERE {where_sql}
        ORDER BY similarity(nombre_busqueda, unaccent(lower(%s))) DESC,
                 grupo ASC,
                 nombre ASC
        LIMIT %s;
    """
    params.append(q)
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    # Mapeo a dicts
    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "nombre": r[1],
            "grupo": r[2],        # ← aquí viene el “stock/grupo”
            "stock": r[3],
            "unidad": r[4],
            "vencimiento": r[5],
        })
    return results
