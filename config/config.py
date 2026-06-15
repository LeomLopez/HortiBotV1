import os
from dotenv import load_dotenv

load_dotenv()  # Carga el archivo .env

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "phi")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "pt")
WHISPER_TIMEOUT_SECONDS = int(os.getenv("WHISPER_TIMEOUT_SECONDS", "300"))
FFMPEG_PATH = os.getenv("FFMPEG_PATH")


if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL no está definida en el archivo .env")
