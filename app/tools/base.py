"""Provider-neutral contracts for future Veronica tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

JSONValue: TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)
ParameterSchema: TypeAlias = dict[str, JSONValue]


class ToolStatus(StrEnum):
    """Outcome categories understood by a future tool-calling orchestrator."""

    SUCCESS = "success"
    VALIDATION_FAILURE = "validation_failure"
    EXECUTION_FAILURE = "execution_failure"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    PERMISSION_REQUIRED = "permission_required"
    LIMIT_REACHED = "limit_reached"


class ToolUnavailableError(Exception):
    """Raised when a registered tool cannot run due to missing configuration."""


class ToolValidationError(Exception):
    """Raised when a tool-specific parameter constraint is not satisfied."""


@dataclass(frozen=True)
class ToolError:
    """Structured tool failure without an exception traceback."""

    code: ToolStatus
    message: str


@dataclass(frozen=True)
class ToolResult:
    """Structured, non-fabricated outcome returned by registry dispatch."""

    status: ToolStatus
    data: JSONValue = None
    error: ToolError | None = None

    @property
    def succeeded(self) -> bool:
        """Whether the operation completed successfully."""
        return self.status is ToolStatus.SUCCESS

    @classmethod
    def success(cls, data: JSONValue) -> ToolResult:
        """Create a successful result containing the tool's actual output."""
        return cls(status=ToolStatus.SUCCESS, data=data)

    @classmethod
    def failure(cls, status: ToolStatus, message: str) -> ToolResult:
        """Create a failed result with a stable status and safe message."""
        if status is ToolStatus.SUCCESS:
            raise ValueError("A successful result cannot contain an error.")
        return cls(status=status, error=ToolError(status, message))


class Tool(ABC):
    """A registered action with a declarative parameter schema."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable tool identifier used for lookup and model-facing selection."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief explanation of the tool's bounded purpose."""

    @property
    @abstractmethod
    def parameters_schema(self) -> ParameterSchema:
        """JSON-schema-like object schema for accepted parameters."""

    @property
    def requires_confirmation(self) -> bool:
        """Whether dispatch requires a separate explicit confirmation."""
        return False

    @abstractmethod
    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        """Perform the action and return only verified output."""
