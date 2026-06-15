import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from config.config import FFMPEG_PATH, WHISPER_LANGUAGE, WHISPER_MODEL, WHISPER_TIMEOUT_SECONDS


def transcribe_audio(audio_path: str) -> str:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError("Archivo de audio no encontrado.")

    ffmpeg_path = _resolve_ffmpeg_path()
    if not ffmpeg_path:
        raise RuntimeError(
            "ffmpeg no está instalado o no está en el PATH. "
            "Whisper lo necesita para leer audios de Telegram. "
            "Si ya lo instalaste, configura FFMPEG_PATH en .env con la ruta completa a ffmpeg.exe."
        )

    _add_ffmpeg_to_path(ffmpeg_path)

    if importlib.util.find_spec("whisper"):
        return _transcribe_with_python_whisper(path)

    if shutil.which("whisper"):
        return _transcribe_with_cli(path)

    raise RuntimeError(
        "Whisper no está disponible. Instala openai-whisper en el .venv "
        "o deja disponible el comando local 'whisper'."
    )


def _resolve_ffmpeg_path() -> str | None:
    if FFMPEG_PATH:
        configured = Path(FFMPEG_PATH.strip('"'))
        if configured.exists():
            return str(configured)

    return shutil.which("ffmpeg")


def _add_ffmpeg_to_path(ffmpeg_path: str) -> None:
    ffmpeg_dir = str(Path(ffmpeg_path).parent)
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if ffmpeg_dir not in path_parts:
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def _transcribe_with_python_whisper(path: Path) -> str:
    import whisper

    model = whisper.load_model(WHISPER_MODEL)
    result = model.transcribe(str(path), language=WHISPER_LANGUAGE, fp16=False)
    return (result.get("text") or "").strip()


def _transcribe_with_cli(path: Path) -> str:
    with tempfile.TemporaryDirectory() as output_dir:
        command = [
            "whisper",
            str(path),
            "--model",
            WHISPER_MODEL,
            "--language",
            WHISPER_LANGUAGE,
            "--output_format",
            "txt",
            "--output_dir",
            output_dir,
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=WHISPER_TIMEOUT_SECONDS,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"Whisper falló: {detail}")

        transcript_path = Path(output_dir) / f"{path.stem}.txt"
        if not transcript_path.exists():
            raise RuntimeError("Whisper no generó transcripción.")

        return transcript_path.read_text(encoding="utf-8").strip()
