"""Unit tests for the isolated tool contracts and registry."""

import logging
import unittest
from unittest.mock import Mock

from app.tools import (
    DuplicateToolError,
    InvalidToolDefinitionError,
    JSONValue,
    ParameterSchema,
    Tool,
    ToolRegistry,
    ToolResult,
    ToolStatus,
)


class _EchoTool(Tool):
    def __init__(
        self,
        *,
        name: str = "echo",
        execute: Mock | None = None,
    ) -> None:
        self._name = name
        self.execution = execute or Mock(return_value={"echo": "hello"})

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Return the provided test phrase."

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": {
                "phrase": {"type": "string", "minLength": 1},
                "count": {"type": "integer", "minimum": 1, "maximum": 3},
            },
            "required": ["phrase"],
            "additionalProperties": False,
        }

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        return self.execution(parameters)


class ToolRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry()
        self.tool = _EchoTool()

    def test_register_and_lookup_tool(self) -> None:
        self.registry.register(self.tool)

        self.assertIs(self.registry.get("echo"), self.tool)
        self.assertIsNone(self.registry.get("unknown"))

    def test_lists_tools_in_registration_order(self) -> None:
        second_tool = _EchoTool(name="echo-second")

        self.registry.register(self.tool)
        self.registry.register(second_tool)

        self.assertEqual(
            tuple(tool.name for tool in self.registry.list_tools()),
            ("echo", "echo-second"),
        )

    def test_rejects_duplicate_names(self) -> None:
        self.registry.register(self.tool)

        with self.assertRaises(DuplicateToolError):
            self.registry.register(_EchoTool())

    def test_registry_instances_are_isolated(self) -> None:
        self.registry.register(self.tool)
        another_registry = ToolRegistry()

        self.assertIsNone(another_registry.get("echo"))
        self.assertEqual(another_registry.list_tools(), ())

    def test_sensitive_tool_requires_explicit_confirmation(self) -> None:
        class ConfirmationTool(_EchoTool):
            @property
            def requires_confirmation(self) -> bool:
                return True

        confirmation_tool = ConfirmationTool()
        self.registry.register(confirmation_tool)

        blocked = self.registry.execute("echo", {"phrase": "hello"})
        confirmed = self.registry.execute(
            "echo",
            {"phrase": "hello"},
            confirmed=True,
        )

        self.assertEqual(blocked.status, ToolStatus.PERMISSION_REQUIRED)
        confirmation_tool.execution.assert_called_once_with({"phrase": "hello"})
        self.assertEqual(confirmed.status, ToolStatus.SUCCESS)

    def test_rejects_invalid_name_and_schema(self) -> None:
        with self.assertRaises(InvalidToolDefinitionError):
            self.registry.register(_EchoTool(name=" echo "))

        class InvalidSchemaTool(_EchoTool):
            @property
            def parameters_schema(self) -> ParameterSchema:
                return {"type": "array"}

        with self.assertRaises(InvalidToolDefinitionError):
            self.registry.register(InvalidSchemaTool())

    def test_validates_required_types_ranges_and_extra_parameters(self) -> None:
        self.registry.register(self.tool)
        invalid_requests = (
            {},
            {"phrase": 1},
            {"phrase": "hello", "count": 4},
            {"phrase": "hello", "extra": True},
            ["not", "an", "object"],
        )

        for parameters in invalid_requests:
            with self.subTest(parameters=parameters):
                result = self.registry.execute("echo", parameters)
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)
                self.assertIsNotNone(result.error)
        self.tool.execution.assert_not_called()

    def test_executes_validated_parameters_and_returns_actual_output(self) -> None:
        self.registry.register(self.tool)

        result = self.registry.execute(
            "echo",
            {"phrase": "hello", "count": 2},
        )

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.data, {"echo": "hello"})
        self.assertIsNone(result.error)
        self.tool.execution.assert_called_once_with(
            {"phrase": "hello", "count": 2}
        )

    def test_unknown_tool_returns_unavailable_without_execution(self) -> None:
        self.registry.register(self.tool)

        result = self.registry.execute("not-registered", {})

        self.assertEqual(result.status, ToolStatus.UNAVAILABLE)
        self.assertIsNotNone(result.error)
        self.tool.execution.assert_not_called()

    def test_execution_exception_returns_safe_execution_failure(self) -> None:
        secret_value = "test-password-not-for-logs"
        executor = Mock(side_effect=RuntimeError(secret_value))
        self.registry.register(_EchoTool(execute=executor))

        with self.assertLogs("app.tools.registry", level=logging.INFO) as captured:
            result = self.registry.execute("echo", {"phrase": "private"})

        self.assertEqual(result.status, ToolStatus.EXECUTION_FAILURE)
        if result.error is None:
            self.fail("Execution failure must include a structured error.")
        self.assertEqual(result.error.message, "Tool execution failed.")
        self.assertNotIn(secret_value, "\n".join(captured.output))
        self.assertNotIn("private", "\n".join(captured.output))

    def test_timeout_error_maps_to_timeout_result(self) -> None:
        executor = Mock(side_effect=TimeoutError("timeout details"))
        self.registry.register(_EchoTool(execute=executor))

        result = self.registry.execute("echo", {"phrase": "hello"})

        self.assertEqual(result.status, ToolStatus.TIMEOUT)
        if result.error is None:
            self.fail("Timeout must include a structured error.")
        self.assertEqual(
            result.error.message,
            "Tool execution exceeded its permitted time.",
        )

    def test_tool_result_rejects_success_status_as_failure(self) -> None:
        with self.assertRaises(ValueError):
            ToolResult.failure(ToolStatus.SUCCESS, "not a failure")


if __name__ == "__main__":
    unittest.main()
