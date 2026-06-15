import asyncio
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from services.llm_inventory_assistant import answer_hortifruti_question
from services.voice_transcription import transcribe_audio


MAX_TG = 3900


async def ai_hortifruti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args).strip() if context.args else ""

    if not question:
        await update.message.reply_text(
            "Pergunte algo sobre o inventário de Hortifruti.\n"
            "Exemplos:\n"
            "• `/ai quanto tenho de tomate?`\n"
            "• `/ai quais frutas tenho?`\n"
            "• `/ai o que vence nos próximos 2 dias?`",
            parse_mode="Markdown",
        )
        return

    try:
        answer = answer_hortifruti_question(question)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Erro ao consultar o assistente: {exc}")
        return

    await _send_long(update, answer, parse_mode="Markdown")


async def ai_hortifruti_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    voice_or_audio = message.voice or message.audio
    if not voice_or_audio:
        return

    await message.reply_text("🎙️ Transcrevendo áudio...")

    suffix = ".ogg" if message.voice else ".mp3"
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)

        telegram_file = await context.bot.get_file(voice_or_audio.file_id)
        await telegram_file.download_to_drive(custom_path=str(temp_path))

        question = await asyncio.to_thread(transcribe_audio, str(temp_path))
        if not question:
            await message.reply_text("Não consegui entender o áudio. Tente uma pergunta mais curta.")
            return

        await message.reply_text(f"Ouvi: {question}")
        answer = await asyncio.to_thread(answer_hortifruti_question, question)
        await _send_long(update, answer, parse_mode="Markdown")
    except Exception as exc:
        await message.reply_text(f"⚠️ Erro ao processar áudio: {exc}")
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


async def _send_long(update: Update, text: str, parse_mode=None):
    lines = (text or "").split("\n")
    chunk = ""

    for line in lines:
        if len(chunk) + len(line) + 1 > MAX_TG:
            await update.message.reply_text(chunk, parse_mode=parse_mode)
            chunk = line
        else:
            chunk = chunk + ("\n" if chunk else "") + line

    if chunk:
        await update.message.reply_text(chunk, parse_mode=parse_mode)
