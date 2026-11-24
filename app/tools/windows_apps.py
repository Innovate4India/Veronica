"""Bounded discovery of GUI applications registered in Windows Start Menus."""

from __future__ import annotations

import ctypes
import os
import re
import stat
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

_MAX_ENTRIES = 10_000
_MAX_SHORTCUTS = 500
_MAX_PACKAGED_APP_RECORDS = 1_000
_MAX_DISCOVERY_SECONDS = 2.0
_SHORTCUT_EXTENSION = ".lnk"
_REPARSE_POINT_ATTRIBUTE = 0x400
_BLOCKED_EXECUTABLES = {
    "bash.exe",
    "certutil.exe",
    "cmd.exe",
    "cscript.exe",
    "mshta.exe",
    "powershell.exe",
    "pwsh.exe",
    "python.exe",
    "pythonw.exe",
    "regsvr32.exe",
    "rundll32.exe",
    "sh.exe",
    "wscript.exe",
    "windowsterminal.exe",
    "wt.exe",
}
_BLOCKED_DISPLAY_NAMES = {
    "cmd",
    "command prompt",
    "powershell",
    "windows powershell",
    "pwsh",
    "python",
    "pythonw",
    "windows terminal",
}
_REGISTERED_GUI_APPLICATIONS = {
    "chrome.exe": ("Google Chrome", "google chrome"),
    "msedge.exe": ("Microsoft Edge", "microsoft edge"),
    "firefox.exe": ("Mozilla Firefox", "mozilla firefox"),
    "spotify.exe": ("Spotify", "spotify"),
    "discord.exe": ("Discord", "discord"),
    "whatsapp.exe": ("WhatsApp", "whatsapp"),
    "code.exe": ("Visual Studio Code", "visual studio code"),
    "winword.exe": ("Microsoft Word", "microsoft word"),
    "excel.exe": ("Microsoft Excel", "microsoft excel"),
}
_KNOWN_PACKAGED_APPLICATIONS = {
    "5319275a.whatsappdesktop_": ("WhatsApp", "whatsapp"),
    "microsoft.paint_": ("Microsoft Paint", "microsoft paint"),
    "microsoft.windowscalculator_": ("Calculator", "calculator"),
    "microsoft.windows.photos_": ("Microsoft Photos", "microsoft photos"),
    "spotifyab.spotifymusic_": ("Spotify", "spotify"),
}
_PACKAGED_APPS_REGISTRY_PATH = (
    r"Software\Classes\Local Settings\Software\Microsoft\Windows"
    r"\CurrentVersion\AppModel\Repository\Packages"
)
_APP_PATHS_REGISTRY_KEYS = (
    ("HKCU", 0x0100, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
    ("HKCU", 0x0200, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
    ("HKLM", 0x0100, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
    ("HKLM", 0x0200, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
)

_KNOWN_FOLDERS = {
    "roaming_appdata": "{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}",
    "program_data": "{62AB5D82-FDC1-4DC3-A9DD-070D1D495D97}",
    "program_files": "{905e63b6-c1bf-494e-b29c-65b732d3d21a}",
    "program_files_x86": "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}",
    "local_appdata": "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}",
}


@dataclass(frozen=True)
class DiscoveredApplication:
    """Validated metadata from a trusted Windows application registration."""

    display_name: str
    normalized_name: str
    target: Path | None
    source_type: str
    target_exists: bool
    launch_type: str = "executable"
    expected_executable: str | None = None
    package_identity: str | None = None


@dataclass(frozen=True)
class DeveloperApplicationDiagnostic:
    """Internal diagnostic metadata; never included in assistant tool results."""

    display_name: str
    normalized_name: str
    source_type: str
    target_path: str
    target_filename: str
    target_type: str
    target_exists: bool
    passes_validation: bool
    launch_type: str = "executable"
    package_identity: str | None = None


@dataclass(frozen=True)
class _ResolvedShortcut:
    target: Path
    arguments: str


def normalize_application_name(value: str) -> str:
    """Normalize a display name for exact, punctuation-insensitive matching."""
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def discover_windows_applications() -> tuple[DiscoveredApplication, ...]:
    """Discover apps from trusted Start Menu and known App Paths registrations."""
    if not _is_windows():
        return ()
    install_roots = _trusted_install_roots()
    applications: list[DiscoveredApplication] = []
    start_menu_roots = _start_menu_roots() if install_roots else ()
    if start_menu_roots:
        applications.extend(
            _discover_from_roots(
                start_menu_roots,
                install_roots,
                _resolve_shortcut,
            )
        )
    if install_roots:
        applications.extend(_discover_app_paths(install_roots))
    applications.extend(_discover_packaged_applications())
    return _deduplicate_applications(tuple(applications))


def _discover_app_paths(
    install_roots: tuple[Path, ...],
    registry_reader: Callable[[str, str], str | None] | None = None,
) -> tuple[DiscoveredApplication, ...]:
    """Read only fixed App Paths keys for the known GUI executable allowlist."""
    if not _is_windows():
        return ()
    read_value = registry_reader or _read_app_paths_default_value
    discovered: list[DiscoveredApplication] = []
    for executable_name, (display_name, normalized_name) in (
        _REGISTERED_GUI_APPLICATIONS.items()
    ):
        for hive, view, key_path in _APP_PATHS_REGISTRY_KEYS:
            registered_value = read_value(
                f"{hive}|{view}|{key_path}\\{executable_name}",
                "",
            )
            if registered_value is None:
                continue
            target = _parse_registered_executable(registered_value)
            if target is None or target.name.casefold() != executable_name:
                continue
            validated_target = _validate_shortcut_target(
                _ResolvedShortcut(target, ""),
                install_roots,
            )
            if validated_target is None:
                continue
            discovered.append(
                DiscoveredApplication(
                    display_name=display_name,
                    normalized_name=normalized_name,
                    target=validated_target,
                    source_type="app_paths_registry",
                    target_exists=True,
                    expected_executable=executable_name,
                )
            )
    return _deduplicate_applications(tuple(discovered))


def _read_app_paths_default_value(key_reference: str, value_name: str) -> str | None:
    if not _is_windows():
        return None
    import winreg

    hive_name, view_text, key_path = key_reference.split("|", 2)
    hive = (
        winreg.HKEY_CURRENT_USER
        if hive_name == "HKCU"
        else winreg.HKEY_LOCAL_MACHINE
    )
    view = int(view_text)
    try:
        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ | view) as key:
            value, value_type = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    if value_type != winreg.REG_SZ or not isinstance(value, str):
        return None
    return value


def _discover_packaged_applications(
    package_reader: Callable[[], tuple[str, ...]] | None = None,
) -> tuple[DiscoveredApplication, ...]:
    """Discover known Store app registrations as metadata only, never targets."""
    if not _is_windows():
        return ()
    read_packages = package_reader or _read_registered_package_names
    discovered: list[DiscoveredApplication] = []
    for package_identity in read_packages():
        folded_identity = package_identity.casefold()
        for prefix, (display_name, normalized_name) in (
            _KNOWN_PACKAGED_APPLICATIONS.items()
        ):
            if not folded_identity.startswith(prefix):
                continue
            package_family = package_identity.split("_", 1)[0]
            discovered.append(
                DiscoveredApplication(
                    display_name=display_name,
                    normalized_name=normalized_name,
                    target=None,
                    source_type="packaged_app_registry",
                    target_exists=False,
                    launch_type="packaged_discovery_only",
                    package_identity=package_family,
                )
            )
            break
    return _deduplicate_applications(tuple(discovered))


def _read_registered_package_names() -> tuple[str, ...]:
    """Read bounded package identities from the current user's fixed registry key."""
    if not _is_windows():
        return ()
    import winreg

    package_names: list[str] = []
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _PACKAGED_APPS_REGISTRY_PATH,
            0,
            winreg.KEY_READ,
        ) as key:
            count = min(
                winreg.QueryInfoKey(key)[0],
                _MAX_PACKAGED_APP_RECORDS,
            )
            for index in range(count):
                try:
                    package_names.append(winreg.EnumKey(key, index))
                except OSError:
                    continue
    except OSError:
        return ()
    return tuple(package_names)


def _parse_registered_executable(value: str) -> Path | None:
    candidate = value.strip()
    if len(candidate) < 3 or len(candidate) > 32767:
        return None
    if candidate.startswith('"') and candidate.endswith('"'):
        candidate = candidate[1:-1]
    if (
        '"' in candidate
        or any(character in candidate for character in ("\r", "\n", "\0"))
        or candidate.casefold().endswith((".bat", ".cmd", ".js", ".msi", ".ps1", ".url", ".vbs"))
    ):
        return None
    target = Path(candidate)
    if (
        not target.is_absolute()
        or target.suffix.casefold() != ".exe"
        or target.name.casefold() not in _REGISTERED_GUI_APPLICATIONS
    ):
        return None
    return target


def _deduplicate_applications(
    applications: tuple[DiscoveredApplication, ...],
) -> tuple[DiscoveredApplication, ...]:
    deduplicated: dict[tuple[str, str, str], DiscoveredApplication] = {}
    for application in applications:
        target_path = (
            str(application.target.resolve(strict=False)).casefold()
            if application.target is not None
            else ""
        )
        identity = (
            application.normalized_name,
            target_path,
            (application.package_identity or "").casefold(),
        )
        previous = deduplicated.get(identity)
        if previous is None:
            deduplicated[identity] = application
            continue
        sources = set(previous.source_type.split("+"))
        sources.add(application.source_type)
        deduplicated[identity] = DiscoveredApplication(
            display_name=previous.display_name,
            normalized_name=previous.normalized_name,
            target=previous.target,
            source_type="+".join(sorted(sources)),
            target_exists=previous.target_exists or application.target_exists,
            launch_type=previous.launch_type,
            expected_executable=(
                previous.expected_executable or application.expected_executable
            ),
            package_identity=previous.package_identity or application.package_identity,
        )
    return tuple(deduplicated.values())


def _discover_from_roots(
    start_menu_roots: tuple[Path, ...],
    install_roots: tuple[Path, ...],
    shortcut_resolver: Callable[[Path], _ResolvedShortcut],
) -> tuple[DiscoveredApplication, ...]:
    applications: list[DiscoveredApplication] = []
    visited_entries = 0
    resolved_shortcuts = 0
    started_at = time.monotonic()
    for root in start_menu_roots:
        trusted_root = _safe_existing_directory(root)
        if trusted_root is None:
            continue
        pending_directories = [trusted_root]
        while (
            pending_directories
            and visited_entries < _MAX_ENTRIES
            and time.monotonic() - started_at < _MAX_DISCOVERY_SECONDS
        ):
            directory = pending_directories.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if time.monotonic() - started_at >= _MAX_DISCOVERY_SECONDS:
                            break
                        visited_entries += 1
                        if visited_entries > _MAX_ENTRIES:
                            break
                        try:
                            entry_stat = entry.stat(follow_symlinks=False)
                        except OSError:
                            continue
                        if _is_reparse_stat(entry_stat):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            pending_directories.append(Path(entry.path))
                            continue
                        if (
                            not entry.is_file(follow_symlinks=False)
                            or Path(entry.name).suffix.casefold() != _SHORTCUT_EXTENSION
                            or resolved_shortcuts >= _MAX_SHORTCUTS
                        ):
                            continue
                        resolved_shortcuts += 1
                        shortcut_path = Path(entry.path)
                        try:
                            shortcut = shortcut_resolver(shortcut_path)
                            target = _validate_shortcut_target(
                                shortcut,
                                install_roots,
                                require_exists=False,
                            )
                        except (OSError, ValueError):
                            continue
                        if target is None:
                            continue
                        display_name = "".join(
                            character
                            for character in Path(entry.name).stem
                            if ord(character) >= 32 and ord(character) != 127
                        ).strip()[:100]
                        normalized_name = normalize_application_name(display_name)
                        if (
                            not normalized_name
                            or normalized_name in _BLOCKED_DISPLAY_NAMES
                        ):
                            continue
                        applications.append(
                            DiscoveredApplication(
                                display_name=display_name,
                                normalized_name=normalized_name,
                                target=target,
                                source_type="start_menu_shortcut",
                                target_exists=target.is_file(),
                            )
                        )
            except OSError:
                continue
            if resolved_shortcuts >= _MAX_SHORTCUTS:
                break
        if (
            visited_entries >= _MAX_ENTRIES
            or resolved_shortcuts >= _MAX_SHORTCUTS
            or time.monotonic() - started_at >= _MAX_DISCOVERY_SECONDS
        ):
            break
    return tuple(applications)


def validate_discovered_target(target: Path) -> Path | None:
    """Revalidate a discovered target immediately before a launch request."""
    if not _is_windows():
        return None
    return _validate_shortcut_target(
        _ResolvedShortcut(target=target, arguments=""),
        _trusted_install_roots(),
    )


def diagnose_discovered_applications(
    applications: tuple[DiscoveredApplication, ...] | None = None,
) -> tuple[DeveloperApplicationDiagnostic, ...]:
    """Return target details for developer diagnostics only, not tool responses."""
    discovered = (
        discover_windows_applications()
        if applications is None
        else applications
    )
    return tuple(
        DeveloperApplicationDiagnostic(
            display_name=application.display_name,
            normalized_name=application.normalized_name,
            source_type=application.source_type,
            target_path=(
                str(application.target) if application.target is not None else ""
            ),
            target_filename=(
                application.target.name if application.target is not None else ""
            ),
            target_type=(
                application.target.suffix.casefold()
                if application.target is not None
                else ".appx"
            ),
            target_exists=application.target_exists,
            passes_validation=(
                application.target_exists
                and application.target is not None
                and validate_discovered_target(application.target) is not None
            ),
            launch_type=application.launch_type,
            package_identity=application.package_identity,
        )
        for application in discovered
    )


def _start_menu_roots() -> tuple[Path, ...]:
    roaming = _known_folder_path(_KNOWN_FOLDERS["roaming_appdata"])
    program_data = _known_folder_path(_KNOWN_FOLDERS["program_data"])
    roots: list[Path] = []
    if roaming is not None:
        roots.append(roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if program_data is not None:
        roots.append(program_data / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return tuple(roots)


def _trusted_install_roots() -> tuple[Path, ...]:
    folders = (
        "program_files",
        "program_files_x86",
        "local_appdata",
    )
    roots: list[Path] = []
    for folder in folders:
        base = _known_folder_path(_KNOWN_FOLDERS[folder])
        if base is None:
            continue
        if folder == "local_appdata":
            roots.extend((base / "Programs", base / "Microsoft" / "WindowsApps"))
        else:
            roots.append(base)
    return tuple(roots)


def _known_folder_path(identifier: str) -> Path | None:
    if not _is_windows():
        return None
    try:
        guid = _GUID.from_string(identifier)
        path_pointer = wintypes.LPWSTR()
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
        get_known_folder = shell32.SHGetKnownFolderPath
        get_known_folder.argtypes = [
            ctypes.POINTER(_GUID),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        get_known_folder.restype = ctypes.c_long
        result = get_known_folder(
            ctypes.byref(guid),
            0,
            None,
            ctypes.byref(path_pointer),
        )
    except (AttributeError, OSError):
        return None
    if result < 0 or not path_pointer or not path_pointer.value:
        return None
    try:
        return Path(path_pointer.value)
    finally:
        free_task_memory = ole32.CoTaskMemFree
        free_task_memory.argtypes = [ctypes.c_void_p]
        free_task_memory.restype = None
        free_task_memory(ctypes.cast(path_pointer, ctypes.c_void_p))


def _safe_existing_directory(path: Path) -> Path | None:
    if not _is_local_path(path):
        return None
    try:
        if _contains_reparse_point(path):
            return None
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    return resolved if resolved.is_dir() else None


def _validate_shortcut_target(
    shortcut: _ResolvedShortcut,
    install_roots: tuple[Path, ...],
    *,
    require_exists: bool = True,
) -> Path | None:
    if shortcut.arguments.strip():
        return None
    target = shortcut.target
    if not target.is_absolute() or target.suffix.casefold() != ".exe":
        return None
    if target.name.casefold() in _BLOCKED_EXECUTABLES:
        return None
    if not _is_local_path(target):
        return None
    trusted_roots: list[Path] = []
    for root in install_roots:
        if not _is_local_path(root) or _contains_reparse_point(root):
            continue
        try:
            resolved_root = root.resolve(strict=True)
        except OSError:
            continue
        if _is_relative_to(target, root) or _is_relative_to(target, resolved_root):
            trusted_roots.append(resolved_root)
    if not trusted_roots:
        return None
    if _contains_reparse_point(target.parent):
        return None
    target_exists = target.is_file()
    if target_exists:
        if _contains_reparse_point(target):
            return None
    elif require_exists:
        return None
    try:
        resolved_target = target.resolve(strict=require_exists)
    except OSError:
        return None

    for resolved_root in trusted_roots:
        try:
            resolved_target.relative_to(resolved_root)
        except (OSError, ValueError):
            continue
        if not _contains_reparse_point_between(
            resolved_root,
            resolved_target,
            allow_missing_leaf=not target_exists,
        ):
            return resolved_target
    return None


def _is_local_path(path: Path) -> bool:
    anchor = path.anchor
    return path.is_absolute() and not anchor.startswith("\\\\")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _contains_reparse_point(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            if _is_reparse_stat(current.lstat()):
                return True
        except OSError:
            return True
    return False


def _contains_reparse_point_between(
    root: Path,
    target: Path,
    *,
    allow_missing_leaf: bool = False,
) -> bool:
    try:
        relative_parts = target.relative_to(root).parts
    except ValueError:
        return True
    current = root
    for index, part in enumerate(relative_parts):
        current = current / part
        try:
            if _is_reparse_stat(current.lstat()):
                return True
        except FileNotFoundError:
            if allow_missing_leaf and index == len(relative_parts) - 1:
                return False
            return True
        except OSError:
            return True
    return False


def _is_reparse_stat(stat_result: os.stat_result) -> bool:
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return stat.S_ISLNK(stat_result.st_mode) or bool(
        attributes & _REPARSE_POINT_ATTRIBUTE
    )


def _resolve_shortcut(shortcut_path: Path) -> _ResolvedShortcut:
    """Resolve a .lnk through Windows Shell COM without launching its target."""
    if not _is_windows():
        raise OSError("Windows shortcut resolution is available only on Windows.")

    shell_link = ctypes.c_void_p()
    persist_file = ctypes.c_void_p()
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    initialize_com = ole32.CoInitializeEx
    initialize_com.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    initialize_com.restype = ctypes.c_long
    initialized = initialize_com(None, 2)
    if initialized < 0 and initialized != -2147417850:
        raise OSError("Windows COM initialization failed.")
    should_uninitialize = initialized >= 0
    try:
        class_id = _GUID.from_string("{00021401-0000-0000-C000-000000000046}")
        shell_link_id = _GUID.from_string("{000214F9-0000-0000-C000-000000000046}")
        persist_file_id = _GUID.from_string("{0000010b-0000-0000-C000-000000000046}")
        create_instance = ole32.CoCreateInstance
        create_instance.argtypes = [
            ctypes.POINTER(_GUID),
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_GUID),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        create_instance.restype = ctypes.c_long
        _check_hresult(
            create_instance(
                ctypes.byref(class_id),
                None,
                1,
                ctypes.byref(shell_link_id),
                ctypes.byref(shell_link),
            )
        )

        query_interface = _com_method(
            shell_link,
            0,
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.POINTER(_GUID),
            ctypes.POINTER(ctypes.c_void_p),
        )
        _check_hresult(
            query_interface(
                shell_link,
                ctypes.byref(persist_file_id),
                ctypes.byref(persist_file),
            )
        )
        load_shortcut = _com_method(
            persist_file,
            5,
            ctypes.c_long,
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            wintypes.DWORD,
        )
        _check_hresult(load_shortcut(persist_file, str(shortcut_path), 0))

        target_buffer = ctypes.create_unicode_buffer(32768)
        get_path = _com_method(
            shell_link,
            3,
            ctypes.c_long,
            ctypes.c_void_p,
            wintypes.LPWSTR,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        _check_hresult(
            get_path(shell_link, target_buffer, len(target_buffer), None, 0)
        )

        arguments_buffer = ctypes.create_unicode_buffer(32768)
        get_arguments = _com_method(
            shell_link,
            10,
            ctypes.c_long,
            ctypes.c_void_p,
            wintypes.LPWSTR,
            ctypes.c_int,
        )
        _check_hresult(
            get_arguments(shell_link, arguments_buffer, len(arguments_buffer))
        )
        if not target_buffer.value:
            raise OSError("Shortcut has no filesystem target.")
        return _ResolvedShortcut(
            target=Path(target_buffer.value),
            arguments=arguments_buffer.value,
        )
    finally:
        _release_com_object(persist_file)
        _release_com_object(shell_link)
        if should_uninitialize:
            ole32.CoUninitialize()


def _com_method(
    instance: ctypes.c_void_p,
    index: int,
    result_type: Any,
    *argument_types: Any,
) -> Callable[..., int]:
    vtable = ctypes.cast(
        instance,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
    ).contents
    function_type = ctypes.WINFUNCTYPE(result_type, *argument_types)
    return function_type(vtable[index])


def _release_com_object(instance: ctypes.c_void_p) -> None:
    if instance.value is None:
        return
    release = _com_method(instance, 2, ctypes.c_ulong, ctypes.c_void_p)
    release(instance)


def _check_hresult(result: int) -> None:
    if result < 0:
        raise OSError(f"Windows API failed with HRESULT 0x{result & 0xFFFFFFFF:08X}.")


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, value: str) -> _GUID:
        import uuid

        return cls.from_buffer_copy(uuid.UUID(value.strip("{}")).bytes_le)


def _is_windows() -> bool:
    return sys.platform == "win32"
