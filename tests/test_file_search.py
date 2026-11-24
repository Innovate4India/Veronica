"""Tests for bounded, read-only local file-name search."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.ai import OllamaToolCallingService
from app.ai.ollama_client import OllamaAssistantResponse, OllamaToolCall
from app.config import PROJECT_ROOT, WebSearchConfig, load_file_search_roots
from app.tools import (
    CalculatorTool,
    FileSearchTool,
    JSONValue,
    ToolRegistry,
    ToolStatus,
    WebSearchTool,
)


class FileSearchToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "allowed"
        self.root.mkdir()
        self.outside = Path(self.temporary_directory.name) / "outside"
        self.outside.mkdir()
        self.tool = FileSearchTool((self.root,))
        self.registry = ToolRegistry()
        self.registry.register(self.tool)

    def _search(self, query: str, path: str | None = None) -> dict[str, JSONValue]:
        parameters: dict[str, JSONValue] = {"query": query}
        if path is not None:
            parameters["path"] = path
        result = self.registry.execute("file_search", parameters)
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        if not isinstance(result.data, dict):
            self.fail("Successful file search must return a structured object.")
        return result.data

    def test_searches_filenames_case_insensitively_and_returns_metadata_only(self) -> None:
        target = self.root / "Reports"
        target.mkdir()
        file_path = target / "Quarterly-REPORT.txt"
        file_path.write_text("private file contents", encoding="utf-8")

        data = self._search("quarterly-report")

        results = data["results"]
        if not isinstance(results, list):
            self.fail("Search results must be a list.")
        self.assertEqual(len(results), 1)
        result = results[0]
        if not isinstance(result, dict):
            self.fail("Each search result must be an object.")
        self.assertEqual(result["name"], file_path.name)
        self.assertEqual(result["path"], str(file_path.resolve()))
        self.assertEqual(result["type"], "file")
        self.assertEqual(result["size"], len("private file contents"))
        self.assertNotIn("contents", json.dumps(data))
        self.assertEqual(file_path.read_text(encoding="utf-8"), "private file contents")

    def test_searches_directory_names(self) -> None:
        directory = self.root / "Python Projects"
        directory.mkdir()

        data = self._search("python")

        results = data["results"]
        if not isinstance(results, list):
            self.fail("Search results must be a list.")
        self.assertEqual(
            results,
            [
                {
                    "name": directory.name,
                    "path": str(directory.resolve()),
                    "type": "directory",
                }
            ],
        )

    def test_optional_path_scopes_search_within_configured_root(self) -> None:
        first = self.root / "first"
        second = self.root / "second"
        first.mkdir()
        second.mkdir()
        (first / "needle-one.txt").touch()
        (second / "needle-two.txt").touch()

        data = self._search("needle", "first")

        results = data["results"]
        if not isinstance(results, list) or not results:
            self.fail("Search results must include the scoped file.")
        result = results[0]
        if not isinstance(result, dict):
            self.fail("Each search result must be an object.")
        self.assertEqual(result["name"], "needle-one.txt")

    def test_rejects_parent_traversal_and_absolute_outside_paths(self) -> None:
        outside_file = self.outside / "needle.txt"
        outside_file.touch()

        for path in ("..", "../outside", str(self.outside)):
            with self.subTest(path=path):
                result = self.registry.execute(
                    "file_search",
                    {"query": "needle", "path": path},
                )
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)
        self.assertEqual(outside_file.read_bytes(), b"")

    def test_missing_root_is_reported_as_unavailable(self) -> None:
        missing_tool = FileSearchTool((self.root / "not-created",))
        registry = ToolRegistry()
        registry.register(missing_tool)

        result = registry.execute("file_search", {"query": "anything"})

        self.assertEqual(result.status, ToolStatus.UNAVAILABLE)

    def test_nonexistent_scoped_directory_is_rejected(self) -> None:
        result = self.registry.execute(
            "file_search",
            {"query": "anything", "path": "does-not-exist"},
        )

        self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)

    def test_result_limit_is_enforced(self) -> None:
        for index in range(5):
            (self.root / f"result-{index}.txt").touch()

        with patch("app.tools.file_search.MAX_RESULTS", 2):
            data = self._search("result-")

        results = data["results"]
        if not isinstance(results, list):
            self.fail("Search results must be a list.")
        self.assertEqual(len(results), 2)
        self.assertFalse(data["complete"])

    def test_traversal_limit_is_enforced(self) -> None:
        for index in range(8):
            (self.root / f"item-{index}.txt").touch()

        with patch("app.tools.file_search.MAX_VISITED_ENTRIES", 2):
            data = self._search("item-")

        visited_entries = data["visited_entries"]
        if not isinstance(visited_entries, int):
            self.fail("Visited entry count must be an integer.")
        self.assertLessEqual(visited_entries, 2)
        self.assertFalse(data["complete"])

    def test_runtime_limit_is_enforced(self) -> None:
        (self.root / "slow-result.txt").touch()

        with patch("app.tools.file_search.SEARCH_TIMEOUT_SECONDS", 0):
            data = self._search("slow")

        self.assertEqual(data["results"], [])
        self.assertEqual(data["visited_entries"], 0)
        self.assertFalse(data["complete"])

    def test_sensitive_names_and_directories_are_not_returned_or_traversed(self) -> None:
        (self.root / "needle-client_secret.txt").touch()
        (self.root / ".env.needle").touch()
        sensitive_directory = self.root / "credentials-needle"
        sensitive_directory.mkdir()
        (sensitive_directory / "needle.txt").touch()
        safe_file = self.root / "needle-notes.txt"
        safe_file.touch()

        data = self._search("needle")
        serialized = json.dumps(data).casefold()

        self.assertIn(safe_file.name.casefold(), serialized)
        self.assertNotIn("client_secret", serialized)
        self.assertNotIn(".env", serialized)
        self.assertNotIn("credentials", serialized)

    def test_symlinked_directories_are_skipped_and_symlink_paths_rejected(self) -> None:
        outside_file = self.outside / "symlink-target.txt"
        outside_file.touch()
        link = self.root / "linked-folder"
        internal_target = self.root / "actual-folder"
        internal_target.mkdir()
        internal_link = self.root / "internal-link"
        try:
            link.symlink_to(self.outside, target_is_directory=True)
            internal_link.symlink_to(internal_target, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Directory symlinks are unavailable: {error}")

        data = self._search("symlink-target")
        self.assertEqual(data["results"], [])
        for requested_path in (link, internal_link):
            with self.subTest(path=requested_path):
                result = self.registry.execute(
                    "file_search",
                    {"query": "anything", "path": str(requested_path)},
                )
                self.assertEqual(
                    result.status,
                    ToolStatus.VALIDATION_FAILURE,
                )

    def test_search_does_not_modify_files_or_run_commands(self) -> None:
        target = self.root / "unchanged.txt"
        target.write_text("unchanged", encoding="utf-8")
        original_stat = target.stat()
        with (
            patch("os.system", side_effect=AssertionError("shell execution")),
            patch("subprocess.Popen", side_effect=AssertionError("subprocess")),
        ):
            self._search("unchanged")

        self.assertEqual(target.read_text(encoding="utf-8"), "unchanged")
        self.assertEqual(target.stat().st_mtime_ns, original_stat.st_mtime_ns)

    def test_rejects_invalid_queries(self) -> None:
        for parameters in (
            {},
            {"query": ""},
            {"query": "x" * 129},
            {"query": 42},
            {"query": "ok", "unexpected": True},
        ):
            with self.subTest(parameters=parameters):
                result = self.registry.execute("file_search", parameters)
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)


class FileSearchToolCallingIntegrationTests(unittest.TestCase):
    def test_calculator_project_request_routes_through_file_search_without_scanning(
        self,
    ) -> None:
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                "",
                (
                    OllamaToolCall(
                        "file_search",
                        {
                            "query": "calculator Veronica project",
                            "path": "",
                        },
                    ),
                ),
            ),
            OllamaAssistantResponse(
                "I found calculator-related files in the Veronica project."
            ),
        ]
        search_tool = FileSearchTool((Path("D:/veronica"),))
        search_result = {
            "query": "calculator Veronica project",
            "results": [
                {
                    "name": "calculator.py",
                    "path": "D:\\veronica\\app\\tools\\calculator.py",
                    "type": "file",
                    "size": 1234,
                }
            ],
            "visited_entries": 20,
            "complete": True,
        }
        with patch.object(search_tool, "execute", return_value=search_result) as execute:
            registry = ToolRegistry()
            registry.register(
                WebSearchTool(
                    provider=Mock(),
                    config=WebSearchConfig("tavily", ""),
                )
            )
            registry.register(CalculatorTool())
            registry.register(search_tool)

            response = OllamaToolCallingService(provider, registry).respond(
                [
                    {
                        "role": "user",
                        "content": (
                            "Find files related to calculator in my Veronica project"
                        ),
                    }
                ]
            )

        self.assertEqual(
            response,
            "I found calculator-related files in the Veronica project.",
        )
        execute.assert_called_once_with(
            {"query": "calculator Veronica project"}
        )
        tool_messages = provider.generate_tool_response.call_args_list[1].args[0]
        returned_result = json.loads(tool_messages[-1]["content"])
        self.assertEqual(returned_result["status"], "success")
        self.assertEqual(
            returned_result["data"]["results"][0]["name"],
            "calculator.py",
        )
        self.assertNotIn("path", tool_messages[-1])
        definitions = provider.generate_tool_response.call_args_list[0].args[1]
        self.assertIn(
            "file_search",
            {definition["function"]["name"] for definition in definitions},
        )
        self.assertEqual(provider.generate_tool_response.call_count, 2)

    def test_ollama_tool_call_uses_registry_and_returns_structured_file_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            target = root / "project-plan.txt"
            target.write_text("do not return these contents", encoding="utf-8")
            provider = Mock()
            provider.generate_tool_response.side_effect = [
                OllamaAssistantResponse(
                    "",
                    (
                        OllamaToolCall(
                            "file_search",
                            {"query": "project-plan"},
                        ),
                    ),
                ),
                OllamaAssistantResponse(
                    "I found project-plan.txt in the configured local folder."
                ),
            ]
            registry = ToolRegistry()
            registry.register(
                WebSearchTool(
                    provider=Mock(),
                    config=WebSearchConfig("tavily", ""),
                )
            )
            registry.register(CalculatorTool())
            registry.register(FileSearchTool((root,)))

            response = OllamaToolCallingService(provider, registry).respond(
                [
                    {
                        "role": "user",
                        "content": "Find the project plan file.",
                    }
                ]
            )

            self.assertEqual(
                response,
                "I found project-plan.txt in the configured local folder.",
            )
            definitions = provider.generate_tool_response.call_args_list[0].args[1]
            self.assertEqual(
                {definition["function"]["name"] for definition in definitions},
                {"web_search", "calculator", "file_search"},
            )
            returned_messages = (
                provider.generate_tool_response.call_args_list[1].args[0]
            )
            tool_result = json.loads(returned_messages[-1]["content"])
            self.assertEqual(tool_result["status"], "success")
            self.assertEqual(tool_result["data"]["results"][0]["name"], target.name)
            self.assertNotIn("do not return these contents", json.dumps(tool_result))
            self.assertEqual(
                returned_messages[-1]["role"],
                "tool",
            )


class FileSearchConfigurationTests(unittest.TestCase):
    def test_defaults_to_project_root(self) -> None:
        self.assertEqual(load_file_search_roots({}), (PROJECT_ROOT.resolve(),))

    def test_loads_and_deduplicates_multiple_absolute_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root_a = Path(temporary_directory) / "a"
            root_b = Path(temporary_directory) / "b"

            roots = load_file_search_roots(
                {
                    "VERONICA_FILE_SEARCH_ROOTS": (
                        f"{root_a};{root_b};{root_a}"
                    )
                }
            )

        self.assertEqual(roots, (root_a.resolve(), root_b.resolve()))

    def test_rejects_relative_root_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            FileSearchTool((Path("relative-root"),))
        with self.assertRaisesRegex(ValueError, "absolute"):
            load_file_search_roots(
                {"VERONICA_FILE_SEARCH_ROOTS": "relative-root"}
            )

    def test_rejects_too_many_configured_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            roots = [
                str(Path(temporary_directory) / f"root-{index}")
                for index in range(17)
            ]
            with self.assertRaisesRegex(ValueError, "at most 16"):
                load_file_search_roots(
                    {"VERONICA_FILE_SEARCH_ROOTS": ";".join(roots)}
                )


if __name__ == "__main__":
    unittest.main()
