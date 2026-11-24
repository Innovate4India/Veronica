"""Tests for the strictly allowlisted Windows application launcher."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.ai import AIService, OllamaToolCallingService
from app.ai.ollama_client import OllamaAssistantResponse, OllamaToolCall
from app.config import WebSearchConfig
from app.tools import (
    AppLauncherTool,
    CalculatorTool,
    FileSearchTool,
    OpenURLTool,
    SystemInfoTool,
    ToolRegistry,
    ToolStatus,
    WebSearchTool,
)
from app.tools.windows_apps import DiscoveredApplication


class AppLauncherToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = AppLauncherTool()
        self.registry = ToolRegistry()
        self.registry.register(self.tool)
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.system_directory = Path(self.temp_directory.name) / "System32"
        self.system_directory.mkdir()
        for executable in ("notepad.exe", "calc.exe", "mspaint.exe"):
            (self.system_directory / executable).touch()

    def _launch(self, application: str):
        with (
            patch("app.tools.app_launcher.sys.platform", "win32"),
            patch(
                "app.tools.app_launcher._windows_system_directory",
                return_value=self.system_directory,
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": application},
            )
        return result, popen

    def test_builtin_aliases_map_only_to_fixed_system_executables(self) -> None:
        aliases = {
            "notepad": ("notepad", "notepad.exe", "Notepad"),
            "notes": ("notepad", "notepad.exe", "Notepad"),
            "windows notepad": ("notepad", "notepad.exe", "Notepad"),
            "calculator": ("calculator", "calc.exe", "Calculator"),
            "calc": ("calculator", "calc.exe", "Calculator"),
            "windows calculator": ("calculator", "calc.exe", "Calculator"),
            "paint": ("paint", "mspaint.exe", "Paint"),
            "mspaint": ("paint", "mspaint.exe", "Paint"),
            "microsoft paint": ("paint", "mspaint.exe", "Paint"),
        }
        for alias, (canonical, executable, label) in aliases.items():
            with self.subTest(alias=alias):
                result, popen = self._launch(alias)
                self.assertEqual(result.status, ToolStatus.SUCCESS)
                self.assertEqual(
                    result.data,
                    {
                        "status": "success",
                        "application": canonical,
                        "message": f"Requested {label} to launch.",
                    },
                )
                popen.assert_called_once_with(
                    [str(self.system_directory / executable)],
                    shell=False,
                )

    def test_vscode_aliases_resolve_only_the_named_code_launcher(self) -> None:
        install_directory = Path(self.temp_directory.name) / "Microsoft VS Code"
        install_directory.mkdir()
        executable = install_directory / "Code.exe"
        executable.touch()
        discovered = (
            DiscoveredApplication(
                "Visual Studio Code",
                "visual studio code",
                executable,
                "start_menu_shortcut",
                True,
            ),
        )

        for alias in ("vscode", "vs code", "visual studio code", "code"):
            with self.subTest(alias=alias):
                with (
                    patch(
                        "app.tools.app_launcher.discover_windows_applications",
                        return_value=discovered,
                    ),
                    patch(
                        "app.tools.app_launcher.validate_discovered_target",
                        return_value=executable,
                    ),
                    patch("app.tools.app_launcher.subprocess.Popen") as popen,
                ):
                    result = self.registry.execute(
                        "app_launcher",
                        {"application": alias},
                    )
                self.assertEqual(result.status, ToolStatus.SUCCESS)
                self.assertEqual(
                    result.data,
                    {
                        "status": "success",
                        "application": "vscode",
                        "message": "Requested Visual Studio Code to launch.",
                    },
                )
                popen.assert_called_once_with([str(executable)], shell=False)

    def test_invalid_targets_never_reach_process_launch_api(self) -> None:
        invalid_values = (
            "powershell",
            "cmd",
            "python",
            "arbitrary.exe",
            r"C:\Users\someone\malware.exe",
            "some-script.bat",
            "some-script.cmd",
            "some-script.ps1",
            "some-script.vbs",
            "some-script.js",
            "some-installer.msi",
            "notepad.exe",
            "calculator & powershell",
            "https://example.com",
            "",
            "   ",
        )
        with (
            patch(
                "app.tools.app_launcher.discover_windows_applications",
                return_value=(),
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            for value in invalid_values:
                with self.subTest(value=value):
                    result = self.registry.execute(
                        "app_launcher",
                        {"application": value},
                    )
                    self.assertEqual(
                        result.status,
                        ToolStatus.VALIDATION_FAILURE,
                    )
            extra_parameters = self.registry.execute(
                "app_launcher",
                {
                    "application": "calculator",
                    "path": r"C:\Users\someone\malware.exe",
                },
            )
        self.assertEqual(extra_parameters.status, ToolStatus.VALIDATION_FAILURE)
        popen.assert_not_called()

    def test_unavailable_application_returns_structured_result(self) -> None:
        with (
            patch("app.tools.app_launcher.sys.platform", "win32"),
            patch(
                "app.tools.app_launcher._windows_system_directory",
                return_value=None,
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "calculator"},
            )
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(
            result.data,
            {
                "status": "unavailable",
                "application": "calculator",
                "message": "Calculator is not available on this computer.",
            },
        )
        popen.assert_not_called()

    def test_vscode_missing_launcher_returns_unavailable(self) -> None:
        with (
            patch(
                "app.tools.app_launcher.discover_windows_applications",
                return_value=(),
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "VS Code"},
            )
        self.assertEqual(
            result.data,
            {
                "status": "unavailable",
                "application": "vscode",
                "message": "Visual Studio Code is not available on this computer.",
            },
        )
        popen.assert_not_called()

    def test_packaged_application_metadata_is_reported_unavailable_without_launch(self) -> None:
        packaged_whatsapp = DiscoveredApplication(
            "WhatsApp",
            "whatsapp",
            None,
            "packaged_app_registry",
            False,
            launch_type="packaged_discovery_only",
            package_identity="5319275A.WhatsAppDesktop",
        )
        with (
            patch(
                "app.tools.app_launcher.discover_windows_applications",
                return_value=(packaged_whatsapp,),
            ),
            patch(
                "app.tools.app_launcher.validate_discovered_target",
                side_effect=AssertionError("packaged apps have no executable target"),
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "WhatsApp"},
            )

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(
            result.data,
            {
                "status": "unavailable",
                "application": "whatsapp",
                "message": "WhatsApp is not available on this computer.",
            },
        )
        popen.assert_not_called()

    def test_missing_discovered_target_returns_unavailable(self) -> None:
        missing = DiscoveredApplication(
            "Google Chrome",
            "google chrome",
            Path(self.temp_directory.name) / "missing.exe",
            "start_menu_shortcut",
            False,
        )
        with (
            patch(
                "app.tools.app_launcher.discover_windows_applications",
                return_value=(missing,),
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "chrome"},
            )
        self.assertEqual(
            result.data,
            {
                "status": "unavailable",
                "application": "chrome",
                "message": "Chrome is not available on this computer.",
            },
        )
        popen.assert_not_called()

    def test_process_start_failure_is_reported_without_claiming_success(self) -> None:
        with (
            patch("app.tools.app_launcher.sys.platform", "win32"),
            patch(
                "app.tools.app_launcher._windows_system_directory",
                return_value=self.system_directory,
            ),
            patch(
                "app.tools.app_launcher.subprocess.Popen",
                side_effect=OSError("private system error"),
            ) as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "calc"},
            )
        self.assertEqual(
            result.data,
            {
                "status": "unavailable",
                "application": "calculator",
                "message": "Calculator could not be started.",
            },
        )
        popen.assert_called_once_with(
            [str(self.system_directory / "calc.exe")],
            shell=False,
        )

    def test_launcher_uses_no_shell_api_or_subprocess_run(self) -> None:
        with (
            patch("app.tools.app_launcher.sys.platform", "win32"),
            patch(
                "app.tools.app_launcher._windows_system_directory",
                return_value=self.system_directory,
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
            patch.object(os, "system", side_effect=AssertionError("shell use")),
            patch.object(subprocess, "run", side_effect=AssertionError("shell use")),
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "calculator"},
            )
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        popen.assert_called_once_with(
            [str(self.system_directory / "calc.exe")],
            shell=False,
        )

    def test_registry_schema_is_one_bounded_logical_application_parameter(self) -> None:
        schema = self.tool.parameters_schema
        self.assertEqual(self.tool.name, "app_launcher")
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            self.fail("Application schema must define object properties.")
        application_schema = properties.get("application")
        if not isinstance(application_schema, dict):
            self.fail("Application parameter must have an object schema.")
        self.assertNotIn("enum", application_schema)
        self.assertEqual(application_schema.get("type"), "string")
        self.assertEqual(schema["required"], ["application"])
        self.assertFalse(schema["additionalProperties"])

    def test_discovered_chrome_and_spotify_aliases_launch_validated_targets(self) -> None:
        for display_name, aliases, expected_name, label, executable_name in (
            (
                "Google Chrome",
                ("chrome", "google chrome"),
                "chrome",
                "Chrome",
                "chrome.exe",
            ),
            (
                "Microsoft Edge",
                ("edge", "microsoft edge"),
                "edge",
                "Microsoft Edge",
                "msedge.exe",
            ),
            (
                "Mozilla Firefox",
                ("firefox", "mozilla firefox"),
                "firefox",
                "Firefox",
                "firefox.exe",
            ),
            (
                "Spotify",
                ("spotify",),
                "spotify",
                "Spotify",
                "Spotify.exe",
            ),
            (
                "Visual Studio Code",
                ("vscode", "vs code"),
                "vscode",
                "Visual Studio Code",
                "Code.exe",
            ),
        ):
            target = Path(self.temp_directory.name) / executable_name
            target.touch()
            discovered = (
                DiscoveredApplication(
                    display_name,
                    display_name.casefold(),
                    target,
                    "start_menu_shortcut",
                    True,
                ),
            )
            for alias in aliases:
                with self.subTest(display_name=display_name, alias=alias):
                    with (
                        patch(
                            "app.tools.app_launcher.discover_windows_applications",
                            return_value=discovered,
                        ),
                        patch(
                            "app.tools.app_launcher.validate_discovered_target",
                            return_value=target,
                        ),
                        patch("app.tools.app_launcher.subprocess.Popen") as popen,
                    ):
                        result = self.registry.execute(
                            "app_launcher",
                            {"application": alias},
                        )
                    self.assertEqual(result.status, ToolStatus.SUCCESS)
                    self.assertEqual(
                        result.data,
                        {
                            "status": "success",
                            "application": expected_name,
                            "message": f"Requested {label} to launch.",
                        },
                    )
                    popen.assert_called_once_with([str(target)], shell=False)

    def test_edge_alias_only_selects_msedge_not_another_browser(self) -> None:
        chrome = Path(self.temp_directory.name) / "chrome.exe"
        chrome.touch()
        msedge = Path(self.temp_directory.name) / "msedge.exe"
        msedge.touch()
        discovered = (
            DiscoveredApplication(
                "Edge",
                "edge",
                chrome,
                "start_menu_shortcut",
                True,
            ),
            DiscoveredApplication(
                "Google Chrome",
                "google chrome",
                chrome,
                "start_menu_shortcut",
                True,
            ),
            DiscoveredApplication(
                "Microsoft Edge",
                "microsoft edge",
                msedge,
                "start_menu_shortcut",
                True,
            ),
        )
        with (
            patch(
                "app.tools.app_launcher.discover_windows_applications",
                return_value=discovered,
            ),
            patch(
                "app.tools.app_launcher.validate_discovered_target",
                side_effect=lambda target: target,
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "edge"},
            )

        self.assertEqual(
            result.data,
            {
                "status": "success",
                "application": "edge",
                "message": "Requested Microsoft Edge to launch.",
            },
        )
        popen.assert_called_once_with([str(msedge)], shell=False)
        self.assertIsInstance(result.data, dict)
        if not isinstance(result.data, dict):
            self.fail("App launcher result must be a structured object.")
        self.assertNotIn("path", result.data)
        self.assertNotIn(str(msedge), repr(result.data))

    def test_edge_is_unavailable_if_only_a_differently_named_browser_matches(self) -> None:
        chrome = Path(self.temp_directory.name) / "chrome.exe"
        chrome.touch()
        discovered = (
            DiscoveredApplication(
                "Edge",
                "edge",
                chrome,
                "start_menu_shortcut",
                True,
            ),
        )
        with (
            patch(
                "app.tools.app_launcher.discover_windows_applications",
                return_value=discovered,
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "edge"},
            )

        self.assertEqual(
            result.data,
            {
                "status": "unavailable",
                "application": "edge",
                "message": "Microsoft Edge is not available on this computer.",
            },
        )
        popen.assert_not_called()

    def test_known_discovered_apps_require_their_expected_executable_names(self) -> None:
        known = (
            ("chrome", "Chrome", "chrome.exe"),
            ("edge", "Microsoft Edge", "msedge.exe"),
            ("firefox", "Firefox", "firefox.exe"),
            ("spotify", "Spotify", "Spotify.exe"),
            ("vscode", "Visual Studio Code", "Code.exe"),
        )
        for requested, display, executable_name in known:
            with self.subTest(application=requested):
                target = Path(self.temp_directory.name) / executable_name
                target.touch()
                discovered = (
                    DiscoveredApplication(
                        display,
                        display.casefold(),
                        target,
                        "start_menu_shortcut",
                        True,
                    ),
                )
                with (
                    patch(
                        "app.tools.app_launcher.discover_windows_applications",
                        return_value=discovered,
                    ),
                    patch(
                        "app.tools.app_launcher.validate_discovered_target",
                        return_value=target,
                    ),
                    patch(
                        "app.tools.app_launcher.subprocess.Popen",
                    ) as popen,
                ):
                    result = self.registry.execute(
                        "app_launcher",
                        {"application": requested},
                    )
                self.assertEqual(result.status, ToolStatus.SUCCESS)
                popen.assert_called_once_with([str(target)], shell=False)

    def test_non_exact_phrase_does_not_fuzzy_match_an_application(self) -> None:
        applications = tuple(
            DiscoveredApplication(
                name,
                name.casefold(),
                Path(self.temp_directory.name) / f"{index}" / "chrome.exe",
                "start_menu_shortcut",
                True,
            )
            for index, name in enumerate(("Chrome", "Google Chrome"))
        )
        with (
            patch(
                "app.tools.app_launcher.discover_windows_applications",
                return_value=applications,
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "open chrome"},
            )
        self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)
        popen.assert_not_called()

    def test_ambiguous_alias_returns_structured_result_without_launching(self) -> None:
        applications = tuple(
            DiscoveredApplication(
                name,
                name.casefold(),
                Path(self.temp_directory.name) / f"{index}" / "chrome.exe",
                "start_menu_shortcut",
                True,
            )
            for index, name in enumerate(("Chrome", "Google Chrome"))
        )
        with (
            patch(
                "app.tools.app_launcher.discover_windows_applications",
                return_value=applications,
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "chrome"},
            )
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(
            result.data,
            {
                "status": "ambiguous",
                "application": "chrome",
                "matches": ["Chrome", "Google Chrome"],
                "match_count": 2,
                "message": (
                    "I found multiple applications matching that name. "
                    "Please specify which one."
                ),
            },
        )
        popen.assert_not_called()

    def test_arbitrary_app_name_is_not_fuzzy_matched(self) -> None:
        discovered = (
            DiscoveredApplication(
                "Chrome",
                "chrome",
                Path(self.temp_directory.name) / "chrome.exe",
                "start_menu_shortcut",
                True,
            ),
        )
        with (
            patch(
                "app.tools.app_launcher.discover_windows_applications",
                return_value=discovered,
            ),
            patch("app.tools.app_launcher.subprocess.Popen") as popen,
        ):
            result = self.registry.execute(
                "app_launcher",
                {"application": "open cmd"},
            )
        self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)
        popen.assert_not_called()


class AppLauncherToolCallingIntegrationTests(unittest.TestCase):
    def test_model_tool_call_is_dispatched_and_result_returns_to_ollama(self) -> None:
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                "",
                (OllamaToolCall("app_launcher", {"application": "vs code"}),),
            ),
            OllamaAssistantResponse(
                "I requested Visual Studio Code to launch."
            ),
        ]
        launcher = AppLauncherTool()
        mocked_result = {
            "status": "success",
            "application": "vscode",
            "message": "Requested Visual Studio Code to launch.",
        }
        with patch.object(launcher, "execute", return_value=mocked_result) as execute:
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
            registry.register(OpenURLTool())
            registry.register(launcher)

            response = OllamaToolCallingService(provider, registry).respond(
                [{"role": "user", "content": "Start VS Code"}]
            )

        self.assertEqual(response, "I requested Visual Studio Code to launch.")
        execute.assert_called_once_with({"application": "vs code"})
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
        tool_reply = json.loads(messages[-1]["content"])
        self.assertEqual(tool_reply["status"], "success")
        self.assertEqual(tool_reply["data"], mocked_result)

    def test_english_hindi_and_hinglish_launch_requests_use_logical_app_names(self) -> None:
        launch_requests = (
            ("Open WhatsApp", "WhatsApp"),
            ("direct WhatsApp open karo", "WhatsApp"),
            ("WhatsApp open karo", "WhatsApp"),
            ("WhatsApp kholo", "WhatsApp"),
            ("WhatsApp chalao", "WhatsApp"),
            ("WhatsApp launch karo", "WhatsApp"),
            ("Chrome kholo", "Chrome"),
            ("Chrome open karo", "Chrome"),
            ("Edge open kar do", "Microsoft Edge"),
            ("Calculator kholo", "Calculator"),
            ("VS Code start karo", "VS Code"),
            ("WhatsApp kholo please", "WhatsApp"),
            ("please WhatsApp open karo", "WhatsApp"),
            ("bhai WhatsApp chala do", "WhatsApp"),
            ("WhatsApp ko open karo", "WhatsApp"),
            ("mujhe WhatsApp open karna hai", "WhatsApp"),
        )
        for user_text, expected_application in launch_requests:
            with self.subTest(user_text=user_text):
                provider = Mock()
                provider.generate_tool_response.side_effect = [
                    OllamaAssistantResponse(
                        "",
                        (
                            OllamaToolCall(
                                "app_launcher",
                                {"application": expected_application},
                            ),
                        ),
                    ),
                    OllamaAssistantResponse(
                        f"I requested {expected_application} to launch."
                    ),
                ]
                launcher = AppLauncherTool()
                mocked_result = {
                    "status": "success",
                    "application": expected_application.casefold(),
                    "message": f"Requested {expected_application} to launch.",
                }
                with patch.object(
                    launcher,
                    "execute",
                    return_value=mocked_result,
                ) as execute:
                    registry = ToolRegistry()
                    registry.register(launcher)
                    tool_service = OllamaToolCallingService(provider, registry)
                    service = AIService(
                        provider,
                        tool_calling_service=tool_service,
                    )
                    answer = service.respond(user_text)

                self.assertEqual(
                    answer,
                    f"I requested {expected_application} to launch.",
                )
                execute.assert_called_once_with(
                    {"application": expected_application}
                )
                first_call = provider.generate_tool_response.call_args_list[0]
                definitions = first_call.args[1]
                self.assertEqual(
                    definitions[0]["function"]["name"],
                    "app_launcher",
                )
                parameter_description = definitions[0]["function"]["parameters"][
                    "properties"
                ]["application"]["description"]
                self.assertIn("ONLY the logical application name", parameter_description)
                sent_messages = first_call.args[0]
                self.assertTrue(
                    any(
                        message["role"] == "user"
                        and message["content"] == user_text
                        for message in sent_messages
                    )
                )
                system_message = sent_messages[0]["content"]
                self.assertIn("direct WhatsApp open karo", system_message)
                self.assertIn("WhatsApp kya hai?", system_message)

    def test_information_questions_do_not_call_app_launcher(self) -> None:
        questions = (
            "What is WhatsApp?",
            "How does WhatsApp work?",
            "Tell me about WhatsApp",
            "WhatsApp kya hai?",
        )
        for user_text in questions:
            with self.subTest(user_text=user_text):
                provider = Mock()
                provider.generate_response.side_effect = [
                    '{"role":"assistant"}',
                    "Here is information about WhatsApp.",
                ]
                launcher = AppLauncherTool()
                with patch.object(launcher, "execute") as execute:
                    registry = ToolRegistry()
                    registry.register(launcher)
                    service = AIService(
                        provider,
                        tool_calling_service=OllamaToolCallingService(
                            provider,
                            registry,
                        ),
                    )
                    answer = service.respond(user_text)
                self.assertEqual(answer, "Here is information about WhatsApp.")
                provider.generate_response.assert_called()
                provider.generate_tool_response.assert_not_called()
                execute.assert_not_called()

    def test_command_interpreter_path_is_still_rejected(self) -> None:
        registry = ToolRegistry()
        registry.register(AppLauncherTool())
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                "",
                (
                    OllamaToolCall(
                        "app_launcher",
                        {"application": r"Run C:\Windows\System32\cmd.exe"},
                    ),
                ),
            ),
            OllamaAssistantResponse("I cannot launch a command interpreter."),
        ]
        response = OllamaToolCallingService(provider, registry).respond(
            [{"role": "user", "content": r"Run C:\Windows\System32\cmd.exe"}]
        )
        self.assertEqual(response, "I cannot launch a command interpreter.")
        tool_reply = json.loads(
            provider.generate_tool_response.call_args_list[1].args[0][-1]["content"]
        )
        self.assertEqual(tool_reply["status"], ToolStatus.VALIDATION_FAILURE.value)

    def test_open_chrome_request_routes_logical_name_to_launcher(self) -> None:
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                "",
                (OllamaToolCall("app_launcher", {"application": "Chrome"}),),
            ),
            OllamaAssistantResponse("I requested Chrome to launch."),
        ]
        launcher = AppLauncherTool()
        result = {
            "status": "success",
            "application": "chrome",
            "message": "Requested Chrome to launch.",
        }
        with patch.object(launcher, "execute", return_value=result) as execute:
            registry = ToolRegistry()
            registry.register(launcher)
            response = OllamaToolCallingService(provider, registry).respond(
                [{"role": "user", "content": "Open Chrome"}]
            )
        self.assertEqual(response, "I requested Chrome to launch.")
        execute.assert_called_once_with({"application": "Chrome"})


if __name__ == "__main__":
    unittest.main()
