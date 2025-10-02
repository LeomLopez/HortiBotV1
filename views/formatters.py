# formatters.py
from datetime import date, datetime

__all__ = ["mensaje_por_fecha_from_tuples", "mensaje_por_nombre_from_tuples"]

# ── Helpers ────────────────────────────────────────────────────────────────────
def _only_date(d):
    if d is None: 
        return None
    if isinstance(d, datetime):
        return d.date()
    return d



def _fmt_fecha(venc):
    return venc.strftime("%d/%m") if venc else "—"

def _consolidar_por_nombre_unidad_fecha(rows_tuples):
    """
    Convierte la lista de filas en un dict:
    key = (nombre, unidad, vencimiento_date) -> cantidad_total
    """
    acc = {}
    for nombre, cantidad, unidad, _grupo, venc, _contenedor in rows_tuples:
        nombre = (nombre or "").strip()
        unidad = (unidad or "").strip()
        venc_d = _only_date(venc)
        cant = int(cantidad or 0)
        key = (nombre, unidad, venc_d)
        acc[key] = acc.get(key, 0) + cant
    return acc

# ── Vista 1: Ordenada por fecha (la más próxima arriba) ───────────────────────
def mensaje_por_fecha_from_tuples(rows_tuples, titulo_grupo="Inventario"):
    """
    Muestra cada lote como una línea, ordenando por fecha (próximas primero).
    Si un mismo producto tiene varias fechas, aparecen como líneas separadas.
    """
    acc = _consolidar_por_nombre_unidad_fecha(rows_tuples)

    def sort_key(item_key):
        nombre, _unidad, venc = item_key
        # 1) con fecha primero; 2) fecha asc; 3) nombre asc para desempatar
        return (0 if venc is not None else 1, venc or date.max, nombre.lower())

    lineas = [f"📦 *Estoque – {titulo_grupo}*"]
    for (nombre, unidad, venc), cant in sorted(acc.items(), key=lambda kv: sort_key(kv[0])):
        suf = f" {unidad}" if unidad else ""
        lineas.append(f"• {nombre}: {cant}{suf} ({_fmt_fecha(venc)})")

    return "\n".join(lineas)

# ── Vista 2: Detallada/alfabética (agrupa el producto y lista sus fechas) ─────
def mensaje_por_nombre_from_tuples(rows_tuples, titulo_grupo="Inventario"):
    """
    Agrupa por (nombre, unidad) y lista sus lotes (cantidad + vencimiento)
    ordenados por fecha ascendente. Si hay fechas repetidas, suma cantidades.
    """
    acc = _consolidar_por_nombre_unidad_fecha(rows_tuples)

    # agrupar por (nombre, unidad)
    grupos = {}
    for (nombre, unidad, venc), cant in acc.items():
        grupos.setdefault((nombre, unidad), []).append((venc, cant))

    def sort_lote(lote):
        venc, _cant = lote
        return (0 if venc is not None else 1, venc or date.max)

    lineas = [f"📦 *Estoque – {titulo_grupo}*"]
    for (nombre, unidad) in sorted(grupos.keys(), key=lambda k: k[0].lower()):
        lineas.append(f"{nombre}")
        for venc, cant in sorted(grupos[(nombre, unidad)], key=sort_lote):
            suf = f" {unidad}" if unidad else ""
            lineas.append(f"• {cant}{suf} – ({_fmt_fecha(venc)})")
        lineas.append("")  # separación entre productos

    return "\n".join(lineas).rstrip()

