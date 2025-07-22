from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from views.menu import get_menu_text as v_menu
from models.db import obtener_productos, insertar_producto
from datetime import datetime


# Menú del teclado personalizado
keyboard = [
    ["📥 /entrada", "📤 /saida"],
    ["♻️ /devolucao", "🗑️ /descarte"],
    ["📦 /estoque", "📝 /resumo"]
]
menu_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Mensaje de bienvenida
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Eu sou o Bot de Estoque. Use /menu para ver as opções disponíveis.",
        reply_markup=menu_markup
    )

# Mostrar menú
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(v_menu(), parse_mode="Markdown", reply_markup=menu_markup)

# Parsear la entrada del usuario

def parse_args(update: Update, requiere_fecha=False):
    try:
        partes = update.message.text.split(' ', 1)[1].split(',')
        if requiere_fecha:
            if len(partes) < 3:
                return None, None, None, None
            cantidad = int(partes[0].strip())
            nombre = partes[1].strip()
            fecha_producto = datetime.strptime(partes[2].strip() + "/2025", "%d/%m/%Y").date()
            return nombre, cantidad, fecha_producto, 'entrada'
        else:
            if len(partes) < 2:
                return None, None
            nombre = partes[0].strip()
            cantidad = int(partes[1].strip())
            return nombre, cantidad
    except Exception:
        return (None,) * (4 if requiere_fecha else 2)



# Comando: entrada
async def entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad, fecha_producto, tipo = parse_args(update, requiere_fecha=True)
    if not nombre or not cantidad or not fecha_producto:
        await update.message.reply_text("❌ Usa el formato: /entrada, [cantidad], [producto], [dd/mm]")
        return
    insertar_producto(nombre, cantidad, 'entrada', fecha_producto)
    await update.message.reply_text(f"📥 Entrada registrada: {cantidad}kg de {nombre} (fecha: {fecha_producto.strftime('%d/%m')})")


# Comando: saída
async def saida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad, fecha = parse_args(update)
    if not nombre or not cantidad or not fecha:
        await update.message.reply_text("❌ Usa el formato: /saida [producto] [cantidad]")
        return
    insertar_producto(nombre, cantidad, "salida")
    await update.message.reply_text(f"📤 Saída registrada: {cantidad} de {nombre}")

# Comando: devolucao
async def devolucao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad = parse_args(update)
    if not nombre or not cantidad:
        await update.message.reply_text("❌ Usa el formato: /devolucao [producto] [cantidad]")
        return
    insertar_producto(nombre, cantidad, "devolucao")
    await update.message.reply_text(f"♻️ Devolução registrada: {cantidad} de {nombre}")

# Comando: descarte
async def descarte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre, cantidad = parse_args(update)
    if not nombre or not cantidad:
        await update.message.reply_text("❌ Usa el formato: /descarte [producto] [cantidad]")
        return
    insertar_producto(nombre, cantidad, "descarte")
    await update.message.reply_text(f"🗑️ Descarte registrado: {cantidad} de {nombre}")

# Comando: resumo por producto y tipo
async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    productos = obtener_productos()
    if not productos:
        await update.message.reply_text("📊 No hay datos para resumir.")
        return

    resumen = {}
    for _, nombre, cantidad, tipo, _ in productos:
        clave = (nombre, tipo)
        resumen[clave] = resumen.get(clave, 0) + cantidad

    mensaje = "📊 Resumen por tipo de movimiento:\n"
    for (nombre, tipo), total in resumen.items():
        mensaje += f"• {nombre} ({tipo}): {total} kg\n"

    await update.message.reply_text(mensaje)

# Comando: debug → muestra los últimos registros sin filtrar
async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    productos = obtener_productos()
    if not productos:
        await update.message.reply_text("⚠️ No hay ningún registro en la base de datos.")
        return

    mensaje = "🧪 Últimos registros:\n"
    for p in productos[:5]:
        mensaje += f"• {p[1]} | {p[2]} unid | {p[3]} | {p[4].strftime('%Y-%m-%d %H:%M')}\n"

    await update.message.reply_text(mensaje)
