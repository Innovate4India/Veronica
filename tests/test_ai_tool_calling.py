"""Tests for native Ollama tool-call parsing and bounded orchestration."""

import json
import unittest
from unittest.mock import Mock

from app.ai import (
    OllamaConnectionError,
    OllamaToolCallingService,
    ToolCallingServiceError,
)
from app.ai.ollama_client import OllamaAssistantResponse, OllamaToolCall
from app.config import WebSearchConfig
from app.tools import (
    CalculatorTool,
    JSONValue,
    ParameterSchema,
    Tool,
    ToolRegistry,
    ToolStatus,
    WebSearchTool,
)


class _TestTool(Tool):
    def __init__(
        self,
        *,
        name: str = "lookup",
        execute: Mock | None = None,
        requires_confirmation: bool = False,
    ) -> None:
        self._name = name
        self._execute = execute or Mock(return_value={"answer": "verified"})
        self._requires_confirmation = requires_confirmation

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Return test-only verified data."

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    @property
    def requires_confirmation(self) -> bool:
        return self._requires_confirmation

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        return self._execute(parameters)


def _call(
    name: str = "lookup",
    arguments: object = None,
    *,
    malformed: bool = False,
) -> OllamaAssistantResponse:
    return OllamaAssistantResponse(
        content="",
        tool_calls=(OllamaToolCall(name, arguments, malformed),),
    )


class OllamaToolCallingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry()
        self.tool = _TestTool()
        self.registry.register(self.tool)
        self.provider = Mock()

    def test_converts_registered_tool_to_native_definition(self) -> None:
        self.provider.generate_tool_response.return_value = OllamaAssistantResponse(
            "Final answer"
        )
        service = OllamaToolCallingService(self.provider, self.registry)

        result = service.respond([{"role": "user", "content": "hello"}])

        self.assertEqual(result, "Final answer")
        definitions = self.provider.generate_tool_response.call_args.args[1]
        self.assertEqual(
            definitions,
            (
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "description": "Return test-only verified data.",
                        "parameters": self.tool.parameters_schema,
                    },
                },
            ),
        )

    def test_valid_call_executes_via_registry_and_returns_final_text(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            _call(arguments={"query": "test"}),
            OllamaAssistantResponse("Verified final answer"),
        ]
        service = OllamaToolCallingService(self.provider, self.registry)

        result = service.respond([{"role": "user", "content": "lookup test"}])

        self.assertEqual(result, "Verified final answer")
        self.tool._execute.assert_called_once_with({"query": "test"})
        second_messages = self.provider.generate_tool_response.call_args_list[1].args[0]
        self.assertEqual(second_messages[1]["role"], "assistant")
        self.assertEqual(second_messages[1]["tool_calls"][0]["function"]["name"], "lookup")
        tool_message = second_messages[2]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(
            json.loads(tool_message["content"]),
            {"status": "success", "data": {"answer": "verified"}},
        )

    def test_unknown_tool_becomes_unavailable_tool_result(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            _call(name="not-registered", arguments={}),
            OllamaAssistantResponse("That tool is unavailable."),
        ]
        service = OllamaToolCallingService(self.provider, self.registry)

        result = service.respond([{"role": "user", "content": "do it"}])

        self.assertEqual(result, "That tool is unavailable.")
        self.tool._execute.assert_not_called()
        second_messages = self.provider.generate_tool_response.call_args_list[1].args[0]
        self.assertEqual(
            json.loads(second_messages[-1]["content"])["status"],
            ToolStatus.UNAVAILABLE.value,
        )

    def test_validation_failure_is_returned_to_model_without_execution(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            _call(arguments={"query": 3}),
            OllamaAssistantResponse("The requested parameters were invalid."),
        ]
        service = OllamaToolCallingService(self.provider, self.registry)

        result = service.respond([{"role": "user", "content": "lookup"}])

        self.assertEqual(result, "The requested parameters were invalid.")
        self.tool._execute.assert_not_called()
        second_messages = self.provider.generate_tool_response.call_args_list[1].args[0]
        self.assertEqual(
            json.loads(second_messages[-1]["content"])["status"],
            ToolStatus.VALIDATION_FAILURE.value,
        )

    def test_malformed_tool_call_is_not_executed(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            _call(arguments="not an object", malformed=True),
            OllamaAssistantResponse("The call was malformed."),
        ]
        service = OllamaToolCallingService(self.provider, self.registry)

        result = service.respond([{"role": "user", "content": "lookup"}])

        self.assertEqual(result, "The call was malformed.")
        self.tool._execute.assert_not_called()
        second_messages = self.provider.generate_tool_response.call_args_list[1].args[0]
        self.assertEqual(
            json.loads(second_messages[-1]["content"])["status"],
            ToolStatus.VALIDATION_FAILURE.value,
        )

    def test_valid_web_search_content_envelope_uses_registry(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                '{"name":"web_search","parameters":{"query":"latest Python"}}'
            ),
            OllamaAssistantResponse("Here are current results."),
        ]
        search_tool = _TestTool(name="web_search")
        registry = ToolRegistry()
        registry.register(search_tool)
        service = OllamaToolCallingService(self.provider, registry)

        result = service.respond([{"role": "user", "content": "latest Python"}])

        self.assertEqual(result, "Here are current results.")
        search_tool._execute.assert_called_once_with({"query": "latest Python"})
        second_messages = self.provider.generate_tool_response.call_args_list[1].args[0]
        self.assertEqual(second_messages[1]["role"], "assistant")
        self.assertEqual(second_messages[2]["role"], "tool")
        self.assertEqual(
            json.loads(second_messages[2]["content"]),
            {"status": "success", "data": {"answer": "verified"}},
        )

    def test_malformed_observed_web_search_json_is_rejected_not_executed(self) -> None:
        malformed_text = (
            '{"name":"web_search",""parameters":{"query":'
            '""latest major AI developments 2024"","max_results":10}}'
        )
        self.provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(malformed_text),
            OllamaAssistantResponse("I could not use that malformed search request."),
        ]
        search_tool = _TestTool(name="web_search")
        registry = ToolRegistry()
        registry.register(search_tool)
        service = OllamaToolCallingService(self.provider, registry)

        result = service.respond([{"role": "user", "content": "latest AI news"}])

        self.assertEqual(result, "I could not use that malformed search request.")
        self.assertNotIn(malformed_text, result)
        search_tool._execute.assert_not_called()
        second_messages = self.provider.generate_tool_response.call_args_list[1].args[0]
        tool_result = json.loads(second_messages[-1]["content"])
        self.assertEqual(tool_result["status"], ToolStatus.VALIDATION_FAILURE.value)
        self.assertNotIn(malformed_text, json.dumps(second_messages))

    def test_ordinary_assistant_json_remains_ordinary_text(self) -> None:
        ordinary_json = '{"name":"Veronica","status":"ready"}'
        self.provider.generate_tool_response.return_value = OllamaAssistantResponse(
            ordinary_json
        )
        result = OllamaToolCallingService(self.provider, self.registry).respond(
            [{"role": "user", "content": "show status"}]
        )

        self.assertEqual(result, ordinary_json)
        self.provider.generate_tool_response.assert_called_once()
        self.tool._execute.assert_not_called()

    def test_embedded_web_search_json_is_rejected_not_returned_as_text(self) -> None:
        embedded_text = (
            "The previous parameters were invalid. Correct call:\n"
            '{"name":"web_search",""parameters":{"query":'
            '""latest AI developments"","max_results":8}}'
        )
        self.provider.generate_tool_response.side_effect = [
            _call(
                name="web_search",
                arguments={"query": "latest AI developments"},
            ),
            OllamaAssistantResponse(embedded_text),
            OllamaAssistantResponse("I cannot search with malformed parameters."),
        ]
        search_tool = _TestTool(name="web_search")
        registry = ToolRegistry()
        registry.register(search_tool)

        result = OllamaToolCallingService(
            self.provider,
            registry,
            max_tool_iterations=3,
        ).respond([{"role": "user", "content": "latest AI"}])

        self.assertEqual(result, "I cannot search with malformed parameters.")
        self.assertNotIn("Correct call", result)
        search_tool._execute.assert_called_once_with(
            {"query": "latest AI developments"}
        )
        tool_messages = [
            message
            for message in self.provider.generate_tool_response.call_args_list[2].args[0]
            if message["role"] == "tool"
        ]
        self.assertEqual(
            json.loads(tool_messages[-1]["content"])["status"],
            ToolStatus.VALIDATION_FAILURE.value,
        )

    def test_tool_like_content_after_iteration_limit_is_not_returned(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            _call(arguments={"query": "ordinary lookup"}),
            OllamaAssistantResponse(
                '{"name":"web_search","parameters":{"query":"latest AI"}}'
            ),
        ]
        service = OllamaToolCallingService(
            self.provider,
            self.registry,
            max_tool_iterations=1,
        )

        with self.assertRaises(ToolCallingServiceError):
            service.respond([{"role": "user", "content": "latest AI"}])
        self.tool._execute.assert_called_once_with({"query": "ordinary lookup"})

    def test_content_tool_envelope_with_invalid_arguments_is_not_executed(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                '{"name":"web_search","parameters":{"query":""latest AI""}}'
            ),
            OllamaAssistantResponse("I could not use that malformed request."),
        ]
        search_tool = _TestTool(name="web_search")
        registry = ToolRegistry()
        registry.register(search_tool)
        service = OllamaToolCallingService(self.provider, registry)

        result = service.respond([{"role": "user", "content": "latest AI"}])

        self.assertEqual(result, "I could not use that malformed request.")
        search_tool._execute.assert_not_called()
        second_messages = self.provider.generate_tool_response.call_args_list[1].args[0]
        self.assertEqual(
            json.loads(second_messages[-1]["content"])["status"],
            ToolStatus.VALIDATION_FAILURE.value,
        )

    def test_native_web_search_normalizes_string_result_count_with_both_tools_registered(
        self,
    ) -> None:
        search_provider = Mock()
        search_provider.search.return_value = ()
        search_tool = WebSearchTool(
            provider=search_provider,
            config=WebSearchConfig("tavily", "configured-for-test"),
        )
        calculator = CalculatorTool()
        registry = ToolRegistry()
        registry.register(search_tool)
        registry.register(calculator)
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            _call(
                name="web_search",
                arguments={
                    "query": "latest AI developments today",
                    "max_results": "8",
                },
            ),
            OllamaAssistantResponse("I found current information from web search."),
        ]

        result = OllamaToolCallingService(provider, registry).respond(
            [{"role": "user", "content": "What are the latest AI developments today?"}]
        )

        self.assertEqual(result, "I found current information from web search.")
        definitions = provider.generate_tool_response.call_args_list[0].args[1]
        self.assertEqual(
            {definition["function"]["name"] for definition in definitions},
            {"calculator", "web_search"},
        )
        search_provider.search.assert_called_once_with(
            "latest AI developments today",
            8,
        )
        tool_message = provider.generate_tool_response.call_args_list[1].args[0][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(
            json.loads(tool_message["content"]),
            {
                "status": ToolStatus.SUCCESS.value,
                "data": {
                    "query": "latest AI developments today",
                    "results": [],
                },
            },
        )

    def test_native_web_search_rejects_out_of_range_string_result_count(self) -> None:
        search_provider = Mock()
        search_tool = WebSearchTool(
            provider=search_provider,
            config=WebSearchConfig("tavily", "configured-for-test"),
        )
        registry = ToolRegistry()
        registry.register(search_tool)
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            _call(
                name="web_search",
                arguments={
                    "query": "latest AI developments",
                    "max_results": "10",
                },
            ),
            OllamaAssistantResponse(
                "I could not use those invalid search parameters."
            ),
        ]

        result = OllamaToolCallingService(provider, registry).respond(
            [{"role": "user", "content": "latest AI developments"}]
        )

        self.assertEqual(
            result,
            "I could not use those invalid search parameters.",
        )
        search_provider.search.assert_not_called()
        tool_message = provider.generate_tool_response.call_args_list[1].args[0][-1]
        failure = json.loads(tool_message["content"])
        self.assertEqual(failure["status"], ToolStatus.VALIDATION_FAILURE.value)

    def test_calculator_tool_runs_through_registry_and_returns_result_to_ollama(self) -> None:
        registry = ToolRegistry()
        calculator = CalculatorTool()
        registry.register(calculator)
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            _call(name="calculator", arguments={"expression": "125 * 48"}),
            OllamaAssistantResponse("125 times 48 is 6000."),
        ]

        result = OllamaToolCallingService(provider, registry).respond(
            [{"role": "user", "content": "Calculate 125 times 48."}]
        )

        self.assertEqual(result, "125 times 48 is 6000.")
        definitions = provider.generate_tool_response.call_args_list[0].args[1]
        self.assertEqual(len(definitions), 1)
        self.assertEqual(definitions[0]["function"]["name"], "calculator")
        tool_message = provider.generate_tool_response.call_args_list[1].args[0][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(
            json.loads(tool_message["content"]),
            {"status": "success", "data": {"result": "6000"}},
        )

    def test_execution_failure_is_safely_returned_to_model(self) -> None:
        secret_error = "sensitive failure"
        failing_tool = _TestTool(execute=Mock(side_effect=RuntimeError(secret_error)))
        registry = ToolRegistry()
        registry.register(failing_tool)
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            _call(arguments={"query": "private"}),
            OllamaAssistantResponse("I could not complete that action."),
        ]

        result = OllamaToolCallingService(provider, registry).respond(
            [{"role": "user", "content": "lookup"}]
        )

        self.assertEqual(result, "I could not complete that action.")
        tool_message = provider.generate_tool_response.call_args_list[1].args[0][-1]
        serialized_result = tool_message["content"]
        self.assertEqual(
            json.loads(serialized_result)["status"],
            ToolStatus.EXECUTION_FAILURE.value,
        )
        self.assertNotIn(secret_error, serialized_result)

    def test_timeout_result_is_returned_to_model(self) -> None:
        timeout_tool = _TestTool(execute=Mock(side_effect=TimeoutError("private")))
        registry = ToolRegistry()
        registry.register(timeout_tool)
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            _call(arguments={"query": "slow"}),
            OllamaAssistantResponse("That operation timed out."),
        ]

        result = OllamaToolCallingService(provider, registry).respond(
            [{"role": "user", "content": "lookup"}]
        )

        self.assertEqual(result, "That operation timed out.")
        tool_message = provider.generate_tool_response.call_args_list[1].args[0][-1]
        self.assertEqual(
            json.loads(tool_message["content"])["status"],
            ToolStatus.TIMEOUT.value,
        )
        self.assertNotIn("private", tool_message["content"])

    def test_ollama_failure_propagates_without_tool_execution(self) -> None:
        self.provider.generate_tool_response.side_effect = OllamaConnectionError(
            "offline"
        )
        service = OllamaToolCallingService(self.provider, self.registry)

        with self.assertRaises(OllamaConnectionError):
            service.respond([{"role": "user", "content": "lookup"}])

        self.tool._execute.assert_not_called()

    def test_confirmation_required_tool_is_not_executed(self) -> None:
        confirmation_tool = _TestTool(requires_confirmation=True)
        registry = ToolRegistry()
        registry.register(confirmation_tool)
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            _call(arguments={"query": "sensitive"}),
            OllamaAssistantResponse("Confirmation is needed."),
        ]

        result = OllamaToolCallingService(provider, registry).respond(
            [{"role": "user", "content": "lookup"}]
        )

        self.assertEqual(result, "Confirmation is needed.")
        confirmation_tool._execute.assert_not_called()
        tool_message = provider.generate_tool_response.call_args_list[1].args[0][-1]
        self.assertEqual(
            json.loads(tool_message["content"])["status"],
            ToolStatus.PERMISSION_REQUIRED.value,
        )

    def test_multiple_sequential_tool_rounds_are_supported(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            _call(arguments={"query": "first"}),
            _call(arguments={"query": "second"}),
            OllamaAssistantResponse("Both steps are complete."),
        ]
        service = OllamaToolCallingService(
            self.provider,
            self.registry,
            max_tool_iterations=2,
        )

        result = service.respond([{"role": "user", "content": "two lookups"}])

        self.assertEqual(result, "Both steps are complete.")
        self.assertEqual(self.tool._execute.call_count, 2)
        third_messages = self.provider.generate_tool_response.call_args_list[2].args[0]
        self.assertEqual(
            [message["role"] for message in third_messages],
            ["user", "assistant", "tool", "assistant", "tool"],
        )

    def test_tool_loop_limit_forces_one_final_turn_without_tools(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            _call(arguments={"query": "first"}),
            _call(arguments={"query": "second"}),
            OllamaAssistantResponse("Stopped at the configured limit."),
        ]
        service = OllamaToolCallingService(
            self.provider,
            self.registry,
            max_tool_iterations=2,
        )

        result = service.respond([{"role": "user", "content": "keep going"}])

        self.assertEqual(result, "Stopped at the configured limit.")
        self.assertEqual(self.provider.generate_tool_response.call_count, 3)
        self.assertEqual(
            self.provider.generate_tool_response.call_args_list[-1].args[1],
            (),
        )
        self.assertEqual(self.tool._execute.call_count, 2)

    def test_tool_call_limit_caps_calls_returned_in_one_response(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                content="",
                tool_calls=(
                    OllamaToolCall("lookup", {"query": "first"}),
                    OllamaToolCall("lookup", {"query": "second"}),
                    OllamaToolCall("lookup", {"query": "third"}),
                ),
            ),
            OllamaAssistantResponse("Stopped at the configured limit."),
        ]
        service = OllamaToolCallingService(
            self.provider,
            self.registry,
            max_tool_iterations=2,
        )

        result = service.respond([{"role": "user", "content": "run three"}])

        self.assertEqual(result, "Stopped at the configured limit.")
        self.assertEqual(self.tool._execute.call_count, 2)
        tool_messages = [
            message
            for message in self.provider.generate_tool_response.call_args_list[1].args[0]
            if message["role"] == "tool"
        ]
        self.assertEqual(len(tool_messages), 3)
        self.assertEqual(
            json.loads(tool_messages[-1]["content"])["status"],
            ToolStatus.LIMIT_REACHED.value,
        )

    def test_still_requesting_tools_after_limit_without_final_text_fails(self) -> None:
        self.provider.generate_tool_response.side_effect = [
            _call(arguments={"query": "first"}),
            _call(arguments={"query": "second"}),
            _call(arguments={"query": "unexecuted"}),
        ]
        service = OllamaToolCallingService(
            self.provider,
            self.registry,
            max_tool_iterations=2,
        )

        with self.assertRaises(ToolCallingServiceError):
            service.respond([{"role": "user", "content": "keep going"}])

        self.assertEqual(self.tool._execute.call_count, 2)

    def test_requires_positive_iteration_limit(self) -> None:
        with self.assertRaises(ValueError):
            OllamaToolCallingService(
                self.provider,
                self.registry,
                max_tool_iterations=0,
            )

    def test_empty_final_response_is_not_fabricated(self) -> None:
        self.provider.generate_tool_response.return_value = OllamaAssistantResponse("")

        with self.assertRaises(ToolCallingServiceError):
            OllamaToolCallingService(self.provider, self.registry).respond(
                [{"role": "user", "content": "hello"}]
            )


if __name__ == "__main__":
    unittest.main()
