"""Adapter exposing the existing AI service through application contracts."""

from app.services.contracts.chat import ChatService


class AIServiceAdapter:
    def __init__(self, service: ChatService) -> None:
        self._service = service

    def respond(self, user_message: str) -> str:
        return self._service.respond(user_message)

    def clear(self) -> None:
        self._service.clear()

    @property
    def message_count(self) -> int:
        return self._service.message_count
