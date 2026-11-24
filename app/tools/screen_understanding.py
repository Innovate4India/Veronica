"""Validated user-requested local screen understanding."""

import re
from typing import Protocol

from app.tools.base import (
    JSONValue,
    ParameterSchema,
    Tool,
    ToolValidationError,
)

_MAX_QUESTION_LENGTH = 500
_FORBIDDEN_QUESTION_PATTERNS = (
    re.compile(r"(?:https?|data):", re.IGNORECASE),
    re.compile(r"(?:[A-Za-z]:\\|\\\\)"),
    re.compile(r"^[A-Za-z0-9+/]{64,}={0,2}$"),
    re.compile(
        r"(?:^|\s)(?:cmd(?:\.exe)?|powershell(?:\.exe)?|python(?:\.exe)?)(?:\s|$)",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*(?:run|execute|invoke)\b", re.IGNORECASE),
)


class _ScreenVisionService(Protocol):
    def understand_primary_screen(self, question: str) -> str: ...


class ScreenUnderstandingTool(Tool):
    """Capture and ask the configured local Ollama vision model about the screen."""

    def __init__(self, vision_service: _ScreenVisionService) -> None:
        self._vision_service = vision_service

    @property
    def name(self) -> str:
        return "screen_understanding"

    @property
    def description(self) -> str:
        return (
            "Use only when the user explicitly asks what is currently visible "
            "on their screen, asks you to look at or describe it, identify an "
            "open application, or read visible text. Captures only the primary "
            "display and sends that in-memory image only to the configured "
            "local Ollama vision model. This tool does not accept image data, "
            "URLs, paths, model names, or capture targets. If local vision is "
            "unavailable, report that limitation and do not guess screen "
            "contents. This is one explicit capture, not monitoring or "
            "computer control."
        )

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": (
                        "A concise question about the current visible screen; "
                        "not a URL, filesystem path, image/base64 data, command, "
                        "or model override."
                    ),
                    "minLength": 1,
                    "maxLength": _MAX_QUESTION_LENGTH,
                },
            },
            "required": ["question"],
            "additionalProperties": False,
        }

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        question = parameters.get("question")
        if (
            not isinstance(question, str)
            or not question.strip()
            or len(question) > _MAX_QUESTION_LENGTH
            or any(pattern.search(question) for pattern in _FORBIDDEN_QUESTION_PATTERNS)
            or question.lstrip().startswith(("-", ">", "$"))
        ):
            raise ToolValidationError(
                "Provide a short question about the current screen only."
            )
        answer = self._vision_service.understand_primary_screen(question.strip())
        return {
            "status": "success",
            "answer": answer,
            "message": "Answered using the configured local vision model.",
        }
