import json
import unittest
from unittest.mock import patch

from PIL import Image

from app.ai import (
    AIProvider,
    AIService,
    AIServiceError,
    AssistantResponse,
    ConversationMessage,
    OllamaClient,
    OllamaToolCallingService,
    ProviderCapabilityError,
    ProviderConfigurationError,
    ProviderModelUnavailableError,
    ToolCall,
    ToolCallingService,
    ToolCallingServiceError,
    ToolErrorPayload,
    ToolResultPayload,
    VeronicaModelProvider,
    VisionRequest,
    VisionProvider,
    VisionResponse,
    create_provider,
    register_provider,
)
from app.ai.base import _MAX_JSON_NESTING_DEPTH
from app.ai.ollama_client import OllamaAssistantResponse
from app.ai.provider import _PROVIDER_FACTORIES
from app.config import (
    OllamaConfig,
    ProviderSelectionConfig,
    load_provider_selection_config,
)
from app.tools import CalculatorTool, ToolRegistry


class FakeProvider(AIProvider):
    def __init__(self) -> None:
        self.requests = []

    def generate_response(self, messages) -> str:
        self.requests.append(messages)
        return "Fake provider answer"


class FakeToolProvider:
    def __init__(self) -> None:
        self.requests: list[tuple[ConversationMessage, ...]] = []
        self.responses = iter(
            (
                AssistantResponse(
                    "",
                    (ToolCall("calculator", {"expression": "2 + 3"}),),
                ),
                AssistantResponse("Five"),
            )
        )

    def generate_provider_tool_response(self, messages, tools):
        self.requests.append(tuple(messages))
        return next(self.responses)


class LegacyToolProvider:
    def __init__(self) -> None:
        self.responses = iter(
            (
                AssistantResponse(
                    "",
                    (ToolCall("calculator", {"expression": "2 + 3"}),),
                ),
                AssistantResponse("Five"),
            )
        )

    def generate_tool_response(self, messages, tools):
        return next(self.responses)


class ProviderContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry()
        self.registry.register(CalculatorTool())
        self.user_message = [{"role": "user", "content": "Calculate"}]

    def test_fake_provider_works_without_ollama(self) -> None:
        provider = FakeProvider()
        service = AIService(provider)

        response = service.respond("Hello Veronica")

        self.assertEqual(response, "Fake provider answer")
        self.assertEqual(provider.requests[0][-1]["content"], "Hello Veronica")

    def test_streaming_fallback_returns_one_chunk(self) -> None:
        provider = FakeProvider()

        chunks = list(
            provider.generate_stream(
                [{"role": "user", "content": "Hello"}]
            )
        )

        self.assertEqual(chunks, ["Fake provider answer"])

    def test_provider_selection_defaults_to_ollama(self) -> None:
        self.assertEqual(
            load_provider_selection_config({}).provider_name,
            "ollama",
        )
        config = OllamaConfig("http://127.0.0.1:11434", "llama3.2", 5)
        with (
            patch(
                "app.ai.provider.load_provider_selection_config",
                return_value=ProviderSelectionConfig("ollama"),
            ),
            patch("app.config.load_ollama_config", return_value=config),
        ):
            provider = create_provider()

        self.assertIsInstance(provider, OllamaClient)
        self.assertEqual(provider.metadata.model, "llama3.2")

    def test_provider_factory_can_register_a_future_provider(self) -> None:
        provider = FakeProvider()
        with patch.dict(_PROVIDER_FACTORIES, {}):
            register_provider("test-native", lambda: provider)
            self.assertIs(create_provider("test-native"), provider)

    def test_unknown_provider_is_a_configuration_error(self) -> None:
        with self.assertRaisesRegex(
            ProviderConfigurationError,
            "not registered",
        ):
            create_provider("unregistered-test-provider")

    def test_provider_selection_rejects_empty_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            load_provider_selection_config({"VERONICA_AI_PROVIDER": " "})

    def test_ollama_owns_model_discovery_and_validation(self) -> None:
        config = OllamaConfig("http://127.0.0.1:11434", "llama3.2", 5)
        provider = OllamaClient(config)
        with patch.object(provider, "list_models", return_value=("llama3.2:latest",)) as models:
            provider.validate_startup()
        models.assert_called_once_with()

        with patch.object(provider, "list_models", return_value=("other:latest",)):
            with self.assertRaises(ProviderModelUnavailableError):
                provider.validate_startup()

    def test_ollama_capabilities_match_implemented_interfaces(self) -> None:
        provider = OllamaClient(
            OllamaConfig("http://127.0.0.1:11434", "llama3.2", 5)
        )

        capabilities = provider.metadata.capabilities

        self.assertTrue(capabilities.text)
        self.assertFalse(capabilities.streaming)
        self.assertTrue(capabilities.tools)
        self.assertTrue(capabilities.vision)
        self.assertTrue(callable(provider.generate_provider_tool_response))
        self.assertIsInstance(provider.create_vision_provider(), VisionProvider)

    def test_ollama_parses_text_tool_calls_into_neutral_contracts(self) -> None:
        provider = OllamaClient(
            OllamaConfig("http://127.0.0.1:11434", "llama3.2", 5)
        )

        call = provider.parse_tool_call_text(
            '{"name":"web_search","parameters":{"query":"latest news"}}'
        )
        malformed = provider.parse_tool_call_text(
            '{"name":"web_search","parameters":'
        )
        non_json_arguments = provider.parse_tool_call_text(
            '{"name":"web_search","parameters":{"query":NaN}}'
        )

        self.assertEqual(call, ToolCall("web_search", {"query": "latest news"}))
        self.assertIsNotNone(malformed)
        self.assertTrue(malformed.malformed)
        self.assertIsNotNone(non_json_arguments)
        self.assertTrue(non_json_arguments.malformed)
        self.assertIsNone(non_json_arguments.arguments)

    def test_tool_call_requires_recursively_valid_json_object_arguments(self) -> None:
        valid_arguments = {
            "nested": [None, True, 1, 1.5, "text", {"value": []}],
        }
        self.assertEqual(
            ToolCall("calculator", valid_arguments).arguments,
            valid_arguments,
        )
        self.assertTrue(ToolCall("calculator", {}).arguments == {})

        invalid_arguments = (
            None,
            [],
            "scalar",
            1,
            ({"value": 1},),
            {"nested": (1,)},
            {"nested": {1: "value"}},
            {"nested": {1, 2}},
            {"nested": object()},
            {"nested": float("nan")},
            {"nested": float("inf")},
        )
        for arguments in invalid_arguments:
            with self.subTest(arguments=repr(arguments)):
                with self.assertRaises(ValueError):
                    ToolCall("calculator", arguments)

        self.assertTrue(
            ToolCall("calculator", None, malformed=True).malformed
        )
        with self.assertRaises(ValueError):
            ToolCall("calculator", {"value": 1}, malformed=True)

    def test_tool_call_rejects_cycles_and_excessive_json_nesting(self) -> None:
        cyclic_list: list[object] = []
        cyclic_list.append(cyclic_list)
        cyclic_dict: dict[str, object] = {}
        cyclic_dict["self"] = cyclic_dict

        nested_list: object = []
        for _ in range(_MAX_JSON_NESTING_DEPTH):
            nested_list = [nested_list]
        nested_dict: object = {}
        for _ in range(_MAX_JSON_NESTING_DEPTH):
            nested_dict = {"nested": nested_dict}

        invalid_arguments = (
            ("cyclic list", {"cycle": cyclic_list}),
            ("cyclic dictionary", {"cycle": cyclic_dict}),
            ("deep list", {"nested": nested_list}),
            ("deep dictionary", {"nested": nested_dict}),
        )
        for case, arguments in invalid_arguments:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    ToolCall("calculator", arguments)

    def test_normalization_rejects_mutated_nested_arguments_before_dispatch(self) -> None:
        arguments: dict[str, list[object]] = {"nested": []}
        call = ToolCall("calculator", arguments)
        arguments["nested"].append(object())

        class MutatedCallProvider:
            def generate_provider_tool_response(self, messages, tools):
                return AssistantResponse("", (call,))

        with patch.object(
            self.registry,
            "execute",
            wraps=self.registry.execute,
        ) as execute:
            with self.assertRaises(ToolCallingServiceError):
                ToolCallingService(
                    MutatedCallProvider(),
                    self.registry,
                ).respond(self.user_message)

        execute.assert_not_called()

    def test_normalization_rejects_cycles_before_tool_execution(self) -> None:
        for cycle_kind in ("list", "dictionary"):
            with self.subTest(cycle_kind=cycle_kind):
                nested: dict[str, object] = {}
                if cycle_kind == "list":
                    cyclic_list: list[object] = []
                    nested["cycle"] = cyclic_list
                    call = ToolCall("calculator", nested)
                    cyclic_list.append(cyclic_list)
                else:
                    cyclic_dict: dict[str, object] = {}
                    nested["cycle"] = cyclic_dict
                    call = ToolCall("calculator", nested)
                    cyclic_dict["self"] = cyclic_dict

                class CyclicCallProvider:
                    def generate_provider_tool_response(self, messages, tools):
                        return AssistantResponse("", (call,))

                with patch.object(
                    self.registry,
                    "execute",
                    wraps=self.registry.execute,
                ) as execute:
                    with self.assertRaises(ToolCallingServiceError):
                        ToolCallingService(
                            CyclicCallProvider(),
                            self.registry,
                        ).respond(self.user_message)

                execute.assert_not_called()

    def test_malformed_tool_call_is_not_dispatched(self) -> None:
        class MalformedCallProvider:
            def __init__(self) -> None:
                self.responses = iter(
                    (
                        AssistantResponse(
                            "",
                            (ToolCall("calculator", None, malformed=True),),
                        ),
                        AssistantResponse("Safe final response"),
                    )
                )

            def generate_provider_tool_response(self, messages, tools):
                return next(self.responses)

        with patch.object(
            self.registry,
            "execute",
            wraps=self.registry.execute,
        ) as execute:
            response = ToolCallingService(
                MalformedCallProvider(),
                self.registry,
            ).respond(self.user_message)

        self.assertEqual(response, "Safe final response")
        execute.assert_not_called()

    def test_generic_tool_provider_receives_typed_neutral_conversation(self) -> None:
        provider = FakeToolProvider()
        response = ToolCallingService(provider, self.registry).respond(
            self.user_message
        )

        self.assertEqual(response, "Five")
        conversation = provider.requests[1]
        self.assertIsInstance(conversation[-2], AssistantResponse)
        self.assertIsInstance(conversation[-1], ToolResultPayload)
        result = conversation[-1]
        self.assertEqual(result.tool_name, "calculator")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.data, {"result": "5"})
        self.assertIsNone(result.error)

    def test_generic_service_rejects_legacy_provider_without_ollama_fallback(self) -> None:
        provider = LegacyToolProvider()

        with self.assertRaises(ProviderCapabilityError):
            ToolCallingService(provider, self.registry)

    def test_explicit_ollama_legacy_service_preserves_legacy_provider_support(self) -> None:
        response = OllamaToolCallingService(
            LegacyToolProvider(),
            self.registry,
        ).respond(self.user_message)

        self.assertEqual(response, "Five")
        from app.ai.tool_calling import (
            OllamaToolCallingService as ToolCallingModuleCompatibilityExport,
        )

        self.assertIs(
            ToolCallingModuleCompatibilityExport,
            OllamaToolCallingService,
        )

    def test_ollama_adapter_serializes_neutral_results_at_the_wire_boundary(self) -> None:
        config = OllamaConfig("http://127.0.0.1:11434", "llama3.2", 5)
        provider = OllamaClient(config)
        neutral_messages: list[ConversationMessage] = [
            {"role": "user", "content": "Calculate"},
            AssistantResponse(
                "",
                (ToolCall("calculator", {"expression": "2 + 3"}),),
            ),
            ToolResultPayload(
                tool_name="calculator",
                status="success",
                data={"result": "5"},
            ),
            ToolResultPayload(
                tool_name="web_search",
                status="unavailable",
                error=ToolErrorPayload("permission_required", "Approval required."),
            ),
        ]
        with patch.object(
            provider,
            "generate_tool_response",
            return_value=OllamaAssistantResponse("Five"),
        ) as generate:
            provider.generate_provider_tool_response(neutral_messages, ())

        ollama_messages = generate.call_args.args[0]
        self.assertEqual(ollama_messages[0], {"role": "user", "content": "Calculate"})
        self.assertEqual(ollama_messages[1]["role"], "assistant")
        self.assertEqual(
            ollama_messages[1]["tool_calls"][0]["function"]["name"],
            "calculator",
        )
        self.assertEqual(
            json.loads(ollama_messages[2]["content"]),
            {"status": "success", "data": {"result": "5"}},
        )
        self.assertEqual(
            json.loads(ollama_messages[3]["content"]),
            {
                "status": "unavailable",
                "error": {
                    "code": "permission_required",
                    "message": "Approval required.",
                },
            },
        )

    def test_list_and_tuple_tool_call_sequences_are_supported(self) -> None:
        class ListToolProvider:
            def __init__(self) -> None:
                self.responses = iter(
                    (
                        AssistantResponse(
                            "",
                            [ToolCall("calculator", {"expression": "2 + 3"})],
                        ),
                        AssistantResponse("Five"),
                    )
                )

            def generate_provider_tool_response(self, messages, tools):
                return next(self.responses)

        response = ToolCallingService(
            ListToolProvider(),
            self.registry,
        ).respond(self.user_message)

        self.assertEqual(response, "Five")

    def test_unknown_provider_tool_response_is_rejected(self) -> None:
        class UnknownToolProvider:
            def generate_provider_tool_response(self, messages, tools):
                return object()

        with self.assertRaises(ToolCallingServiceError):
            ToolCallingService(
                UnknownToolProvider(),
                self.registry,
            ).respond(self.user_message)

    def test_veronica_provider_does_not_advertise_unimplemented_capabilities(self) -> None:
        provider = VeronicaModelProvider()

        self.assertFalse(provider.health_check())
        self.assertFalse(provider.metadata.capabilities.text)
        self.assertFalse(provider.metadata.capabilities.streaming)
        self.assertFalse(provider.metadata.capabilities.tools)
        self.assertFalse(provider.metadata.capabilities.vision)
        with self.assertRaises(ProviderModelUnavailableError):
            provider.generate_response(
                [{"role": "user", "content": "Hello"}]
            )

    def test_unimplemented_health_check_is_not_success_shaped(self) -> None:
        with self.assertRaises(ProviderCapabilityError):
            FakeProvider().health_check()

    def test_vision_request_accepts_only_pil_images(self) -> None:
        with Image.new("RGB", (1, 1)) as image:
            request = VisionRequest(question="Describe", image=image)
            self.assertIs(request.image, image)
        with self.assertRaises(TypeError):
            VisionRequest(question="Describe", image=object())

    def test_vision_provider_is_structurally_injected(self) -> None:
        class FakeVisionProvider:
            model_configured = True

            def model_available(self) -> bool:
                return True

            def generate_vision(self, request: VisionRequest) -> VisionResponse:
                return VisionResponse(text=request.question)

        from app.ai.vision import LocalVisionService

        service = LocalVisionService(FakeVisionProvider())
        image = Image.new("RGB", (1, 1))
        try:
            with patch(
                "app.ai.vision.capture_primary_screen",
                return_value=image,
            ):
                self.assertEqual(
                    service.understand_primary_screen("Describe"),
                    "Describe",
                )
        finally:
            image.close()


if __name__ == "__main__":
    unittest.main()
