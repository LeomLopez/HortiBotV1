import psycopg2
from config.config import DATABASE_URL
from datetime import datetime
from models.validation import (
    is_valid_unidade,
    normalize_product_name,
    normalize_unidade,
    unidade_error_message,
)

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
    Nota: Si ya existe en producción, esto no la modifica; solo sirve para instalaciones nuevas.
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
            contenedor VARCHAR(10),
            concepto VARCHAR(30),
            UNIQUE(nombre, tipo, fecha_producto, unidade, grupo, contenedor, concepto)
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Tabla 'movimientos' creada o ya existente.")


# ----------------------------
# Insertar producto / movimiento
# ----------------------------
def insertar_producto(nombre, cantidad, tipo, fecha_producto, unidade, grupo, contenedor=None, concepto=None):
    """
    Guarda histórico en 'movimientos' y actualiza 'stock_actual'.
    - 'movimientos': histórico (no borra nada).
    - 'stock_actual': estado actual (suma/resta y elimina cuando cantidad <= 0).
    """
    # Normalización obligatoria en la frontera de persistencia
    nombre = normalize_product_name(nombre)
    if not nombre:
        raise ValueError("Nome do produto inválido.")

    conn = get_db_connection()
    cursor = conn.cursor()

    if tipo: tipo = tipo.lower().strip()
    unidade = normalize_unidade(unidade)
    if not is_valid_unidade(unidade):
        raise ValueError(unidade_error_message())
    if grupo: grupo = grupo.upper().strip()

    # Normalizar concepto (área)
    if concepto is not None:
        concepto = normalize_product_name(concepto)
        if concepto == "":
            concepto = None

    # Manejo contenedor
    if grupo == "CON":
        if not contenedor:
            raise ValueError("Debe indicar contenedor (C1, C2 o C3) para congelados.")
        contenedor = str(contenedor).strip().upper()
    else:
        contenedor = "N/A"

    # Determinar signo (entradas suman; bajas restan en stock_actual)
    signo = 1 if tipo in ["entrada", "volta", "transferencia_entrada"] else -1

    # 1) Movimientos (histórico)
    cursor.execute("""
        INSERT INTO movimientos (nombre, cantidad, tipo, fecha_producto, unidade, grupo, contenedor, concepto)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """, (nombre, cantidad, tipo, fecha_producto, unidade, grupo, contenedor, concepto))

    # 2) Stock actual (estado)
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
        nombre = normalize_product_name(nombre)
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
    Devuelve el stock actual filtrado por grupo o nombre.
    Incluye productos vencidos (no filtra por fecha).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT nombre, cantidad, unidade, grupo, fecha_producto, contenedor
        FROM stock_actual
        WHERE cantidad > 0
    """
    params = []

    if grupo:
        query += " AND grupo = %s"
        params.append(grupo.upper())
    if nombre:
        query += " AND nombre = %s"
        params.append(normalize_product_name(nombre))

    query += " ORDER BY grupo, fecha_producto"

    cursor.execute(query, params)
    resultado = cursor.fetchall()

    cursor.close()
    conn.close()

    return resultado


def obtener_stock_vencido(grupo=None):
    """
    Devuelve productos vencidos que aún tienen cantidad en stock_actual.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT nombre, cantidad, unidade, grupo, fecha_producto, contenedor
        FROM stock_actual
        WHERE cantidad > 0
        AND fecha_producto < %s
    """
    params = [datetime.now().date()]

    if grupo:
        query += " AND grupo = %s"
        params.append(grupo.upper())

    query += " ORDER BY grupo, fecha_producto"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows



# Obtener producto especifico
def registrar_transferencia(
    nombre,
    cantidad,
    fecha_producto,
    unidade,
    grupo_origen,
    grupo_destino,
    contenedor_origen=None,
    contenedor_destino=None,
):
    """
    Registra una transferencia de grupo en una sola transacción:
    - transferencia_saida resta del grupo origen
    - transferencia_entrada suma al grupo destino
    """
    nombre = normalize_product_name(nombre)
    if not nombre:
        raise ValueError("Nome do produto inválido.")

    conn = get_db_connection()
    cursor = conn.cursor()

    unidade = normalize_unidade(unidade)
    if not is_valid_unidade(unidade):
        raise ValueError(unidade_error_message())
    if grupo_origen: grupo_origen = grupo_origen.upper().strip()
    if grupo_destino: grupo_destino = grupo_destino.upper().strip()

    contenedor_origen = (
        str(contenedor_origen).strip().upper()
        if grupo_origen == "CON"
        else "N/A"
    )
    contenedor_destino = (
        str(contenedor_destino).strip().upper()
        if grupo_destino == "CON"
        else "N/A"
    )

    stamp = datetime.now().strftime("%H%M%S%f")
    concepto_saida = f"p:{grupo_destino}:{stamp}"
    concepto_entrada = f"d:{grupo_origen}:{stamp}"

    try:
        cursor.execute("""
            INSERT INTO movimientos
                (nombre, cantidad, tipo, fecha_producto, unidade, grupo, contenedor, concepto)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s),
                (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            nombre, cantidad, "transferencia_saida", fecha_producto, unidade,
            grupo_origen, contenedor_origen, concepto_saida,
            nombre, cantidad, "transferencia_entrada", fecha_producto, unidade,
            grupo_destino, contenedor_destino, concepto_entrada,
        ))

        cursor.execute("""
            UPDATE stock_actual
            SET cantidad = cantidad - %s
            WHERE nombre = %s
              AND unidade = %s
              AND grupo = %s
              AND fecha_producto = %s
              AND contenedor = %s;
        """, (cantidad, nombre, unidade, grupo_origen, fecha_producto, contenedor_origen))

        if cursor.rowcount == 0:
            raise ValueError("Lote de origem não encontrado para transferência.")

        cursor.execute("""
            INSERT INTO stock_actual (nombre, unidade, grupo, fecha_producto, contenedor, cantidad)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (nombre, unidade, grupo, fecha_producto, contenedor)
            DO UPDATE SET cantidad = stock_actual.cantidad + EXCLUDED.cantidad;
        """, (nombre, unidade, grupo_destino, fecha_producto, contenedor_destino, cantidad))

        cursor.execute("DELETE FROM stock_actual WHERE cantidad <= 0;")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def registrar_operacion_lote(modo, items):
    """Registra todos los items de un flujo guiado en una sola transacción."""
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("Não foi possível conectar ao banco de dados.")

    cursor = conn.cursor()
    try:
        for index, raw_item in enumerate(items, start=1):
            item = dict(raw_item)
            nombre = normalize_product_name(item.get("nome"))
            unidade = normalize_unidade(item.get("unidade"))
            grupo = (item.get("grupo") or "").upper().strip()
            contenedor = (
                str(item.get("contenedor") or "").upper().strip()
                if grupo == "CON"
                else "N/A"
            )
            cantidad = int(item.get("quantidade") or 0)

            if not nombre or cantidad <= 0 or not is_valid_unidade(unidade):
                raise ValueError(f"Item {index} inválido para gravação.")

            if modo == "mover":
                destino_grupo = (item.get("destino_grupo") or "").upper().strip()
                destino_contenedor = (
                    str(item.get("destino_contenedor") or "").upper().strip()
                    if destino_grupo == "CON"
                    else "N/A"
                )
                stamp = datetime.now().strftime("%H%M%S%f")
                cursor.execute(
                    """
                    INSERT INTO movimientos
                        (nombre, cantidad, tipo, fecha_producto, unidade, grupo, contenedor, concepto)
                    VALUES
                        (%s, %s, 'transferencia_saida', %s, %s, %s, %s, %s),
                        (%s, %s, 'transferencia_entrada', %s, %s, %s, %s, %s);
                    """,
                    (
                        nombre, cantidad, item["fecha_producto"], unidade, grupo,
                        contenedor, f"p:{destino_grupo}:{stamp}",
                        nombre, cantidad, item["fecha_producto"], unidade, destino_grupo,
                        destino_contenedor, f"d:{grupo}:{stamp}",
                    ),
                )
                cursor.execute(
                    """
                    UPDATE stock_actual
                    SET cantidad = cantidad - %s
                    WHERE nombre = %s AND unidade = %s AND grupo = %s
                      AND fecha_producto = %s AND contenedor = %s
                      AND cantidad >= %s;
                    """,
                    (cantidad, nombre, unidade, grupo, item["fecha_producto"], contenedor, cantidad),
                )
                if cursor.rowcount != 1:
                    raise ValueError(f"Item {index}: lote de origem inexistente ou sem estoque suficiente.")
                cursor.execute(
                    """
                    INSERT INTO stock_actual (nombre, unidade, grupo, fecha_producto, contenedor, cantidad)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (nombre, unidade, grupo, fecha_producto, contenedor)
                    DO UPDATE SET cantidad = stock_actual.cantidad + EXCLUDED.cantidad;
                    """,
                    (nombre, unidade, destino_grupo, item["fecha_producto"], destino_contenedor, cantidad),
                )
                continue

            tipo = item["tipo"]
            concepto = item.get("concepto")
            if concepto is not None:
                concepto = normalize_product_name(concepto) or None
            signo = 1 if tipo in {"entrada", "volta", "transferencia_entrada"} else -1
            cursor.execute(
                """
                INSERT INTO movimientos
                    (nombre, cantidad, tipo, fecha_producto, unidade, grupo, contenedor, concepto)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (nombre, cantidad, tipo, item["fecha_producto"], unidade, grupo, contenedor, concepto),
            )
            cursor.execute(
                """
                INSERT INTO stock_actual (nombre, unidade, grupo, fecha_producto, contenedor, cantidad)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (nombre, unidade, grupo, fecha_producto, contenedor)
                DO UPDATE SET cantidad = stock_actual.cantidad + EXCLUDED.cantidad * %s;
                """,
                (nombre, unidade, grupo, item["fecha_producto"], contenedor, cantidad, signo),
            )

        cursor.execute("DELETE FROM stock_actual WHERE cantidad <= 0;")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def obtener_lote_stock_actual(nombre, grupo, fecha_producto, contenedor=None, unidade=None):
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
        normalize_product_name(nombre),
        (grupo or "").upper().strip(),
        fecha_producto,
    ]

    if grupo and grupo.upper().strip() == "CON":
        sql += " AND contenedor = %s"
        params.append((contenedor or "N/A").upper().strip())

    if unidade:
        sql += " AND unidade = %s"
        params.append(normalize_unidade(unidade))

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
    q = normalize_product_name(query)
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
