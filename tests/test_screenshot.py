"""Privacy and registration tests for the local screenshot tool."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.ai import OllamaToolCallingService
from app.ai.ollama_client import OllamaAssistantResponse, OllamaToolCall
from app.config import WebSearchConfig
from app.ai.ollama_client import OllamaClient
from app.tools import JSONValue, ScreenshotTool, ToolRegistry, ToolResult, ToolStatus
from app.tools.screenshot import capture_primary_screen
from dev_ai import _create_tool_registry


def _result_data(result: ToolResult) -> dict[str, JSONValue]:
    if not isinstance(result.data, dict):
        raise AssertionError("Tool result data should be an object.")
    return result.data


def _error_message(result: ToolResult) -> str:
    if result.error is None:
        raise AssertionError("Tool result should contain a safe error.")
    return result.error.message


class ScreenshotToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = ScreenshotTool()
        self.registry = ToolRegistry()
        self.registry.register(self.tool)
        self.image = SimpleNamespace(size=(1366, 768), close=Mock())

    def _execute_with_image(self):
        with patch(
            "app.tools.screenshot.capture_primary_screen",
            return_value=self.image,
        ):
            result = self.registry.execute("screenshot", {})
        return result

    def test_success_returns_only_safe_image_metadata_and_closes_image(self) -> None:
        result = self._execute_with_image()
        data = _result_data(result)

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["width"], 1366)
        self.assertEqual(data["height"], 768)
        self.assertEqual(data["format"], "PNG")
        duration_ms = data["capture_duration_ms"]
        if not isinstance(duration_ms, (int, float)):
            self.fail("Capture duration must be numeric.")
        self.assertGreaterEqual(duration_ms, 0)
        self.assertEqual(
            data["message"],
            "Screenshot captured locally. Screen understanding is not "
            "implemented yet.",
        )
        self.assertNotIn(self.image, data.values())
        self.image.close.assert_called_once_with()

    def test_capture_uses_imagegrab_only_when_capture_helper_is_called(self) -> None:
        image_grab = SimpleNamespace(grab=Mock(return_value=self.image))
        with (
            patch("app.tools.screenshot.sys.platform", "win32"),
            patch(
                "app.tools.screenshot.importlib.import_module",
                return_value=image_grab,
            ) as import_module,
        ):
            self.assertIs(capture_primary_screen(), self.image)

        import_module.assert_called_once_with("PIL.ImageGrab")
        image_grab.grab.assert_called_once_with()

    def test_missing_pillow_returns_unavailable_without_exception_details(self) -> None:
        with (
            patch("app.tools.screenshot.sys.platform", "win32"),
            patch(
                "app.tools.screenshot.importlib.import_module",
                side_effect=ModuleNotFoundError("Pillow private detail"),
            ),
        ):
            result = self.registry.execute("screenshot", {})

        self.assertEqual(result.status, ToolStatus.UNAVAILABLE)
        message = _error_message(result)
        self.assertNotIn("Pillow private detail", message)
        self.assertIn("Pillow", message)

    def test_capture_failure_is_returned_without_internal_exception_details(self) -> None:
        with patch(
            "app.tools.screenshot.capture_primary_screen",
            side_effect=PermissionError("private display API detail"),
        ):
            result = self.registry.execute("screenshot", {})

        self.assertEqual(result.status, ToolStatus.EXECUTION_FAILURE)
        message = _error_message(result)
        self.assertEqual(message, "Tool execution failed.")
        self.assertNotIn("private display API detail", message)

    def test_non_windows_platform_is_reported_unavailable(self) -> None:
        with patch("app.tools.screenshot.sys.platform", "linux"):
            result = self.registry.execute("screenshot", {})

        self.assertEqual(result.status, ToolStatus.UNAVAILABLE)
        self.assertIn("unavailable on this platform", _error_message(result))

    def test_capture_performs_no_filesystem_subprocess_or_network_actions(self) -> None:
        with (
            patch(
                "app.tools.screenshot.capture_primary_screen",
                return_value=self.image,
            ),
            patch("builtins.open", side_effect=AssertionError("filesystem access")),
            patch.object(
                Path,
                "write_bytes",
                side_effect=AssertionError("filesystem write"),
            ),
            patch.object(
                Path,
                "write_text",
                side_effect=AssertionError("filesystem write"),
            ),
            patch("PIL.Image.Image.save", side_effect=AssertionError("image save")),
            patch("subprocess.Popen", side_effect=AssertionError("process launch")),
            patch("app.tools.web_search.urlopen", side_effect=AssertionError("network")),
            patch(
                "app.tools.web_search.TavilySearchProvider.search",
                side_effect=AssertionError("web search"),
            ),
            patch(
                "app.memory.service.MemoryService.save_memory",
                side_effect=AssertionError("memory persistence"),
            ),
            patch(
                "app.memory.service.MemoryService.search_memories",
                side_effect=AssertionError("memory lookup"),
            ),
        ):
            result = self.registry.execute("screenshot", {})

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.image.close.assert_called_once_with()

    def test_tool_description_is_explicit_about_capture_and_no_vision(self) -> None:
        description = self.tool.description
        for expected in (
            "explicitly asks",
            "primary display locally",
            "does not provide image bytes to Ollama",
            "does not interpret the image",
            "never describe or infer screen contents",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, description)

    def test_enabled_registry_keeps_existing_tools_and_registers_screenshot(self) -> None:
        registry = _create_tool_registry(
            WebSearchConfig("tavily", "test-key"),
            (Path("D:/veronica"),),
            Mock(spec=OllamaClient),
        )

        self.assertEqual(
            tuple(tool.name for tool in registry.list_tools()),
            (
                "web_search",
                "calculator",
                "file_search",
                "system_info",
                "open_url",
                "app_launcher",
                "screenshot",
                "screen_understanding",
            ),
        )
        self.assertEqual(
            registry.parameters_schema_for("screenshot"),
            {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        )

    def test_ollama_tool_call_reaches_registry_and_receives_metadata_only(self) -> None:
        registry = _create_tool_registry(
            WebSearchConfig("tavily", "test-key"),
            (Path("D:/veronica"),),
            Mock(spec=OllamaClient),
        )
        image = self.image
        with patch(
            "app.tools.screenshot.capture_primary_screen",
            return_value=image,
        ):
            provider = Mock()
            provider.generate_tool_response.side_effect = [
                OllamaAssistantResponse(
                    "",
                    (OllamaToolCall("screenshot", {}),),
                ),
                OllamaAssistantResponse(
                    "Screenshot captured locally, but I cannot interpret it yet."
                ),
            ]

            response = OllamaToolCallingService(provider, registry).respond(
                [{"role": "user", "content": "Take a screenshot"}]
            )

        self.assertIn("cannot interpret it yet", response)
        definitions = provider.generate_tool_response.call_args_list[0].args[1]
        screenshot_definition = next(
            definition["function"]
            for definition in definitions
            if definition["function"]["name"] == "screenshot"
        )
        self.assertIn("does not interpret the image", screenshot_definition["description"])
        tool_messages = provider.generate_tool_response.call_args_list[1].args[0]
        result_data = tool_messages[-1]["content"]
        self.assertIn('"width":1366', result_data)
        self.assertNotIn("base64", result_data.casefold())
        self.assertNotIn("bytes", result_data.casefold())
        image.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
