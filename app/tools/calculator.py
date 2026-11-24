"""Safe, bounded arithmetic calculator for Veronica tool calls."""

import ast
import io
import math
import operator
import re
import tokenize
from decimal import (
    Decimal,
    DecimalException,
    InvalidOperation,
    localcontext,
)
from typing import Callable

from app.tools.base import JSONValue, ParameterSchema, Tool, ToolValidationError

MAX_EXPRESSION_LENGTH = 256
MAX_EXPRESSION_NODES = 64
MAX_EXPRESSION_DEPTH = 16
MAX_POWER_MAGNITUDE = 100
MAX_RESULT_ADJUSTED_EXPONENT = 100
DECIMAL_PRECISION = 50

_DECIMAL_LITERAL = re.compile(
    r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z"
)
_BINARY_OPERATORS: dict[type[ast.operator], Callable[[Decimal, Decimal], Decimal]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}


class CalculatorTool(Tool):
    """Evaluate bounded arithmetic expressions without executing Python code."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "Calculate mathematical arithmetic expressions. Supports decimal "
            "numbers, +, -, *, /, %, exponentiation with **, and parentheses. "
            "Use this for calculations; pass one expression string."
        )

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_EXPRESSION_LENGTH,
                    "description": "A mathematical arithmetic expression only.",
                },
            },
            "required": ["expression"],
            "additionalProperties": False,
        }

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        """Evaluate exactly one validated expression and return its numeric text."""
        expression = parameters.get("expression")
        if (
            not isinstance(expression, str)
            or not expression.strip()
            or len(expression) > MAX_EXPRESSION_LENGTH
        ):
            raise ToolValidationError(
                "expression must be a non-empty string within the length limit."
            )

        try:
            _validate_source(expression)
            tree = ast.parse(expression, mode="eval")
            _validate_complexity(tree)
            with localcontext() as context:
                context.prec = DECIMAL_PRECISION
                context.Emax = MAX_RESULT_ADJUSTED_EXPONENT
                context.Emin = -MAX_RESULT_ADJUSTED_EXPONENT
                result = _evaluate(tree.body)
        except ZeroDivisionError:
            raise
        except (SyntaxError, ValueError, TypeError, DecimalException, OverflowError):
            raise ToolValidationError(
                "expression is not a supported, bounded arithmetic expression."
            ) from None

        if not result.is_finite():
            raise ToolValidationError("expression result must be finite.")
        if result and abs(result.adjusted()) > MAX_RESULT_ADJUSTED_EXPONENT:
            raise ToolValidationError("expression result exceeds the supported range.")
        return {"result": _format_decimal(result)}


def _validate_complexity(tree: ast.Expression) -> None:
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_EXPRESSION_NODES:
        raise ToolValidationError("expression is too complex.")
    if _tree_depth(tree) > MAX_EXPRESSION_DEPTH:
        raise ToolValidationError("expression is too deeply nested.")


def _validate_source(expression: str) -> None:
    parenthesis_depth = 0
    try:
        for token in tokenize.generate_tokens(io.StringIO(expression).readline):
            if token.type == tokenize.NUMBER:
                if not _DECIMAL_LITERAL.fullmatch(token.string):
                    raise ToolValidationError(
                        "only ordinary decimal numeric literals are supported."
                    )
                literal = Decimal(token.string)
                if (
                    not literal.is_finite()
                    or literal
                    and abs(literal.adjusted()) > MAX_RESULT_ADJUSTED_EXPONENT
                ):
                    raise ToolValidationError(
                        "numeric literal exceeds the supported range."
                    )
            elif token.type == tokenize.OP:
                if token.string == "(":
                    parenthesis_depth += 1
                    if parenthesis_depth > MAX_EXPRESSION_DEPTH:
                        raise ToolValidationError(
                            "expression is too deeply nested."
                        )
                elif token.string == ")":
                    parenthesis_depth -= 1
    except (tokenize.TokenError, InvalidOperation):
        raise ToolValidationError(
            "expression is not a supported, bounded arithmetic expression."
        ) from None


def _tree_depth(node: ast.AST) -> int:
    children = list(ast.iter_child_nodes(node))
    return 1 if not children else 1 + max(_tree_depth(child) for child in children)


def _evaluate(node: ast.expr) -> Decimal:
    if isinstance(node, ast.Constant):
        return _number_constant(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _evaluate(node.operand)
        return operand if isinstance(node.op, ast.UAdd) else -operand
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        operation = _BINARY_OPERATORS.get(type(node.op))
        if operation is not None:
            if isinstance(node.op, (ast.Div, ast.Mod)) and right.is_zero():
                raise ZeroDivisionError
            return operation(left, right)
        if isinstance(node.op, ast.Pow):
            return _power(left, right)
    raise ToolValidationError(
        "expression contains an unsupported operation or Python construct."
    )


def _number_constant(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolValidationError("only decimal numeric literals are supported.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ToolValidationError("numeric literals must be finite.")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ToolValidationError("numeric literal is invalid.") from None
    if not number.is_finite():
        raise ToolValidationError("numeric literals must be finite.")
    if number and abs(number.adjusted()) > MAX_RESULT_ADJUSTED_EXPONENT:
        raise ToolValidationError("numeric literal exceeds the supported range.")
    return number


def _power(base: Decimal, exponent: Decimal) -> Decimal:
    if not exponent.is_finite() or exponent != exponent.to_integral_value():
        raise ToolValidationError("exponentiation requires an integer exponent.")
    if abs(exponent) > MAX_POWER_MAGNITUDE:
        raise ToolValidationError("exponent magnitude exceeds the supported limit.")
    if base.is_zero() and exponent.is_signed():
        raise ZeroDivisionError
    return base**int(exponent)


def _format_decimal(value: Decimal) -> str:
    if value.is_zero():
        return "0"
    normalized = value.normalize()
    return format(normalized, "f")
