"""Tests for Veronica's interactive developer chat interface."""

import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import dev_ai
from app.ai import (
    AIProvider,
    AIService,
    AssistantResponse,
    OllamaClient,
    OllamaConnectionError,
    ProviderCapabilities,
    ProviderCapabilityError,
    ProviderConfigurationError,
    ProviderModelUnavailableError,
    ProviderMetadata,
    ProviderResponseError,
    ProviderTimeoutError,
    VisionRequest,
    VisionProvider,
    VisionResponse,
)
from app.ai.base import ProviderError
from app.config import OllamaConfig, SpokenResponseConfig, WebSearchConfig
from app.memory import MemoryService
from app.services.composition import compose_chat_use_case
from app.tools import ToolRegistry
from app.voice import VoiceModelUnavailableError


def _assistant_role() -> str:
    return json.dumps(
        {
            "role": "assistant",
            "subject": None,
            "topic": None,
            "level": None,
            "quiz_mode": False,
            "answer_attempt": False,
            "answer_correct": None,
            "request_hint": False,
        }
    )


class DeveloperChatCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = Mock(spec=AIProvider)
        self.provider.generate_response.return_value = "Hello!"
        self.service = AIService(self.provider)
        self.service.respond("Hello")
        self.chat_use_case = compose_chat_use_case(self.service)
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.memory_service = MemoryService(
            f"{self.temporary_directory.name}\\memories.db"
        )
        self.state = dev_ai._CommandState()

    def test_clear_command_resets_history(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            should_exit = dev_ai._handle_command(
                "/clear", self.chat_use_case, self.memory_service, self.state
            )

        self.assertFalse(should_exit)
        self.assertEqual(self.service.message_count, 1)
        self.assertIn("Conversation cleared.", output.getvalue())

    def test_history_command_shows_current_message_count(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            dev_ai._handle_command(
                "/history", self.chat_use_case, self.memory_service, self.state
            )

        self.assertIn("Conversation messages: 3", output.getvalue())

    def test_help_command_shows_all_commands(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            dev_ai._handle_command(
                "/help", self.chat_use_case, self.memory_service, self.state
            )

        for command in (
            "/exit",
            "/clear",
            "/history",
            "/remember",
            "/memory",
            "/forget",
            "/memory-search",
            "/clear-memory",
            "/help",
        ):
            with self.subTest(command=command):
                self.assertIn(command, output.getvalue())

    def test_exit_command_requests_session_exit(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            should_exit = dev_ai._handle_command(
                "/exit", self.chat_use_case, self.memory_service, self.state
            )

        self.assertTrue(should_exit)
        self.assertIn("Goodbye.", output.getvalue())

    def test_memory_commands_save_list_search_and_delete(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            dev_ai._handle_command(
                "/remember My main project is Veronica.",
                self.chat_use_case,
                self.memory_service,
                self.state,
            )
            dev_ai._handle_command(
                "/memory", self.chat_use_case, self.memory_service, self.state
            )
            dev_ai._handle_command(
                "/memory-search Veronica",
                self.chat_use_case,
                self.memory_service,
                self.state,
            )
            dev_ai._handle_command(
                "/forget 1", self.chat_use_case, self.memory_service, self.state
            )
            dev_ai._handle_command(
                "/memory", self.chat_use_case, self.memory_service, self.state
            )

        transcript = output.getvalue()
        self.assertIn("Saved local memory [1].", transcript)
        self.assertIn("My main project is Veronica.", transcript)
        self.assertIn("Deleted local memory [1].", transcript)
        self.assertIn("No matching memories found.", transcript)

    def test_clear_memory_requires_yes_confirmation(self) -> None:
        self.memory_service.save_memory("My main project is Veronica.")
        output = StringIO()

        with redirect_stdout(output):
            dev_ai._handle_command(
                "/clear-memory",
                self.chat_use_case,
                self.memory_service,
                self.state,
            )
            self.assertTrue(self.state.pending_memory_clear)
            dev_ai._confirm_memory_clear(
                "no", self.memory_service, self.state
            )

        self.assertEqual(len(self.memory_service.list_memories()), 1)
        self.assertIn("Type YES", output.getvalue())
        self.assertIn("cancelled", output.getvalue().lower())

    def test_clear_memory_deletes_only_after_yes_confirmation(self) -> None:
        self.memory_service.save_memory("My main project is Veronica.")
        state = dev_ai._CommandState()
        output = StringIO()
        with redirect_stdout(output):
            dev_ai._confirm_memory_clear("YES", self.memory_service, state)

        self.assertEqual(self.memory_service.list_memories(), [])
        self.assertIn("Deleted 1 local memory.", output.getvalue())


class DeveloperChatStartupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.memory_path_patch = patch(
            "dev_ai.MEMORY_DATABASE_PATH",
            f"{self.temporary_directory.name}\\memories.db",
        )
        self.memory_path_patch.start()
        self.addCleanup(self.memory_path_patch.stop)
        self.web_search_enabled_patch = patch(
            "dev_ai.load_web_search_enabled",
            return_value=False,
        )
        self.web_search_enabled_patch.start()
        self.addCleanup(self.web_search_enabled_patch.stop)

    @patch("dev_ai._create_provider")
    def test_unavailable_ollama_is_reported_without_traceback(
        self,
        provider_factory: Mock,
    ) -> None:
        provider = provider_factory.return_value
        provider.validate_startup.side_effect = (
            OllamaConnectionError("offline")
        )
        output = StringIO()

        with redirect_stdout(output):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 1)
        self.assertIn(dev_ai.AI_PROVIDER_UNAVAILABLE_MESSAGE, output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    @patch("dev_ai._create_provider")
    def test_base_provider_error_is_reported_without_traceback_or_details(
        self,
        provider_factory: Mock,
    ) -> None:
        provider_factory.return_value.validate_startup.side_effect = (
            ProviderError("private provider detail")
        )
        output = StringIO()

        with redirect_stdout(output):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 1)
        self.assertIn(
            "The configured AI provider could not be started.",
            output.getvalue(),
        )
        self.assertNotIn("private provider detail", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_typed_provider_startup_errors_are_stable_and_sanitized(self) -> None:
        error_cases = (
            (
                ProviderConfigurationError,
                "The configured AI provider has invalid configuration.",
                2,
            ),
            (
                ProviderCapabilityError,
                "The configured AI provider does not support a required capability.",
                2,
            ),
            (
                ProviderModelUnavailableError,
                "The configured AI provider model is unavailable.",
                2,
            ),
            (
                ProviderTimeoutError,
                dev_ai.AI_PROVIDER_UNAVAILABLE_MESSAGE,
                1,
            ),
            (
                ProviderResponseError,
                "The AI provider returned an invalid response.",
                1,
            ),
        )
        for error_type, expected_message, expected_exit_code in error_cases:
            with self.subTest(error_type=error_type.__name__):
                provider = Mock(spec=AIProvider)
                provider.validate_startup.side_effect = error_type(
                    "private startup detail"
                )
                output = StringIO()

                with (
                    patch("dev_ai._create_provider", return_value=provider),
                    redirect_stdout(output),
                ):
                    exit_code = dev_ai.main()

                self.assertEqual(exit_code, expected_exit_code)
                self.assertEqual(output.getvalue(), expected_message + "\n")
                self.assertNotIn("private startup detail", output.getvalue())
                self.assertNotIn("Traceback", output.getvalue())

    @patch("builtins.input", side_effect=["Hello", "/exit"])
    @patch("dev_ai._create_provider")
    def test_unavailable_ollama_during_chat_is_reported(
        self,
        provider_factory: Mock,
        _input: Mock,
    ) -> None:
        provider = provider_factory.return_value
        provider.validate_startup.return_value = None
        provider.generate_response.side_effect = OllamaConnectionError("offline")
        output = StringIO()
        error_output = StringIO()

        with redirect_stdout(output), redirect_stderr(error_output):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 0)
        self.assertIn(
            dev_ai.AI_PROVIDER_UNAVAILABLE_MESSAGE,
            error_output.getvalue(),
        )
        self.assertNotIn("Traceback", error_output.getvalue())
        _input.assert_called()

    @patch(
        "builtins.input",
        side_effect=[
            "/help",
            "Remember that my favorite language is Python.",
            "Hello",
            "/exit",
        ],
    )
    @patch("dev_ai.load_spoken_response_config")
    @patch("dev_ai.MicrosoftNeuralTTS")
    @patch("dev_ai._create_provider")
    def test_enabled_spoken_response_uses_selected_language_and_is_nonfatal(
        self,
        provider_factory: Mock,
        tts_class: Mock,
        load_spoken: Mock,
        _input: Mock,
    ) -> None:
        speech_config = SpokenResponseConfig(
            enabled=True,
            language="hi",
            hindi_voice="hi-IN-SwaraNeural",
            english_voice="hi-IN-SwaraNeural",
            rate="-10%",
            pitch="+0Hz",
            volume="+0%",
        )
        load_spoken.return_value = speech_config
        provider = provider_factory.return_value
        provider.validate_startup.return_value = None
        provider.generate_response.return_value = "नमस्ते"
        tts = tts_class.return_value
        tts.speak.side_effect = VoiceModelUnavailableError("online service unavailable")
        output = StringIO()
        error_output = StringIO()

        with redirect_stdout(output), redirect_stderr(error_output):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 0)
        tts_class.assert_called_once_with(speech_config)
        tts.speak.assert_called_once_with("नमस्ते", language="hi")
        self.assertIn("Veronica: नमस्ते", output.getvalue())
        self.assertIn("I’ll remember this locally", output.getvalue())
        self.assertIn(
            "Spoken response unavailable: online service unavailable",
            error_output.getvalue(),
        )
        self.assertEqual(_input.call_count, 4)

    @patch("builtins.input", side_effect=["Hello", "/exit"])
    @patch("dev_ai.load_spoken_response_config")
    @patch("dev_ai.MicrosoftNeuralTTS")
    @patch("dev_ai._create_provider")
    def test_disabled_spoken_responses_never_construct_piper(
        self,
        provider_factory: Mock,
        tts_class: Mock,
        load_spoken: Mock,
        _input: Mock,
    ) -> None:
        load_spoken.return_value = SpokenResponseConfig(
            enabled=False,
            language="en",
            hindi_voice="hi-IN-SwaraNeural",
            english_voice="hi-IN-SwaraNeural",
            rate="-10%",
            pitch="+0Hz",
            volume="+0%",
        )
        provider = provider_factory.return_value
        provider.validate_startup.return_value = None
        provider.generate_response.return_value = "Hello there."

        with redirect_stdout(StringIO()):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 0)
        tts_class.assert_not_called()
        provider_factory.assert_called_once_with()
        provider.validate_startup.assert_called_once_with()
        self.assertFalse(hasattr(dev_ai, "OllamaClient"))
        _input.assert_called()

    def test_provider_without_tool_support_fails_startup_clearly(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.validate_startup.return_value = None
        output = StringIO()
        with (
            patch("dev_ai._create_provider", return_value=provider),
            patch("dev_ai.load_web_search_enabled", return_value=True),
            patch("dev_ai.load_web_search_config", return_value=object()),
            patch("dev_ai.load_file_search_roots", return_value=()),
            patch("dev_ai._create_tool_registry", return_value=ToolRegistry()),
            redirect_stdout(output),
        ):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            output.getvalue(),
            "Configured AI provider cannot support enabled tools.\n",
        )
        self.assertNotIn("Traceback", output.getvalue())

    def test_tool_setup_capability_error_does_not_expose_details(self) -> None:
        private_detail = (
            "api_key=private-test-secret; internal endpoint=service.local"
        )
        output = StringIO()
        with (
            patch("dev_ai._create_provider", return_value=Mock(spec=AIProvider)),
            patch("dev_ai.load_web_search_enabled", return_value=True),
            patch("dev_ai.load_web_search_config", return_value=object()),
            patch("dev_ai.load_file_search_roots", return_value=()),
            patch(
                "dev_ai._create_tool_registry",
                side_effect=ProviderCapabilityError(private_detail),
            ),
            redirect_stdout(output),
        ):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            output.getvalue(),
            "Configured AI provider cannot support enabled tools.\n",
        )
        self.assertNotIn(private_detail, output.getvalue())
        self.assertNotIn("private-test-secret", output.getvalue())
        self.assertNotIn("service.local", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_tool_definitions_follow_provider_vision_capability(self) -> None:
        class FakeVisionAdapter:
            model_configured = True

            def model_available(self) -> bool:
                return True

            def generate_vision(self, request: VisionRequest) -> VisionResponse:
                return VisionResponse("A test screen.")

        class FakeToolProvider(AIProvider):
            def __init__(
                self,
                vision_enabled: bool,
                adapter_available: bool,
            ) -> None:
                self._vision_enabled = vision_enabled
                self._adapter_available = adapter_available
                self.vision_factory_calls = 0
                self.available_tools: tuple[str, ...] = ()
                self.available_tool_descriptions: dict[str, str] = {}

            @property
            def metadata(self) -> ProviderMetadata:
                return ProviderMetadata(
                    name="fake",
                    kind="test",
                    model="",
                    capabilities=ProviderCapabilities(
                        text=True,
                        tools=True,
                        vision=self._vision_enabled,
                    ),
                )

            def generate_response(self, messages) -> str:
                return "Ready."

            def create_vision_provider(self) -> VisionProvider | None:
                self.vision_factory_calls += 1
                return (
                    FakeVisionAdapter()
                    if self._adapter_available
                    else None
                )

            def generate_provider_tool_response(self, messages, tools):
                self.available_tools = tuple(tool["name"] for tool in tools)
                self.available_tool_descriptions = {
                    tool["name"]: tool["description"]
                    for tool in tools
                }
                return AssistantResponse("Ready.")

        config = WebSearchConfig(provider="tavily", api_key="test-key")
        provider_cases = ((False, True), (True, False), (True, True))
        for vision_enabled, adapter_available in provider_cases:
            with self.subTest(
                vision_enabled=vision_enabled,
                adapter_available=adapter_available,
            ):
                provider = FakeToolProvider(
                    vision_enabled,
                    adapter_available,
                )
                registry = dev_ai._create_tool_registry(
                    config,
                    (Path(self.temporary_directory.name),),
                    provider,
                )
                response = dev_ai.ToolCallingService(
                    provider,
                    registry,
                ).respond([{"role": "user", "content": "Hello"}])

                self.assertEqual(response, "Ready.")
                self.assertEqual(
                    "screen_understanding" in provider.available_tools,
                    vision_enabled and adapter_available,
                )
                self.assertIn("screenshot", provider.available_tools)
                screenshot_description = provider.available_tool_descriptions[
                    "screenshot"
                ]
                if vision_enabled and adapter_available:
                    self.assertIn(
                        "screen_understanding",
                        provider.available_tools,
                    )
                else:
                    self.assertNotIn(
                        "screen_understanding",
                        provider.available_tools,
                    )
                    self.assertIn(
                        "If it is unavailable, tell the user",
                        screenshot_description,
                    )
                self.assertEqual(
                    provider.vision_factory_calls,
                    int(vision_enabled),
                )

        ollama_provider = OllamaClient(
            OllamaConfig("http://127.0.0.1:11434", "llama3.2", 5)
        )
        with patch.object(
            ollama_provider,
            "create_vision_provider",
            return_value=FakeVisionAdapter(),
        ):
            registry = dev_ai._create_tool_registry(
                config,
                (Path(self.temporary_directory.name),),
                ollama_provider,
            )
        self.assertIn(
            "screen_understanding",
            {tool.name for tool in registry.list_tools()},
        )

    @patch("builtins.input", side_effect=[
        "Hello Veronica",
        "My name is Hardik.",
        "What is my name?",
        "/history",
        "/clear",
        "/history",
        "/help",
        "Veronica mujhe Python simple language mein samjha do.",
        "/exit",
    ])
    @patch("dev_ai._create_provider")
    def test_interactive_conversation_and_commands(
        self,
        provider_factory: Mock,
        _input: Mock,
    ) -> None:
        provider = provider_factory.return_value
        provider.validate_startup.return_value = None
        provider.generate_response.side_effect = [
            "Hello!",
            _assistant_role(),
            "Nice to meet you, Hardik.",
            _assistant_role(),
            "Your name is Hardik.",
            json.dumps(
                {
                    "role": "teacher",
                    "subject": "coding",
                    "topic": "Python",
                    "level": "beginner",
                }
            ),
            "Python ek programming language hai.",
        ]
        output = StringIO()

        with redirect_stdout(output):
            exit_code = dev_ai.main()

        transcript = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("VERONICA AI", transcript)
        self.assertIn("Veronica: Hello!", transcript)
        self.assertIn("Veronica: Your name is Hardik.", transcript)
        self.assertIn("Conversation messages: 7", transcript)
        self.assertIn("Conversation messages: 1", transcript)
        self.assertIn("/history", transcript)
        self.assertIn("Veronica: Python ek programming language hai.", transcript)
        self.assertNotIn("You are Veronica, a private personal AI assistant.", transcript)

        history_question = provider.generate_response.call_args_list[3].args[0]
        self.assertEqual(history_question[1]["content"], "Hello Veronica")
        self.assertEqual(history_question[3]["content"], "My name is Hardik.")
        self.assertEqual(_input.call_count, 9)


if __name__ == "__main__":
    unittest.main()
