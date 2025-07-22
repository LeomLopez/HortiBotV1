import os
from dotenv import load_dotenv

load_dotenv()  # Carga el archivo .env

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL no está definida en el archivo .env")