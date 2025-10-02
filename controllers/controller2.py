from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from views.menu import get_menu_text as v_menu
from models.db import obtener_productos, insertar_producto, obtener_stock_actual
from datetime import datetime, timedelta

# =========================
# Constantes y teclado
# =========================

GRUPOS_MAP = {
    "HOR": "🥕 Hortaliças",
    "FRU": "🍎 Frutas",
    "LAC": "🧀 Lácteos",
    "CON": "❄️ Congelados",
    "SEC": "📦 Secos"
}

keyboard = [
    ["🥕 HortiFruti", "❄️ Congelados"],
    ["📦 Estoque Seco", "🧪 Estoque Químico"],
    ["🧻 Estoque Descartáveis", "📋 Requisições"]
]
menu_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =========================
# Helpers
# =========================

def agrupar_e_formatar(produtos, por_contenedor=False, detalhado=False):
    """
    produtos: [(nome, quantidade, unidade, grupo, fecha_producto, contenedor)]
    Devuelve un string listo para Telegram.
    """
    # Estructura: grupo -> (contenedor?) -> nome -> [ (fecha, qtd, un) ]
    tree = {}
    for nome, qtd, un, grupo, fecha, cont in produtos:
        key_cont = cont if (por_contenedor and grupo == "CON") else "_"
        tree.setdefault(grupo, {}).setdefault(key_cont, {}).setdefault(nome, []).append((fecha, qtd, un))

    linhas = ["📦 *Estoque Atual*"]
    for grupo in sorted(tree.keys()):
        linhas.append(f"\n{GRUPOS_MAP.get(grupo, grupo)}")
        cont_map = tree[grupo]

        for cont in (sorted(cont_map.keys()) if por_contenedor and grupo == "CON" else cont_map.keys()):
            nomes = cont_map[cont]
            if por_contenedor and grupo == "CON":
                linhas.append(f"*{cont}*")

            for nome in sorted(nomes.keys()):
                lotes = nomes[nome]
                lotes.sort(key=lambda x: x[0])  # por fecha asc
                total = sum(q for _, q, _ in lotes)
                un = lotes[0][2] if lotes else ""
                if not detalhado:
                    linhas.append(f"• {nome}: {total}{un} (lotes: {len(lotes)})")
                else:
                    linhas.append(f"• {nome} — total {total}{un} ({len(lotes)} lotes)")
                    for i, (fecha, q, un) in enumerate(lotes):
                        prefix = "└─" if i == len(lotes)-1 else "├─"
                        linhas.append(f"   {prefix} {q}{un} ({fecha.strftime('%d/%m')})")
    return "\n".join(linhas)

def parse_args(update: Update, requiere_fecha=False):
    """
    Parsea:
      /entrada 20 kg, tomate, 29/07, HOR
      /entrada 10 kg, frango, 29/07, CON, C1
    Retorna: nombre, cantidad, unidad, fecha_producto, grupo
    """
    try:
        texto = update.message.text.split(' ', 1)
        if len(texto) < 2:
            return None, None, None, None, None

        partes = texto[1].split(',')

        if requiere_fecha:
            if len(partes) < 4:
                return None, None, None, None, None

            cant_unid = partes[0].strip().split()
            if len(cant_unid) != 2:
                return None, None, None, None, None

            try:
                cantidad = int(cant_unid[0])
            except ValueError:
                return None, None, None, None, None

            unidad = cant_unid[1].lower()
            nombre = partes[1].strip().lower()

            try:
                # seguimos completando con /2025 como tu esquema actual
                fecha_producto = datetime.strptime(partes[2].strip() + "/2025", "%d/%m/%Y").date()
            except ValueError:
                return None, None, None, None, None

            grupo = partes[3].strip().upper()
            return nombre, cantidad, unidad, fecha_producto, grupo

        return None, None, None, None, None

    except Exception:
        return (None,) * 5

def calcular_estoque(nome, grupo, productos):
    """Calcula stock actual de un producto en un grupo a partir de la tabla movimientos."""
    estoque = 0
    for _, n, q, t, d, u, g, _ in productos:
        if n.lower() == nome.lower() and g == grupo:
            if t == 'entrada':
                estoque += q
            elif t in ['saida', 'descarte', 'devolucao']:
                estoque -= q
    return estoque

# =========================
# Comandos base + menú
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Eu sou o Bot de Estoque. Use /menu para ver as opções disponíveis.",
        reply_markup=menu_markup
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Puedes reemplazar por v_menu() si lo prefieres
    mensaje = """
📋 *Comandos principais*

• /entrada — Registrar entrada
  - Não congelados: `/entrada 20 kg, tomate, 30/07, HOR`
  - Congelados   : `/entrada 10 kg, frango, 30/07, CON, C1`

• /saida — Registrar saída
  - Não congelados: `/saida 5 kg, tomate, 30/07, HOR`
  - Congelados   : `/saida 3 kg, frango, 30/07, CON, C1`

• /estoque_horti — Hortaliças e Frutas (resumo)
• /estoque_congelados [C1|C2|C3] — Congelados (opcional filtrar contêiner)
• /buscar [texto|HOR|CON|C1] — Buscar por nome, grupo ou contêiner
• /vencimentos — Ontem (em estoque) e amanhã
• /movimentacoes [dd/mm ou dd/mm-dd/mm] — Histórico

Dica: use os botões:
🥕 HortiFruti  → estoque de horti
❄️ Congelados → estoque de congelados
"""
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=menu_markup)

# =========================
# Entrada / Saída / Descarte
# =========================

async def entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad, unidad, fecha_producto, grupo = parse_args(update, requiere_fecha=True)

    if not all([nombre, cantidad, unidad, fecha_producto, grupo]):
        await update.message.reply_text(
            "❌ Formato inválido.\n\n"
            "*Não congelados (HOR/LAC/FRU/SEC):*\n"
            "`/entrada 20 kg, tomate, 30/07, HOR`\n\n"
            "*Congelados (CON):*\n"
            "`/entrada 10 kg, frango, 30/07, CON, C1`",
            parse_mode="Markdown"
        )
        return

    contenedor = None
    if grupo == "CON":
        partes = update.message.text.split(',')
        if len(partes) < 5:
            await update.message.reply_text(
                "❌ Indique o contêiner (C1/C2/C3) para congelados.\n"
                "Exemplo: `/entrada 10 kg, frango, 30/07, CON, C1`",
                parse_mode="Markdown"
            )
            return
        contenedor = partes[4].strip().upper()

    try:
        insertar_producto(nombre, cantidad, 'entrada', fecha_producto, unidad, grupo, contenedor)
        await update.message.reply_text(
            f"📥 Entrada registrada: {cantidad}{unidad} de {nombre} "
            f"({fecha_producto.strftime('%d/%m')}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error na entrada: {e}")

async def saida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad, unidad, fecha_producto, grupo = parse_args(update, requiere_fecha=True)

    if not all([nombre, cantidad, unidad, fecha_producto, grupo]):
        await update.message.reply_text(
            "❌ Formato inválido.\n\n"
            "*Não congelados (HOR/LAC/FRU/SEC):*\n"
            "`/saida 5 kg, tomate, 30/07, HOR`\n\n"
            "*Congelados (CON):*\n"
            "`/saida 3 kg, frango, 30/07, CON, C1`",
            parse_mode="Markdown"
        )
        return

    contenedor = None
    if grupo == "CON":
        partes = update.message.text.split(',')
        if len(partes) < 5:
            await update.message.reply_text(
                "❌ Indique o contêiner (C1/C2/C3) para congelados.\n"
                "Exemplo: `/saida 3 kg, frango, 30/07, CON, C1`",
                parse_mode="Markdown"
            )
            return
        contenedor = partes[4].strip().upper()

    # Verificar stock atual em stock_actual
    stock_actual = obtener_stock_actual(grupo=grupo, nombre=nombre)
    cont_cmp = contenedor if grupo == "CON" else "N/A"
    cantidad_actual = sum([item[1] for item in stock_actual if item[5] == cont_cmp])

    if cantidad_actual < cantidad:
        await update.message.reply_text(
            f"❌ Estoque insuficiente. {nombre} disponível: {cantidad_actual} {unidad}. "
            f"Tentativa de saída: {cantidad} {unidad}."
        )
        return

    try:
        insertar_producto(nombre, cantidad, 'saida', fecha_producto, unidad, grupo, contenedor)
        await update.message.reply_text(
            f"📤 Saída registrada: {cantidad}{unidad} de {nombre} "
            f"({fecha_producto.strftime('%d/%m')}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error na saída: {e}")

async def descarte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad, unidad, fecha_producto, grupo = parse_args(update, requiere_fecha=True)

    if not all([nombre, cantidad, unidad, fecha_producto, grupo]):
        await update.message.reply_text(
            "❌ Formato inválido.\n"
            "Exemplo: `/descarte 3 kg, tomate, 29/07, HOR`",
            parse_mode="Markdown"
        )
        return

    contenedor = None
    if grupo == "CON":
        partes = update.message.text.split(',')
        if len(partes) < 5:
            await update.message.reply_text(
                "❌ Indique o contêiner (C1/C2/C3) para congelados.\n"
                "Exemplo: `/descarte 3 kg, frango, 30/07, CON, C1`",
                parse_mode="Markdown"
            )
            return
        contenedor = partes[4].strip().upper()

    try:
        insertar_producto(nombre, cantidad, 'descarte', fecha_producto, unidad, grupo, contenedor)
        await update.message.reply_text(
            f"🗑️ Descarte registrado: {cantidad}{unidad} de {nombre} "
            f"({fecha_producto.strftime('%d/%m')}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error no descarte: {e}")

# =========================
# Vencimientos (ayer en stock, y mañana)
# =========================

async def vencimentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = datetime.now().date()
    produtos = obtener_stock_actual()  # vigentes

    proximos = []
    vencidos_ayer = []
    for nome, qtd, un, grupo, fecha, cont in produtos:
        if fecha == hoje + timedelta(days=1):
            proximos.append((nome, qtd, un, fecha, grupo, cont))
        elif fecha == hoje - timedelta(days=1):
            vencidos_ayer.append((nome, qtd, un, fecha, grupo, cont))

    if not proximos and not vencidos_ayer:
        await update.message.reply_text("✅ Sem alertas (ontem em estoque / amanhã a vencer).")
        return

    mensaje = "📅 *Alertas de Vencimento*\n"

    if vencidos_ayer:
        mensaje += "\n⚠️ *Vencidos ONTEM (ainda em estoque):*\n"
        for nome, qtd, un, fecha, grupo, cont in sorted(vencidos_ayer, key=lambda x: x[3]):
            mensaje += f"• {nome} – {qtd}{un} – {GRUPOS_MAP.get(grupo, grupo)}"
            if grupo == "CON":
                mensaje += f" ({cont})"
            mensaje += f" – {fecha.strftime('%d/%m')}\n"

    if proximos:
        mensaje += "\n⏳ *Vencem AMANHÃ:*\n"
        for nome, qtd, un, fecha, grupo, cont in sorted(proximos, key=lambda x: x[3]):
            mensaje += f"• {nome} – {qtd}{un} – {GRUPOS_MAP.get(grupo, grupo)}"
            if grupo == "CON":
                mensaje += f" ({cont})"
            mensaje += f" – {fecha.strftime('%d/%m')}\n"

    await update.message.reply_text(mensaje, parse_mode="Markdown")

# =========================
# Estoque Horti (HOR + FRU) y Congelados
# =========================

async def estoque_horti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = [p for p in obtener_stock_actual() if p[3] in ("HOR", "FRU", "LAC")]
    if not produtos:
        await update.message.reply_text("🥕🍎 Nenhum item no estoque hortifruti.")
        return
    msg = agrupar_e_formatar(produtos, por_contenedor=False, detalhado=False)
    await update.message.reply_text(msg, parse_mode="Markdown")

# ------------------------
# ESTOQUE CONGELADOS (resumido/detalhado)
# ------------------------
async def estoque_congelados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = datetime.now().date()
    produtos = obtener_stock_actual(grupo="CON")

    if not produtos:
        await update.message.reply_text("❄️ Nenhum item registrado no estoque de congelados.")
        return

    detalhado = False
    if context.args and context.args[0].lower() in ["detalhado", "detalhada", "d"]:
        detalhado = True

    if detalhado:
        mensagem = "❄️ *Estoque Congelados - Vista Detalhada:*\n"
        contenedores = {}
        for nome, quantidade, unidade, grupo, fecha_producto, contenedor in produtos:
            contenedores.setdefault(contenedor, [])
            contenedores[contenedor].append((nome, quantidade, unidade, fecha_producto))

        for contenedor, items in contenedores.items():
            mensagem += f"\n*{contenedor}*\n"
            items_ordenados = sorted(items, key=lambda x: x[3])
            for nome, quantidade, unidade, fecha_producto in items_ordenados:
                mensagem += f"• {nome}: {quantidade}{unidade} ({fecha_producto.strftime('%d/%m')})\n"
    else:
        mensagem = "❄️ *Estoque Congelados - Vista Resumida:*\n"
        resumo = {}
        for nome, quantidade, unidade, _, _, _ in produtos:
            key = f"{nome} ({unidade})"
            resumo[key] = resumo.get(key, 0) + quantidade
        for nome_unidade, total in sorted(resumo.items()):
            mensagem += f"• {nome_unidade}: {total}\n"

    await update.message.reply_text(mensagem, parse_mode="Markdown")

# =========================
# Movimentações (histórico)
# =========================

async def movimentacoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hoje = datetime.now().date()

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

        productos = obtener_productos()  # (id, nombre, cantidad, tipo, fecha_prod, unidade, grupo, fecha_mov)
        movimentos = [p for p in productos if inicio <= p[7].date() <= fim]

        if not movimentos:
            if inicio == fim:
                await update.message.reply_text(f"📅 Nenhum movimento registrado em {inicio.strftime('%d/%m')}.")
            else:
                await update.message.reply_text(f"📅 Nenhum movimento registrado entre {inicio.strftime('%d/%m')} e {fim.strftime('%d/%m')}.")
            return

        if inicio == fim:
            mensaje = f"📅 *Movimentos de {inicio.strftime('%d/%m')}*\n"
        else:
            mensaje = f"📅 *Movimentos de {inicio.strftime('%d/%m')} até {fim.strftime('%d/%m')}*\n"

        for _, nome, quantidade, tipo, fecha_producto, unidade, grupo, fecha_mov in sorted(movimentos, key=lambda x: x[7]):
            mensaje += (
                f"• {nome} – {quantidade}{unidade} ({tipo.upper()}) – Grupo: {grupo} "
                f"– Produto: {fecha_producto.strftime('%d/%m')} – {fecha_mov.strftime('%H:%M')}\n"
            )

        await update.message.reply_text(mensaje, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao buscar movimentos: {str(e)}")

# =========================
# Buscar
# =========================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Use: /buscar [produto|grupo|contêiner]\n"
            "Exemplos:\n"
            "/buscar frango\n"
            "/buscar CON\n"
            "/buscar C1"
        )
        return

    query = " ".join(context.args).strip().upper()
    grupos_validos = ["HOR", "CON", "LAC", "FRU", "SEC"]
    contenedores_validos = ["C1", "C2", "C3"]

    if query in grupos_validos:
        resultados = obtener_stock_actual(grupo=query)
        if not resultados:
            await update.message.reply_text(f"📦 Sem estoque para o grupo {query}.")
            return

        mensaje = f"*Estoque do grupo {GRUPOS_MAP.get(query, query)}:*\n"
        if query == "CON":
            contenedores = {}
            for nombre, cantidad, unidade, grupo, fecha, contenedor in resultados:
                contenedores.setdefault(contenedor, [])
                contenedores[contenedor].append((nombre, quantidade, unidade, fecha))

            for contenedor in sorted(contenedores.keys()):
                items = contenedores[contenedor]
                mensaje += f"\n*{contenedor}*\n"
                for nombre, cantidad, unidade, fecha in items:
                    mensaje += f"• {nombre}: {cantidad}{unidade} ({fecha.strftime('%d/%m')})\n"
        else:
            for nombre, cantidad, unidade, grupo, fecha, _ in resultados:
                mensaje += f"• {nombre}: {cantidad}{unidade} ({fecha.strftime('%d/%m')})\n"

        await update.message.reply_text(mensaje, parse_mode="Markdown")
        return

    elif query in contenedores_validos:
        resultados = obtener_stock_actual(grupo="CON")
        resultados = [r for r in resultados if r[5] == query]

        if not resultados:
            await update.message.reply_text(f"📦 Sem estoque no contêiner {query}.")
            return

        mensaje = f"*Estoque no Contêiner {query} (Congelados):*\n"
        for nombre, quantidade, unidade, grupo, fecha, contenedor in resultados:
            mensaje += f"• {nombre}: {quantidade}{unidade} ({fecha.strftime('%d/%m')})\n"

        await update.message.reply_text(mensaje, parse_mode="Markdown")
        return

    else:
        resultados = obtener_stock_actual(nombre=query.lower())
        if not resultados:
            await update.message.reply_text(f"📦 Não foi encontrado estoque para '{query}'.")
            return

        mensaje = f"*Resultados para '{query}':*\n"
        for nombre, quantidade, unidade, grupo, fecha, contenedor in resultados:
            grupo_nombre = GRUPOS_MAP.get(grupo, grupo)
            if grupo == "CON":
                mensaje += f"• {quantidade}{unidade} – {grupo_nombre} ({contenedor}) – {fecha.strftime('%d/%m')}\n"
            else:
                mensaje += f"• {quantidade}{unidade} – {grupo_nombre} – {fecha.strftime('%d/%m')}\n"

        await update.message.reply_text(mensaje, parse_mode="Markdown")

# =========================
# Handlers para botones del teclado
# =========================
# Estos no son comandos: responden cuando el usuario toca los botones del ReplyKeyboard.

async def on_keyboard_horti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Botón "🥕 HortiFruti"
    return await estoque_horti(update, context)

async def on_keyboard_congelados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Botón "❄️ Congelados"
    return await estoque_congelados(update, context)

