"""Explicit, local-only capture of the Windows primary display."""

from __future__ import annotations

import importlib
import sys
from time import perf_counter
from typing import TYPE_CHECKING, Protocol, cast

from app.tools.base import (
    JSONValue,
    ParameterSchema,
    Tool,
    ToolUnavailableError,
    ToolValidationError,
)

if TYPE_CHECKING:
    from PIL import Image


class _ImageGrabModule(Protocol):
    def grab(self) -> Image.Image: ...


class ScreenshotTool(Tool):
    """Capture a primary-screen image in memory and return metadata only."""

    @property
    def name(self) -> str:
        return "screenshot"

    @property
    def description(self) -> str:
        return (
            "Capture the current primary display locally, in memory only, when "
            "the user explicitly asks Veronica to take a screenshot, capture "
            "the screen, or look at the current screen (for example, 'Take a "
            "screenshot', 'Capture my screen', 'What's on my screen?', or "
            "'Look at my screen'). This tool does not provide image bytes to "
            "Ollama and does not interpret the image. After a successful "
            "capture, tell the user that screen understanding is not "
            "implemented yet; never describe or infer screen contents. Do not "
            "capture unless explicitly requested. No monitoring, recording, "
            "upload, saving, or computer control is performed."
        )

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        """Capture once, then discard the image after extracting safe metadata."""
        if parameters:
            raise ToolValidationError("Screenshot does not accept parameters.")
        started_at = perf_counter()
        image = capture_primary_screen()
        try:
            width, height = image.size
            duration_ms = round((perf_counter() - started_at) * 1000, 1)
            return {
                "status": "success",
                "width": width,
                "height": height,
                "format": "PNG",
                "capture_duration_ms": duration_ms,
                "message": (
                    "Screenshot captured locally. Screen understanding is not "
                    "implemented yet."
                ),
            }
        finally:
            image.close()


def capture_primary_screen() -> Image.Image:
    """Capture one primary-display PIL image, without persisting it."""
    if not _is_windows():
        raise ToolUnavailableError(
            "Primary-display capture is unavailable on this platform."
        )
    try:
        image_grab = importlib.import_module("PIL.ImageGrab")
    except ImportError:
        raise ToolUnavailableError(
            "Screenshot capture requires the Pillow package."
        ) from None
    return cast(_ImageGrabModule, image_grab).grab()


def _is_windows() -> bool:
    return sys.platform == "win32"
