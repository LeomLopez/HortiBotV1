from telegram import Update, ReplyKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config.config import BOT_TOKEN
from controllers.controller1 import start, menu, entrada, saida, estoque, vencimentos, movimentacoes,estoque_congelados, buscar, descarte, estoque_secos, estoque_quimicos, estoque_descartaveis, descarte_vencidos, ajuste
from models.db import crear_tablas_productos, insertar_producto, obtener_productos


# Define comandos visibles en el menú
BOT_COMMANDS = [
    BotCommand("start", "Iniciar o bot"),
    BotCommand("menu", "Mostrar o menu principal"),
    BotCommand("buscar", "Buscar produtos no estoque"),
    BotCommand("entrada", "Registrar uma entrada de produto"),
    BotCommand("saida", "Registrar uma saída de produto"),
    BotCommand("ajuste","Anular um lote registrado incorretamente"),
    BotCommand("descarte", "Registrar um descarte"),
    BotCommand("descarte_vencidos", "Listar itens vencidos para descarte"),
    BotCommand("vencimentos", "Ver produtos vencidos"),
    BotCommand("estoque", "Ver resumo geral"),
    BotCommand("estoque_congelados", "Ver estoque de produtos congelados"),
    BotCommand("estoque_secos", "Ver estoque de produtos secos"),
    BotCommand("estoque_quimicos", "Ver estoque de produtos químicos"),
    BotCommand("estoque_descartaveis", "Ver estoque de produtos descartáveis"),
    BotCommand("movimentacoes", "Ver últimas movimentações"),
]

async def set_commands(application):
    await application.bot.set_my_commands(BOT_COMMANDS)


# Crear la app
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("menu", menu))
application.add_handler(CommandHandler("buscar", buscar))
application.add_handler(CommandHandler("entrada", entrada))
application.add_handler(CommandHandler("saida", saida))
application.add_handler(CommandHandler("ajuste", ajuste))
application.add_handler(CommandHandler("descarte", descarte))
application.add_handler(CommandHandler("descarte_vencidos", descarte_vencidos))
application.add_handler(CommandHandler("vencimentos", vencimentos))
application.add_handler(CommandHandler("estoque", estoque))
application.add_handler(CommandHandler("estoque_congelados", estoque_congelados))
application.add_handler(CommandHandler("estoque_secos", estoque_secos))
application.add_handler(CommandHandler("estoque_quimicos", estoque_quimicos))
application.add_handler(CommandHandler("estoque_descartaveis", estoque_descartaveis))



application.add_handler(CommandHandler("movimentacoes", movimentacoes))

# Llama a set_commands luego de iniciar
application.post_init = set_commands



application.run_polling()
