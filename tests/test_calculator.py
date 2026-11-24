"""Tests for the bounded, non-executing calculator tool."""

import unittest

from app.tools import CalculatorTool, ToolRegistry, ToolStatus


class CalculatorToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = CalculatorTool()
        self.registry = ToolRegistry()
        self.registry.register(self.tool)

    def _calculate(self, expression: str):
        return self.registry.execute(
            "calculator",
            {"expression": expression},
        )

    def test_basic_arithmetic_examples(self) -> None:
        cases = (
            ("2 + 2", "4"),
            ("125 * 48", "6000"),
            ("(2 + 3) * 4", "20"),
            ("0.1 + 0.2", "0.3"),
            ("2 ** 10", "1024"),
            ("17 % 5", "2"),
            ("-3 + +5", "2"),
            ("2 ** -2", "0.25"),
        )
        for expression, expected in cases:
            with self.subTest(expression=expression):
                result = self._calculate(expression)
                self.assertEqual(result.status, ToolStatus.SUCCESS)
                self.assertEqual(result.data, {"result": expected})

    def test_calculator_schema_requires_only_expression(self) -> None:
        schema = self.tool.parameters_schema
        required = schema["required"]
        self.assertIsInstance(required, list)
        if not isinstance(required, list):
            self.fail("required must be a list.")
        self.assertEqual(required, ["expression"])
        properties = schema["properties"]
        self.assertIsInstance(properties, dict)
        if not isinstance(properties, dict):
            self.fail("properties must be an object.")
        self.assertEqual(set(properties.keys()), {"expression"})
        self.assertIs(schema["additionalProperties"], False)
        self.assertFalse(self.tool.requires_confirmation)

        self.assertEqual(
            self.registry.execute("calculator", {}).status,
            ToolStatus.VALIDATION_FAILURE,
        )
        self.assertEqual(
            self.registry.execute(
                "calculator",
                {"expression": "2 + 2", "extra": "value"},
            ).status,
            ToolStatus.VALIDATION_FAILURE,
        )

    def test_division_and_modulo_by_zero_are_structured_failures(self) -> None:
        for expression in ("1 / 0", "12 % 0", "0 ** -1"):
            with self.subTest(expression=expression):
                result = self._calculate(expression)
                self.assertEqual(result.status, ToolStatus.EXECUTION_FAILURE)
                self.assertIsNotNone(result.error)

    def test_invalid_syntax_and_python_constructs_are_rejected(self) -> None:
        expressions = (
            "2 +",
            "__import__('os')",
            "open('secret.txt')",
            "2.real",
            "x = 5",
            "[value for value in (1, 2)]",
            "lambda: 3",
        )
        for expression in expressions:
            with self.subTest(expression=expression):
                result = self._calculate(expression)
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)

    def test_function_calls_and_unknown_operators_are_rejected(self) -> None:
        for expression in ("abs(-5)", "pow(2, 3)", "2 // 1", "2 << 1"):
            with self.subTest(expression=expression):
                result = self._calculate(expression)
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)

    def test_expression_and_computational_complexity_limits(self) -> None:
        overly_long = "1" * 257
        overly_complex = "+".join("1" for _ in range(40))
        too_deep = "(" * 20 + "1" + ")" * 20
        huge_power = "2 ** 100000"
        huge_result = "10 ** 101"
        for expression in (overly_long, overly_complex, too_deep, huge_power, huge_result):
            with self.subTest(expression=expression[:32]):
                result = self._calculate(expression)
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)

    def test_non_finite_and_extreme_numeric_literals_are_rejected(self) -> None:
        for expression in ("1e999", "1e-999", "0 / 0"):
            with self.subTest(expression=expression):
                result = self._calculate(expression)
                self.assertNotEqual(result.status, ToolStatus.SUCCESS)

    def test_rejects_non_string_expression(self) -> None:
        result = self.registry.execute("calculator", {"expression": 4})
        self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)


if __name__ == "__main__":
    unittest.main()
