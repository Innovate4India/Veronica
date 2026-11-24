"""Tests for configuration, Ollama client, and AI service behavior."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError

from app.ai import (
    AIProvider,
    AIService,
    AIServiceError,
    OllamaClient,
    OllamaConfigurationError,
    OllamaConnectionError,
    OllamaResponseError,
    OllamaTimeoutError,
    VERONICA_SYSTEM_PROMPT,
)
from app.config import (
    MAX_CONVERSATION_MESSAGES,
    MAX_RELEVANT_MEMORIES,
    MEMORY_DATABASE_PATH,
    OllamaConfig,
    PiperConfig,
    PROJECT_ROOT,
    SpokenResponseConfig,
    WebSearchConfig,
    WhisperConfig,
    load_whisper_config,
    load_piper_config,
    load_spoken_response_config,
    load_max_conversation_messages,
    load_max_relevant_memories,
    load_memory_database_path,
    load_ollama_config,
    load_ollama_vision_model,
    load_web_search_config,
    load_web_search_enabled,
)
from app.ai.ollama_client import OllamaToolDefinition


class ConfigTests(unittest.TestCase):
    def test_vision_model_is_independent_and_unconfigured_by_default(self) -> None:
        self.assertEqual(load_ollama_vision_model({}), "")
        self.assertEqual(
            load_ollama_vision_model({"OLLAMA_VISION_MODEL": "  minicpm-v "}),
            "minicpm-v",
        )

    def test_web_search_is_disabled_by_default_and_config_is_optional(self) -> None:
        self.assertFalse(load_web_search_enabled({}))
        self.assertTrue(load_web_search_enabled({"WEB_SEARCH_ENABLED": "TRUE"}))
        self.assertFalse(load_web_search_enabled({"WEB_SEARCH_ENABLED": "false"}))
        self.assertEqual(
            load_web_search_config({}),
            WebSearchConfig("tavily", "", 8.0),
        )
        with self.assertRaises(ValueError):
            load_web_search_enabled({"WEB_SEARCH_ENABLED": "yes"})

    def test_loads_defaults_and_environment_values(self) -> None:
        defaults = load_ollama_config({})
        self.assertEqual(defaults.base_url, "http://127.0.0.1:11434")
        self.assertEqual(defaults.model, "")
        self.assertEqual(defaults.timeout, 120)

        configured = load_ollama_config(
            {
                "OLLAMA_BASE_URL": "http://localhost:11434/",
                "OLLAMA_MODEL": "llama3.2",
                "OLLAMA_TIMEOUT": "45",
            }
        )
        self.assertEqual(configured, OllamaConfig("http://localhost:11434", "llama3.2", 45))

    def test_rejects_invalid_timeout(self) -> None:
        for timeout in ("bad", "0", "-1", "inf"):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                load_ollama_config({"OLLAMA_TIMEOUT": timeout})

    def test_loads_and_validates_max_conversation_messages(self) -> None:
        self.assertEqual(MAX_CONVERSATION_MESSAGES, 20)
        self.assertEqual(load_max_conversation_messages({}), 20)
        self.assertEqual(
            load_max_conversation_messages({"MAX_CONVERSATION_MESSAGES": "8"}),
            8,
        )
        for value in ("invalid", "0", "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                load_max_conversation_messages(
                    {"MAX_CONVERSATION_MESSAGES": value}
                )

    def test_loads_memory_configuration(self) -> None:
        self.assertEqual(MEMORY_DATABASE_PATH.name, "veronica_memory.db")
        self.assertEqual(MEMORY_DATABASE_PATH.parent.name, "data")
        self.assertEqual(MAX_RELEVANT_MEMORIES, 5)
        self.assertEqual(
            load_memory_database_path(
                {"MEMORY_DATABASE_PATH": "custom/memory.sqlite"}
            ).name,
            "memory.sqlite",
        )
        self.assertEqual(
            load_memory_database_path(
                {"MEMORY_DATABASE_PATH": "D:\\private\\memory.db"}
            ),
            Path("D:\\private\\memory.db"),
        )
        self.assertEqual(
            load_max_relevant_memories({"MAX_RELEVANT_MEMORIES": "3"}),
            3,
        )
        for value in ("bad", "0", "-1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                load_max_relevant_memories({"MAX_RELEVANT_MEMORIES": value})
        with self.assertRaises(ValueError):
            load_memory_database_path({"MEMORY_DATABASE_PATH": " "})

    def test_loads_whisper_settings_and_local_model_path(self) -> None:
        defaults = load_whisper_config({})
        self.assertEqual(defaults.model, "base")
        self.assertEqual(defaults.model_path, PROJECT_ROOT / "data/models/whisper/base")
        self.assertEqual(defaults.device, "cpu")
        self.assertEqual(defaults.compute_type, "int8")

        configured = load_whisper_config(
            {
                "WHISPER_MODEL": "small",
                "WHISPER_MODEL_PATH": "custom/{model}",
                "WHISPER_DEVICE": "cuda",
                "WHISPER_COMPUTE_TYPE": "float16",
            }
        )
        self.assertEqual(
            configured,
            WhisperConfig(
                "small",
                PROJECT_ROOT / "custom/small",
                "cuda",
                "float16",
            ),
        )
        for invalid_device in ("", "mps", "remote"):
            with self.subTest(device=invalid_device), self.assertRaises(ValueError):
                load_whisper_config({"WHISPER_DEVICE": invalid_device})
        with self.assertRaises(ValueError):
            load_whisper_config({"WHISPER_MODEL": " "})
        with self.assertRaises(ValueError):
            load_whisper_config({"WHISPER_COMPUTE_TYPE": " "})

    def test_loads_piper_voice_path_without_assuming_a_voice_name(self) -> None:
        defaults = load_piper_config({})
        self.assertEqual(defaults.model, "")
        self.assertEqual(defaults.model_path, PROJECT_ROOT / "data/models/piper")
        self.assertEqual(
            defaults.hindi_model_path,
            PROJECT_ROOT
            / "data/models/piper/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx",
        )
        self.assertEqual(
            defaults.english_model_path,
            PROJECT_ROOT
            / "data/models/piper/en/en_US/ryan/medium/en_US-ryan-medium.onnx",
        )

        configured = load_piper_config(
            {
                "PIPER_MODEL": "sample-voice",
                "PIPER_MODEL_PATH": "custom/{model}.onnx",
            }
        )
        self.assertEqual(
            configured,
            PiperConfig(
                "sample-voice",
                PROJECT_ROOT / "custom/sample-voice.onnx",
                PROJECT_ROOT
                / "data/models/piper/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx",
                PROJECT_ROOT
                / "data/models/piper/en/en_US/ryan/medium/en_US-ryan-medium.onnx",
            ),
        )
        self.assertEqual(
            load_piper_config(
                {"PIPER_MODEL_PATH": "D:\\voices\\my_voice.onnx"}
            ).model_path,
            Path("D:\\voices\\my_voice.onnx"),
        )
        with self.assertRaises(ValueError):
            load_piper_config({"PIPER_MODEL_PATH": "voices/{model}.onnx"})

    def test_spoken_responses_are_disabled_by_default_and_language_is_explicit(self) -> None:
        self.assertEqual(
            load_spoken_response_config({}),
            SpokenResponseConfig(
                enabled=False,
                language="en",
                hindi_voice="hi-IN-SwaraNeural",
                english_voice="hi-IN-SwaraNeural",
                rate="-10%",
                pitch="+0Hz",
                volume="+0%",
            ),
        )
        self.assertEqual(
            load_spoken_response_config(
                {
                    "VOICE_RESPONSES_ENABLED": "true",
                    "VOICE_RESPONSE_LANGUAGE": "HI",
                    "MICROSOFT_TTS_ENGLISH_VOICE": "en-IN-NeerjaNeural",
                }
            ),
            SpokenResponseConfig(
                enabled=True,
                language="hi",
                hindi_voice="hi-IN-SwaraNeural",
                english_voice="en-IN-NeerjaNeural",
                rate="-10%",
                pitch="+0Hz",
                volume="+0%",
            ),
        )
        for setting in (
            {"VOICE_RESPONSES_ENABLED": "yes"},
            {"VOICE_RESPONSE_LANGUAGE": "fr"},
            {"MICROSOFT_TTS_HINDI_VOICE": "hi-IN-MadhurNeural"},
            {"MICROSOFT_TTS_ENGLISH_VOICE": "en-IN-PrabhatNeural"},
        ):
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                load_spoken_response_config(setting)


class OllamaClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = OllamaConfig(
            base_url="http://127.0.0.1:11434",
            model="llama3.2",
            timeout=10,
        )

    def test_initializes_with_local_configuration(self) -> None:
        client = OllamaClient(self.config)
        self.assertEqual(client.config, self.config)

    def test_rejects_non_loopback_provider_url(self) -> None:
        with self.assertRaises(OllamaConfigurationError):
            OllamaClient(
                OllamaConfig("https://example.com", "llama3.2", 10)
            )

    @patch("app.ai.ollama_client.urlopen", side_effect=URLError("offline"))
    def test_health_check_reports_unavailable_service(self, urlopen_mock: Mock) -> None:
        with self.assertRaises(OllamaConnectionError):
            OllamaClient(self.config).health_check()
        urlopen_mock.assert_called_once()

    @patch("app.ai.ollama_client.urlopen", side_effect=TimeoutError)
    def test_timeout_is_reported(self, urlopen_mock: Mock) -> None:
        with self.assertRaises(OllamaTimeoutError):
            OllamaClient(self.config).health_check()
        urlopen_mock.assert_called_once()

    @patch("app.ai.ollama_client.urlopen")
    def test_invalid_api_response_is_reported(self, urlopen_mock: Mock) -> None:
        response = Mock()
        response.read.return_value = b"not-json"
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        urlopen_mock.return_value = response
        with self.assertRaises(OllamaResponseError):
            OllamaClient(self.config).health_check()

    @patch("app.ai.ollama_client.urlopen")
    def test_posts_text_only_chat_request(self, urlopen_mock: Mock) -> None:
        response = Mock()
        response.read.return_value = json.dumps(
            {"message": {"role": "assistant", "content": "Hello!"}}
        ).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        urlopen_mock.return_value = response

        result = OllamaClient(self.config).generate_response(
            [{"role": "user", "content": "Hello Veronica"}]
        )

        self.assertEqual(result, "Hello!")
        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "llama3.2")
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["messages"], [{"role": "user", "content": "Hello Veronica"}])
        self.assertNotIn("tools", payload)
        self.assertEqual(urlopen_mock.call_args.kwargs["timeout"], 10)

    @patch("app.ai.ollama_client.urlopen")
    def test_tool_chat_posts_native_definition_and_tool_messages(
        self,
        urlopen_mock: Mock,
    ) -> None:
        response = Mock()
        response.read.return_value = json.dumps(
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "example",
                                "arguments": {"query": "hello"},
                            }
                        }
                    ],
                }
            }
        ).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        urlopen_mock.return_value = response
        tools: list[OllamaToolDefinition] = [
            {
                "type": "function",
                "function": {
                    "name": "example",
                    "description": "Example registered function",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

        result = OllamaClient(self.config).generate_tool_response(
            [
                {"role": "user", "content": "run example"},
                {"role": "tool", "content": '{"status":"success"}'},
            ],
            tools,
        )

        self.assertEqual(result.content, "")
        self.assertTrue(result.requests_tools)
        self.assertEqual(result.tool_calls[0].name, "example")
        self.assertEqual(result.tool_calls[0].arguments, {"query": "hello"})
        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["tools"], tools)
        self.assertEqual(payload["messages"][1]["role"], "tool")

    @patch("app.ai.ollama_client.urlopen")
    def test_tool_chat_parses_normal_assistant_response(
        self,
        urlopen_mock: Mock,
    ) -> None:
        response = Mock()
        response.read.return_value = b'{"message":{"role":"assistant","content":"Done."}}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        urlopen_mock.return_value = response

        parsed = OllamaClient(self.config).generate_tool_response(
            [{"role": "user", "content": "hello"}],
            [],
        )

        self.assertEqual(parsed.content, "Done.")
        self.assertFalse(parsed.requests_tools)
        self.assertNotIn("tools", json.loads(urlopen_mock.call_args.args[0].data))

    @patch("app.ai.ollama_client.urlopen")
    def test_malformed_tool_call_is_returned_as_untrusted_malformed_data(
        self,
        urlopen_mock: Mock,
    ) -> None:
        response = Mock()
        response.read.return_value = json.dumps(
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "example", "arguments": "not-an-object"}},
                        None,
                    ],
                }
            }
        ).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        urlopen_mock.return_value = response

        parsed = OllamaClient(self.config).generate_tool_response(
            [{"role": "user", "content": "hello"}],
            [],
        )

        self.assertEqual(len(parsed.tool_calls), 2)
        self.assertTrue(parsed.tool_calls[0].malformed)
        self.assertEqual(parsed.tool_calls[0].arguments, "not-an-object")
        self.assertTrue(parsed.tool_calls[1].malformed)


class AIServiceTests(unittest.TestCase):
    @staticmethod
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

    def test_provider_interface_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            AIProvider()  # type: ignore[abstract]

    def test_sends_casual_greeting_to_friend_response_without_reclassification(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = "  Hello!  "
        service = AIService(provider)

        result = service.respond("Hello Veronica")

        self.assertEqual(result, "Hello!")
        self.assertEqual(provider.generate_response.call_count, 1)
        messages = provider.generate_response.call_args.args[0]
        self.assertEqual(messages[-1], {"role": "user", "content": "Hello Veronica"})
        self.assertIn("CURRENT ROLE: FRIEND", messages[0]["content"])

    def test_tool_calling_service_is_used_only_when_injected(self) -> None:
        provider = Mock(spec=AIProvider)
        tool_service = Mock()
        tool_service.respond.return_value = "Current answer."
        service = AIService(provider, tool_calling_service=tool_service)

        result = service.respond("Search the latest AI news.")

        self.assertEqual(result, "Current answer.")
        provider.generate_response.assert_called_once()
        call_messages = tool_service.respond.call_args.args[0]
        self.assertEqual(
            call_messages[-1],
            {"role": "user", "content": "Search the latest AI news."},
        )
        self.assertIn("Web Search is available", call_messages[0]["content"])
        self.assertIn("do not invent search results", call_messages[0]["content"])
        self.assertIn("file_search instead of asking them", call_messages[0]["content"])
        self.assertIn("never pass an", call_messages[0]["content"].casefold())
        self.assertIn("empty path", call_messages[0]["content"].casefold())
        self.assertEqual(service.messages[-1], {"role": "assistant", "content": "Current answer."})

    def test_tool_calling_failures_do_not_record_a_fabricated_exchange(self) -> None:
        provider = Mock(spec=AIProvider)
        tool_service = Mock()
        tool_service.respond.side_effect = OllamaConnectionError("offline")
        service = AIService(provider, tool_calling_service=tool_service)

        with self.assertRaises(AIServiceError):
            service.respond("Search for current information.")

        provider.generate_response.assert_called_once()
        self.assertEqual(service.message_count, 1)

    def test_disabled_text_path_does_not_expose_web_search_call_json(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = (
            '{"name":"web_search",""parameters":{"query":'
            '""latest AI developments 2024"","max_results":10}}'
        )
        service = AIService(provider)

        with self.assertRaisesRegex(
            AIServiceError,
            "Web Search is disabled",
        ):
            service.respond("What is the latest in AI?")

        self.assertEqual(service.message_count, 1)

    def test_prompt_defines_veronica_and_disallows_unavailable_capabilities(self) -> None:
        prompt = " ".join(VERONICA_SYSTEM_PROMPT.lower().split())
        self.assertIn("you are veronica", prompt)
        self.assertIn("local-first", prompt)
        self.assertIn("english, hindi, or hinglish", prompt)
        self.assertIn("prefer natural latin-script hinglish", prompt)
        self.assertIn("conversational ai capabilities only", prompt)
        for unavailable_capability in (
            "cannot control the computer",
            "access files",
            "microphone",
            "camera",
            "browser",
            "external",
            "do not invent actions",
            "uncertain, say so rather than guessing",
        ):
            with self.subTest(capability=unavailable_capability):
                self.assertIn(unavailable_capability, prompt)

    def test_conversation_history_is_preserved_between_responses(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.side_effect = [
            self._assistant_role(),
            "Nice to meet you, Hardik.",
            self._assistant_role(),
            "Your name is Hardik.",
        ]
        service = AIService(provider)

        service.respond("My name is Hardik.")
        result = service.respond("What is my name?")

        self.assertEqual(result, "Your name is Hardik.")
        messages = provider.generate_response.call_args_list[3].args[0]
        self.assertEqual(
            messages[-3:],
            [
                {"role": "user", "content": "My name is Hardik."},
                {"role": "assistant", "content": "Nice to meet you, Hardik."},
                {"role": "user", "content": "What is my name?"},
            ],
        )
        self.assertIn("CURRENT ROLE: ASSISTANT", messages[0]["content"])
        self.assertEqual(service.message_count, 5)

    def test_trims_old_turns_without_removing_system_prompt(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.side_effect = [
            self._assistant_role(),
            "Answer 1",
            self._assistant_role(),
            "Answer 2",
            self._assistant_role(),
            "Answer 3",
        ]
        service = AIService(provider, max_messages=4)

        service.respond("Question 1")
        service.respond("Question 2")
        service.respond("Question 3")

        self.assertEqual(
            service.messages,
            (
                {"role": "system", "content": VERONICA_SYSTEM_PROMPT},
                {"role": "user", "content": "Question 2"},
                {"role": "assistant", "content": "Answer 2"},
                {"role": "user", "content": "Question 3"},
                {"role": "assistant", "content": "Answer 3"},
            ),
        )
        self.assertEqual(service.message_count - 1, 4)
        self.assertEqual(
            provider.generate_response.call_args_list[5].args[0][0]["role"],
            "system",
        )

    def test_clear_preserves_system_prompt_and_resets_history_count(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = "Hello!"
        service = AIService(provider)
        service.respond("Hi")

        service.clear()

        self.assertEqual(
            service.messages,
            ({"role": "system", "content": VERONICA_SYSTEM_PROMPT},),
        )
        self.assertEqual(service.message_count, 1)

    def test_wraps_provider_errors(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.side_effect = OllamaConnectionError("offline")

        with self.assertRaises(AIServiceError):
            service = AIService(provider)
            service.respond("Hello Veronica")
        self.assertEqual(service.message_count, 1)

    def test_rejects_empty_user_message(self) -> None:
        provider = Mock(spec=AIProvider)
        with self.assertRaises(ValueError):
            AIService(provider).respond(" ")
        provider.generate_response.assert_not_called()


if __name__ == "__main__":
    unittest.main()
