"""Explicit allowlist and validation boundary for future tool execution."""

import logging
import math
from copy import deepcopy
from time import monotonic
from typing import TypeGuard

from app.tools.base import (
    JSONValue,
    ParameterSchema,
    Tool,
    ToolResult,
    ToolStatus,
    ToolUnavailableError,
    ToolValidationError,
)

_LOGGER = logging.getLogger(__name__)


class DuplicateToolError(ValueError):
    """Raised when a tool name is already registered."""


class InvalidToolDefinitionError(ValueError):
    """Raised when a tool has an invalid identity or parameter schema."""


class ToolRegistry:
    """Instance-scoped allowlist of tools; no implicit/global registrations."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._schemas: dict[str, ParameterSchema] = {}

    def register(self, tool: Tool) -> None:
        """Add a tool after validating its name and object parameter schema."""
        name = tool.name.strip()
        if not name or name != tool.name:
            raise InvalidToolDefinitionError(
                "Tool names must be non-empty and have no surrounding whitespace."
            )
        if name in self._tools:
            raise DuplicateToolError(f"Tool {name!r} is already registered.")
        if not tool.description.strip():
            raise InvalidToolDefinitionError("Tool descriptions must not be empty.")
        schema = deepcopy(tool.parameters_schema)
        _validate_schema_definition(schema)
        self._tools[name] = tool
        self._schemas[name] = schema

    def get(self, name: str) -> Tool | None:
        """Return a registered tool, or None when it is not allowlisted."""
        return self._tools.get(name)

    def list_tools(self) -> tuple[Tool, ...]:
        """Return a stable snapshot in registration order."""
        return tuple(self._tools.values())

    def parameters_schema_for(self, name: str) -> ParameterSchema | None:
        """Return the exact defensive schema snapshot used for validation."""
        schema = self._schemas.get(name)
        return deepcopy(schema) if schema is not None else None

    def execute(
        self,
        name: str,
        parameters: object,
        *,
        confirmed: bool = False,
    ) -> ToolResult:
        """Validate and invoke one registered tool, mapping failures by category.

        Logs intentionally omit arguments, results, and exception messages,
        which could contain credentials or user-provided private content.
        """
        started_at = monotonic()
        tool = self._tools.get(name)
        if tool is None:
            result = ToolResult.failure(
                ToolStatus.UNAVAILABLE,
                f"Tool {name!r} is not available.",
            )
            self._log_outcome(name, result.status, started_at)
            return result
        if tool.requires_confirmation and not confirmed:
            result = ToolResult.failure(
                ToolStatus.PERMISSION_REQUIRED,
                "This tool requires explicit confirmation before execution.",
            )
            self._log_outcome(name, result.status, started_at)
            return result
        if not _is_json_object(parameters):
            result = ToolResult.failure(
                ToolStatus.VALIDATION_FAILURE,
                "Tool parameters must be a JSON object.",
            )
            self._log_outcome(name, result.status, started_at)
            return result
        validation_error = _validate_parameters(
            parameters,
            self._schemas[name],
        )
        if validation_error is not None:
            result = ToolResult.failure(
                ToolStatus.VALIDATION_FAILURE,
                validation_error,
            )
            self._log_outcome(name, result.status, started_at)
            return result
        try:
            data = tool.execute(parameters)
            if not _is_json_value(data):
                raise TypeError("Tools must return a JSON-compatible result.")
            result = ToolResult.success(data)
        except ToolValidationError as error:
            result = ToolResult.failure(
                ToolStatus.VALIDATION_FAILURE,
                str(error),
            )
        except ToolUnavailableError as error:
            result = ToolResult.failure(
                ToolStatus.UNAVAILABLE,
                str(error),
            )
        except TimeoutError:
            result = ToolResult.failure(
                ToolStatus.TIMEOUT,
                "Tool execution exceeded its permitted time.",
            )
        except Exception:
            result = ToolResult.failure(
                ToolStatus.EXECUTION_FAILURE,
                "Tool execution failed.",
            )
        self._log_outcome(name, result.status, started_at)
        return result

    @staticmethod
    def _log_outcome(name: str, status: ToolStatus, started_at: float) -> None:
        elapsed_ms = (monotonic() - started_at) * 1000
        _LOGGER.info(
            "Tool execution tool=%s status=%s elapsed_ms=%.1f",
            name,
            status.value,
            elapsed_ms,
        )


def _validate_schema_definition(schema: ParameterSchema) -> None:
    _validate_value_schema(schema, "tool parameters")


def _validate_value_schema(schema: object, location: str) -> None:
    if not isinstance(schema, dict):
        raise InvalidToolDefinitionError(
            f"Schema for {location} must be an object."
        )
    schema_type = schema.get("type")
    allowed_keywords = {
        "type",
        "description",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "required",
        "properties",
        "items",
        "additionalProperties",
    }
    if any(keyword not in allowed_keywords for keyword in schema):
        raise InvalidToolDefinitionError(
            f"Schema for {location} contains an unsupported keyword."
        )
    if not isinstance(schema_type, str) or schema_type not in {
        "string",
        "number",
        "integer",
        "boolean",
        "object",
        "array",
    }:
        raise InvalidToolDefinitionError(
            f"Schema for {location} has an unsupported type."
        )
    enum_values = schema.get("enum")
    if enum_values is not None and (
        not isinstance(enum_values, list)
        or any(not _is_json_value(value) for value in enum_values)
    ):
        raise InvalidToolDefinitionError(
            f"Enum for {location} must contain JSON values."
        )
    for bound_name in ("minimum", "maximum"):
        bound = schema.get(bound_name)
        if bound is not None and (
            schema_type not in {"number", "integer"}
            or not isinstance(bound, (int, float))
            or isinstance(bound, bool)
            or not math.isfinite(bound)
        ):
            raise InvalidToolDefinitionError(
                f"{bound_name} for {location} must be a finite numeric bound."
            )
    for bound_name in ("minLength", "maxLength", "minItems", "maxItems"):
        bound = schema.get(bound_name)
        if bound is not None and (
            (bound_name.endswith("Length") and schema_type != "string")
            or (bound_name.endswith("Items") and schema_type != "array")
            or not isinstance(bound, int)
            or isinstance(bound, bool)
            or bound < 0
        ):
            raise InvalidToolDefinitionError(
                f"{bound_name} for {location} must be a non-negative integer "
                "for the matching schema type."
            )
    if schema_type == "object":
        if schema.get("additionalProperties", False) is not False:
            raise InvalidToolDefinitionError(
                f"Schema for {location} must disallow additional properties."
            )
        properties = schema.get("properties", {})
        if not _is_json_object(properties):
            raise InvalidToolDefinitionError(
                f"Properties for {location} must be an object."
            )
        required = schema.get("required", [])
        if not isinstance(required, list) or any(
            not isinstance(name, str) for name in required
        ):
            raise InvalidToolDefinitionError(
                f"Required properties for {location} must be a list of names."
            )
        if any(name not in properties for name in required):
            raise InvalidToolDefinitionError(
                f"Required properties for {location} must be declared."
            )
        for property_name, property_schema in properties.items():
            _validate_value_schema(
                property_schema,
                f"{location}.{property_name}",
            )
    elif "properties" in schema or "required" in schema or "additionalProperties" in schema:
        raise InvalidToolDefinitionError(
            f"Object-only schema keywords cannot be used for {location}."
        )
    if schema_type == "array":
        if "items" not in schema:
            raise InvalidToolDefinitionError(
                f"Array schema for {location} must declare item types."
            )
        _validate_value_schema(schema["items"], f"{location}[]")
    elif "items" in schema:
        raise InvalidToolDefinitionError(
            f"Array-only schema keyword cannot be used for {location}."
        )


def _validate_parameters(
    parameters: dict[str, JSONValue],
    schema: ParameterSchema,
) -> str | None:
    return _validate_value(parameters, schema, "parameters")


def _validate_value(
    value: JSONValue,
    schema: object,
    location: str,
) -> str | None:
    if not isinstance(schema, dict):
        return "Registered tool schema is invalid."
    if not _matches_schema_type(value, schema.get("type")):
        return f"{location} must be of type {schema.get('type')}."
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        return f"{location} is not an allowed value."
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            return f"{location} must be finite."
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            return f"{location} is below its minimum."
        if isinstance(maximum, (int, float)) and value > maximum:
            return f"{location} exceeds its maximum."
    if isinstance(value, str):
        min_length = schema.get("minLength", 0)
        max_length = schema.get("maxLength")
        if len(value) < min_length:
            return f"{location} is shorter than its minimum length."
        if isinstance(max_length, int) and len(value) > max_length:
            return f"{location} exceeds its maximum length."
    if isinstance(value, list):
        min_items = schema.get("minItems", 0)
        max_items = schema.get("maxItems")
        if len(value) < min_items:
            return f"{location} contains too few items."
        if isinstance(max_items, int) and len(value) > max_items:
            return f"{location} contains too many items."
        item_schema = schema.get("items")
        for index, item in enumerate(value):
            if not _is_json_value(item):
                return f"{location}[{index}] is not a JSON value."
            item_error = _validate_value(item, item_schema, f"{location}[{index}]")
            if item_error:
                return item_error
    if _is_json_object(value):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not _is_json_object(properties) or not isinstance(required, list):
            return "Registered tool schema is invalid."
        missing = [name for name in required if name not in value]
        if missing:
            return f"{location} is missing required properties: {', '.join(missing)}."
        extra = [name for name in value if name not in properties]
        if extra:
            return f"{location} contains undeclared properties: {', '.join(extra)}."
        for name, nested_value in value.items():
            nested_schema = properties.get(name)
            nested_error = _validate_value(
                nested_value,
                nested_schema,
                f"{location}.{name}",
            )
            if nested_error:
                return nested_error
    return None


def _matches_schema_type(value: JSONValue, expected_type: object) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return _is_json_object(value)
    if expected_type == "array":
        return isinstance(value, list)
    else:
        return False


def _is_json_value(value: object) -> TypeGuard[JSONValue]:
    if value is None or isinstance(value, (bool, int, str)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in value.items()
        )
    return False


def _is_json_object(value: object) -> TypeGuard[dict[str, JSONValue]]:
    return isinstance(value, dict) and all(
        isinstance(key, str) and _is_json_value(item)
        for key, item in value.items()
    )
