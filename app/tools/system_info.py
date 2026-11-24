"""Read-only, privacy-conscious local system information."""

import ctypes
import os
import platform
import shutil
from pathlib import Path
from typing import Callable

from app.config import PROJECT_ROOT
from app.tools.base import JSONValue, ParameterSchema, Tool, ToolValidationError

_CATEGORIES = ("overview", "os", "cpu", "memory", "python", "disk")


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class SystemInfoTool(Tool):
    """Provide bounded, local facts about this computer without controlling it."""

    @property
    def name(self) -> str:
        return "system_info"

    @property
    def description(self) -> str:
        return (
            "Use this read-only tool to answer questions about the current "
            "computer's operating system, CPU, RAM usage, Python version, "
            "architecture, or Veronica project-drive capacity. Choose a "
            "category from overview, os, cpu, memory, python, or disk; omit "
            "category for a general overview. This tool only reads bounded "
            "system metrics. It cannot control the computer, change settings, "
            "run programs, inspect credentials, or access user/browser data."
        )

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional metric group to retrieve.",
                    "enum": list(_CATEGORIES),
                },
            },
            "required": [],
            "additionalProperties": False,
        }

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        category = parameters.get("category", "overview")
        if not isinstance(category, str) or category not in _CATEGORIES:
            raise ToolValidationError(
                "category must be one of overview, os, cpu, memory, python, or disk."
            )

        collectors: dict[str, Callable[[], dict[str, JSONValue]]] = {
            "os": self._os_info,
            "cpu": self._cpu_info,
            "memory": self._memory_info,
            "python": self._python_info,
            "disk": self._disk_info,
        }
        categories = (
            ("os", "cpu", "memory", "python", "disk")
            if category == "overview"
            else (category,)
        )
        information: dict[str, JSONValue] = {}
        for name in categories:
            information[name] = self._collect(collectors[name])
        return {"category": category, "information": information}

    @staticmethod
    def _collect(
        collector: Callable[[], dict[str, JSONValue]],
    ) -> JSONValue:
        try:
            return collector()
        except Exception:
            return {
                "status": "unavailable",
                "reason": "This system metric is unavailable on this computer.",
            }

    @staticmethod
    def _os_info() -> dict[str, JSONValue]:
        return {
            "name": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
        }

    @staticmethod
    def _cpu_info() -> dict[str, JSONValue]:
        processor_name = _processor_name()
        physical_count = _physical_cpu_count()
        return {
            "processor_name": processor_name
            if processor_name
            else _unavailable_metric(),
            "logical_cpu_count": os.cpu_count() or _unavailable_metric(),
            "physical_cpu_count": physical_count
            if physical_count is not None
            else _unavailable_metric(),
        }

    @staticmethod
    def _memory_info() -> dict[str, JSONValue]:
        total, available = _physical_memory()
        used = total - available
        return {
            "total_bytes": total,
            "available_bytes": available,
            "used_bytes": used,
            "usage_percent": round((used / total) * 100, 1) if total else 0,
        }

    @staticmethod
    def _python_info() -> dict[str, JSONValue]:
        return {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        }

    @staticmethod
    def _disk_info() -> dict[str, JSONValue]:
        usage = shutil.disk_usage(Path(PROJECT_ROOT).anchor or str(PROJECT_ROOT))
        return {
            "scope": "Veronica project drive",
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "usage_percent": round((usage.used / usage.total) * 100, 1)
            if usage.total
            else 0,
        }


def _processor_name() -> str | None:
    if platform.system() == "Windows":
        import winreg

        key_path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        except OSError:
            return None
        return value.strip() if isinstance(value, str) and value.strip() else None
    value = platform.processor().strip()
    return value or None


def _physical_cpu_count() -> int | None:
    return None


def _physical_memory() -> tuple[int, int]:
    if platform.system() == "Windows":
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("Windows memory status query failed.")
        total = int(status.ullTotalPhys)
        available = int(status.ullAvailPhys)
        if total <= 0 or not 0 <= available <= total:
            raise OSError("Windows returned invalid physical memory values.")
        return total, available

    sysconf = getattr(os, "sysconf", None)
    if not callable(sysconf):
        raise OSError("Physical memory metrics are not supported.")
    page_size = sysconf("SC_PAGE_SIZE")
    total_pages = sysconf("SC_PHYS_PAGES")
    available_pages = sysconf("SC_AVPHYS_PAGES")
    if (
        not isinstance(page_size, int)
        or not isinstance(total_pages, int)
        or not isinstance(available_pages, int)
    ):
        raise OSError("Physical memory values are unavailable.")
    page_size_value = int(page_size)
    total_pages_value = int(total_pages)
    available_pages_value = int(available_pages)
    total = page_size_value * total_pages_value
    available = page_size_value * available_pages_value
    if total <= 0 or not 0 <= available <= total:
        raise OSError("Physical memory values are unavailable.")
    return total, available


def _unavailable_metric() -> dict[str, JSONValue]:
    return {
        "status": "unavailable",
        "reason": "This metric is unavailable on this computer.",
    }
