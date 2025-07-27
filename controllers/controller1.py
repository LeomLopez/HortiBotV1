from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from views.menu import get_menu_text as v_menu
from models.db import obtener_productos, insertar_producto
from datetime import datetime
import re

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


# Mensagem de boas-vindas
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Eu sou o Bot de Estoque. Use /menu para ver as opções disponíveis.",
        reply_markup=menu_markup
    )


# Mostrar menu
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(v_menu(), parse_mode="Markdown", reply_markup=menu_markup)


# Parsear a entrada do usuário
def parse_args(update: Update, requiere_fecha=False):
    try:
        partes = update.message.text.split(' ', 1)[1].split(',')
        partes = [p.strip() for p in partes]  # Limpiar espacios extra

        if requiere_fecha:
            # Deben llegar 4 partes: cantidad+unidad, nombre, grupo, fecha
            if len(partes) < 4:
                return None, None, None, None, None, None

            # Parsear cantidad y unidad (ej. "10kg")
            match = re.match(r"(\d+)([a-zA-Z]+)", partes[0])
            if not match:
                return None, None, None, None, None, None
            cantidad = int(match.group(1))
            unidad = match.group(2).lower()

            nombre = partes[1].lower()
            grupo = partes[2].lower()

            fecha_producto = datetime.strptime(partes[3] + "/2025", "%d/%m/%Y").date()

            return nombre, cantidad, unidad, fecha_producto, 'entrada', grupo
        else:
            # Si no requiere fecha, retorna valores básicos
            return None, None, None, None, None, None
    except Exception:
        return (None,) * 6



# Comando: entrada
async def entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome, quantidade, unidade, data_produto, tipo, grupo = parse_args(update, requiere_fecha=True)

    # Validar campos
    if not nome or not quantidade or not unidade or not data_produto or not grupo:
        await update.message.reply_text(
            "❌ Use o formato: /entrada [quantidade+unidade], [produto], [dd/mm], [grupo]\n"
            "Exemplo: /entrada 10kg, tomate, 26/07, HOR"
        )
        return

    # Validar grupo
    if grupo not in GRUPOS_MAP:
        await update.message.reply_text(
            f"❌ Grupo '{grupo}' não é válido. Use um destes: {', '.join(GRUPOS_MAP.keys())}"
        )
        return

    # Insertar en la base
    insertar_producto(nome, quantidade, 'entrada', data_produto, unidade, grupo)

    # Mensaje de confirmación
    await update.message.reply_text(
        f"📥 Entrada registrada: {quantidade}{unidade} de {nome} "
        f"({data_produto.strftime('%d/%m')}) – Grupo: {GRUPOS_MAP[grupo]}"
    )




# Comando: saída
async def saida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome, quantidade, unidade, data_produto, tipo, grupo = parse_args(update, requiere_fecha=True)

    # Validar campos
    if not nome or not quantidade or not unidade or not data_produto or not grupo:
        await update.message.reply_text(
            "❌ Use o formato: /saida [quantidade+unidade], [produto], [dd/mm], [grupo]\n"
            "Exemplo: /saida 5kg, tomate, 26/07, HOR"
        )
        return

    if grupo not in GRUPOS_MAP:
        await update.message.reply_text(
            f"❌ Grupo '{grupo}' não é válido. Use um destes: {', '.join(GRUPOS_MAP.keys())}"
        )
        return

    # Verificar estoque disponible
    produtos = obtener_productos(nome)
    estoque = 0
    for _, n, q, t, _, _, g in produtos:
        if n.lower() == nome.lower() and g == grupo:
            if t == 'entrada':
                estoque += q
            elif t in ['saida', 'descarte', 'devolucao']:
                estoque -= q

    if estoque < quantidade:
        await update.message.reply_text(
            f"❌ Estoque insuficiente. {nome} disponível: {estoque}{unidade} no grupo {grupo}."
        )
        return

    # Registrar saída
    insertar_producto(nome, quantidade, 'saida', data_produto, unidade, grupo)

    await update.message.reply_text(
        f"📤 Saída registrada: {quantidade}{unidade} de {nome} "
        f"({data_produto.strftime('%d/%m')}) – Grupo: {GRUPOS_MAP[grupo]}"
    )



# Comando: devolução
async def devolucao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ O comando /devolucao foi desativado temporariamente.")
    
    """nome, quantidade = parse_args(update)
    if not nome or not quantidade:
        await update.message.reply_text("❌ Use o formato: /devolucao [produto], [quantidade]")
        return
    insertar_producto(nome, quantidade, "devolucao", datetime.now().date())
    await update.message.reply_text(f"♻️ Devolução registrada: {quantidade} de {nome}")"""
    
    
async def vencimentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = obtener_productos()
    hoje = datetime.now().date()

    alerta_proximos = []
    alerta_hoy = []

    for _, nome, quantidade, tipo, data, unidade in produtos:
        # Solo entradas cuentan para vencimiento
        if tipo != "entrada":
            continue

        # Diferencia en días entre hoy y fecha del producto
        dias_restantes = (data - hoje).days

        # Próximos a vencer (2 días)
        if 1 <= dias_restantes <= 2:
            alerta_proximos.append((nome, quantidade, unidade, data))
        # Vencen hoy
        elif dias_restantes == 0:
            alerta_hoy.append((nome, quantidade, unidade, data))

    # Construir mensaje
    if not alerta_proximos and not alerta_hoy:
        await update.message.reply_text("✅ Nenhum item próximo de vencer ou vencendo hoje.")
        return

    mensagem = "📅 *Alertas de Vencimento*\n"

    # Productos que vencen hoy
    if alerta_hoy:
        mensagem += "\n⚠️ *Vencem HOJE:*\n"
        for nome, quantidade, unidade, data in sorted(alerta_hoy, key=lambda x: x[3]):
            mensagem += f"• {nome}: {quantidade}{unidade} ({data.strftime('%d/%m')})\n"

    # Productos próximos a vencer
    if alerta_proximos:
        mensagem += "\n⏳ *Próximos a vencer (2 dias):*\n"
        for nome, quantidade, unidade, data in sorted(alerta_proximos, key=lambda x: x[3]):
            mensagem += f"• {nome}: {quantidade}{unidade} ({data.strftime('%d/%m')})\n"

    await update.message.reply_text(mensagem, parse_mode="Markdown")



async def estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = obtener_productos()
    if not produtos:
        await update.message.reply_text("📦 Nenhum item registrado no estoque.")
        return

    hoje = datetime.now().date()

    # Diccionario agrupado: { grupo: { (nome, fecha): {quantidade, unidade} } }
    grupos_estoque = {}

    for _, nome, quantidade, tipo, data, unidade, grupo, _ in produtos:
        # Ignorar productos vencidos
        if data < hoje:
            continue

        chave = (nome.lower(), data)

        # Asegurar que el grupo exista
        if grupo not in grupos_estoque:
            grupos_estoque[grupo] = {}

        # Asegurar que el producto-fecha exista dentro del grupo
        if chave not in grupos_estoque[grupo]:
            grupos_estoque[grupo][chave] = {"quantidade": 0, "unidade": unidade}

        # Sumar/restar según tipo
        if tipo == 'entrada':
            grupos_estoque[grupo][chave]["quantidade"] += quantidade
        elif tipo in ['saida', 'descarte', 'devolucao']:
            grupos_estoque[grupo][chave]["quantidade"] -= quantidade

    # Construir mensaje final
    mensagem = "📦 *Estoque Atual:*\n"

    for cod_grupo, itens in grupos_estoque.items():
        # Traducir código a nombre largo
        nome_grupo = GRUPOS_MAP.get(cod_grupo, cod_grupo)

        # Filtrar solo cantidades positivas
        itens_validos = [(nome, data, info["quantidade"], info["unidade"])
                         for (nome, data), info in itens.items()
                         if info["quantidade"] > 0]

        if not itens_validos:
            continue

        # Ordenar por fecha
        itens_ordenados = sorted(itens_validos, key=lambda x: x[1])

        # Sección del grupo
        mensagem += f"\n{nome_grupo}\n"

        # Listar productos
        for nome, data, quantidade, unidade in itens_ordenados:
            mensagem += f"• {nome}: {quantidade}{unidade} ({data.strftime('%d/%m')})\n"

    # Si no hay nada válido
    if mensagem == "📦 *Estoque Atual:*\n":
        await update.message.reply_text("📦 Nenhum item válido no estoque.")
        return

    await update.message.reply_text(mensagem, parse_mode="Markdown")


# Comando: resumo por produto e tipo
async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = obtener_productos()
    if not produtos:
        await update.message.reply_text("📊 Nenhum dado disponível para exibir.")
        return

    resumo = {}
    for _, nome, quantidade, tipo, data, unidade in produtos:
        chave = (nome.lower(), tipo.lower(), data, unidade)
        resumo[chave] = resumo.get(chave, 0) + quantidade

    mensagem = "📊 *Resumo por tipo e data:*\n"
    for (nome, tipo, data, unidade), total in resumo.items():
        mensagem += f"• {nome} ({tipo}) – {total} {unidade} em {data.strftime('%d/%m/%y')}\n"

    await update.message.reply_text(mensagem, parse_mode="Markdown")



# Comando: debug → mostra os últimos registros sem filtro
async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = obtener_productos()
    if not produtos:
        await update.message.reply_text("⚠️ Nenhum registro encontrado no banco de dados.")
        return

    mensagem = "🧪 Últimos registros:\n"
    for p in produtos[:5]:
        mensagem += f"• {p[1]} | {p[2]} unid | {p[3]} | {p[4].strftime('%Y-%m-%d %H:%M')}\n"

    await update.message.reply_text(mensagem)




async def movimentacoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hoje = datetime.now().date()

        # Ver si pasaron fecha o rango
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

        # Filtrar por fecha de movimiento (no fecha de producto)
        movimientos_filtrados = [
            p for p in productos if inicio <= p[6].date() <= fim
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

        for _, nome, quantidade, tipo, fecha_producto, unidade, grupo, fecha_mov in sorted(movimientos_filtrados, key=lambda x: x[6]):
            mensaje += (
                f"• {nome} – {quantidade}{unidade} ({tipo.upper()}) – Grupo: {grupo} "
                f"– Produto: {fecha_producto.strftime('%d/%m')} – {fecha_mov.strftime('%H:%M')}\n"
            )

        await update.message.reply_text(mensaje, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao buscar movimentos: {str(e)}")


