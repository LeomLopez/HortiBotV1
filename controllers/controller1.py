from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from views.menu import get_menu_text as v_menu
from models.db import obtener_productos, insertar_producto
from datetime import datetime
import re

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
def parse_args(update, requiere_fecha=False):
    try:
        texto = update.message.text.split(' ', 1)[1]
        partes = [p.strip() for p in texto.split(',')]

        if requiere_fecha:
            if len(partes) < 3:
                return None, None, None, None, None

            # Buscar cantidad y unidad con o sin espacio (ej. "10kg" o "10 kg")
            match = re.match(r"(\d+)\s*([a-zA-Z]+)", partes[0])
            if not match:
                return None, None, None, None, None

            cantidad = int(match.group(1))
            unidad = match.group(2).lower()
            nombre = partes[1].strip().lower()
            fecha_producto = datetime.strptime(partes[2].strip() + "/2025", "%d/%m/%Y").date()

            return nombre, cantidad, unidad, fecha_producto, 'entrada'
        else:
            return None, None, None  # para otros comandos aún no usados
    except Exception as e:
        print(f"❌ Error en parse_args: {e}")
        return (None,) * (5 if requiere_fecha else 3)



# Comando: entrada
async def entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome, quantidade, unidade, data_produto, tipo = parse_args(update, requiere_fecha=True)
    if not nome or not quantidade or not unidade or not data_produto:
        await update.message.reply_text(
    "❌ Use o formato: /entrada [quantidade+unidade], [produto], [dd/mm]\nExemplo: /entrada 10kg, manga, 26/07")
        return

    insertar_producto(nome, quantidade, tipo, data_produto, unidade)
    await update.message.reply_text(
        f"📥 Entrada registrada: {quantidade}{unidade} de {nome} (data: {data_produto.strftime('%d/%m/%y')})"
    )



# Comando: saída
async def saida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome, quantidade, unidade, data_produto, tipo = parse_args(update, requiere_fecha=True)

    if not nome or not quantidade or not unidade or not data_produto:
        await update.message.reply_text(
            "❌ Use o formato: /saida [quantidade+unidade], [produto], [dd/mm]\nExemplo: /saida 3kg, cebola, 25/07")
        return

    produtos = obtener_productos(nome)
    estoque = 0
    for _, n, q, t, _, u in produtos:
        if n.lower() == nome.lower():
            if t == 'entrada':
                estoque += q
            elif t in ['saida', 'descarte', 'devolucao']:
                estoque -= q

    if estoque < quantidade:
        await update.message.reply_text(
            f"❌ Estoque insuficiente. {nome} disponível: {estoque} {unidade}. Tentativa de saída: {quantidade} {unidade}."
        )
        return

    insertar_producto(nome, quantidade, 'saida', data_produto, unidade)
    await update.message.reply_text(
        f"📤 Saída registrada: {quantidade}{unidade} de {nome} (data: {data_produto.strftime('%d/%m/%y')})"
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

    for _, nombre, cantidad, tipo, fecha_producto, _ in productos:
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

    # Diccionario: { (nome, fecha) : {"quantidade": X, "unidade": Y} }
    estoque_atual = {}

    for _, nome, quantidade, tipo, data, unidade in produtos:
        chave = (nome.lower(), data)  # Separa por nombre y fecha
        if chave not in estoque_atual:
            estoque_atual[chave] = {"quantidade": 0, "unidade": unidade}

        if tipo == 'entrada':
            estoque_atual[chave]["quantidade"] += quantidade
        elif tipo in ['saida', 'descarte', 'devolucao']:
            estoque_atual[chave]["quantidade"] -= quantidade

    # Construir mensaje
    mensagem = "📦 *Estoque Atual:*\n"
    for (nome, data), info in estoque_atual.items():
        if info["quantidade"] > 0:  # No mostrar si queda en cero
            mensagem += f"• {nome}: {info['quantidade']}{info['unidade']} ({data.strftime('%d/%m')})\n"

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




async def movimentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # 1. Obtener fecha del comando o usar hoy
        if context.args:
            try:
                fecha_str = context.args[0]
                fecha = datetime.strptime(fecha_str + "/2025", "%d/%m/%Y").date()
            except ValueError:
                await update.message.reply_text("❌ Formato inválido. Use: /movimentos [dd/mm]")
                return
        else:
            fecha = datetime.now().date()

        # 2. Obtener todos los movimientos
        productos = obtener_productos()

        # 3. Filtrar por fecha del movimiento (p[4] = fecha_producto)
        movimientos_dia = [p for p in productos if p[4] == fecha]

        # 4. Si no hay movimientos, avisar
        if not movimientos_dia:
            await update.message.reply_text(f"📅 Nenhum movimento registrado em {fecha.strftime('%d/%m')}.")
            return

        # 5. Construir mensaje
        mensaje = f"📅 *Movimentos de {fecha.strftime('%d/%m')}*\n"
        for _, nome, quantidade, tipo, fecha_producto, unidade in movimientos_dia:
            mensaje += f"• {nome} – {quantidade}{unidade} ({tipo}) – {fecha_producto.strftime('%d/%m')}\n"

        # 6. Enviar mensaje
        await update.message.reply_text(mensaje, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao buscar movimentos: {str(e)}")

