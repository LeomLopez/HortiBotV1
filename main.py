import re

from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config.config import BOT_TOKEN
from controllers.controller1 import entrada, saida, volta, estoque, vencimentos, devolucao, movimentacoes,estoque_congelados, buscar, descarte, estoque_secos, estoque_quimicos, estoque_descartaveis, descarte_vencidos, ajuste, mover
from controllers.navigation import (
    REPLY_CONGELADOS_SECTORS,
    REPLY_DIRECT_SECTORS,
    REPLY_HORTI_SECTORS,
    REPLY_SECTOR_ACTIONS_MENU,
    handle_flow_text,
    handle_reply_congelados_menu,
    handle_reply_horti_menu,
    handle_reply_main_menu,
    handle_reply_sector_action,
    show_main_menu,
    show_reply_main_menu,
    start_navigation,
)


# Define comandos visibles en el menú
BOT_COMMANDS = [
    BotCommand("start", "Iniciar o bot"),
    BotCommand("buscar", "Buscar produtos no estoque"),
    BotCommand("entrada", "Registrar uma entrada de produto"),
    BotCommand("saida", "Registrar uma saída de produto"),
    BotCommand("volta", "Registrar retorno de produção (soma no estoque)"),
    BotCommand("mover", "Corrigir grupo de um lote"),
    BotCommand("ajuste","Anular um lote registrado incorretamente"),
    BotCommand("descarte_vencidos", "Listar itens vencidos para descarte"),
    BotCommand("descarte", "Registrar um descarte"),
    BotCommand("devolucao", "Registrar devolução ao fornecedor (baixa no estoque)"),
    BotCommand("vencimentos", "Ver produtos vencidos"),
    BotCommand("estoque", "Ver resumo geral"),
    BotCommand("estoque_congelados", "Ver estoque de produtos congelados"),
    BotCommand("estoque_secos", "Ver estoque de produtos secos"),
    BotCommand("estoque_quimicos", "Ver estoque de produtos químicos"),
    BotCommand("estoque_descartaveis", "Ver estoque de produtos descartáveis"),
    BotCommand("movimentacoes", "Ver últimas movimentações"),
    BotCommand("menu", "Mostrar o menu principal"),
    BotCommand("menu_teclado", "Testar menu inferior"),
]

async def set_commands(application):
    await application.bot.set_my_commands(BOT_COMMANDS)


# Crear la app
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Handlers
application.add_handler(CommandHandler("start", start_navigation))
application.add_handler(CommandHandler("menu", show_main_menu))
application.add_handler(CommandHandler("menu_teclado", show_reply_main_menu))
application.add_handler(CommandHandler("buscar", buscar))
application.add_handler(CommandHandler("entrada", entrada))
application.add_handler(CommandHandler("saida", saida))
application.add_handler(CommandHandler("volta", volta))
application.add_handler(CommandHandler("mover", mover))
application.add_handler(CommandHandler("ajuste", ajuste))
application.add_handler(CommandHandler("descarte_vencidos", descarte_vencidos))
application.add_handler(CommandHandler("descarte", descarte))
application.add_handler(CommandHandler("devolucao", devolucao))
application.add_handler(CommandHandler("vencimentos", vencimentos))
application.add_handler(CommandHandler("estoque", estoque))
application.add_handler(CommandHandler("estoque_congelados", estoque_congelados))
application.add_handler(CommandHandler("estoque_secos", estoque_secos))
application.add_handler(CommandHandler("estoque_quimicos", estoque_quimicos))
application.add_handler(CommandHandler("estoque_descartaveis", estoque_descartaveis))



application.add_handler(CommandHandler("movimentacoes", movimentacoes))

# Handlers de teste para teclado inferior.
application.add_handler(MessageHandler(
    filters.TEXT & filters.Regex("^(✅ Confirmar|❌ Cancelar)$"),
    handle_reply_sector_action,
))
reply_actions = [button for row in REPLY_SECTOR_ACTIONS_MENU for button in row]
application.add_handler(MessageHandler(
    filters.TEXT & filters.Regex("^(" + "|".join(map(re.escape, reply_actions)) + ")$"),
    handle_reply_sector_action,
))
application.add_handler(MessageHandler(
    filters.TEXT & filters.Regex(
        "^(" + "|".join(map(re.escape, REPLY_DIRECT_SECTORS.keys())) + "|🥕 HortiFruti|❄️ Congelados|📋 Requisições)$"
    ),
    handle_reply_main_menu,
))
application.add_handler(MessageHandler(
    filters.TEXT & filters.Regex(
        "^(" + "|".join(map(re.escape, REPLY_HORTI_SECTORS.keys())) + "|⬅️ Voltar)$"
    ),
    handle_reply_horti_menu,
))
application.add_handler(MessageHandler(
    filters.TEXT & filters.Regex(
        "^(" + "|".join(map(re.escape, REPLY_CONGELADOS_SECTORS.keys())) + "|⬅️ Voltar)$"
    ),
    handle_reply_congelados_menu,
))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_flow_text))

# Llama a set_commands luego de iniciar
application.post_init = set_commands



application.run_polling()
