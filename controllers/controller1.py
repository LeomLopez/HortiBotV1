from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from views.menu import get_menu_text as v_menu
from models.db import obtener_productos, insertar_producto
from datetime import datetime

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

def parse_args(update: Update, requiere_fecha=False):
    """Parsea el mensaje del usuario en formato:
    /entrada 20 kg, tomate, 29/07, HOR
    """
    try:
        partes = update.message.text.split(' ', 1)[1].split(',')

        if requiere_fecha:
            if len(partes) < 4:
                return None, None, None, None, None

            cant_unid = partes[0].strip().split()
            if len(cant_unid) != 2:
                return None, None, None, None, None

            cantidad = int(cant_unid[0])
            unidad = cant_unid[1].lower()

            nombre = partes[1].strip().lower()
            fecha_producto = datetime.strptime(partes[2].strip() + "/2025", "%d/%m/%Y").date()
            grupo = partes[3].strip().upper()

            return nombre, cantidad, unidad, fecha_producto, grupo

        return None, None, None, None, None

    except Exception:
        return (None,) * 5


def calcular_estoque(nome, grupo, produtos):
    """Calcula stock actual de un producto en un grupo"""
    estoque = 0
    for _, n, q, t, d, u, g, _ in produtos:
        if n.lower() == nome.lower() and g == grupo:
            if t == 'entrada':
                estoque += q
            elif t in ['saida', 'descarte', 'devolucao']:
                estoque -= q
    return estoque


def mover_para_descarte(produtos):
    """Mueve automáticamente productos vencidos (1 día después) al descarte"""
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
    await update.message.reply_text(v_menu(), parse_mode="Markdown", reply_markup=menu_markup)

# ------------------------
# ENTRADA
# ------------------------
async def entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome, quantidade, unidade, data_produto, grupo = parse_args(update, requiere_fecha=True)

    if not nome or not quantidade or not unidade or not data_produto or not grupo:
        await update.message.reply_text(
            "❌ Use o formato: /entrada [quantidade] [unidade], [produto], [dd/mm], [grupo]\n"
            "Exemplo: /entrada 20 kg, tomate, 29/07, HOR"
        )
        return

    insertar_producto(nome, quantidade, 'entrada', data_produto, unidade, grupo)

    await update.message.reply_text(
        f"📥 Entrada registrada: {quantidade}{unidade} de {nome} "
        f"({data_produto.strftime('%d/%m')}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}"
    )

# ------------------------
# SAIDA
# ------------------------
async def saida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome, quantidade, unidade, data_produto, grupo = parse_args(update, requiere_fecha=True)

    if not nome or not quantidade or not unidade or not data_produto or not grupo:
        await update.message.reply_text(
            "❌ Use o formato: /saida [quantidade] [unidade], [produto], [dd/mm], [grupo]\n"
            "Exemplo: /saida 5 kg, tomate, 29/07, HOR"
        )
        return

    produtos = obtener_productos()
    estoque = calcular_estoque(nome, grupo, produtos)

    if estoque < quantidade:
        await update.message.reply_text(
            f"❌ Estoque insuficiente. {nome} disponível: {estoque} {unidade}. "
            f"Tentativa de saída: {quantidade} {unidade}."
        )
        return

    insertar_producto(nome, quantidade, 'saida', data_produto, unidade, grupo)

    await update.message.reply_text(
        f"📤 Saída registrada: {quantidade}{unidade} de {nome} "
        f"({data_produto.strftime('%d/%m')}) – Grupo: {GRUPOS_MAP.get(grupo, grupo)}"
    )

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
        for nome, quantidade, unidade, data in sorted(alerta_hoy, key=lambda x: x[3]):
            mensagem += f"• {nome}: {quantidade}{unidade} ({data.strftime('%d/%m')})\n"

    if alerta_proximos:
        mensagem += "\n⏳ *Próximos a vencer (2 dias):*\n"
        for nome, quantidade, unidade, data in sorted(alerta_proximos, key=lambda x: x[3]):
            mensagem += f"• {nome}: {quantidade}{unidade} ({data.strftime('%d/%m')})\n"

    await update.message.reply_text(mensagem, parse_mode="Markdown")

# ------------------------
# ESTOQUE
# ------------------------
async def estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = obtener_productos()
    if not produtos:
        await update.message.reply_text("📦 Nenhum item registrado no estoque.")
        return

    hoje = datetime.now().date()
    grupos_estoque = {}

    for _, nome, quantidade, tipo, data, unidade, grupo, _ in produtos:
        if data < hoje:
            continue

        chave = (nome.lower(), data)

        if grupo not in grupos_estoque:
            grupos_estoque[grupo] = {}

        if chave not in grupos_estoque[grupo]:
            grupos_estoque[grupo][chave] = {"quantidade": 0, "unidade": unidade}

        if tipo == 'entrada':
            grupos_estoque[grupo][chave]["quantidade"] += quantidade
        elif tipo in ['saida', 'descarte', 'devolucao']:
            grupos_estoque[grupo][chave]["quantidade"] -= quantidade

    mensagem = "📦 *Estoque Atual:*\n"

    for cod_grupo, itens in grupos_estoque.items():
        nome_grupo = GRUPOS_MAP.get(cod_grupo, cod_grupo)

        itens_validos = [(nome, data, info["quantidade"], info["unidade"])
                         for (nome, data), info in itens.items()
                         if info["quantidade"] > 0]

        if not itens_validos:
            continue

        itens_ordenados = sorted(itens_validos, key=lambda x: x[1])

        mensagem += f"\n{nome_grupo}\n"
        for nome, data, quantidade, unidade in itens_ordenados:
            mensagem += f"• {nome}: {quantidade}{unidade} ({data.strftime('%d/%m')})\n"

    if mensagem == "📦 *Estoque Atual:*\n":
        await update.message.reply_text("📦 Nenhum item válido no estoque.")
        return

    await update.message.reply_text(mensagem, parse_mode="Markdown")

# ------------------------
# MOVIMENTACOES
# ------------------------
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

        # Obtener productos
        productos = obtener_productos()

        # Filtrar por fecha de movimiento (índice 7)
        movimientos_filtrados = [
            p for p in productos if inicio <= p[7].date() <= fim
        ]

        if not movimientos_filtrados:
            if inicio == fim:
                await update.message.reply_text(f"📅 Nenhum movimento registrado em {inicio.strftime('%d/%m')}.")
            else:
                await update.message.reply_text(f"📅 Nenhum movimento registrado entre {inicio.strftime('%d/%m')} e {fim.strftime('%d/%m')}.")
            return

        # Construir mensaje
        if inicio == fim:
            mensaje = f"📅 *Movimentos de {inicio.strftime('%d/%m')}*\n"
        else:
            mensaje = f"📅 *Movimentos de {inicio.strftime('%d/%m')} até {fim.strftime('%d/%m')}*\n"

        for _, nome, quantidade, tipo, fecha_producto, unidade, grupo, fecha_mov in sorted(movimientos_filtrados, key=lambda x: x[7]):
            mensaje += (
                f"• {nome} – {quantidade}{unidade} ({tipo.upper()}) – Grupo: {grupo} "
                f"– Produto: {fecha_producto.strftime('%d/%m')} – {fecha_mov.strftime('%H:%M')}\n"
            )

        await update.message.reply_text(mensaje, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao buscar movimentos: {str(e)}")
