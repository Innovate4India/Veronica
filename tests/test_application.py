"""Tests for Veronica's shared application layer."""

import unittest
from unittest.mock import Mock

from app.services.composition import compose_chat_use_case
from app.services.contracts.chat import (
    ChatRequest,
    ChatResult,
    InvalidChatRequestError,
)
from app.services.use_cases.chat import ChatUseCase


class FakeChatService:
    def __init__(self) -> None:
        self.message_count = 1

    def respond(self, _user_message: str) -> str:
        self.message_count += 2
        return "Response."

    def clear(self) -> None:
        self.message_count = 1


class ChatUseCaseTests(unittest.TestCase):
    def test_execute_delegates_and_returns_chat_result(self) -> None:
        chat_service = Mock()
        chat_service.respond.return_value = "Hello!"
        use_case = ChatUseCase(chat_service)

        result = use_case.execute(ChatRequest("Hi"))

        self.assertEqual(result, ChatResult("Hello!"))
        chat_service.respond.assert_called_once_with("Hi")

    def test_execute_rejects_empty_message_without_calling_service(self) -> None:
        chat_service = Mock()
        use_case = ChatUseCase(chat_service)

        with self.assertRaises(InvalidChatRequestError):
            use_case.execute(ChatRequest("  "))

        chat_service.respond.assert_not_called()

    def test_conversation_operations_delegate(self) -> None:
        chat_service = Mock()
        chat_service.message_count = 3
        use_case = ChatUseCase(chat_service)

        self.assertEqual(use_case.message_count, 3)
        use_case.clear_conversation()

        chat_service.clear.assert_called_once_with()

    def test_service_errors_are_not_rewritten(self) -> None:
        service_error = RuntimeError("Service unavailable.")
        service = Mock()
        service.respond.side_effect = service_error
        use_case = compose_chat_use_case(service)

        with self.assertRaises(RuntimeError) as raised:
            use_case.execute(ChatRequest("Hi"))

        self.assertIs(raised.exception, service_error)

    def test_composed_chat_instances_do_not_share_history(self) -> None:
        first_service = FakeChatService()
        second_service = FakeChatService()
        first = compose_chat_use_case(first_service)
        second = compose_chat_use_case(second_service)

        first.execute(ChatRequest("First request"))

        self.assertEqual(first.message_count, 3)
        self.assertEqual(second.message_count, 1)


if __name__ == "__main__":
    unittest.main()
