"""Tests for safe default-browser URL opening."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.ai import OllamaToolCallingService
from app.ai.ollama_client import OllamaAssistantResponse, OllamaToolCall
from app.config import WebSearchConfig
from app.tools import (
    AppLauncherTool,
    CalculatorTool,
    FileSearchTool,
    JSONValue,
    OpenURLTool,
    SystemInfoTool,
    ToolRegistry,
    ToolStatus,
    WebSearchTool,
)


class OpenURLToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = OpenURLTool()
        self.registry = ToolRegistry()
        self.registry.register(self.tool)

    def _open(self, value: str) -> dict[str, JSONValue]:
        with patch("app.tools.open_url.webbrowser.open", return_value=True) as opener:
            result = self.registry.execute("open_url", {"url": value})
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        opener.assert_called_once()
        if not isinstance(result.data, dict):
            self.fail("Successful open request must return structured data.")
        return result.data

    def test_opens_valid_https_and_http_urls(self) -> None:
        for value in ("https://github.com", "http://example.com"):
            with self.subTest(value=value):
                with patch(
                    "app.tools.open_url.webbrowser.open",
                    return_value=True,
                ) as opener:
                    result = self.registry.execute("open_url", {"url": value})
                self.assertEqual(result.status, ToolStatus.SUCCESS)
                opener.assert_called_once_with(value, new=2)

    def test_normalizes_a_plain_public_domain(self) -> None:
        with patch(
            "app.tools.open_url.webbrowser.open",
            return_value=True,
        ) as opener:
            result = self.registry.execute(
                "open_url",
                {"url": "  github.com  "},
            )

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        opener.assert_called_once_with("https://github.com", new=2)
        if not isinstance(result.data, dict):
            self.fail("Successful open request must return structured data.")
        self.assertEqual(result.data.get("url"), "https://github.com")

    def test_validates_before_requesting_the_browser(self) -> None:
        invalid_urls = (
            "javascript:alert(1)",
            "data:text/html,<h1>bad</h1>",
            "file:///C:/Windows/win.ini",
            "vbscript:msgbox(1)",
            "about:blank",
            "https://",
            "https:///path",
            "https://example.com:bad",
            "https://user:pass@example.com",
            "https://user:password@example.com",
            "not a domain",
            "localhost",
            "C:\\Windows\\System32",
            "C:/Windows/System32",
            "cmd.exe /c whoami",
            "start https://github.com",
            "//example.com",
            "https://-invalid.example",
        )
        with patch("app.tools.open_url.webbrowser.open") as opener:
            for value in invalid_urls:
                with self.subTest(value=value):
                    result = self.registry.execute("open_url", {"url": value})
                    self.assertEqual(
                        result.status,
                        ToolStatus.VALIDATION_FAILURE,
                    )
            opener.assert_not_called()

    def test_empty_whitespace_and_invalid_types_are_rejected(self) -> None:
        with patch("app.tools.open_url.webbrowser.open") as opener:
            for parameters in (
                {"url": ""},
                {"url": " \t "},
                {"url": 5},
                {},
                {"url": "https://github.com", "extra": True},
            ):
                with self.subTest(parameters=parameters):
                    result = self.registry.execute("open_url", parameters)
                    self.assertEqual(
                        result.status,
                        ToolStatus.VALIDATION_FAILURE,
                    )
            opener.assert_not_called()

    def test_result_confirms_request_not_successful_page_load(self) -> None:
        result = self._open("https://github.com")
        serialized = json.dumps(result).casefold()

        self.assertEqual(result.get("status"), "success")
        message = result.get("message")
        if not isinstance(message, str):
            self.fail("Open request message must be text.")
        self.assertIn("requested", message.casefold())
        self.assertNotIn("loaded", serialized)
        self.assertNotIn("successfully opened", serialized)

    def test_browser_failure_is_structured(self) -> None:
        for browser_result in (False, OSError("browser unavailable")):
            with self.subTest(browser_result=browser_result):
                with patch(
                    "app.tools.open_url.webbrowser.open",
                    return_value=browser_result
                    if isinstance(browser_result, bool)
                    else None,
                    side_effect=None
                    if isinstance(browser_result, bool)
                    else browser_result,
                ) as opener:
                    result = self.registry.execute(
                        "open_url",
                        {"url": "https://example.com"},
                    )

                self.assertEqual(result.status, ToolStatus.SUCCESS)
                opener.assert_called_once()
                if not isinstance(result.data, dict):
                    self.fail("Browser failure must return structured data.")
                self.assertEqual(result.data["status"], "unavailable")
                message = result.data["message"]
                if not isinstance(message, str):
                    self.fail("Browser failure message must be text.")
                self.assertNotIn("loaded", message)

    def test_no_shell_or_subprocess_is_used(self) -> None:
        with (
            patch("os.system", side_effect=AssertionError("shell execution")),
            patch("subprocess.Popen", side_effect=AssertionError("subprocess")),
            patch("subprocess.run", side_effect=AssertionError("subprocess")),
            patch("app.tools.open_url.webbrowser.open", return_value=True) as opener,
        ):
            result = self.registry.execute(
                "open_url",
                {"url": "https://example.com"},
            )

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        opener.assert_called_once_with("https://example.com", new=2)


class OpenURLToolCallingIntegrationTests(unittest.TestCase):
    def test_explicit_open_request_dispatches_open_url_via_registry(self) -> None:
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                "",
                (OllamaToolCall("open_url", {"url": "https://www.youtube.com/"}),),
            ),
            OllamaAssistantResponse(
                "I requested your default browser to open YouTube."
            ),
        ]
        open_tool = OpenURLTool()
        mocked_result = {
            "status": "success",
            "url": "https://www.youtube.com/",
            "message": "Requested the default browser to open the URL.",
        }
        with patch.object(open_tool, "execute", return_value=mocked_result) as execute:
            registry = ToolRegistry()
            registry.register(
                WebSearchTool(
                    provider=Mock(),
                    config=WebSearchConfig("tavily", ""),
                )
            )
            registry.register(CalculatorTool())
            registry.register(FileSearchTool((Path("D:/veronica"),)))
            registry.register(SystemInfoTool())
            registry.register(open_tool)
            registry.register(AppLauncherTool())

            response = OllamaToolCallingService(provider, registry).respond(
                [{"role": "user", "content": "Open YouTube"}]
            )

        self.assertEqual(
            response,
            "I requested your default browser to open YouTube.",
        )
        execute.assert_called_once_with({"url": "https://www.youtube.com/"})
        definitions = provider.generate_tool_response.call_args_list[0].args[1]
        self.assertEqual(
            {definition["function"]["name"] for definition in definitions},
            {
                "web_search",
                "calculator",
                "file_search",
                "system_info",
                "open_url",
                "app_launcher",
            },
        )
        messages = provider.generate_tool_response.call_args_list[1].args[0]
        result = json.loads(messages[-1]["content"])
        if not isinstance(result, dict):
            self.fail("Tool reply must be a JSON object.")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"], mocked_result)


if __name__ == "__main__":
    unittest.main()
