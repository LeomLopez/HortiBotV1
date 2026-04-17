from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from views.menu import get_menu_text as v_menu
from models.db import obtener_productos, insertar_producto, obtener_stock_actual, obtener_ultima_actualizacion, search_productos, obtener_lote_stock_actual, obtener_stock_vencido
from datetime import datetime, date
from textwrap import shorten
from views.formatters import mensaje_por_nombre_from_tuples, _only_date, _fmt_fecha, mensaje_por_fecha_from_tuples, mensaje_order_from_tuples
import unicodedata


# Diccionario para traducir abreviaturas a nombre largo + emoji
GRUPOS_MAP = {
    "HOR": "🥕 Hortaliças",
    "FRU": "🍎 Frutas",
    "LAC": "🧀 Lácteos",
    "CON": "❄️ Congelados",
    "SEC": "📦 Secos",
    "QUI": "🧪 Químicos",        
    "DES": "🧻 Descartáveis"     
}

AREAS_VALIDAS = {"alm": "Almoço", "jan": "Janta", "cof": "Coffee", "kit": "Kit Lanche"}


# Teclado personalizado
keyboard = [
    ["🥕 HortiFruti", "❄️ Congelados"],
    ["📦 Estoque Seco", "🧪 Estoque Químico"],
    ["🧻 Estoque Descartáveis", "📋 Requisições"]
]
menu_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def _estoque_help_short():
    return (
        "Uso:\n"
        "• /estoque <SETOR>\n"
        "• /estoque <SETOR> fifo\n"
        "• /estoque <SETOR> order\n\n"
        "Exemplos:\n"
        "• /estoque hor\n"
        "• /estoque sec order\n"
        "• /estoque con fifo"
    )

# ------------------------
# Funciones Auxiliares
# ------------------------


def _norm(s: str) -> str:
    # lower + sin acentos
    s = (s or "").lower().strip()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def parse_fecha_flexible(fecha_str: str) -> date | None:
    """
    Acepta:
    - 'dd/mm'       -> usa el año actual
    - 'dd/mm/yy'    -> convierte a 20yy (ej: '26' -> 2026)
    - 'dd/mm/yyyy'  -> año completo
    También tolera 'dd-mm' reemplazando por '/'.
    """
    if not fecha_str:
        return None

    s = fecha_str.strip().replace('-', '/')
    hoy = datetime.now()

    try:
        partes = s.split('/')
        if len(partes) == 2:
            d, m = partes
            return datetime.strptime(f"{d}/{m}/{hoy.year}", "%d/%m/%Y").date()
        elif len(partes) == 3:
            d, m, a = partes
            a = a.strip()
            if len(a) == 2:
                a = "20" + a  # ej: 26 -> 2026
            return datetime.strptime(f"{d}/{m}/{a}", "%d/%m/%Y").date()
        else:
            return None
    except ValueError:
        return None

def parse_args(update: Update, requiere_fecha=False):
    """
    Parsea mensaje en formato:
    /entrada 20 kg, tomate, 29/07, HOR
    /entrada 10 kg, pollo, 29/07, CON, C1
    Devuelve: nombre, cantidad, unidad, fecha_producto, grupo
    """
    try:
        # Separar comando de argumentos
        texto = update.message.text.split(' ', 1)
        if len(texto) < 2:
            return None, None, None, None, None

        partes = texto[1].split(',')

        if requiere_fecha:
            if len(partes) < 4:  # Faltan parámetros
                return None, None, None, None, None

            # Cantidad y unidad
            cant_unid = partes[0].strip().split()
            if len(cant_unid) != 2:
                return None, None, None, None, None

            try:
                cantidad = int(cant_unid[0])
            except ValueError:
                return None, None, None, None, None

            unidad = cant_unid[1].lower()
            nombre = partes[1].strip().lower()

            # ✅ usar tu parser flexible (dd/mm | dd/mm/yy | dd/mm/yyyy)
            fecha_producto = parse_fecha_flexible(partes[2])
            if not fecha_producto:
                return None, None, None, None, None

            grupo = partes[3].strip().upper()

            return nombre, cantidad, unidad, fecha_producto, grupo

        return None, None, None, None, None

    except Exception:
        return (None,) * 5


def calcular_estoque(nome, grupo, produtos):
    estoque = 0
    for _, n, q, t, d, u, g, _ in produtos:
        if n.lower() == nome.lower() and g == grupo:
            if t in ['entrada', 'volta']:
                estoque += q
            elif t in ['saida', 'descarte', 'devolucao']:
                estoque -= q
    return estoque

# DESATIVADO: não usar descarte automático (decisão de processo)
"""def mover_para_descarte(produtos):
    hoje = datetime.now().date()
    for _, nome, quantidade, tipo, data, unidade, grupo, _ in produtos:
        if tipo == "entrada" and (data - hoje).days == -1:
            insertar_producto(nome, quantidade, 'descarte', data, unidade, grupo)
    return """

def handle_buscar(update, context, conn):
    args = context.args
    query = " ".join(args).strip() if args else ""
    if not query:
        update.message.reply_text("Dime qué buscas. Ej: /buscar batata")
        return

    # Si en el futuro quieres permitir filtrar por grupo en el mismo comando,
    # puedes parsear algo tipo: "/buscar batata g:secos"
    grupo = None
    # Ejemplo de parseo básico (opcional):
    # for a in list(args):
    #     if a.lower().startswith("g:"):
    #         grupo = a.split(":", 1)[1]
    #         query = " ".join([x for x in args if x != a])

    resultados = search_productos(conn, query=query, limit=60, grupo=grupo)

    if not resultados:
        update.message.reply_text(f"No encontré nada para “{query}”.")
        return

    lineas = []
    for r in resultados:
        nom = shorten(r["nombre"], width=38, placeholder="…")
        grp = (r.get("grupo") or "-").upper()
        stk = r.get("stock")
        uni = r.get("unidad") or ""
        ven = r.get("vencimiento")
        ven_txt = f" • vence: {ven:%Y-%m-%d}" if ven else ""
        lineas.append(f"• [{grp}] {nom} — {stk}{uni}{ven_txt}")

    # Envía hasta 30 líneas por mensaje para no exceder límites
    chunk = "\n".join(lineas[:30])
    update.message.reply_text(chunk)


def _aviso_vencido(fecha_produto):
    hoje = datetime.now().date()
    if fecha_produto and fecha_produto < hoje:
        dias = (hoje - fecha_produto).days
        return (
            "\n\n⚠️ *ATENÇÃO: PRODUTO VENCIDO*\n"
            f"• Vencido há {dias} dia(s)\n"
            "Confira se a data está correta antes de guardar."
        )
    return ""

#Divide mensaje
MAX_TG = 3900  # margen de seguridad (<4096)

async def _send_long(update: Update, text: str, parse_mode=None):
    """
    Envía mensajes largos en partes, cortando por líneas.
    """
    if not text:
        return

    lines = text.split("\n")
    chunk = ""

    for line in lines:
        # +1 por el salto de línea
        if len(chunk) + len(line) + 1 > MAX_TG:
            await update.message.reply_text(chunk, parse_mode=parse_mode)
            chunk = line
        else:
            chunk = chunk + ("\n" if chunk else "") + line

    if chunk:
        await update.message.reply_text(chunk, parse_mode=parse_mode)

# ------------------------
# Comandos del Bot
# ------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Eu sou o Bot de Estoque. Use /menu para ver as opções disponíveis.",
        reply_markup=menu_markup
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = """
📋 *Comandos do Bot de Estoque*

*➤ Entrada de produtos*
- HortiFruti / Laticínios / Outros:
`/entrada 20 kg, tomate, 29/07, HOR`

- Congelados (com contêiner):
`/entrada 10 kg, frango, 30/07, CON, C1`

*➤ Saída de produtos*
- HortiFruti / Laticínios / Outros:
`/saida 5 kg, tomate, 29/07, HOR, alm`

- Congelados (com contêiner + área):
`/saida 3 kg, frango, 30/07, CON, C1, alm`

*➤ Volta de produção (retorno)*
- HortiFruti / Laticínios / Outros:
`/volta 2 kg, tomate, 30/07, HOR, alm`

- Congelados (com contêiner + área):
`/volta 2 kg, frango, 30/07, CON, C1, alm`

*➤ Outros comandos*
- `/estoque` → Ver estoque total  
- `/estoque_congelados` → Ver estoque de congelados por contêiner  
- `/vencimentos` → Alertas de vencimento  
- `/buscar frango` → Buscar produto ou grupo  
- `/movimentacoes 28/07-30/07` → Histórico de movimentações

"""
    await update.message.reply_text(mensaje, parse_mode="Markdown")


# ------------------------
# ENTRADA
# ------------------------
async def entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad, unidad, fecha_producto, grupo = parse_args(update, requiere_fecha=True)

    # Validación básica
    if not all([nombre, cantidad, unidad, fecha_producto, grupo]):
        await update.message.reply_text(
            "❌ Formato inválido.\n\n"
            "*Não congelados (HOR/LAC/etc):*\n"
            "`/entrada 20 kg, tomate, 30/07, HOR`\n\n"
            "*Congelados (CON):*\n"
            "`/entrada 10 kg, frango, 30/07, CON, C1`",
            parse_mode="Markdown"
        )
        return

    # Manejo de contenedor para congelados
    contenedor = None
    if grupo == "CON":
        partes = update.message.text.split(',')
        if len(partes) < 5:
            await update.message.reply_text(
                "❌ Você deve indicar o contêiner (C1/C2/C3) para congelados.\n"
                "Exemplo: `/entrada 10 kg, frango, 30/07, CON, C1`",
                parse_mode="Markdown"
            )
            return
        contenedor = partes[4].strip().upper()

    # ✅ Aviso si está vencido (NO bloquea)
    aviso_vencido = _aviso_vencido(fecha_producto)

    try:
        # Registrar movimento
        insertar_producto(nombre, cantidad, 'entrada', fecha_producto, unidad, grupo, contenedor, concepto="fornecedor")

        # Buscar lote atualizado em stock_actual
        lote = obtener_lote_stock_actual(nombre, grupo, fecha_producto, contenedor)
        if lote:
            _, q_restante, un_restante, _, _, cont = lote
            extra = f" – ({cont})" if grupo == "CON" and cont and cont != "N/A" else ""
            msg_estoque = (
                f"📊 Agora há {q_restante}{un_restante} de {nombre}{extra} "
                f"({_fmt_fecha(fecha_producto)})."
            )
        else:
            msg_estoque = (
                "📊 Não foi possível localizar o lote em estoque, "
                "mas a entrada foi registrada."
            )

        await update.message.reply_text(
            f"📥 Entrada registrada: {cantidad}{unidad} de {nombre} "
            f"({_fmt_fecha(fecha_producto)}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}\n"
            f"{msg_estoque}"
            f"{aviso_vencido}",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro na entrada: {e}")



# ------------------------
# SAIDA
# ------------------------
async def saida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad, unidad, fecha_producto, grupo = parse_args(update, requiere_fecha=True)

    # Validación básica
    if not all([nombre, cantidad, unidad, fecha_producto, grupo]):
        await update.message.reply_text(
            "❌ Formato inválido.\n\n"
            "*Uso correto (não congelados):*\n"
            "`/saida 5 kg, tomate, 30/07, HOR, alm`\n\n"
            "*Uso correto (congelados):*\n"
            "`/saida 3 kg, frango, 30/07, CON, C1, alm`\n\n"
            "Áreas válidas: alm, jan, cof, kit",
            parse_mode="Markdown"
        )
        return

    # Manejo de contenedor + captura de concepto (área)
    partes = update.message.text.split(',')

    contenedor = None
    concepto = None

    if grupo == "CON":
        # Esperado: /saida 3 kg, frango, 30/07, CON, C1, alm
        if len(partes) < 6:
            await update.message.reply_text(
                "❌ Formato inválido para congelados.\n\n"
                "Use:\n"
                "`/saida 3 kg, frango, 30/07, CON, C1, alm`\n\n"
                "Áreas válidas: alm, jan, cof, kit",
                parse_mode="Markdown"
            )
            return

        contenedor = partes[4].strip().upper()
        concepto = partes[5].strip().lower()

    else:
        # Esperado: /saida 5 kg, tomate, 30/07, HOR, alm
        if len(partes) < 5:
            await update.message.reply_text(
                "❌ Formato inválido.\n\n"
                "Use:\n"
                "`/saida 5 kg, tomate, 30/07, HOR, alm`\n\n"
                "Áreas válidas: alm, jan, cof, kit",
                parse_mode="Markdown"
            )
            return

        concepto = partes[4].strip().lower()

    # Validar concepto (área)
    if not concepto or concepto not in AREAS_VALIDAS:
        await update.message.reply_text(
            "❌ Área inválida.\n\n"
            "Use uma destas: `alm`, `jan`, `cof`, `kit`",
            parse_mode="Markdown"
        )
        return

    # ✅ Aviso si está vencido (NO bloquea)
    aviso_vencido = _aviso_vencido(fecha_producto)

    # 🔹 Consultar el lote actual en stock_actual (antes de la salida)
    lote = obtener_lote_stock_actual(nombre, grupo, fecha_producto, contenedor)
    estoque_lote = int(lote[1]) if lote and lote[1] is not None else 0
    unidade_lote = (lote[2] or "").lower() if lote else ""

    # ✅ Validación de existencia y cantidad
    if estoque_lote < cantidad:
        await update.message.reply_text(
            f"⚠️ *Estoque insuficiente para {nombre} ({_fmt_fecha(fecha_producto)}).*\n\n"
            f"• Estoque do lote: {estoque_lote}{unidade_lote or unidad}\n"
            f"• Saída solicitada: {cantidad}{unidad}",
            parse_mode="Markdown"
        )
        return

    # ✅ VALIDACIÓN DE UNIDADE (si tenemos unidad del lote)
    if unidade_lote and unidad.lower() != unidade_lote:
        await update.message.reply_text(
            "❌ Unidade diferente da cadastrada para esse lote.\n\n"
            f"• Unidade do lote: *{unidade_lote}*\n"
            f"• Unidade informada: *{unidad.lower()}*\n\n"
            "Use a mesma unidade do estoque para registrar a saída.",
            parse_mode="Markdown"
        )
        return

    try:
        # 1️⃣ Registrar movimento de saída (con concepto)
        insertar_producto(nombre, cantidad, 'saida', fecha_producto, unidad, grupo, contenedor, concepto=concepto)

        # 2️⃣ Volver a consultar el lote después de la salida
        lote_restante = obtener_lote_stock_actual(nombre, grupo, fecha_producto, contenedor)
        if lote_restante:
            _, q_restante, un_restante, _, _, cont = lote_restante
            extra = f" – ({cont})" if grupo == "CON" and cont and cont != "N/A" else ""
            msg_estoque = (
                f"📊 Agora há {q_restante}{un_restante} de {nombre}{extra} "
                f"({_fmt_fecha(fecha_producto)})."
            )
        else:
            msg_estoque = (
                f"📊 O lote de {nombre} ({_fmt_fecha(fecha_producto)}) "
                f"foi zerado no estoque."
            )

        # 3️⃣ Mensaje final (con aviso de vencido)
        await update.message.reply_text(
            f"📤 Saída registrada: {cantidad}{unidad} de {nombre} "
            f"({_fmt_fecha(fecha_producto)}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}\n"
            f"• Área: *{AREAS_VALIDAS.get(concepto, concepto)}*\n"
            f"{msg_estoque}"
            f"{aviso_vencido}",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro na saída: {e}")

# ------------------------
# VOLTA (retorno de produção)
# ------------------------
async def volta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad, unidad, fecha_producto, grupo = parse_args(update, requiere_fecha=True)

    # Validación básica
    if not all([nombre, cantidad, unidad, fecha_producto, grupo]):
        await update.message.reply_text(
            "❌ Formato inválido.\n\n"
            "*Uso correto (não congelados):*\n"
            "`/volta 5 kg, tomate, 30/07, HOR, alm`\n\n"
            "*Uso correto (congelados):*\n"
            "`/volta 2 kg, frango, 30/07, CON, C1, alm`\n\n"
            "Áreas válidas: alm, jan, cof, kit",
            parse_mode="Markdown"
        )
        return

    partes = update.message.text.split(',')

    contenedor = None
    concepto = None

    if grupo == "CON":
        # Esperado: /volta 2 kg, frango, 30/07, CON, C1, alm
        if len(partes) < 6:
            await update.message.reply_text(
                "❌ Formato inválido para congelados.\n\n"
                "Use:\n"
                "`/volta 2 kg, frango, 30/07, CON, C1, alm`\n\n"
                "Áreas válidas: alm, jan, cof, kit",
                parse_mode="Markdown"
            )
            return

        contenedor = partes[4].strip().upper()
        concepto = partes[5].strip().lower()

    else:
        # Esperado: /volta 5 kg, tomate, 30/07, HOR, alm
        if len(partes) < 5:
            await update.message.reply_text(
                "❌ Formato inválido.\n\n"
                "Use:\n"
                "`/volta 5 kg, tomate, 30/07, HOR, alm`\n\n"
                "Áreas válidas: alm, jan, cof, kit",
                parse_mode="Markdown"
            )
            return

        concepto = partes[4].strip().lower()

    # Validar concepto (área)
    if not concepto or concepto not in AREAS_VALIDAS:
        await update.message.reply_text(
            "❌ Área inválida.\n\n"
            "Use uma destas: `alm`, `jan`, `cof`, `kit`",
            parse_mode="Markdown"
        )
        return

    try:
        # Registrar VOLTA como ENTRADA (suma stock), con concepto=área
        insertar_producto(nombre, cantidad, 'volta', fecha_producto, unidad, grupo, contenedor, concepto=concepto)

        # Consultar lote actualizado en stock_actual
        lote = obtener_lote_stock_actual(nombre, grupo, fecha_producto, contenedor)
        if lote:
            _, q_restante, un_restante, _, _, cont = lote
            extra = f" – ({cont})" if grupo == "CON" and cont and cont != "N/A" else ""
            msg_estoque = (
                f"📊 Agora há {q_restante}{un_restante} de {nombre}{extra} "
                f"({_fmt_fecha(fecha_producto)})."
            )
        else:
            msg_estoque = "📊 Entrada registrada, mas não foi possível localizar o lote no estoque."

        await update.message.reply_text(
            f"🔄 Volta registrada: {cantidad}{unidad} de {nombre} "
            f"({_fmt_fecha(fecha_producto)}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}\n"
            f"• Origem (área): *{AREAS_VALIDAS.get(concepto, concepto)}*\n"
            f"{msg_estoque}",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro na volta: {e}")

# ------------------------
# AJUSTE
# ------------------------

async def ajuste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Parseo igual a /saida
    nombre, cantidad, unidad, fecha_producto, grupo = parse_args(update, requiere_fecha=True)

    if not all([nombre, cantidad, unidad, fecha_producto, grupo]):
        await update.message.reply_text(
            "❌ Formato inválido.\n\n"
            "*Não congelados:*\n"
            "`/ajuste 20 kg, tomate, 30/07, HOR, ERRO`\n"
            "`/ajuste 20 kg, tomate, 30/07, HOR, DIVG`\n\n"
            "*Congelados:*\n"
            "`/ajuste 10 kg, frango, 30/07, CON, C1, ERRO`\n"
            "`/ajuste 10 kg, frango, 30/07, CON, C1, DIVG`",
            parse_mode="Markdown"
        )
        return

    partes = [p.strip() for p in update.message.text.split(",")]

    # 2️⃣ Contenedor (solo CON)
    contenedor = None
    concepto = None

    if grupo == "CON":
        # Esperado: /ajuste X unid, nombre, data, CON, C1, CONCEITO
        if len(partes) < 6:
            await update.message.reply_text(
                "❌ Formato inválido para congelados.\n"
                "Exemplo: `/ajuste 10 kg, frango, 30/07, CON, C1, ERRO`",
                parse_mode="Markdown"
            )
            return
        contenedor = partes[4].upper()
        concepto = partes[5].upper()
    else:
        # Esperado: /ajuste X unid, nombre, data, HOR, CONCEITO
        if len(partes) < 5:
            await update.message.reply_text(
                "❌ Indique o conceito do ajuste.\n"
                "Exemplos:\n"
                "`/ajuste 3 kg, tomate, 30/07, HOR, ERRO`\n"
                "`/ajuste 3 kg, tomate, 30/07, HOR, DIVG`",
                parse_mode="Markdown"
            )
            return
        concepto = partes[4].upper()

    # 3️⃣ Validar conceito
    if concepto not in ("ERRO", "DIVG"):
        await update.message.reply_text(
            "❌ Conceito inválido.\n"
            "Use apenas: `ERRO` ou `DIVG`.",
            parse_mode="Markdown"
        )
        return

    # 4️⃣ Buscar lote exacto en stock_actual
    lote = obtener_lote_stock_actual(nombre, grupo, fecha_producto, contenedor)

    if not lote:
        await update.message.reply_text(
            "❌ Nenhum lote encontrado para ajuste.\n"
            "Verifique nome, data e grupo."
        )
        return

    # lote = (nombre, cantidad, unidade, grupo, fecha_producto, contenedor)
    _, cantidad_lote, unidad_lote, _, _, _ = lote

    # 5️⃣ Validación de unidad
    if unidad.lower() != (unidad_lote or "").lower():
        await update.message.reply_text("❌ Unidade diferente da cadastrada para esse lote.")
        return

    # 6️⃣ Regras por conceito
    try:
        cantidad = int(cantidad)
        cantidad_lote = int(cantidad_lote)
    except ValueError:
        await update.message.reply_text("❌ Quantidade inválida.")
        return

    if cantidad <= 0:
        await update.message.reply_text("❌ A quantidade deve ser maior que zero.")
        return

    # ERRO = remove lote inteiro (força)
    if concepto == "ERRO":
        cantidad_a_remover = cantidad_lote

    # DIVG = pode parcial, mas nunca maior que o lote
    else:  # DIVG
        if cantidad > cantidad_lote:
            await update.message.reply_text(
                "❌ Ajuste DIVG não permitido.\n"
                "A quantidade não pode ser maior que a do lote."
            )
            return
        cantidad_a_remover = cantidad

    try:
        # 7️⃣ Registrar movimiento de AJUSTE
        insertar_producto(
            nombre=nombre,
            cantidad=cantidad_a_remover,
            tipo="ajuste",
            fecha_producto=fecha_producto,
            unidade=unidad,
            grupo=grupo,
            contenedor=contenedor,
            concepto=concepto
        )

        if concepto == "ERRO":
            await update.message.reply_text(
                f"🛠️ Ajuste ERRO realizado.\n"
                f"O lote foi removido por completo ({cantidad_lote} {unidad})."
            )
        else:
            restante = cantidad_lote - cantidad_a_remover
            await update.message.reply_text(
                f"🛠️ Ajuste DIVG realizado.\n"
                f"Removido: {cantidad_a_remover} {unidad} | Restante no lote: {restante} {unidad}"
            )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro no ajuste: {e}")

# ------------------------
# DESCARTE (manual)
# ------------------------
async def descarte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome, quantidade, unidade, data_produto, grupo = parse_args(update, requiere_fecha=True)

    if not nome or not quantidade or not unidade or not data_produto or not grupo:
        await update.message.reply_text(
            "❌ Formato inválido.\n\n"
            "*Uso correto (não congelados):*\n"
            "`/descarte 3 kg, tomate, 29/07, HOR`\n\n"
            "*Uso correto (congelados):*\n"
            "`/descarte 3 kg, frango, 29/07, CON, C1`",
            parse_mode="Markdown"
        )
        return

    partes = update.message.text.split(',')
    contenedor = None

    if grupo == "CON":
        if len(partes) < 5:
            await update.message.reply_text(
                "❌ Indique o contêiner (C1/C2/C3) para congelados.\n"
                "Exemplo: `/descarte 3 kg, frango, 29/07, CON, C1`",
                parse_mode="Markdown"
            )
            return
        contenedor = partes[4].strip().upper()

    lote = obtener_lote_stock_actual(nome, grupo, data_produto, contenedor)
    if not lote:
        await update.message.reply_text(
            "❌ Nenhum lote encontrado para descarte.\n"
            "Verifique nome, data, grupo e contêiner."
        )
        return

    _, quantidade_lote, unidade_lote, _, _, cont_lote = lote
    unidade_lote = (unidade_lote or "").lower()

    if unidade_lote and unidade.lower() != unidade_lote:
        await update.message.reply_text(
            "❌ Unidade diferente da cadastrada para esse lote.\n\n"
            f"• Unidade do lote: *{unidade_lote}*\n"
            f"• Unidade informada: *{unidade.lower()}*\n\n"
            "Use a mesma unidade do estoque para registrar o descarte.",
            parse_mode="Markdown"
        )
        return

    if int(quantidade_lote or 0) < quantidade:
        await update.message.reply_text(
            f"⚠️ *Estoque insuficiente para descarte de {nome} ({_fmt_fecha(data_produto)}).*\n\n"
            f"• Estoque do lote: {quantidade_lote}{unidade_lote or unidade}\n"
            f"• Descarte solicitado: {quantidade}{unidade}",
            parse_mode="Markdown"
        )
        return

    insertar_producto(nome, quantidade, 'descarte', data_produto, unidade, grupo, contenedor)

    lote_restante = obtener_lote_stock_actual(nome, grupo, data_produto, contenedor)
    if lote_restante:
        _, q_restante, un_restante, _, _, cont = lote_restante
        extra = f" – ({cont})" if grupo == "CON" and cont and cont != "N/A" else ""
        msg_estoque = (
            f"📊 Agora há {q_restante}{un_restante} de {nome}{extra} "
            f"({_fmt_fecha(data_produto)})."
        )
    else:
        extra = f" – ({cont_lote})" if grupo == "CON" and cont_lote and cont_lote != "N/A" else ""
        msg_estoque = (
            f"📊 O lote de {nome}{extra} ({_fmt_fecha(data_produto)}) "
            f"foi zerado no estoque."
        )

    await update.message.reply_text(
        f"🗑️ Descarte registrado: {quantidade}{unidade} de {nome} "
        f"({_fmt_fecha(data_produto)}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}\n"
        f"{msg_estoque}",
        parse_mode="Markdown"
    )
    
#Comando Descarte Vencidos
async def descarte_vencidos(update, context):
    grupo = context.args[0].upper() if context.args else None

    vencidos = obtener_stock_vencido(grupo=grupo)

    if not vencidos:
        await update.message.reply_text(
            "✅ Não há itens vencidos com quantidade em estoque."
        )
        return

    mensagem = "⚠️ *Itens vencidos no estoque:*\n\n"

    for nome, quantidade, unidade, grupo, fecha, contenedor in vencidos:
        extra = f" – ({contenedor})" if grupo == "CON" and contenedor and contenedor != "N/A" else ""
        dias = (datetime.now().date() - fecha).days

        mensagem += (
            f"• {nome}: {quantidade}{unidade}{extra}\n"
            f"  📅 Vencido há {dias} dia(s) ({_fmt_fecha(fecha)})\n"
        )

    mensagem += (
        "⚠️ *Este comando ainda NÃO realiza o descarte.*\n"
        "Use apenas para conferência."
    )

    await update.message.reply_text(mensagem, parse_mode="Markdown")

# ------------------------
# DEVOLUÇÃO (ao fornecedor)
# ------------------------
async def devolucao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad, unidad, fecha_producto, grupo = parse_args(update, requiere_fecha=True)

    # Validación básica
    if not all([nombre, cantidad, unidad, fecha_producto, grupo]):
        await update.message.reply_text(
            "❌ Formato inválido.\n\n"
            "*Uso correto:*\n"
            "`/devolucao [quantidade] [unidade], [produto], [dd/mm], [grupo]`\n\n"
            "*Exemplo:*\n"
            "`/devolucao 5 kg, tomate, 30/07, HOR`",
            parse_mode="Markdown"
        )
        return

    # Manejo de contenedor para congelados
    contenedor = None
    if grupo == "CON":
        partes = update.message.text.split(',')
        if len(partes) < 5:
            await update.message.reply_text(
                "❌ Indique o contêiner (C1/C2/C3) para congelados.\n"
                "Exemplo: `/devolucao 3 kg, frango, 30/07, CON, C1`",
                parse_mode="Markdown"
            )
            return
        contenedor = partes[4].strip().upper()

    # 🔹 Consultar el lote actual en stock_actual (antes de la devolução)
    lote = obtener_lote_stock_actual(nombre, grupo, fecha_producto, contenedor)
    estoque_lote = int(lote[1]) if lote and lote[1] is not None else 0
    unidade_lote = (lote[2] or "").lower() if lote else ""

    # ✅ Validación de existencia y cantidad
    if estoque_lote < cantidad:
        await update.message.reply_text(
            f"⚠️ *Estoque insuficiente para devolução de {nombre} ({_fmt_fecha(fecha_producto)}).*\n\n"
            f"• Estoque do lote: {estoque_lote}{unidade_lote or unidad}\n"
            f"• Devolução solicitada: {cantidad}{unidad}",
            parse_mode="Markdown"
        )
        return

    # ✅ VALIDACIÓN DE UNIDADE
    if unidade_lote and unidad.lower() != unidade_lote:
        await update.message.reply_text(
            "❌ Unidade diferente da cadastrada para esse lote.\n\n"
            f"• Unidade do lote: *{unidade_lote}*\n"
            f"• Unidade informada: *{unidad.lower()}*\n\n"
            "Use a mesma unidade do estoque para registrar a devolução.",
            parse_mode="Markdown"
        )
        return

    try:
        # 1️⃣ Registrar movimento de devolução (ao fornecedor)
        insertar_producto(nombre, cantidad, 'devolucao', fecha_producto, unidad, grupo, contenedor)

        # 2️⃣ Consultar lote después
        lote_restante = obtener_lote_stock_actual(nombre, grupo, fecha_producto, contenedor)
        if lote_restante:
            _, q_restante, un_restante, _, _, cont = lote_restante
            extra = f" – ({cont})" if grupo == "CON" and cont and cont != "N/A" else ""
            msg_estoque = (
                f"📊 Agora há {q_restante}{un_restante} de {nombre}{extra} "
                f"({_fmt_fecha(fecha_producto)})."
            )
        else:
            msg_estoque = (
                f"📊 O lote de {nombre} ({_fmt_fecha(fecha_producto)}) "
                f"foi zerado no estoque."
            )

        await update.message.reply_text(
            f"↩️📦 *Devolução ao fornecedor registrada:* {cantidad}{unidad} de {nombre} "
            f"({_fmt_fecha(fecha_producto)}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}\n"
            f"{msg_estoque}",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro na devolução: {e}")


# ------------------------
# VENCIMIENTOS
# ------------------------
async def vencimentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = obtener_stock_actual()
    hoje = datetime.now().date()

    #mover_para_descarte(produtos)  # Descarta automáticamente

    alerta_proximos = []
    alerta_hoy = []

    for nome, quantidade, unidade, grupo, data, contenedor in produtos:

        dias_restantes = (data - hoje).days

        if 1 <= dias_restantes <= 2:
            alerta_proximos.append((nome, quantidade, unidade, data))
        elif dias_restantes == 0:
            alerta_hoy.append((nome, quantidade, unidade, data))

    if not alerta_proximos and not alerta_hoy:
        await update.message.reply_text("✅ Nenhum item próximo de vencer ou vencendo hoje.")
        return

    mensagem = "📅 *Alertas de Vencimento*\n"

    if alerta_hoy:
        mensagem += "\n⚠️ *Vencem HOJE:*\n"
        for nome, quantidade, unidade, data in alerta_hoy:
            mensagem += f"• {nome}: {quantidade}{unidade} ({_fmt_fecha(data)})\n"

    if alerta_proximos:
        mensagem += "\n⏳ *Próximos a vencer (2 dias):*\n"
        for nome, quantidade, unidade, data in alerta_proximos:
            mensagem += f"• {nome}: {quantidade}{unidade} ({_fmt_fecha(data)})\n"

    await update.message.reply_text(mensagem, parse_mode="Markdown")

# ------------------------
# ESTOQUE
# ------------------------
async def estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1) exigir setor
    if not context.args:
        await _send_long(update, _estoque_help_short())
        return
    
    setor = context.args[0].upper()
    
    # 2) vista default + parseo mínimo
    
    args_lower = [a.lower() for a in context.args[1:]]
    vista = "order" if "order" in args_lower else "fifo"
    
    # 3) obtener stock actual del grupo/setor
    
    productos = obtener_stock_actual(grupo=setor)
    if not productos:
        await update.message.reply_text(f"📦 Nenhum item registrado no estoque para {setor}.")
        return
    
    nome_grupo = GRUPOS_MAP.get(setor,setor)
    
    # 4) formatter
    
    if vista == "order":
        mensagem = mensaje_order_from_tuples(productos, titulo_grupo=nome_grupo)
    else:
        mensagem = mensaje_por_fecha_from_tuples(productos, titulo_grupo=nome_grupo)
    # 5) enviar
    await _send_long(update, mensagem, parse_mode="Markdown")

# ------------------------
# ESTOQUE CONGELADOS
# ------------------------
async def estoque_congelados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = datetime.now().date()
    produtos = obtener_stock_actual(grupo="CON")

    if not produtos:
        await update.message.reply_text("❄️ Nenhum item registrado no estoque de congelados.")
        return

    mensagem = "❄️ *Estoque Congelados por Contenedor:*\n"
    contenedores = {}
    alerta_hoy = []
    alerta_proximos = []

    for nome, quantidade, unidade, grupo, fecha_producto, contenedor in produtos:
        dias_restantes = (fecha_producto - hoje).days
        if dias_restantes == 0:
            alerta_hoy.append((nome, quantidade, unidade, fecha_producto, contenedor))
        elif 1 <= dias_restantes <= 2:
            alerta_proximos.append((nome, quantidade, unidade, fecha_producto, contenedor))

        contenedores.setdefault(contenedor, [])
        contenedores[contenedor].append((nome, quantidade, unidade, fecha_producto))

    for contenedor, items in contenedores.items():
        mensagem += f"\n*{contenedor}*\n"
        for nome, quantidade, unidade, fecha_producto in items:
            mensagem += f"• {nome}: {quantidade}{unidade} ({_fmt_fecha(fecha_producto)})\n"

    if alerta_hoy or alerta_proximos:
        mensagem += "\n📅 *Alertas de Vencimento*\n"

        if alerta_hoy:
            mensagem += "\n⚠️ *Vencem HOJE:*\n"
            for nome, quantidade, unidade, fecha_producto, contenedor in alerta_hoy:
                mensagem += f"• {nome} ({contenedor}): {quantidade}{unidade} ({_fmt_fecha(fecha_producto)})\n"

        if alerta_proximos:
            mensagem += "\n⏳ *Próximos a vencer (2 dias):*\n"
            for nome, quantidade, unidade, fecha_producto, contenedor in alerta_proximos:
                mensagem += f"• {nome} ({contenedor}): {quantidade}{unidade} ({_fmt_fecha(fecha_producto)})\n"

    await _send_long(update, mensagem, parse_mode="Markdown")
    

# ------------------------
# ESTOQUE SECOS
# ------------------------
async def estoque_secos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Trae tu lista de tuplas: (nombre, cantidad, unidad, grupo, fecha_producto, contenedor)
    resultados = obtener_stock_actual(grupo="SEC")

    if not resultados:
        await update.message.reply_text("📦 Nenhum item registrado no Estoque Seco.")
        return

    # --- Agrupar por (nombre, unidad) y consolidar lotes por fecha ---
    # acc[(nombre, unidad, fecha)] = suma_cantidades
    acc = {}
    for nombre, cantidad, unidad, _grupo, fecha_producto, _ in resultados:
        nombre = (nombre or "").strip()
        unidad = (unidad or "").strip()
        fecha = _only_date(fecha_producto)
        cant = int(cantidad or 0)
        key = (nombre, unidad, fecha)
        acc[key] = acc.get(key, 0) + cant

    # grupos[(nombre, unidad)] = [(fecha, cantidad_sumada), ...]
    grupos = {}
    for (nombre, unidad, fecha), cant in acc.items():
        grupos.setdefault((nombre, unidad), []).append((fecha, cant))

    # Orden: productos por nombre (A-Z); lotes por fecha asc (None al final)
    def sort_lote(item):
        fecha, _ = item
        return (0 if fecha is not None else 1, fecha or date.max)

    linhas = ["📦 *Estoque – Secos*"]
    for (nombre, unidad) in sorted(grupos.keys(), key=lambda k: k[0].lower()):
        linhas.append(f"{nombre}")
        for fecha, cant in sorted(grupos[(nombre, unidad)], key=sort_lote):
            suf = f" {unidad}" if unidad else ""
            linhas.append(f"• {cant}{suf} – ({_fmt_fecha(fecha)})")
        linhas.append("")  # línea en blanco entre productos

    mensagem = "\n".join(linhas).rstrip()
    await _send_long(update, mensagem, parse_mode="Markdown")


# ------------------------
# ESTOQUE QUÍMICOS
# ------------------------
async def estoque_quimicos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resultados = obtener_stock_actual(grupo="QUI")

    if not resultados:
        await update.message.reply_text("🧪 Nenhum item registrado no Estoque Químico.")
        return

    mensagem = mensaje_order_from_tuples(
        resultados,
        titulo_grupo="🧪 Químicos"
    )

    await _send_long(update, mensagem, parse_mode="Markdown")


# ------------------------
# ESTOQUE DESCARTÁVEIS
# ------------------------
async def estoque_descartaveis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resultados = obtener_stock_actual(grupo="DES")

    if not resultados:
        await update.message.reply_text("🧻 Nenhum item registrado no Estoque Descartáveis.")
        return

    mensagem = mensaje_order_from_tuples(
        resultados,
        titulo_grupo="🧻 Descartáveis"
    )

    await _send_long(update, mensagem, parse_mode="Markdown")


# ------------------------
# BUSCAR
# ------------------------
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sin mensaje de ayuda: si no hay argumentos, no respondemos
    if not context.args:
        await update.message.reply_text(
            "❌ Use: /buscar [produto|grupo|contêiner]\n\n"
            "*Exemplos:*\n"
            "`/buscar frango`\n"
            "`/buscar CON`\n"
            "`/buscar C1`",
        )
        return

    raw_query = " ".join(context.args).strip()   # texto tal cual (para mostrar)
    query_upper = raw_query.upper()              # para HOR/CON/LAC/FRU/SEC y C1/C2/C3
    grupos_validos = ["HOR", "CON", "LAC", "FRU", "SEC"]
    contenedores_validos = ["C1", "C2", "C3"]

    # --- Buscar por GRUPO ---
    if query_upper in grupos_validos:
        resultados = obtener_stock_actual(grupo=query_upper)
        if not resultados:
            await update.message.reply_text(f"📦 Sem estoque no grupo {GRUPOS_MAP.get(query_upper, query_upper)}.")
            return

        mensaje = f"*Estoque do grupo {GRUPOS_MAP.get(query_upper, query_upper)}:*\n"

        # Congelados: agrupar por contêiner
        if query_upper == "CON":
            contenedores = {}
            for nombre, quantidade, unidade, grupo, fecha, contenedor in resultados:
                contenedores.setdefault(contenedor, [])
                contenedores[contenedor].append((nombre, quantidade, unidade, fecha))

            for cont in sorted(contenedores.keys(), key=lambda x: (x is None, x)):
                mensagem_cont = f"\n*{cont}*\n" if cont else "\n*Sem contêiner*\n"
                mensaje += mensagem_cont
                for nombre, quantidade, unidade, fecha in contenedores[cont]:
                    mensaje += f"• {nombre}: {quantidade}{unidade} ({_fmt_fecha(fecha)})\n"
        else:
            for nombre, quantidade, unidade, grupo, fecha, _ in resultados:
                mensaje += f"• {nombre}: {quantidade}{unidade} ({_fmt_fecha(fecha)})\n"

        await _send_long(update, mensaje, parse_mode="Markdown")
        return

    # --- Buscar por CONTÊINER ---
    elif query_upper in contenedores_validos:
        resultados = obtener_stock_actual(grupo="CON")
        resultados = [r for r in resultados if (r[5] or "") == query_upper]

        if not resultados:
            await update.message.reply_text(f"📦 Sem estoque no contêiner {query_upper}.")
            return

        mensaje = f"*Estoque no Contêiner {query_upper} (Congelados):*\n"
        for nombre, quantidade, unidade, grupo, fecha, contenedor in resultados:
            mensaje += f"• {nombre}: {quantidade}{unidade} ({_fmt_fecha(fecha)})\n"

        await _send_long(update, mensaje, parse_mode="Markdown")
        return

    # --- Buscar por PRODUTO (texto livre, 1+ palavras, sem acentos) ---
    else:
        # Traer todo el stock y filtrar en Python por tokens normalizados
        todos = obtener_stock_actual()  # [(nombre, q, un, grupo, fecha, cont), ...]
        tokens = [_norm(t) for t in raw_query.split() if t.strip()]
        if not tokens:
            return

        filtrados = []
        for nombre, quantidade, unidade, grupo, fecha, contenedor in todos:
            nom_norm = _norm(nombre)
            if all(tok in nom_norm for tok in tokens):  # AND de tokens
                filtrados.append((nombre, quantidade, unidade, grupo, fecha, contenedor))

        if not filtrados:
            await update.message.reply_text(f"📦 Não foi encontrado estoque para '{query_upper}'.")
            return

        # Agrupar por (grupo, nombre, unidade) y consolidar lotes por (fecha, contêiner)
        grupos_prod = {}
        for nombre, quantidade, unidade, grupo, fecha, cont in filtrados:
            key = (grupo, (nombre or "").strip(), (unidade or "").strip())
            grupos_prod.setdefault(key, []).append((_only_date(fecha), int(quantidade or 0), cont or ""))

        # Construir mensaje: encabezado por producto, lotes debajo
        mensaje = f"*Resultados para '{raw_query}':*\n"
        # Ordenar productos por nombre (A-Z) y luego por grupo
        for (grupo, nombre, unidade) in sorted(grupos_prod.keys(), key=lambda k: (k[1].lower(), k[0])):
            grupo_nombre = GRUPOS_MAP.get(grupo, grupo)
            mensaje += f"[{grupo_nombre}] {nombre}\n"

            # Consolidar lotes (fecha, cont) y ordenarlos por fecha asc (None al final)
            acc = {}
            for f, q, c in grupos_prod[(grupo, nombre, unidade)]:
                acc[(f, c)] = acc.get((f, c), 0) + q

            def _sort_lote(item):
                (f, c), _q = item
                f2 = f or date.max
                return (0 if f is not None else 1, f2, c)

            for (f, c), q in sorted(acc.items(), key=_sort_lote):
                su = f" {unidade}" if unidade else ""
                ft = _fmt_fecha(f)
                if grupo == "CON" and c:
                    mensaje += f"• {q}{su} – ({c}) – ({ft})\n"
                else:
                    mensaje += f"• {q}{su} – ({ft})\n"

            mensaje += "\n"

        await _send_long(update, mensaje.rstrip(), parse_mode="Markdown")


async def movimentacoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hoje = datetime.now().date()

        # Parseo de fechas
        if context.args:
            arg = context.args[0]
            if "-" in arg:
                inicio_str, fim_str = arg.split("-")
                inicio = datetime.strptime(inicio_str.strip() + "/2025", "%d/%m/%Y").date()
                fim = datetime.strptime(fim_str.strip() + "/2025", "%d/%m/%Y").date()
            else:
                inicio = fim = datetime.strptime(arg + "/2025", "%d/%m/%Y").date()
        else:
            inicio = fim = hoje

        # Obtener movimientos históricos
        productos = obtener_productos()

        # Filtrar por fecha de movimiento (índice 7 en la tupla)
        movimientos_filtrados = [
            p for p in productos if inicio <= p[7].date() <= fim
        ]

        if not movimientos_filtrados:
            if inicio == fim:
                await update.message.reply_text(f"📅 Nenhum movimento registrado em {inicio.strftime('%d/%m')}.")
            else:
                await update.message.reply_text(f"📅 Nenhum movimento registrado entre {inicio.strftime('%d/%m')} e {fim.strftime('%d/%m')}.")
            return

        # Construir mensaje (orden ascendente por fecha_movimiento)
        if inicio == fim:
            mensaje = f"📅 *Movimentos de {inicio.strftime('%d/%m')}*\n"
        else:
            mensaje = f"📅 *Movimentos de {inicio.strftime('%d/%m')} até {fim.strftime('%d/%m')}*\n"

        # Ordenar por fecha de movimiento ascendente
        for _, nome, quantidade, tipo, fecha_producto, unidade, grupo, fecha_mov in sorted(movimientos_filtrados, key=lambda x: x[7]):
            mensaje += (
                f"• {nome} – {quantidade}{unidade} ({tipo.upper()}) – Grupo: {grupo} "
                f"– Produto: {_fmt_fecha(fecha_producto)} – {fecha_mov.strftime('%H:%M')}\n"
            )

        await _send_long(update, mensaje, parse_mode="Markdown")       

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao buscar movimentos: {str(e)}")
