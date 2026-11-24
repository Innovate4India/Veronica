"""End-to-end tests for opt-in Web Search through the normal CLI path."""

import json
import unittest
from collections.abc import Sequence
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import dev_ai
from app.ai.ollama_client import (
    OllamaAssistantResponse,
    OllamaChatMessage,
    OllamaToolCall,
    OllamaToolDefinition,
)
from app.config import (
    OllamaConfig,
    SpokenResponseConfig,
    WebSearchConfig,
)
from app.memory import MemoryService

_API_KEY = "integration-secret-key"
_SEARCH_QUERY = "What is the latest information about X?"


def _tavily_response() -> Mock:
    response = Mock()
    response.read.return_value = json.dumps(
        {
            "results": [
                {
                    "title": f"Source {index}",
                    "url": f"https://example.com/{index}",
                    "content": f"Verified snippet {index}",
                }
                for index in range(1, 4)
            ]
        }
    ).encode()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=None)
    return response


def _spoken_config(*, enabled: bool) -> SpokenResponseConfig:
    return SpokenResponseConfig(
        enabled=enabled,
        language="en",
        hindi_voice="hi-IN-SwaraNeural",
        english_voice="hi-IN-SwaraNeural",
        rate="-10%",
        pitch="+0Hz",
        volume="+0%",
    )


class WebSearchConversationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.memory_path = f"{self.temporary_directory.name}\\memories.db"
        self.ollama_config = OllamaConfig(
            "http://127.0.0.1:11434",
            "llama3.2",
            10,
        )
        self.web_config = WebSearchConfig(
            "tavily",
            _API_KEY,
            timeout_seconds=2,
        )

    def _base_patches(self, stack: ExitStack, *, enabled: bool) -> None:
        stack.enter_context(
            patch("dev_ai.load_ollama_config", return_value=self.ollama_config)
        )
        stack.enter_context(
            patch(
                "dev_ai.load_spoken_response_config",
                return_value=_spoken_config(enabled=True),
            )
        )
        stack.enter_context(
            patch("dev_ai.load_web_search_enabled", return_value=enabled)
        )
        stack.enter_context(
            patch(
                "dev_ai.load_file_search_roots",
                return_value=(Path(self.temporary_directory.name),),
            )
        )
        stack.enter_context(patch("dev_ai.MEMORY_DATABASE_PATH", self.memory_path))

    def test_search_round_trip_reaches_output_and_speaks_only_final_answer(self) -> None:
        client = Mock()
        client.list_models.return_value = ("llama3.2:latest",)
        responses = iter([
            OllamaAssistantResponse(
                '{"name":"web_search",""parameters":{"query":'
                '""latest major AI developments 2024"","max_results":10}}'
            ),
            OllamaAssistantResponse(
                "",
                (
                    OllamaToolCall(
                        "web_search",
                        {
                            "query": "latest major AI developments today",
                            "max_results": 3,
                        },
                    ),
                ),
            ),
            OllamaAssistantResponse("Here is the latest information from three sources."),
        ])
        observed_calls: list[
            tuple[list[OllamaChatMessage], list[OllamaToolDefinition]]
        ] = []

        def generate_tool_response(
            messages: Sequence[OllamaChatMessage],
            tools: Sequence[OllamaToolDefinition],
        ) -> OllamaAssistantResponse:
            observed_calls.append(
                (deepcopy(list(messages)), deepcopy(list(tools)))
            )
            return next(responses)

        client.generate_tool_response.side_effect = generate_tool_response
        tts = Mock()
        with ExitStack() as stack:
            self._base_patches(stack, enabled=True)
            stack.enter_context(
                patch("dev_ai.load_web_search_config", return_value=self.web_config)
            )
            stack.enter_context(patch("dev_ai.OllamaClient", return_value=client))
            stack.enter_context(patch("dev_ai.MicrosoftNeuralTTS", return_value=tts))
            stack.enter_context(
                patch("builtins.input", side_effect=[_SEARCH_QUERY, "/exit"])
            )
            tavily_request = stack.enter_context(
                patch(
                "app.tools.web_search.urlopen",
                return_value=_tavily_response(),
                )
            )
            output = StringIO()
            error_output = StringIO()
            stack.enter_context(redirect_stdout(output))
            stack.enter_context(redirect_stderr(error_output))
            registry_logs = stack.enter_context(
                self.assertLogs("app.tools.registry", level="INFO")
            )
            exit_code = dev_ai.main()

        transcript = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn(
            "Veronica: Here is the latest information from three sources.",
            transcript,
        )
        self.assertNotIn(_API_KEY, transcript + error_output.getvalue())
        self.assertNotIn(_API_KEY, "\n".join(registry_logs.output))
        tts.speak.assert_called_once_with(
            "Here is the latest information from three sources.",
            language="en",
        )

        self.assertEqual(client.generate_tool_response.call_count, 3)
        first_messages, definitions = observed_calls[0]
        first_content = first_messages[-1].get("content")
        if not isinstance(first_content, str):
            self.fail("Ollama user message must contain text.")
        self.assertEqual(first_content, _SEARCH_QUERY)
        system_content = first_messages[0].get("content")
        if not isinstance(system_content, str):
            self.fail("Ollama system message must contain text.")
        self.assertIn(date.today().isoformat(), system_content)
        self.assertEqual(
            {definition["function"]["name"] for definition in definitions},
            {"web_search"},
        )

        malformed_tool_result = observed_calls[1][0][-1].get("content")
        if not isinstance(malformed_tool_result, str):
            self.fail("Rejected content call must result in a tool error message.")
        malformed_result = json.loads(malformed_tool_result)
        self.assertEqual(
            malformed_result["status"],
            "validation_failure",
        )
        self.assertNotIn("2024", malformed_tool_result)

        search_messages = observed_calls[2][0]
        self.assertEqual(search_messages[-1].get("role"), "tool")
        tool_content = search_messages[-1].get("content")
        if not isinstance(tool_content, str):
            self.fail("Ollama tool result message must contain text.")
        tool_result = json.loads(tool_content)
        self.assertEqual(tool_result["status"], "success")
        self.assertEqual(len(tool_result["data"]["results"]), 3)
        self.assertNotIn(_API_KEY, json.dumps(search_messages))

        request = tavily_request.call_args.args[0]
        request_body = json.loads(request.data.decode())
        self.assertEqual(request_body["query"], "latest major AI developments today")
        self.assertEqual(
            set(request_body),
            {
                "query",
                "max_results",
                "search_depth",
                "include_answer",
                "include_raw_content",
                "include_images",
            },
        )
        self.assertEqual(
            request.get_header("Authorization"),
            "".join(("Be", "arer ", _API_KEY)),
        )

        memory_service = MemoryService(self.memory_path)
        self.assertEqual(memory_service.list_memories(), [])

    def test_enabled_tool_service_does_not_search_when_model_returns_normal_text(self) -> None:
        client = Mock()
        client.list_models.return_value = ("llama3.2:latest",)
        client.generate_response.return_value = (
            "This does not need current web information."
        )
        with (
            patch("dev_ai.load_ollama_config", return_value=self.ollama_config),
            patch("dev_ai.load_spoken_response_config", return_value=_spoken_config(enabled=False)),
            patch("dev_ai.load_web_search_enabled", return_value=True),
            patch("dev_ai.load_web_search_config", return_value=self.web_config),
            patch("dev_ai.MEMORY_DATABASE_PATH", self.memory_path),
            patch("dev_ai.OllamaClient", return_value=client),
            patch("dev_ai.MicrosoftNeuralTTS") as tts_factory,
            patch("builtins.input", side_effect=["What is Python?", "/exit"]),
            patch("app.tools.web_search.urlopen") as tavily_request,
            redirect_stdout(StringIO()) as output,
        ):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 0)
        self.assertIn(
            "Veronica: This does not need current web information.",
            output.getvalue(),
        )
        client.generate_tool_response.assert_not_called()
        client.generate_response.assert_called()
        tavily_request.assert_not_called()
        tts_factory.assert_not_called()

    def test_disabled_search_uses_unchanged_text_path_without_tools_or_network(self) -> None:
        client = Mock()
        client.list_models.return_value = ("llama3.2:latest",)
        client.generate_response.return_value = "An ordinary local answer."
        with ExitStack() as stack:
            self._base_patches(stack, enabled=False)
            search_config_loader = stack.enter_context(
                patch("dev_ai.load_web_search_config")
            )
            stack.enter_context(patch("dev_ai.OllamaClient", return_value=client))
            stack.enter_context(patch("dev_ai.MicrosoftNeuralTTS"))
            stack.enter_context(patch("builtins.input", side_effect=["Hello", "/exit"]))
            tavily_request = stack.enter_context(
                patch("app.tools.web_search.urlopen")
            )
            output = StringIO()
            stack.enter_context(redirect_stdout(output))
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 0)
        self.assertIn("Veronica: An ordinary local answer.", output.getvalue())
        self.assertEqual(client.generate_response.call_count, 1)
        client.generate_tool_response.assert_not_called()
        search_config_loader.assert_not_called()
        tavily_request.assert_not_called()

    def test_disabled_search_does_not_display_model_tool_call_json(self) -> None:
        client = Mock()
        client.list_models.return_value = ("llama3.2:latest",)
        malformed = (
            '{"name":"web_search",""parameters":{"query":'
            '""latest AI developments 2024"","max_results":10}}'
        )
        client.generate_response.return_value = malformed
        with ExitStack() as stack:
            self._base_patches(stack, enabled=False)
            search_config_loader = stack.enter_context(
                patch("dev_ai.load_web_search_config")
            )
            stack.enter_context(patch("dev_ai.OllamaClient", return_value=client))
            tts_factory = stack.enter_context(patch("dev_ai.MicrosoftNeuralTTS"))
            stack.enter_context(
                patch("builtins.input", side_effect=["latest AI", "/exit"])
            )
            tavily_request = stack.enter_context(
                patch("app.tools.web_search.urlopen")
            )
            output = StringIO()
            error_output = StringIO()
            stack.enter_context(redirect_stdout(output))
            stack.enter_context(redirect_stderr(error_output))
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 0)
        self.assertNotIn(malformed, output.getvalue() + error_output.getvalue())
        self.assertIn("Web Search is disabled", error_output.getvalue())
        client.generate_tool_response.assert_not_called()
        search_config_loader.assert_not_called()
        tavily_request.assert_not_called()
        tts_factory.return_value.speak.assert_not_called()

    def test_missing_key_is_returned_to_ollama_as_unavailable_not_fabricated(self) -> None:
        client = Mock()
        client.list_models.return_value = ("llama3.2:latest",)
        client.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                "",
                (OllamaToolCall("web_search", {"query": _SEARCH_QUERY}),),
            ),
            OllamaAssistantResponse(
                "I could not search the web because search is not configured."
            ),
        ]
        no_key_config = WebSearchConfig("tavily", "")
        with (
            patch("dev_ai.load_ollama_config", return_value=self.ollama_config),
            patch("dev_ai.load_spoken_response_config", return_value=_spoken_config(enabled=False)),
            patch("dev_ai.load_web_search_enabled", return_value=True),
            patch("dev_ai.load_web_search_config", return_value=no_key_config),
            patch("dev_ai.MEMORY_DATABASE_PATH", self.memory_path),
            patch("dev_ai.OllamaClient", return_value=client),
            patch("builtins.input", side_effect=[_SEARCH_QUERY, "/exit"]),
            patch("app.tools.web_search.urlopen") as tavily_request,
            redirect_stdout(StringIO()) as output,
        ):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 0)
        self.assertIn(
            "Veronica: I could not search the web because search is not configured.",
            output.getvalue(),
        )
        tool_messages = client.generate_tool_response.call_args_list[1].args[0]
        unavailable = json.loads(tool_messages[-1]["content"])
        self.assertEqual(unavailable["status"], "unavailable")
        self.assertNotIn("data", unavailable)
        tavily_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
