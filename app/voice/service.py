"""Orchestrate one explicit speech request through Veronica's AI service."""

from app.ai.service import AIService
from app.voice.base import SpeechToTextProvider, TextToSpeechProvider


class VoiceService:
    """Connect STT to conversational AI and speak its response locally."""

    def __init__(
        self,
        speech_to_text: SpeechToTextProvider,
        ai_service: AIService,
        text_to_speech: TextToSpeechProvider,
    ) -> None:
        self._speech_to_text = speech_to_text
        self._ai_service = ai_service
        self._text_to_speech = text_to_speech

    def interact(self) -> str:
        """Listen once, get a conversational response, and speak it locally."""
        user_text = self._speech_to_text.listen()
        response = self._ai_service.respond(user_text)
        self._text_to_speech.speak(response)
        return response
