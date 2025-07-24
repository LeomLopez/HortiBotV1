from telegram import Update, ReplyKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config.config import BOT_TOKEN
from controllers.controller1 import start, menu, entrada, saida, resumo, estoque,devolucao, vencimentos, movimentacoes
from models.db import crear_tablas_productos, insertar_producto, obtener_productos


# Define comandos visibles en el menú
BOT_COMMANDS = [
    BotCommand("entrada", "Registrar uma entrada de produto"),
    BotCommand("saida", "Registrar uma saída de produto"),
    BotCommand("devolucao", "Registrar uma devolução"),
    BotCommand("descarte", "Registrar um descarte"),
    BotCommand("vencimentos", "Ver produtos vencidos"),
    BotCommand("estoque", "Ver resumo geral"),
    BotCommand("movimentacoes", "Ver últimas movimentações"),
]

async def set_commands(application):
    await application.bot.set_my_commands(BOT_COMMANDS)


# Crear la app
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("menu", menu))
application.add_handler(CommandHandler("entrada", entrada))
application.add_handler(CommandHandler("saida", saida))
application.add_handler(CommandHandler("devolucao", devolucao))
application.add_handler(CommandHandler("vencimentos", vencimentos))
"""application.add_handler(CommandHandler("descarte", descarte))"""
application.add_handler(CommandHandler("estoque", estoque))
application.add_handler(CommandHandler("resumo", resumo))
application.add_handler(CommandHandler("movimentacoes", movimentacoes))

# Llama a set_commands luego de iniciar
application.post_init = set_commands



application.run_polling()
