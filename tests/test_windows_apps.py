"""Tests for bounded, read-only Windows Start Menu application discovery."""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.tools import windows_apps
from app.tools.windows_apps import (
    DiscoveredApplication,
    _ResolvedShortcut,
    _discover_app_paths,
    _discover_packaged_applications,
    _discover_from_roots,
    _validate_shortcut_target,
    diagnose_discovered_applications,
    normalize_application_name,
)


class WindowsApplicationDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.base = Path(self.temp_directory.name)
        self.start_menu = self.base / "Start Menu" / "Programs"
        self.install_root = self.base / "Program Files"
        self.start_menu.mkdir(parents=True)
        self.install_root.mkdir()
        self.target = self.install_root / "Vendor" / "Example" / "Example.exe"
        self.target.parent.mkdir(parents=True)
        self.target.touch()

    def _discover(
        self,
        shortcuts: dict[str, _ResolvedShortcut],
    ) -> tuple[DiscoveredApplication, ...]:
        for shortcut in shortcuts:
            path = self.start_menu / shortcut
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

        def resolve(path: Path) -> _ResolvedShortcut:
            return shortcuts[path.name]

        return _discover_from_roots(
            (self.start_menu,),
            (self.install_root,),
            resolve,
        )

    def test_finds_metadata_from_shortcut_without_executing_application(self) -> None:
        shortcut = self.start_menu / "Google Chrome.lnk"
        shortcut.touch()
        resolver = Mock(return_value=_ResolvedShortcut(self.target, ""))

        with patch("os.system", side_effect=AssertionError("shell must not run")):
            applications = _discover_from_roots(
                (self.start_menu,),
                (self.install_root,),
                resolver,
            )

        self.assertEqual(
            applications,
            (
                DiscoveredApplication(
                    "Google Chrome",
                    "google chrome",
                    self.target.resolve(),
                    "start_menu_shortcut",
                    True,
                ),
            ),
        )
        resolver.assert_called_once_with(shortcut.resolve())

    def test_skips_shortcuts_with_arguments_or_untrusted_targets(self) -> None:
        targets = {
            "arguments.lnk": _ResolvedShortcut(self.target, "--profile=private"),
            "batch.lnk": _ResolvedShortcut(
                self.install_root / "bad.bat",
                "",
            ),
            "command-script.lnk": _ResolvedShortcut(
                self.install_root / "bad.cmd",
                "",
            ),
            "powershell-script.lnk": _ResolvedShortcut(
                self.install_root / "bad.ps1",
                "",
            ),
            "command.lnk": _ResolvedShortcut(
                self.install_root / "cmd.exe",
                "",
            ),
            "powershell.lnk": _ResolvedShortcut(
                self.install_root / "powershell.exe",
                "",
            ),
            "installer.lnk": _ResolvedShortcut(
                self.install_root / "setup.msi",
                "",
            ),
            "terminal.lnk": _ResolvedShortcut(
                self.install_root / "WindowsTerminal.exe",
                "",
            ),
            "url.lnk": _ResolvedShortcut(Path("https://example.com"), ""),
            "outside.lnk": _ResolvedShortcut(
                self.base / "Downloads" / "arbitrary.exe",
                "",
            ),
        }

        applications = self._discover(targets)

        self.assertEqual(applications, ())

    def test_missing_target_is_reported_in_metadata_but_not_launchable(self) -> None:
        applications = self._discover(
            {
                "Example.lnk": _ResolvedShortcut(
                    self.install_root / "Vendor" / "Example" / "Removed.exe",
                    "",
                )
            }
        )
        self.assertEqual(len(applications), 1)
        self.assertFalse(applications[0].target_exists)

    def test_accepts_discovered_chrome_and_spotify_targets(self) -> None:
        spotify = self.install_root / "Spotify" / "Spotify.exe"
        spotify.parent.mkdir()
        spotify.touch()
        applications = self._discover(
            {
                "Google Chrome.lnk": _ResolvedShortcut(self.target, ""),
                "Spotify.lnk": _ResolvedShortcut(spotify, ""),
            }
        )
        self.assertEqual(
            {application.display_name for application in applications},
            {"Google Chrome", "Spotify"},
        )
        self.assertTrue(all(application.target_exists for application in applications))

    def test_does_not_consider_shortcuts_outside_the_supplied_start_menu_root(self) -> None:
        external_root = self.base / "Downloads"
        external_root.mkdir()
        external_shortcut = external_root / "Untrusted.lnk"
        external_shortcut.touch()
        resolver = Mock(return_value=_ResolvedShortcut(self.target, ""))

        applications = _discover_from_roots(
            (self.start_menu,),
            (self.install_root,),
            resolver,
        )

        self.assertEqual(applications, ())
        resolver.assert_not_called()

    def test_skips_reparse_points_in_shortcut_tree_and_target_path(self) -> None:
        nested = self.start_menu / "Nested"
        nested.mkdir()
        shortcut = nested / "Example.lnk"
        shortcut.touch()
        resolver = Mock(return_value=_ResolvedShortcut(self.target, ""))

        with (
            patch(
                "app.tools.windows_apps._safe_existing_directory",
                return_value=self.start_menu.resolve(),
            ),
            patch(
                "app.tools.windows_apps._is_reparse_stat",
                side_effect=lambda result: stat.S_ISDIR(result.st_mode),
            ),
        ):
            applications = _discover_from_roots(
                (self.start_menu,),
                (self.install_root,),
                resolver,
            )
        self.assertEqual(applications, ())
        resolver.assert_not_called()

        with patch(
            "app.tools.windows_apps._contains_reparse_point",
            return_value=True,
        ):
            self.assertIsNone(
                _validate_shortcut_target(
                    _ResolvedShortcut(self.target, ""),
                    (self.install_root,),
                )
            )

    def test_discovery_is_bounded_by_entry_and_shortcut_limits(self) -> None:
        shortcuts = {
            f"app-{index}.lnk": _ResolvedShortcut(self.target, "")
            for index in range(8)
        }
        for name in shortcuts:
            (self.start_menu / name).touch()
        resolver = Mock(return_value=_ResolvedShortcut(self.target, ""))
        with (
            patch("app.tools.windows_apps._MAX_SHORTCUTS", 3),
            patch("app.tools.windows_apps._MAX_ENTRIES", 100),
        ):
            applications = _discover_from_roots(
                (self.start_menu,),
                (self.install_root,),
                resolver,
            )
        self.assertEqual(len(applications), 3)
        self.assertEqual(resolver.call_count, 3)

    def test_discovery_does_not_resolve_or_execute_any_program(self) -> None:
        shortcut = self.start_menu / "Example.lnk"
        shortcut.touch()
        resolver = Mock(return_value=_ResolvedShortcut(self.target, ""))
        with (
            patch("subprocess.Popen", side_effect=AssertionError("must not execute")),
            patch("os.system", side_effect=AssertionError("must not use a shell")),
        ):
            applications = _discover_from_roots(
                (self.start_menu,),
                (self.install_root,),
                resolver,
            )
        self.assertEqual(len(applications), 1)

    def test_known_start_menu_roots_are_only_the_two_documented_locations(self) -> None:
        roaming = self.base / "Roaming"
        program_data = self.base / "ProgramData"
        with patch(
            "app.tools.windows_apps._known_folder_path",
            side_effect=[roaming, program_data],
        ):
            roots = windows_apps._start_menu_roots()
        self.assertEqual(
            roots,
            (
                roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs",
                program_data
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs",
            ),
        )

    def test_normalization_is_exact_and_not_fuzzy(self) -> None:
        self.assertEqual(normalize_application_name("  Google-Chrome! "), "google chrome")
        self.assertNotEqual(
            normalize_application_name("open cmd"),
            normalize_application_name("cmd"),
        )

    def test_developer_diagnostic_reports_name_source_target_and_validation(self) -> None:
        application = DiscoveredApplication(
            "Microsoft Edge",
            "microsoft edge",
            self.target.resolve(),
            "start_menu_shortcut",
            True,
        )
        with patch(
            "app.tools.windows_apps.validate_discovered_target",
            return_value=self.target.resolve(),
        ):
            diagnostics = diagnose_discovered_applications((application,))

        self.assertEqual(len(diagnostics), 1)
        diagnostic = diagnostics[0]
        self.assertEqual(diagnostic.display_name, "Microsoft Edge")
        self.assertEqual(diagnostic.normalized_name, "microsoft edge")
        self.assertEqual(diagnostic.source_type, "start_menu_shortcut")
        self.assertEqual(diagnostic.target_path, str(self.target.resolve()))
        self.assertEqual(diagnostic.target_filename, "Example.exe")
        self.assertEqual(diagnostic.target_type, ".exe")
        self.assertTrue(diagnostic.target_exists)
        self.assertTrue(diagnostic.passes_validation)

        public_result = {
            "status": "success",
            "application": "edge",
            "message": "Requested Microsoft Edge to launch.",
        }
        self.assertNotIn(diagnostic.target_path, str(public_result))

    def test_shortcut_metadata_contains_no_environment_values(self) -> None:
        result = self._discover({"Example.lnk": _ResolvedShortcut(self.target, "")})
        self.assertEqual(len(result), 1)
        application = result[0]
        self.assertEqual(application.source_type, "start_menu_shortcut")
        self.assertTrue(application.target_exists)
        username = os.environ.get("USERNAME")
        if username:
            self.assertNotIn(username, application.display_name)

    def test_app_paths_reads_only_fixed_allowlisted_registry_entries(self) -> None:
        edge = self.install_root / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        edge.parent.mkdir(parents=True)
        edge.touch()
        registered_keys: list[str] = []

        def read_value(key: str, _: str) -> str | None:
            registered_keys.append(key)
            if key.endswith(r"App Paths\msedge.exe"):
                return str(edge)
            return None

        with patch("app.tools.windows_apps._is_windows", return_value=True):
            applications = _discover_app_paths((self.install_root,), read_value)

        self.assertEqual(len(applications), 1)
        application = applications[0]
        self.assertEqual(application.display_name, "Microsoft Edge")
        self.assertEqual(application.normalized_name, "microsoft edge")
        self.assertEqual(application.target, edge.resolve())
        self.assertEqual(application.source_type, "app_paths_registry")
        self.assertEqual(application.expected_executable, "msedge.exe")
        self.assertTrue(application.target_exists)
        self.assertEqual(
            len(registered_keys),
            len(windows_apps._REGISTERED_GUI_APPLICATIONS)
            * len(windows_apps._APP_PATHS_REGISTRY_KEYS),
        )
        self.assertTrue(all("App Paths\\" in key for key in registered_keys))

    def test_app_paths_rejects_arguments_wrong_identity_and_untrusted_targets(self) -> None:
        valid_edge = self.install_root / "Edge" / "msedge.exe"
        valid_edge.parent.mkdir()
        valid_edge.touch()
        outside = self.base / "Downloads" / "chrome.exe"
        outside.parent.mkdir()
        outside.touch()
        invalid_values = (
            f'"{valid_edge}" --profile=test',
            str(valid_edge).replace("msedge.exe", "chrome.exe"),
            str(outside),
            str(valid_edge).replace("msedge.exe", "installer.msi"),
            "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
        )

        for value in invalid_values:
            with self.subTest(value=value):
                def read_value(key: str, _: str) -> str | None:
                    return (
                        value
                        if key.endswith(r"App Paths\msedge.exe")
                        else None
                    )

                with patch("app.tools.windows_apps._is_windows", return_value=True):
                    applications = _discover_app_paths(
                        (self.install_root,),
                        read_value,
                    )
                self.assertEqual(applications, ())

    def test_cross_source_duplicates_merge_without_merging_distinct_targets(self) -> None:
        edge = self.install_root / "Edge" / "msedge.exe"
        edge.parent.mkdir()
        edge.touch()
        other_edge = self.install_root / "Edge Beta" / "msedge.exe"
        other_edge.parent.mkdir()
        other_edge.touch()
        applications = windows_apps._deduplicate_applications(
            (
                DiscoveredApplication(
                    "Microsoft Edge",
                    "microsoft edge",
                    edge,
                    "start_menu_shortcut",
                    True,
                ),
                DiscoveredApplication(
                    "Microsoft Edge",
                    "microsoft edge",
                    edge,
                    "app_paths_registry",
                    True,
                    expected_executable="msedge.exe",
                ),
                DiscoveredApplication(
                    "Microsoft Edge",
                    "microsoft edge",
                    other_edge,
                    "app_paths_registry",
                    True,
                    expected_executable="msedge.exe",
                ),
            )
        )

        self.assertEqual(len(applications), 2)
        merged = next(application for application in applications if application.target == edge)
        self.assertEqual(
            set(merged.source_type.split("+")),
            {"start_menu_shortcut", "app_paths_registry"},
        )

    def test_packaged_app_activation_identifiers_are_not_executable_targets(self) -> None:
        self.assertIsNone(
            windows_apps._parse_registered_executable(
                "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"
            )
        )
        self.assertIsNone(
            windows_apps._parse_registered_executable(
                r"C:\Program Files\WindowsApps\Example\appxmanifest.xml"
            )
        )

    def test_known_store_packages_are_discovered_as_nonlaunchable_metadata(self) -> None:
        package_names = (
            "5319275A.WhatsAppDesktop_2.2623.103.0_neutral_split.scale-125_cv1g1gvanyjgm",
            "5319275A.WhatsAppDesktop_2.2637.100.0_x64__cv1g1gvanyjgm",
            "Microsoft.WindowsCalculator_11.2607.0.0_x64__8wekyb3d8bbwe",
            "Untrusted.ArbitraryApp_1.0.0.0_x64__example",
        )

        with patch("app.tools.windows_apps._is_windows", return_value=True):
            applications = _discover_packaged_applications(lambda: package_names)

        self.assertEqual(len(applications), 2)
        whatsapp = next(
            application
            for application in applications
            if application.normalized_name == "whatsapp"
        )
        self.assertIsNone(whatsapp.target)
        self.assertFalse(whatsapp.target_exists)
        self.assertEqual(whatsapp.launch_type, "packaged_discovery_only")
        self.assertEqual(whatsapp.package_identity, "5319275A.WhatsAppDesktop")
        calculator = next(
            application
            for application in applications
            if application.normalized_name == "calculator"
        )
        self.assertEqual(calculator.launch_type, "packaged_discovery_only")
        self.assertIsNone(calculator.target)


if __name__ == "__main__":
    unittest.main()
