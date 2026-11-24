"""Tests for the read-only local system information tool."""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.ai import OllamaToolCallingService
from app.ai.ollama_client import OllamaAssistantResponse, OllamaToolCall
from app.config import WebSearchConfig
from app.tools import (
    CalculatorTool,
    FileSearchTool,
    JSONValue,
    SystemInfoTool,
    ToolRegistry,
    ToolStatus,
    WebSearchTool,
)


class SystemInfoToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = SystemInfoTool()
        self.registry = ToolRegistry()
        self.registry.register(self.tool)

    def _execute(self, category: str | None = None) -> dict[str, JSONValue]:
        parameters = {} if category is None else {"category": category}
        result = self.registry.execute("system_info", parameters)
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        if not isinstance(result.data, dict):
            self.fail("System information must be returned as a structured object.")
        return result.data

    def test_schema_and_name_are_explicit_and_bounded(self) -> None:
        self.assertEqual(self.tool.name, "system_info")
        self.assertEqual(
            self.tool.parameters_schema["properties"]["category"]["enum"],
            ["overview", "os", "cpu", "memory", "python", "disk"],
        )

    def test_each_supported_category_returns_only_its_requested_group(self) -> None:
        collectors = {
            "os": "_os_info",
            "cpu": "_cpu_info",
            "memory": "_memory_info",
            "python": "_python_info",
            "disk": "_disk_info",
        }
        for category, collector_name in collectors.items():
            with self.subTest(category=category):
                with patch.object(
                    SystemInfoTool,
                    collector_name,
                    return_value={"test_metric": 1},
                ):
                    data = self._execute(category)
                self.assertEqual(data["category"], category)
                self.assertEqual(
                    data["information"],
                    {category: {"test_metric": 1}},
                )

    def test_omitted_category_returns_a_bounded_general_overview(self) -> None:
        with (
            patch.object(SystemInfoTool, "_os_info", return_value={"name": "Windows"}),
            patch.object(SystemInfoTool, "_cpu_info", return_value={"logical_cpu_count": 8}),
            patch.object(SystemInfoTool, "_memory_info", return_value={"total_bytes": 4096}),
            patch.object(SystemInfoTool, "_python_info", return_value={"version": "3.14"}),
            patch.object(SystemInfoTool, "_disk_info", return_value={"free_bytes": 1024}),
        ):
            data = self._execute()

        information = data["information"]
        self.assertEqual(
            set(information),
            {"os", "cpu", "memory", "python", "disk"},
        )
        self.assertLess(len(json.dumps(data)), 2048)

    def test_invalid_categories_are_rejected(self) -> None:
        for category in ("processes", "users", "", 3):
            with self.subTest(category=category):
                result = self.registry.execute(
                    "system_info",
                    {"category": category},
                )
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)

    def test_unavailable_metric_does_not_fail_other_overview_categories(self) -> None:
        with (
            patch.object(
                SystemInfoTool,
                "_os_info",
                side_effect=OSError("private platform detail"),
            ),
            patch.object(SystemInfoTool, "_cpu_info", return_value={"logical_cpu_count": 4}),
            patch.object(SystemInfoTool, "_memory_info", return_value={"total_bytes": 1024}),
            patch.object(SystemInfoTool, "_python_info", return_value={"version": "3.14"}),
            patch.object(SystemInfoTool, "_disk_info", return_value={"free_bytes": 512}),
        ):
            data = self._execute()

        information = data["information"]
        self.assertEqual(
            information["os"],
            {
                "status": "unavailable",
                "reason": "This system metric is unavailable on this computer.",
            },
        )
        self.assertEqual(information["cpu"], {"logical_cpu_count": 4})
        self.assertNotIn("private platform detail", json.dumps(data))

    def test_real_metric_formatters_do_not_include_private_identifiers(self) -> None:
        with (
            patch("app.tools.system_info._processor_name", return_value="Test CPU"),
            patch("app.tools.system_info._physical_cpu_count", return_value=None),
            patch("app.tools.system_info.os.cpu_count", return_value=8),
            patch("app.tools.system_info._physical_memory", return_value=(1000, 250)),
            patch("app.tools.system_info.shutil.disk_usage") as disk_usage,
        ):
            disk_usage.return_value = type(
                "DiskUsage",
                (),
                {"total": 1000, "used": 600, "free": 400},
            )()
            cpu = self.tool._cpu_info()
            memory = self.tool._memory_info()
            python = self.tool._python_info()
            disk = self.tool._disk_info()

        self.assertEqual(cpu["logical_cpu_count"], 8)
        self.assertEqual(cpu["processor_name"], "Test CPU")
        self.assertEqual(memory["used_bytes"], 750)
        self.assertEqual(memory["usage_percent"], 75.0)
        self.assertEqual(python["implementation"], "CPython")
        self.assertEqual(disk["scope"], "Veronica project drive")
        self.assertNotIn(str(os.environ.get("USERPROFILE", "")), json.dumps(disk))
        self.assertNotIn("path", disk)
        self.assertNotIn("username", json.dumps({"cpu": cpu, "memory": memory}))

    def test_missing_individual_cpu_metrics_are_structured(self) -> None:
        with (
            patch("app.tools.system_info._processor_name", return_value=None),
            patch("app.tools.system_info._physical_cpu_count", return_value=None),
            patch("app.tools.system_info.os.cpu_count", return_value=None),
        ):
            result = self.tool._cpu_info()

        self.assertEqual(result["logical_cpu_count"]["status"], "unavailable")
        self.assertEqual(result["physical_cpu_count"]["status"], "unavailable")
        self.assertEqual(result["processor_name"]["status"], "unavailable")

    def test_no_environment_variables_or_credentials_are_returned(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TEST_API_KEY": "must-not-leak",
                "TEST_PASSWORD": "private-password",
                "HOME": "C:\\Private\\Home",
            },
        ):
            serialized = json.dumps(self._execute())

        for secret in ("must-not-leak", "private-password", "TEST_API_KEY", "Private"):
            self.assertNotIn(secret, serialized)

    def test_system_info_does_not_use_shell_or_subprocess(self) -> None:
        with (
            patch("os.system", side_effect=AssertionError("shell execution")),
            patch("subprocess.Popen", side_effect=AssertionError("subprocess")),
            patch("subprocess.run", side_effect=AssertionError("subprocess")),
            patch.object(SystemInfoTool, "_os_info", return_value={"name": "Windows"}),
            patch.object(SystemInfoTool, "_cpu_info", return_value={"count": 4}),
            patch.object(SystemInfoTool, "_memory_info", return_value={"used_bytes": 1}),
            patch.object(SystemInfoTool, "_python_info", return_value={"version": "3"}),
            patch.object(SystemInfoTool, "_disk_info", return_value={"free_bytes": 2}),
        ):
            data = self._execute()

        self.assertIn("information", data)


class SystemInfoToolCallingIntegrationTests(unittest.TestCase):
    def test_os_question_routes_through_system_info_and_returns_final_answer(self) -> None:
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                "",
                (OllamaToolCall("system_info", {"category": "os"}),),
            ),
            OllamaAssistantResponse("This computer is running Windows."),
        ]
        system_tool = SystemInfoTool()
        os_result = {
            "category": "os",
            "information": {
                "os": {
                    "name": "Windows",
                    "release": "11",
                    "version": "test-build",
                    "architecture": "AMD64",
                }
            },
        }
        with patch.object(
            system_tool,
            "execute",
            return_value=os_result,
        ) as execute:
            registry = ToolRegistry()
            registry.register(
                WebSearchTool(
                    provider=Mock(),
                    config=WebSearchConfig("tavily", ""),
                )
            )
            registry.register(CalculatorTool())
            registry.register(FileSearchTool((Path("D:/veronica"),)))
            registry.register(system_tool)

            response = OllamaToolCallingService(provider, registry).respond(
                [
                    {
                        "role": "user",
                        "content": "What operating system is this computer running?",
                    }
                ]
            )

        self.assertEqual(response, "This computer is running Windows.")
        execute.assert_called_once_with({"category": "os"})
        definitions = provider.generate_tool_response.call_args_list[0].args[1]
        self.assertEqual(
            {definition["function"]["name"] for definition in definitions},
            {"web_search", "calculator", "file_search", "system_info"},
        )
        messages = provider.generate_tool_response.call_args_list[1].args[0]
        result = json.loads(messages[-1]["content"])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"], os_result)


if __name__ == "__main__":
    unittest.main()
