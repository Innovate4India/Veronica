"""Composition helpers for transport-neutral application operations."""

from app.services.adapters.ai_service import AIServiceAdapter
from app.services.contracts.chat import ChatService
from app.services.use_cases.chat import ChatUseCase


def compose_chat_use_case(service: ChatService) -> ChatUseCase:
    return ChatUseCase(AIServiceAdapter(service))
