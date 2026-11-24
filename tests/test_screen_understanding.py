"""Offline tests for local-only screen understanding."""

import base64
import io
import json
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from app.ai import AIService, LocalVisionService, OllamaClient
from app.ai.ollama_client import (
    OllamaAssistantResponse,
    OllamaConnectionError,
    OllamaModelUnavailableError,
    OllamaResponseError,
    OllamaToolCall,
    OllamaTimeoutError,
)
from app.config import OllamaConfig
from app.config import WebSearchConfig
from app.tools import (
    JSONValue,
    ScreenUnderstandingTool,
    ToolRegistry,
    ToolResult,
    ToolStatus,
    WebSearchTool,
)
from app.ai.tool_calling import OllamaToolCallingService, ToolCallingServiceError


def _error_message(result: ToolResult) -> str:
    if result.error is None:
        raise AssertionError("Expected a structured tool error.")
    return result.error.message


def _result_data(result: ToolResult) -> dict[str, JSONValue]:
    if not isinstance(result.data, dict):
        raise AssertionError("Expected a JSON object in tool result.")
    return result.data


class ScreenUnderstandingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.image = SimpleNamespace(close=Mock(), size=(800, 600))
        self.client = Mock()
        self.client.list_models.return_value = ("vision-local:latest",)
        self.client.generate_vision_response.return_value = "A text editor is open."
        self.vision = LocalVisionService(self.client, "vision-local")
        self.tool = ScreenUnderstandingTool(self.vision)
        self.registry = ToolRegistry()
        self.registry.register(self.tool)
        self.capture = patch(
            "app.ai.vision.capture_primary_screen",
            return_value=self.image,
        )
        self.capture_mock = self.capture.start()
        self.addCleanup(self.capture.stop)

    def _execute(self, parameters: object):
        return self.registry.execute("screen_understanding", parameters)

    def test_valid_question_captures_once_uses_local_model_and_closes_image(self) -> None:
        result = self._execute({"question": "What application is open?"})

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(
            result.data,
            {
                "status": "success",
                "answer": "A text editor is open.",
                "message": "Answered using the configured local vision model.",
            },
        )
        self.client.list_models.assert_called_once_with()
        self.client.generate_vision_response.assert_called_once_with(
            "vision-local",
            "What application is open?",
            self.image,
        )
        self.image.close.assert_called_once_with()

    def test_missing_vision_model_returns_unavailable_without_capture(self) -> None:
        tool = ScreenUnderstandingTool(LocalVisionService(self.client, ""))
        registry = ToolRegistry()
        registry.register(tool)

        result = registry.execute(
            "screen_understanding",
            {"question": "What is visible?"},
        )

        self.assertEqual(result.status, ToolStatus.UNAVAILABLE)
        self.assertIn("OLLAMA_VISION_MODEL is not configured", _error_message(result))
        self.client.list_models.assert_not_called()
        self.capture_mock.assert_not_called()

    def test_empty_and_overlong_questions_are_rejected(self) -> None:
        for question in ("", "  ", "x" * 501):
            with self.subTest(question_length=len(question)):
                result = self._execute({"question": question})
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)
        self.client.list_models.assert_not_called()
        self.capture_mock.assert_not_called()
        self.assertFalse(self.image.close.called)

    def test_url_path_base64_and_arbitrary_overrides_are_rejected(self) -> None:
        invalid_parameters: tuple[object, ...] = (
            {"question": "https://example.com"},
            {"question": r"Read D:\private\screen.png"},
            {"question": "data:image/png;base64,AAAA"},
            {"question": "A" * 80},
            {"question": "powershell.exe -Command Get-Process"},
            {"question": "Run C:\\Windows\\System32\\cmd.exe"},
            {"question": "What is visible?", "model": "untrusted-model"},
            {"question": "What is visible?", "url": "http://127.0.0.1"},
            {"question": "What is visible?", "image": "AAAA"},
            {"question": "What is visible?", "path": r"C:\screen.png"},
            [],
        )
        for parameters in invalid_parameters:
            with self.subTest(parameters=parameters):
                result = self._execute(parameters)
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)
        self.client.list_models.assert_not_called()
        self.capture_mock.assert_not_called()
        self.assertFalse(self.image.close.called)

    def test_uninstalled_configured_model_is_unavailable_before_capture(self) -> None:
        self.client.list_models.return_value = ("llama3.2:latest",)

        result = self._execute({"question": "What is visible?"})

        self.assertEqual(result.status, ToolStatus.UNAVAILABLE)
        self.assertIn("not installed", _error_message(result))
        self.client.generate_vision_response.assert_not_called()
        self.capture_mock.assert_not_called()
        self.assertFalse(self.image.close.called)

    def test_ollama_unavailable_is_returned_without_capture(self) -> None:
        self.client.list_models.side_effect = OllamaConnectionError("private detail")

        result = self._execute({"question": "What is visible?"})

        self.assertEqual(result.status, ToolStatus.UNAVAILABLE)
        self.assertEqual(
            _error_message(result),
            "The local Ollama vision service is unavailable.",
        )
        self.assertNotIn("private detail", _error_message(result))
        self.capture_mock.assert_not_called()
        self.assertFalse(self.image.close.called)

    def test_ollama_unavailable_during_vision_call_closes_capture(self) -> None:
        self.client.generate_vision_response.side_effect = OllamaConnectionError(
            "private connection detail"
        )

        result = self._execute({"question": "What is visible?"})

        self.assertEqual(result.status, ToolStatus.UNAVAILABLE)
        self.assertEqual(
            _error_message(result),
            "The local Ollama vision service is unavailable.",
        )
        self.assertNotIn("private connection detail", _error_message(result))
        self.image.close.assert_called_once_with()

    def test_missing_model_during_generation_is_unavailable(self) -> None:
        self.client.generate_vision_response.side_effect = (
            OllamaModelUnavailableError("private model detail")
        )

        result = self._execute({"question": "What is visible?"})

        self.assertEqual(result.status, ToolStatus.UNAVAILABLE)
        self.assertEqual(
            _error_message(result),
            "The configured local vision model is unavailable.",
        )
        self.image.close.assert_called_once_with()

    def test_timeout_during_vision_request_has_timeout_status_and_closes_image(self) -> None:
        self.client.generate_vision_response.side_effect = OllamaTimeoutError(
            "private timeout detail"
        )

        result = self._execute({"question": "What is visible?"})

        self.assertEqual(result.status, ToolStatus.TIMEOUT)
        self.assertEqual(
            _error_message(result),
            "Tool execution exceeded its permitted time.",
        )
        self.image.close.assert_called_once_with()

    def test_capture_failure_is_structured_and_does_not_expose_exception(self) -> None:
        self.capture.stop()
        with patch(
            "app.ai.vision.capture_primary_screen",
            side_effect=PermissionError("private display detail"),
        ):
            result = self._execute({"question": "What is visible?"})

        self.assertEqual(result.status, ToolStatus.EXECUTION_FAILURE)
        self.assertNotIn("private display detail", _error_message(result))

    def test_empty_or_malformed_model_response_fails_safely(self) -> None:
        self.client.generate_vision_response.return_value = "  "
        result = self._execute({"question": "What is visible?"})
        self.assertEqual(result.status, ToolStatus.EXECUTION_FAILURE)
        self.assertEqual(_error_message(result), "Tool execution failed.")
        self.image.close.assert_called_once_with()

    def test_tool_result_and_logs_never_contain_image_bytes_or_answer(self) -> None:
        with self.assertLogs("app.tools.registry", level=logging.INFO) as captured:
            result = self._execute({"question": "What is visible?"})

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        data = _result_data(result)
        self.assertNotIn(self.image, data.values())
        self.assertFalse(any(isinstance(value, bytes) for value in data.values()))
        self.assertNotIn("A text editor is open.", "\n".join(captured.output))
        self.assertNotIn("base64", json.dumps(data).casefold())
        self.assertNotIn("image data", json.dumps(data).casefold())

    def test_ollama_client_sends_in_memory_png_only_to_loopback(self) -> None:
        image = Image.new("RGB", (2, 2), color="red")
        image_save = patch.object(image, "save", wraps=image.save)
        image_save_mock = image_save.start()
        self.addCleanup(image_save.stop)
        response = Mock()
        response.read.return_value = json.dumps(
            {
                "message": {
                    "role": "assistant",
                    "content": "A red image.",
                }
            }
        ).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        config = OllamaConfig("http://127.0.0.1:11434", "llama3.2", 9)

        with patch("app.ai.ollama_client.urlopen", return_value=response) as urlopen:
            answer = OllamaClient(config).generate_vision_response(
                "vision-local",
                "Describe it.",
                image,
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(answer, "A red image.")
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(payload["model"], "vision-local")
        self.assertEqual(payload["messages"][0]["content"], "Describe it.")
        png_bytes = base64.b64decode(payload["messages"][0]["images"][0])
        with Image.open(io.BytesIO(png_bytes)) as encoded_image:
            self.assertEqual(encoded_image.size, (2, 2))
            self.assertEqual(encoded_image.format, "PNG")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 9)
        image_save_mock.assert_called_once()
        self.assertIsInstance(image_save_mock.call_args.args[0], io.BytesIO)
        image.close()

    def test_ollama_missing_vision_model_is_classified_as_unavailable(self) -> None:
        client = OllamaClient(OllamaConfig("http://127.0.0.1", "text", 5))
        with patch.object(
            client,
            "_request_json",
            return_value={"error": "model 'vision-local' not found"},
        ):
            with self.assertRaises(OllamaModelUnavailableError):
                client.generate_vision_response(
                    "vision-local",
                    "Describe it.",
                    Image.new("RGB", (1, 1)),
                )

    def test_ollama_malformed_vision_response_is_rejected(self) -> None:
        client = OllamaClient(OllamaConfig("http://127.0.0.1", "text", 5))
        image = Image.new("RGB", (1, 1))
        try:
            with patch.object(client, "_request_json", return_value={"message": {}}):
                with self.assertRaises(OllamaResponseError):
                    client.generate_vision_response(
                        "vision-local",
                        "Describe it.",
                        image,
                    )
        finally:
            image.close()

    def test_ai_service_does_not_retain_screen_description_in_history(self) -> None:
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse("", (OllamaToolCall(
                "screen_understanding",
                {"question": "What is visible?"},
            ),)),
            OllamaAssistantResponse("A private document is visible."),
        ]
        tool_calling = OllamaToolCallingService(provider, self.registry)
        ai_service = AIService(
            Mock(),
            tool_calling_service=tool_calling,
        )
        with patch(
            "app.ai.vision.capture_primary_screen",
            return_value=self.image,
        ):
            answer = ai_service.respond("What is visible on my screen?")

        self.assertEqual(answer, "A private document is visible.")
        history_text = "\n".join(message["content"] for message in ai_service.messages)
        self.assertNotIn("A private document is visible.", history_text)
        self.assertIn("omitted from conversation history", history_text)
        second_turn_messages = provider.generate_tool_response.call_args_list[1].args[0]
        self.assertNotIn("images", json.dumps(second_turn_messages))
        self.assertNotIn("base64", json.dumps(second_turn_messages).casefold())
        self.image.close.assert_called_once_with()

    def test_screen_results_cannot_trigger_external_followup_tools(self) -> None:
        search_provider = Mock()
        registry = ToolRegistry()
        registry.register(self.tool)
        registry.register(
            WebSearchTool(
                provider=search_provider,
                config=WebSearchConfig("tavily", "test-key"),
            )
        )
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                "",
                (
                    OllamaToolCall(
                        "screen_understanding",
                        {"question": "Read the visible title."},
                    ),
                    OllamaToolCall(
                        "web_search",
                        {"query": "private screen contents"},
                    ),
                ),
            ),
            OllamaAssistantResponse("I described the screen locally."),
        ]

        response = OllamaToolCallingService(provider, registry).respond(
            [{"role": "user", "content": "Read what is visible on screen."}]
        )

        self.assertEqual(response, "I described the screen locally.")
        search_provider.search.assert_not_called()
        self.assertEqual(
            provider.generate_tool_response.call_args_list[1].args[1],
            (),
        )

    def test_model_tool_call_after_screen_without_tools_is_not_executed(self) -> None:
        search_provider = Mock()
        registry = ToolRegistry()
        registry.register(self.tool)
        registry.register(
            WebSearchTool(
                provider=search_provider,
                config=WebSearchConfig("tavily", "test-key"),
            )
        )
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                "",
                (OllamaToolCall("screen_understanding", {"question": "Describe it."}),),
            ),
            OllamaAssistantResponse(
                "",
                (OllamaToolCall("web_search", {"query": "screen contents"}),),
            ),
        ]

        with self.assertRaises(ToolCallingServiceError):
            OllamaToolCallingService(provider, registry).respond(
                [{"role": "user", "content": "Describe my screen."}]
            )

        search_provider.search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
