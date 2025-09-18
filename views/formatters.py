from datetime import date, datetime

def _only_date(d):
    if d is None: return None
    if isinstance(d, datetime): return d.date()
    return d

def _fmt_fecha(venc):
    return venc.strftime("%d/%m") if venc else "—"

def mensaje_por_nombre_from_tuples(rows_tuples, titulo_grupo="Secos"):
    """
    rows_tuples: iterable de (nombre, cantidad, unidad, grupo, vencimiento, contenedor)
    Agrupa por (nombre, unidad) y lista lotes (cantidad + vencimiento) por fecha asc.
    Si hay el mismo nombre+unidad+fecha repetido, suma cantidades.
    """
    # 1) consolidar por (nombre, unidad, vencimiento)
    acc = {}
    for nombre, cantidad, unidad, _grupo, venc, _contenedor in rows_tuples:
        nombre = (nombre or "").strip()
        unidad = (unidad or "").strip()
        venc_d = _only_date(venc)
        cant = int(cantidad or 0)
        key = (nombre, unidad, venc_d)
        acc[key] = acc.get(key, 0) + cant

    # 2) agrupar por (nombre, unidad)
    grupos = {}
    for (nombre, unidad, venc), cant in acc.items():
        grupos.setdefault((nombre, unidad), []).append((venc, cant))

    # 3) ordenar lotes por fecha (None al final) y productos alfabéticamente
    def sort_lote(item):
        venc, _ = item
        return (0 if venc is not None else 1, venc or date.max)

    linhas = [f"📦 *Estoque – {titulo_grupo}*"]
    for (nombre, unidad) in sorted(grupos.keys(), key=lambda k: k[0].lower()):
        linhas.append(f"{nombre}")
        for venc, cant in sorted(grupos[(nombre, unidad)], key=sort_lote):
            suf = f" {unidad}" if unidad else ""
            linhas.append(f"• {cant}{suf} – ({_fmt_fecha(venc)})")
        linhas.append("")  # línea en blanco entre productos

    return "\n".join(linhas).rstrip()
