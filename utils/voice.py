import io
import os

from groq import Groq


def _client() -> Groq:
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """Transcribe audio bytes using Groq Whisper. Accepts any Whisper-supported mime type."""
    ext = mime_type.split("/")[-1].split(";")[0]  # "webm", "ogg", "wav", etc.
    result = _client().audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        file=(f"audio.{ext}", io.BytesIO(audio_bytes), mime_type),
        response_format="text",
    )
    return (result or "").strip()


def text_to_speech(text: str, voice: str = "Fritz-PlayAI") -> bytes:
    """Convert text to speech using Groq PlayAI TTS. Returns MP3 bytes."""
    response = _client().audio.speech.create(
        model="playai-tts",
        voice=voice,
        input=text[:900],
        response_format="mp3",
    )
    return response.read()
