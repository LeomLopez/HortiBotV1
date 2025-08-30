from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from views.menu import get_menu_text as v_menu
from models.db import obtener_productos, insertar_producto, obtener_stock_actual
from datetime import datetime, date

# Diccionario para traducir abreviaturas a nombre largo + emoji
GRUPOS_MAP = {
    "HOR": "🥕 Hortaliças",
    "FRU": "🍎 Frutas",
    "LAC": "🧀 Lácteos",
    "CON": "❄️ Congelados",
    "SEC": "📦 Secos"
}

# Teclado personalizado
keyboard = [
    ["🥕 HortiFruti", "❄️ Congelados"],
    ["📦 Estoque Seco", "🧪 Estoque Químico"],
    ["🧻 Estoque Descartáveis", "📋 Requisições"]
]
menu_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ------------------------
# Funciones Auxiliares
# ------------------------

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

            # Fecha
            try:
                fecha_producto = datetime.strptime(partes[2].strip() + "/2025", "%d/%m/%Y").date()
            except ValueError:
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
            if t == 'entrada':
                estoque += q
            elif t in ['saida', 'descarte', 'devolucao']:
                estoque -= q
    return estoque

def mover_para_descarte(produtos):
    hoje = datetime.now().date()
    for _, nome, quantidade, tipo, data, unidade, grupo, _ in produtos:
        if tipo == "entrada" and (data - hoje).days == -1:
            insertar_producto(nome, quantidade, 'descarte', data, unidade, grupo)

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
`/saida 5 kg, tomate, 29/07, HOR`

- Congelados (com contêiner):
`/saida 3 kg, frango, 30/07, CON, C1`

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

    # Manejo de contenedor
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

    try:
        insertar_producto(nombre, cantidad, 'entrada', fecha_producto, unidad, grupo, contenedor)
        await update.message.reply_text(
            f"📥 Entrada registrada: {cantidad}{unidad} de {nombre} "
            f"({fecha_producto.strftime('%d/%m')}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}"
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
            "*Não congelados (HOR/LAC/etc):*\n"
            "`/saida 5 kg, tomate, 30/07, HOR`\n\n"
            "*Congelados (CON):*\n"
            "`/saida 3 kg, frango, 30/07, CON, C1`",
            parse_mode="Markdown"
        )
        return

    # Manejo de contenedor
    contenedor = None
    if grupo == "CON":
        partes = update.message.text.split(',')
        if len(partes) < 5:
            await update.message.reply_text(
                "❌ Você deve indicar o contêiner (C1/C2/C3) para congelados.\n"
                "Exemplo: `/saida 3 kg, frango, 30/07, CON, C1`",
                parse_mode="Markdown"
            )
            return
        contenedor = partes[4].strip().upper()

    # Verificar stock actual antes de registrar salida
    stock_actual = obtener_stock_actual(grupo=grupo, nombre=nombre)
    cantidad_actual = sum([item[1] for item in stock_actual if item[5] == (contenedor or "N/A")])

    if cantidad_actual < cantidad:
        await update.message.reply_text(
            f"❌ Estoque insuficiente. {nombre} disponible: {cantidad_actual} {unidad}. "
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
        await update.message.reply_text(f"⚠️ Error en la saída: {e}")




# ------------------------
# DESCARTE (manual)
# ------------------------
async def descarte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome, quantidade, unidade, data_produto, grupo = parse_args(update, requiere_fecha=True)

    if not nome or not quantidade or not unidade or not data_produto or not grupo:
        await update.message.reply_text(
            "❌ Use o formato: /descarte [quantidade] [unidade], [produto], [dd/mm], [grupo]\n"
            "Exemplo: /descarte 3 kg, tomate, 29/07, HOR"
        )
        return

    insertar_producto(nome, quantidade, 'descarte', data_produto, unidade, grupo)

    await update.message.reply_text(
        f"🗑️ Descarte registrado: {quantidade}{unidade} de {nome} "
        f"({data_produto.strftime('%d/%m')}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}"
    )

# ------------------------
# VENCIMIENTOS
# ------------------------
async def vencimentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = obtener_productos()
    hoje = datetime.now().date()

    mover_para_descarte(produtos)  # Descarta automáticamente

    alerta_proximos = []
    alerta_hoy = []

    for _, nome, quantidade, tipo, data, unidade, grupo, _ in produtos:
        if tipo != "entrada":
            continue

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
            mensagem += f"• {nome}: {quantidade}{unidade} ({data.strftime('%d/%m')})\n"

    if alerta_proximos:
        mensagem += "\n⏳ *Próximos a vencer (2 dias):*\n"
        for nome, quantidade, unidade, data in alerta_proximos:
            mensagem += f"• {nome}: {quantidade}{unidade} ({data.strftime('%d/%m')})\n"

    await update.message.reply_text(mensagem, parse_mode="Markdown")

# ------------------------
# ESTOQUE
# ------------------------
async def estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = obtener_stock_actual()  # Optimizado desde stock_actual
    if not produtos:
        await update.message.reply_text("📦 Nenhum item registrado no estoque.")
        return

    mensagem = "📦 *Estoque Atual:*\n"
    grupos = {}

    for nome, quantidade, unidade, grupo, fecha_producto, contenedor in produtos:
        grupos.setdefault(grupo, [])
        grupos[grupo].append((nome, quantidade, unidade, fecha_producto))

    for grupo, items in grupos.items():
        nome_grupo = GRUPOS_MAP.get(grupo, grupo)
        mensagem += f"\n{nome_grupo}\n"

        # Ya no se vuelve a ordenar: confiamos en el orden SQL
        for nome, quantidade, unidade, fecha_producto in items:
            mensagem += f"• {nome}: {quantidade}{unidade} ({fecha_producto.strftime('%d/%m')})\n"

    await update.message.reply_text(mensagem, parse_mode="Markdown")

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
            mensagem += f"• {nome}: {quantidade}{unidade} ({fecha_producto.strftime('%d/%m')})\n"

    if alerta_hoy or alerta_proximos:
        mensagem += "\n📅 *Alertas de Vencimento*\n"

        if alerta_hoy:
            mensagem += "\n⚠️ *Vencem HOJE:*\n"
            for nome, quantidade, unidade, fecha_producto, contenedor in alerta_hoy:
                mensagem += f"• {nome} ({contenedor}): {quantidade}{unidade} ({fecha_producto.strftime('%d/%m')})\n"

        if alerta_proximos:
            mensagem += "\n⏳ *Próximos a vencer (2 dias):*\n"
            for nome, quantidade, unidade, fecha_producto, contenedor in alerta_proximos:
                mensagem += f"• {nome} ({contenedor}): {quantidade}{unidade} ({fecha_producto.strftime('%d/%m')})\n"

    await update.message.reply_text(mensagem, parse_mode="Markdown")

# ------------------------
# BUSCAR
# ------------------------
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

    # Buscar por grupo
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
                contenedores[contenedor].append((nombre, cantidad, unidade, fecha))

            for contenedor, items in contenedores.items():
                mensaje += f"\n*{contenedor}*\n"
                for nombre, cantidad, unidade, fecha in items:
                    mensaje += f"• {nombre}: {cantidad}{unidade} ({fecha.strftime('%d/%m')})\n"
        else:
            for nombre, cantidad, unidade, grupo, fecha, _ in resultados:
                mensaje += f"• {nombre}: {cantidad}{unidade} ({fecha.strftime('%d/%m')})\n"

        await update.message.reply_text(mensaje, parse_mode="Markdown")
        return

    # Buscar por contenedor
    elif query in contenedores_validos:
        resultados = obtener_stock_actual(grupo="CON")
        resultados = [r for r in resultados if r[5] == query]

        if not resultados:
            await update.message.reply_text(f"📦 Sem estoque para o grupo {query}.")
            return

        mensaje = f"*Estoque no Contêiner {query} (Congelados):*\n"
        for nombre, cantidad, unidade, grupo, fecha, contenedor in resultados:
            mensaje += f"• {nombre}: {cantidad}{unidade} ({fecha.strftime('%d/%m')})\n"

        await update.message.reply_text(mensaje, parse_mode="Markdown")
        return

    # Buscar por producto
    else:
        resultados = obtener_stock_actual(nombre=query.lower())

        if not resultados:
            await update.message.reply_text(f"📦 Não foi encontrado estoque para '{query}'.")
            return

        mensaje = f"*Resultados para '{query}':*\n"
        for nombre, cantidad, unidade, grupo, fecha, contenedor in resultados:
            grupo_nombre = GRUPOS_MAP.get(grupo, grupo)
            if grupo == "CON":
                mensaje += f"• {cantidad}{unidade} – {grupo_nombre} ({contenedor}) – {fecha.strftime('%d/%m')}\n"
            else:
                mensaje += f"• {cantidad}{unidade} – {grupo_nombre} – {fecha.strftime('%d/%m')}\n"

        await update.message.reply_text(mensaje, parse_mode="Markdown")


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
                f"– Produto: {fecha_producto.strftime('%d/%m')} – {fecha_mov.strftime('%H:%M')}\n"
            )

        await update.message.reply_text(mensaje, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao buscar movimentos: {str(e)}")
