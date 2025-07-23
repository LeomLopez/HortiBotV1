from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from views.menu import get_menu_text as v_menu
from models.db import obtener_productos, insertar_producto
from datetime import datetime

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
        if requiere_fecha:
            if len(partes) < 3:
                return None, None, None, None
            cantidad = int(partes[0].strip())
            nome = partes[1].strip()
            data_produto = datetime.strptime(partes[2].strip() + "/2025", "%d/%m/%Y").date()
            return nome, cantidad, data_produto, 'entrada'
        else:
            if len(partes) < 2:
                return None, None
            nome = partes[0].strip()
            cantidad = int(partes[1].strip())
            return nome, cantidad
    except Exception:
        return (None,) * (4 if requiere_fecha else 2)

# Comando: entrada
async def entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome, quantidade, data_produto, tipo = parse_args(update, requiere_fecha=True)
    if not nome or not quantidade or not data_produto:
        await update.message.reply_text("❌ Use o formato: /entrada [quantidade], [produto], [dd/mm]")
        return
    insertar_producto(nome, quantidade, 'entrada', data_produto)
    await update.message.reply_text(f"📥 Entrada registrada: {quantidade}kg de {nome} (data: {data_produto.strftime('%d/%m')})")

# Comando: saída
async def saida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome, quantidade, data_produto, tipo = parse_args(update, requiere_fecha=True)
    
    if not nome or not quantidade or not data_produto:
        await update.message.reply_text("❌ Use o formato: /saida [quantidade], [produto], [dd/mm]")
        return

    # Calcular o estoque atual desse produto
    produtos = obtener_productos(nome)
    estoque = 0
    for _, n, q, t, _ in produtos:
        if n.lower() == nome.lower():
            if t == 'entrada':
                estoque += q
            elif t in ['saida', 'descarte', 'devolucao']:
                estoque -= q

    if estoque < quantidade:
        await update.message.reply_text(
            f"❌ Estoque insuficiente. {nome} disponível: {estoque} kg. Você tentou retirar {quantidade} kg."
        )
        return

    # Se há estoque suficiente, registrar a saída
    insertar_producto(nome, quantidade, "saida", data_produto)
    await update.message.reply_text(
        f"📤 Saída registrada: {quantidade}kg de {nome} (data: {data_produto.strftime('%d/%m')})"
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
    productos = obtener_productos()
    hoy = datetime.now().date()
    mensaje_alertas = "📅 *Avisos de Vencimento:*\n"
    mensaje_descartes = f"\n🗑️ *Descartes automáticos de {hoy.strftime('%d/%m/%Y')}:*\n"
    hay_alertas = False
    hay_descartes = False

    revisados = set()

    for _, nombre, cantidad, tipo, fecha_producto in productos:
        if tipo != 'entrada':
            continue

        if (nombre, fecha_producto) in revisados:
            continue
        revisados.add((nombre, fecha_producto))

        dias_diferencia = (fecha_producto - hoy).days

        if dias_diferencia == 2:
            mensaje_alertas += f"⚠️ {nombre} vence em 2 dias ({fecha_producto.strftime('%d/%m')})\n"
            hay_alertas = True
        elif dias_diferencia == 0:
            mensaje_alertas += f"⚠️ {nombre} vence HOJE! ({fecha_producto.strftime('%d/%m')})\n"
            hay_alertas = True
        elif dias_diferencia == -1:
            # Insertar como descarte automático
            insertar_producto(nombre, cantidad, 'descarte', hoy)
            mensaje_descartes += f"🗑️ {nombre} vencido em {fecha_producto.strftime('%d/%m')} – descartado.\n"
            hay_descartes = True

    final = ""
    if hay_alertas:
        final += mensaje_alertas
    if hay_descartes:
        final += mensaje_descartes

    if final:
        await update.message.reply_text(final, parse_mode="Markdown")
    else:
        await update.message.reply_text("✅ Nenhum vencimento próximo ou vencido hoje.")    


# Comando: descarte
async def estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = obtener_productos()
    if not produtos:
        await update.message.reply_text("📦 Nenhum item registrado no estoque.")
        return

    estoque_atual = {}

    for _, nome, quantidade, tipo, data in produtos:
        nome = nome.lower()
        tipo = tipo.lower()
        if nome not in estoque_atual:
            estoque_atual[nome] = {"quantidade": 0, "datas": []}

        if tipo == 'entrada':
            estoque_atual[nome]["quantidade"] += quantidade
            estoque_atual[nome]["datas"].append(data)
        elif tipo in ['saida', 'descarte', 'devolucao']:
            estoque_atual[nome]["quantidade"] -= quantidade
            estoque_atual[nome]["datas"].append(data)

    mensagem = "📦 *Estoque Atual:*\n"
    for nome, info in estoque_atual.items():
        if info["quantidade"] > 0:
            ultima_data = max(info["datas"]).strftime("%d/%m/%y")
            mensagem += f"• {nome}: {info['quantidade']} kg (última: {ultima_data})\n"

    await update.message.reply_text(mensagem, parse_mode="Markdown")




# Comando: resumo por produto e tipo
async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    produtos = obtener_productos()
    if not produtos:
        await update.message.reply_text("📊 Nenhum dado disponível para exibir.")
        return

    resumo = {}
    for _, nome, quantidade, tipo, fecha in produtos:
        chave = (nome.lower(), tipo.lower(), fecha)
        resumo[chave] = resumo.get(chave, 0) + quantidade

    mensagem = "📊 *Resumo por tipo e data:*\n"
    for (nome, tipo, fecha), total in resumo.items():
        mensagem += f"• {nome} ({tipo}) – {total} kg em {fecha}\n"

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
