"""Application use cases for the existing chat service."""

from app.services.contracts.chat import (
    ChatRequest,
    ChatResult,
    ChatService,
    InvalidChatRequestError,
)


class ChatUseCase:
    def __init__(self, chat_service: ChatService) -> None:
        self._chat_service = chat_service

    def execute(self, request: ChatRequest) -> ChatResult:
        if not isinstance(request, ChatRequest):
            raise InvalidChatRequestError("A chat request is required.")
        if not isinstance(request.message, str) or not request.message.strip():
            raise InvalidChatRequestError("The user message must not be empty.")
        return ChatResult(self._chat_service.respond(request.message))

    def clear_conversation(self) -> None:
        self._chat_service.clear()

    @property
    def message_count(self) -> int:
        return self._chat_service.message_count
