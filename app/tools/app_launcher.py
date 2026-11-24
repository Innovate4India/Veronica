"""Allowlisted Windows desktop application launcher."""

import ctypes
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

from app.tools.base import JSONValue, ParameterSchema, Tool, ToolValidationError
from app.tools.windows_apps import (
    DiscoveredApplication,
    discover_windows_applications,
    normalize_application_name,
    validate_discovered_target,
)

_APPLICATION_ALIASES = {
    "notepad": "notepad",
    "notes": "notepad",
    "windows notepad": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "windows calculator": "calculator",
    "paint": "paint",
    "mspaint": "paint",
    "microsoft paint": "paint",
}
_DISCOVERED_ALIASES: dict[str, tuple[str, ...]] = {
    "chrome": ("chrome", "google chrome"),
    "google chrome": ("chrome", "google chrome"),
    "edge": ("edge", "microsoft edge"),
    "microsoft edge": ("edge", "microsoft edge"),
    "firefox": ("firefox", "mozilla firefox"),
    "mozilla firefox": ("firefox", "mozilla firefox"),
    "spotify": ("spotify",),
    "discord": ("discord",),
    "whatsapp": ("whatsapp", "whatsapp desktop"),
    "whatsapp desktop": ("whatsapp", "whatsapp desktop"),
    "vscode": ("vscode", "vs code", "visual studio code"),
    "vs code": ("vscode", "vs code", "visual studio code"),
    "visual studio code": ("vscode", "vs code", "visual studio code"),
    "code": ("vscode", "vs code", "visual studio code"),
    "word": ("word", "microsoft word"),
    "microsoft word": ("word", "microsoft word"),
    "excel": ("excel", "microsoft excel"),
    "microsoft excel": ("excel", "microsoft excel"),
}
_DISCOVERED_LABELS = {
    "chrome": "Chrome",
    "edge": "Microsoft Edge",
    "firefox": "Firefox",
    "spotify": "Spotify",
    "discord": "Discord",
    "whatsapp": "WhatsApp",
    "vscode": "Visual Studio Code",
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
}
_DISCOVERED_EXECUTABLES = {
    "chrome": frozenset({"chrome.exe"}),
    "edge": frozenset({"msedge.exe"}),
    "firefox": frozenset({"firefox.exe"}),
    "spotify": frozenset({"spotify.exe"}),
    "discord": frozenset({"discord.exe"}),
    "whatsapp": frozenset({"whatsapp.exe"}),
    "vscode": frozenset({"code.exe"}),
    "word": frozenset({"winword.exe"}),
    "excel": frozenset({"excel.exe"}),
}
_WINDOWS_EXECUTABLES = {
    "notepad": ("notepad.exe", "Notepad"),
    "calculator": ("calc.exe", "Calculator"),
    "paint": ("mspaint.exe", "Paint"),
}
_APPLICATION_LABELS = {
    **{name: label for name, (_, label) in _WINDOWS_EXECUTABLES.items()},
}
_MAX_APPLICATION_NAME_LENGTH = 64
_BLOCKED_LOGICAL_NAMES = {
    "cmd",
    "command prompt",
    "powershell",
    "windows powershell",
    "pwsh",
    "python",
    "pythonw",
    "windows terminal",
}
_NON_APPLICATION_SUFFIXES = (
    ".bat",
    ".cmd",
    ".exe",
    ".js",
    ".msi",
    ".ps1",
    ".vbs",
)


class AppLauncherTool(Tool):
    """Launch only fixed Windows apps or securely discovered GUI apps."""

    @property
    def name(self) -> str:
        return "app_launcher"

    @property
    def description(self) -> str:
        return (
            "Use this tool when the user explicitly wants to OPEN, LAUNCH, "
            "START, or RUN a GUI application. This includes English, Hindi, "
            "and Hinglish requests such as 'Open WhatsApp', 'direct WhatsApp "
            "open karo', 'WhatsApp kholo', 'WhatsApp chalao', 'Chrome open "
            "kar do', 'Edge open kar do', 'Calculator kholo', and 'VS Code "
            "start karo'. Action words like open, khol, kholo, khol do, open "
            "karo, start karo, chalao, and launch karo describe the action; "
            "they are not part of the application value. Set application to "
            "ONLY the logical app name, for example 'WhatsApp', 'Chrome', "
            "'Microsoft Edge', 'VS Code', 'Calculator', or 'Notepad'. Never "
            "pass the full request sentence. Do not call this tool for normal "
            "questions such as 'What is WhatsApp?' or 'WhatsApp kya hai?'. "
            "It launches Notepad, Calculator, and Paint from fixed Windows "
            "system targets, plus GUI applications discovered from the two "
            "trusted Windows Start Menu locations or fixed App Paths registry "
            "entries, such as Chrome, Edge, Firefox, Spotify, Discord, "
            "WhatsApp, VS Code, Word, and Excel when installed. App Paths "
            "lookup checks only known executable names; discovery accepts "
            "only existing .exe targets in trusted install roots, with no "
            "shortcut arguments, and rejects command/script interpreters. "
            "The application value must not be a sentence, command, Windows "
            "path, executable filename, shell syntax, or command-line "
            "arguments. Arbitrary paths, programs, scripts, shell commands, "
            "and user-supplied arguments are never accepted. Do not use this "
            "tool for websites (use open_url) or system questions "
            "(use system_info). It does not elevate privileges or control "
            "applications after launch."
        )

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": {
                "application": {
                    "type": "string",
                    "description": (
                        "ONLY the logical application name, not the request "
                        "sentence or action words: WhatsApp, Chrome, Microsoft "
                        "Edge, VS Code, Calculator, or Notepad. For example, "
                        "'direct WhatsApp open karo' or 'open WhatsApp' means "
                        "application='WhatsApp'. Invalid values include a "
                        "sentence, command, Windows path, executable filename "
                        "such as whatsapp.exe, shell syntax, or command-line "
                        "arguments. Never include open/khol/karo/chalao in "
                        "the value."
                    ),
                    "minLength": 1,
                    "maxLength": _MAX_APPLICATION_NAME_LENGTH,
                },
            },
            "required": ["application"],
            "additionalProperties": False,
        }

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        application = parameters.get("application")
        if not isinstance(application, str):
            raise ToolValidationError("application must be a string.")
        if not application.strip() or len(application) > _MAX_APPLICATION_NAME_LENGTH:
            raise ToolValidationError("application must be a supported application name.")

        normalized_name = normalize_application_name(application.strip())
        if (
            normalized_name in _BLOCKED_LOGICAL_NAMES
            or any(character in application for character in (":", "\\", "/", "&", "|", ";"))
            or application.strip().casefold().endswith(_NON_APPLICATION_SUFFIXES)
        ):
            raise ToolValidationError(
                "Provide only a supported logical application name."
            )
        fixed_name = _APPLICATION_ALIASES.get(normalized_name)
        if fixed_name in _WINDOWS_EXECUTABLES:
            target = _resolve_launch_target(fixed_name)
            if target is None:
                label = _APPLICATION_LABELS[fixed_name]
                return _unavailable(fixed_name, label)
            return _start_application(fixed_name, _APPLICATION_LABELS[fixed_name], target)

        matching_names = set(_DISCOVERED_ALIASES.get(normalized_name, (normalized_name,)))
        applications = discover_windows_applications()
        canonical_name = _DISCOVERED_ALIASES.get(
            normalized_name,
            (normalized_name,),
        )[0]
        expected_executables = _DISCOVERED_EXECUTABLES.get(canonical_name)
        matches = _matching_applications(
            applications,
            matching_names,
            expected_executables,
        )
        selected = next(iter(matches), None)
        if selected is None:
            if normalized_name in _DISCOVERED_ALIASES:
                canonical_name = _DISCOVERED_ALIASES[normalized_name][0]
                label = _DISCOVERED_LABELS.get(
                    canonical_name,
                    application.strip(),
                )
                return _unavailable(canonical_name, label)
            raise ToolValidationError(
                "application is not an installed application in the supported sources."
            )
        if len(matches) > 1:
            return {
                "status": "ambiguous",
                "application": application.strip(),
                "matches": [match.display_name for match in matches[:5]],
                "match_count": len(matches),
                "message": (
                    "I found multiple applications matching that name. "
                    "Please specify which one."
                    ),
            }
        label = _display_label(normalized_name, selected)
        if (
            selected.launch_type != "executable"
            or selected.target is None
            or not selected.target_exists
        ):
            return _unavailable(selected.normalized_name, label)
        target = validate_discovered_target(selected.target)
        if target is None:
            return _unavailable(selected.normalized_name, label)
        canonical_name = _DISCOVERED_ALIASES.get(
            normalized_name,
            (selected.normalized_name,),
        )[0]
        return _start_application(canonical_name, label, target)


def _resolve_launch_target(application: str) -> Path | None:
    if not _is_windows():
        return None
    if application in _WINDOWS_EXECUTABLES:
        system_directory = _windows_system_directory()
        if system_directory is None:
            return None
        target = system_directory / _WINDOWS_EXECUTABLES[application][0]
        return target if target.is_file() else None
    return None


def _matching_applications(
    applications: tuple[DiscoveredApplication, ...],
    accepted_names: set[str],
    expected_executables: frozenset[str] | None = None,
) -> tuple[DiscoveredApplication, ...]:
    matches: list[DiscoveredApplication] = []
    packaged_matches: list[DiscoveredApplication] = []
    seen_targets: set[str] = set()
    for application in applications:
        if application.normalized_name not in accepted_names:
            continue
        if application.launch_type == "packaged_discovery_only":
            target_key = f"package:{application.package_identity or ''}".casefold()
            target_matches = packaged_matches
        else:
            if application.target is None or (
                expected_executables is not None
                and application.target.name.casefold() not in expected_executables
            ):
                continue
            target_key = str(application.target).casefold()
            target_matches = matches
        if target_key not in seen_targets:
            seen_targets.add(target_key)
            target_matches.append(application)
    return tuple(matches or packaged_matches)


def _display_label(
    requested_name: str,
    application: DiscoveredApplication,
) -> str:
    canonical_name = _DISCOVERED_ALIASES.get(requested_name, (requested_name,))[0]
    return _DISCOVERED_LABELS.get(canonical_name, application.display_name)


def _start_application(
    canonical_name: str,
    label: str,
    target: Path,
) -> JSONValue:
    try:
        subprocess.Popen([str(target)], shell=False)
    except OSError:
        return {
            "status": "unavailable",
            "application": canonical_name,
            "message": f"{label} could not be started.",
        }
    return {
        "status": "success",
        "application": canonical_name,
        "message": f"Requested {label} to launch.",
    }


def _unavailable(canonical_name: str, label: str) -> JSONValue:
    return {
        "status": "unavailable",
        "application": canonical_name,
        "message": f"{label} is not available on this computer.",
    }


def _windows_system_directory() -> Path | None:
    """Obtain the trusted Windows system directory without shell lookup."""
    if not _is_windows():
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_system_directory = kernel32.GetSystemDirectoryW
        get_system_directory.argtypes = [wintypes.LPWSTR, wintypes.UINT]
        get_system_directory.restype = wintypes.UINT
        buffer = ctypes.create_unicode_buffer(32768)
        length = get_system_directory(buffer, len(buffer))
    except (AttributeError, OSError):
        return None
    if length == 0 or length >= len(buffer):
        return None
    return Path(buffer.value)


def _is_windows() -> bool:
    return sys.platform == "win32"
