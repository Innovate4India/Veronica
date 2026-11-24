"""Tests for Veronica's interactive developer chat interface."""

import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import dev_ai
from app.ai import AIProvider, AIService, OllamaConnectionError
from app.config import OllamaConfig, SpokenResponseConfig
from app.memory import MemoryService
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
                "/clear", self.service, self.memory_service, self.state
            )

        self.assertFalse(should_exit)
        self.assertEqual(self.service.message_count, 1)
        self.assertIn("Conversation cleared.", output.getvalue())

    def test_history_command_shows_current_message_count(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            dev_ai._handle_command(
                "/history", self.service, self.memory_service, self.state
            )

        self.assertIn("Conversation messages: 3", output.getvalue())

    def test_help_command_shows_all_commands(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            dev_ai._handle_command(
                "/help", self.service, self.memory_service, self.state
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
                "/exit", self.service, self.memory_service, self.state
            )

        self.assertTrue(should_exit)
        self.assertIn("Goodbye.", output.getvalue())

    def test_memory_commands_save_list_search_and_delete(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            dev_ai._handle_command(
                "/remember My main project is Veronica.",
                self.service,
                self.memory_service,
                self.state,
            )
            dev_ai._handle_command(
                "/memory", self.service, self.memory_service, self.state
            )
            dev_ai._handle_command(
                "/memory-search Veronica",
                self.service,
                self.memory_service,
                self.state,
            )
            dev_ai._handle_command(
                "/forget 1", self.service, self.memory_service, self.state
            )
            dev_ai._handle_command(
                "/memory", self.service, self.memory_service, self.state
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
                "/clear-memory", self.service, self.memory_service, self.state
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

    @patch("dev_ai.load_ollama_config")
    @patch("dev_ai.OllamaClient")
    def test_unavailable_ollama_is_reported_without_traceback(
        self,
        ollama_client_class: Mock,
        load_config: Mock,
    ) -> None:
        load_config.return_value = OllamaConfig(
            "http://127.0.0.1:11434", "llama3.2", 10
        )
        ollama_client_class.return_value.list_models.side_effect = (
            OllamaConnectionError("offline")
        )
        output = StringIO()

        with redirect_stdout(output):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 1)
        self.assertIn(dev_ai.OLLAMA_UNAVAILABLE_MESSAGE, output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    @patch("builtins.input", side_effect=["Hello", "/exit"])
    @patch("dev_ai.load_ollama_config")
    @patch("dev_ai.OllamaClient")
    def test_unavailable_ollama_during_chat_is_reported(
        self,
        ollama_client_class: Mock,
        load_config: Mock,
        _input: Mock,
    ) -> None:
        load_config.return_value = OllamaConfig(
            "http://127.0.0.1:11434", "llama3.2", 10
        )
        client = ollama_client_class.return_value
        client.list_models.return_value = ("llama3.2:latest",)
        client.generate_response.side_effect = OllamaConnectionError("offline")
        output = StringIO()
        error_output = StringIO()

        with redirect_stdout(output), redirect_stderr(error_output):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 0)
        self.assertIn(dev_ai.OLLAMA_UNAVAILABLE_MESSAGE, error_output.getvalue())
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
    @patch("dev_ai.load_ollama_config")
    @patch("dev_ai.OllamaClient")
    def test_enabled_spoken_response_uses_selected_language_and_is_nonfatal(
        self,
        ollama_client_class: Mock,
        load_ollama: Mock,
        tts_class: Mock,
        load_spoken: Mock,
        _input: Mock,
    ) -> None:
        load_ollama.return_value = OllamaConfig(
            "http://127.0.0.1:11434", "llama3.2", 10
        )
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
        client = ollama_client_class.return_value
        client.list_models.return_value = ("llama3.2:latest",)
        client.generate_response.return_value = "नमस्ते"
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
    @patch("dev_ai.load_ollama_config")
    @patch("dev_ai.OllamaClient")
    def test_disabled_spoken_responses_never_construct_piper(
        self,
        ollama_client_class: Mock,
        load_ollama: Mock,
        tts_class: Mock,
        load_spoken: Mock,
        _input: Mock,
    ) -> None:
        load_ollama.return_value = OllamaConfig(
            "http://127.0.0.1:11434", "llama3.2", 10
        )
        load_spoken.return_value = SpokenResponseConfig(
            enabled=False,
            language="en",
            hindi_voice="hi-IN-SwaraNeural",
            english_voice="hi-IN-SwaraNeural",
            rate="-10%",
            pitch="+0Hz",
            volume="+0%",
        )
        client = ollama_client_class.return_value
        client.list_models.return_value = ("llama3.2:latest",)
        client.generate_response.return_value = "Hello there."

        with redirect_stdout(StringIO()):
            exit_code = dev_ai.main()

        self.assertEqual(exit_code, 0)
        tts_class.assert_not_called()
        _input.assert_called()

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
    @patch("dev_ai.load_ollama_config")
    @patch("dev_ai.OllamaClient")
    def test_interactive_conversation_and_commands(
        self,
        ollama_client_class: Mock,
        load_config: Mock,
        _input: Mock,
    ) -> None:
        load_config.return_value = OllamaConfig(
            "http://127.0.0.1:11434", "llama3.2", 10
        )
        client = ollama_client_class.return_value
        client.list_models.return_value = ("llama3.2:latest",)
        client.generate_response.side_effect = [
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

        history_question = client.generate_response.call_args_list[3].args[0]
        self.assertEqual(history_question[1]["content"], "Hello Veronica")
        self.assertEqual(history_question[3]["content"], "My name is Hardik.")
        self.assertEqual(_input.call_count, 9)


if __name__ == "__main__":
    unittest.main()
