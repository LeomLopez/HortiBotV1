# formatters.py
from datetime import date, datetime

__all__ = ["mensaje_por_fecha_from_tuples", "mensaje_por_nombre_from_tuples", "mensaje_order_from_tuples"]

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
    key = (nombre, unidad, vencimiento_date, contenedor_norm) -> cantidad_total
    """
    acc = {}
    for nombre, cantidad, unidad, _grupo, venc, contenedor in rows_tuples:
        nombre = (nombre or "").strip()
        unidad = (unidad or "").strip()
        venc_d = _only_date(venc)
        cant = int(cantidad or 0)

        cont_norm = (contenedor or "").strip().upper() or "N/A"

        key = (nombre, unidad, venc_d, cont_norm)
        acc[key] = acc.get(key, 0) + cant
    return acc


# ── Vista 1: Ordenada por fecha (la más próxima arriba) ───────────────────────
def mensaje_por_fecha_from_tuples(rows_tuples, titulo_grupo="Inventario"):
    acc = _consolidar_por_nombre_unidad_fecha(rows_tuples)

    def sort_key(item_key):
        nombre, _unidad, venc, cont = item_key
        return (0 if venc is not None else 1, venc or date.max, nombre.lower(), cont)

    lineas = [f"📦 *Estoque – {titulo_grupo}*"]
    for (nombre, unidad, venc, cont), cant in sorted(acc.items(), key=lambda kv: sort_key(kv[0])):
        suf = f" {unidad}" if unidad else ""
        extra = f" ({cont})" if cont and cont != "N/A" else ""   # <- muestra C1/C2/C3
        lineas.append(f"• {nombre}: {cant}{suf}{extra} ({_fmt_fecha(venc)})")

    return "\n".join(lineas)


# ── Vista 2: Detallada/alfabética (agrupa el producto y lista sus fechas) ─────
def mensaje_por_nombre_from_tuples(rows_tuples, titulo_grupo="Inventario"):
    """
    ORDER (A–Z): Agrupa por (nombre, unidad) y lista lotes por fecha asc.
    Para CON, incluye contenedor en cada lote y evita mezclar C1/C2/C3.
    """
    acc = _consolidar_por_nombre_unidad_fecha(rows_tuples)
    # acc key: (nombre, unidad, venc, cont) -> cant

    grupos = {}
    for (nombre, unidad, venc, cont), cant in acc.items():
        grupos.setdefault((nombre, unidad), []).append((venc, cont, cant))

    def sort_lote(lote):
        venc, cont, _cant = lote
        return (0 if venc is not None else 1, venc or date.max, cont)

    lineas = [f"📦 *Estoque – {titulo_grupo}*"]
    for (nombre, unidad) in sorted(grupos.keys(), key=lambda k: k[0].lower()):
        lineas.append(f"{nombre}")
        for venc, cont, cant in sorted(grupos[(nombre, unidad)], key=sort_lote):
            suf = f" {unidad}" if unidad else ""
            extra = f" ({cont})" if cont and cont != "N/A" else ""
            lineas.append(f"• {cant}{suf}{extra} – ({_fmt_fecha(venc)})")

    return "\n".join(lineas).rstrip()

# ── Vista 3: Vista especial al usar order donde para no ocupar mucho espacio en mensaje se agrupan las lineas de un producto ─────
def mensaje_order_from_tuples(rows_tuples, titulo_grupo="Inventario", max_line_len=85):
    """
    ORDER compacto:
    - Orden A–Z por producto
    - Dentro del producto: lotes por fecha asc (FIFO interno)
    - Intenta 1 línea por producto; si supera max_line_len -> modo bloque
    - Para CON: muestra contenedor y NO mezcla C1/C2/C3
    - Para DES/QUI sin fecha: compacta siempre (sin lotes)
    """
    acc = _consolidar_por_nombre_unidad_fecha(rows_tuples)
    # acc key: (nombre, unidad, venc, cont) -> cant

    # agrupar por (nombre, unidad)
    grupos = {}
    for (nombre, unidad, venc, cont), cant in acc.items():
        grupos.setdefault((nombre, unidad), []).append((venc, cont, cant))

    def sort_lote(lote):
        venc, cont, _cant = lote
        return (0 if venc is not None else 1, venc or date.max, cont)

    lineas = [f"📦 *Estoque – {titulo_grupo}*"]

    for (nombre, unidad) in sorted(grupos.keys(), key=lambda k: k[0].lower()):
        lotes = sorted(grupos[(nombre, unidad)], key=sort_lote)

        # Caso sin fecha (DES/QUI): compacta siempre sin lotes
        if all(v is None for (v, _c, _q) in lotes):
            total = sum(q for (_v, _c, q) in lotes)
            suf = f"{unidad}" if unidad else ""
            lineas.append(f"• {nombre}: {total}{suf}")
            continue

        # piezas: "5kg (C1) (30/01)" o "5kg (30/01)"
        piezas = []
        for venc, cont, cant in lotes:
            suf = f"{unidad}" if unidad else ""
            extra = f" ({cont})" if cont and cont != "N/A" else ""
            piezas.append(f"{cant}{suf}{extra} ({_fmt_fecha(venc)})")

        base = f"• {nombre}: "
        compacta = base + " | ".join(piezas)

        if len(compacta) <= max_line_len:
            lineas.append(compacta)
        else:
            # modo bloque, intentando cortar por piezas
            lineas.append(f"• {nombre}:")
            indent = "  "
            chunk = ""
            for p in piezas:
                add = (p if not chunk else " | " + p)
                if len(chunk) + len(add) > max_line_len:
                    lineas.append(indent + chunk)
                    chunk = p
                else:
                    chunk += add
            if chunk:
                lineas.append(indent + chunk)
                
        lineas.append("")

    return "\n".join(lineas)