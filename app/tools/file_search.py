"""Bounded, read-only search of explicitly configured local directories."""

import os
import re
import stat
import time
from pathlib import Path
from typing import Iterable

from app.config import load_file_search_roots
from app.tools.base import (
    JSONValue,
    ParameterSchema,
    Tool,
    ToolUnavailableError,
    ToolValidationError,
)

MAX_QUERY_LENGTH = 128
MAX_PATH_LENGTH = 1024
MAX_RESULT_PATH_LENGTH = 2048
MAX_RESULTS = 50
MAX_VISITED_ENTRIES = 10_000
SEARCH_TIMEOUT_SECONDS = 2.0

_SENSITIVE_NAME = re.compile(
    r"(?:^|[._ -])(?:secrets?|credentials?|tokens?|passwords?|passwd|auth|"
    r"id_rsa|id_ed25519|known_hosts|authorized_keys|service[._ -]?account|"
    r"(?:api|access|secret|encryption|signing|private)[._ -]?keys?)(?:$|[._ -])"
)
_SENSITIVE_SUFFIXES = {".pem", ".p12", ".pfx", ".key"}
_EXCLUDED_DIRECTORIES = {
    ".aws",
    ".azure",
    ".docker",
    ".gnupg",
    ".git",
    ".kube",
    ".ssh",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}


class FileSearchTool(Tool):
    """Find names inside configured local roots without opening file contents."""

    def __init__(self, roots: Iterable[Path] | None = None) -> None:
        configured_roots = tuple(
            Path(root).expanduser()
            for root in (roots if roots is not None else load_file_search_roots())
        )
        if not configured_roots or len(configured_roots) > 16:
            raise ValueError("File search requires between 1 and 16 configured roots.")
        if any(not root.is_absolute() for root in configured_roots):
            raise ValueError("Every file-search root must be an absolute path.")
        self._roots = tuple(root.resolve(strict=False) for root in configured_roots)

    @property
    def name(self) -> str:
        return "file_search"

    @property
    def description(self) -> str:
        return (
            "Use this tool when the user asks to find, locate, or search for "
            "files or folders by name in a local project, including requests "
            "such as 'find files related to calculator'. Search matches "
            "filenames and directory names only, recursively within configured "
            "local folders. It is read-only and returns metadata only; it "
            "never reads file contents or searches outside those folders."
        )

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Case-insensitive text to match in a name.",
                    "minLength": 1,
                    "maxLength": MAX_QUERY_LENGTH,
                },
                "path": {
                    "type": "string",
                    "description": (
                        "Optional subdirectory within a configured root. Omit "
                        "this parameter unless the user names a specific folder; "
                        "do not pass an empty string."
                    ),
                    "maxLength": MAX_PATH_LENGTH,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        """Search bounded directory entries and return compact local metadata."""
        query = parameters.get("query")
        requested_path = parameters.get("path")
        if (
            not isinstance(query, str)
            or not query.strip()
            or len(query) > MAX_QUERY_LENGTH
        ):
            raise ToolValidationError(
                f"query must be a non-empty string of at most {MAX_QUERY_LENGTH} characters."
            )
        if requested_path is not None and (
            not isinstance(requested_path, str)
            or not requested_path.strip()
            or len(requested_path) > MAX_PATH_LENGTH
        ):
            raise ToolValidationError(
                f"path must be a non-empty string of at most {MAX_PATH_LENGTH} characters."
            )

        roots = tuple(
            root
            for root in self._roots
            if _is_directory(root) and not _contains_sensitive_component(root)
        )
        if not roots:
            raise ToolUnavailableError(
                "No configured local file-search root is currently available."
            )

        start_directories = _select_directories(roots, requested_path)
        normalized_query = query.strip().casefold()
        results: list[JSONValue] = []
        visited = 0
        complete = len(roots) == len(self._roots)
        deadline = time.monotonic() + SEARCH_TIMEOUT_SECONDS
        pending = list(start_directories)
        visited_directories: set[str] = set()

        while pending:
            if time.monotonic() >= deadline:
                complete = False
                break
            directory = pending.pop()
            identity = os.path.normcase(str(directory))
            if identity in visited_directories:
                continue
            visited_directories.add(identity)
            try:
                directory_stat = directory.stat(follow_symlinks=False)
                resolved_directory = directory.resolve(strict=True)
            except (OSError, RuntimeError):
                complete = False
                continue
            if _is_reparse_point(directory_stat) or not any(
                _is_within(resolved_directory, root)
                for root in roots
            ):
                complete = False
                continue
            try:
                entries = os.scandir(directory)
            except OSError:
                complete = False
                continue

            with entries:
                for entry in entries:
                    if time.monotonic() >= deadline or visited >= MAX_VISITED_ENTRIES:
                        complete = False
                        pending.clear()
                        break
                    visited += 1
                    try:
                        entry_stat = entry.stat(follow_symlinks=False)
                    except OSError:
                        complete = False
                        continue
                    if _is_reparse_point(entry_stat):
                        continue

                    entry_path = Path(entry.path)
                    is_directory = stat.S_ISDIR(entry_stat.st_mode)
                    if _is_sensitive_path(
                        entry_path.name,
                        is_directory=is_directory,
                    ):
                        continue
                    if is_directory:
                        pending.append(entry_path)

                    if normalized_query not in entry.name.casefold():
                        continue
                    if not is_directory and not stat.S_ISREG(entry_stat.st_mode):
                        continue
                    result_path = str(entry_path)
                    if len(result_path) > MAX_RESULT_PATH_LENGTH:
                        complete = False
                        continue
                    result: dict[str, JSONValue] = {
                        "name": entry.name,
                        "path": result_path,
                        "type": "directory" if is_directory else "file",
                    }
                    if not is_directory:
                        result["size"] = entry_stat.st_size
                    results.append(result)
                    if len(results) >= MAX_RESULTS:
                        complete = False
                        pending.clear()
                        break

        return {
            "query": query.strip(),
            "results": results,
            "visited_entries": visited,
            "complete": complete and not pending,
        }


def _select_directories(
    roots: tuple[Path, ...],
    requested_path: str | None,
) -> list[Path]:
    if requested_path is None:
        return list(roots)

    if ".." in requested_path.replace("\\", "/").split("/"):
        raise ToolValidationError("path must not contain parent-directory traversal.")
    user_path = Path(requested_path).expanduser()
    if user_path.is_absolute():
        candidates = [user_path]
    else:
        if user_path.drive:
            raise ToolValidationError("path must be relative or fully absolute.")
        candidates = [root / user_path for root in roots]

    selected: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if not resolved.is_dir():
            continue
        containing_root = next(
            (
                root
                for root in roots
                if _is_within(resolved, root)
            ),
            None,
        )
        if containing_root is None:
            if user_path.is_absolute():
                raise ToolValidationError(
                    "path must resolve inside a configured local file-search root."
                )
            continue
        lexical_candidate = candidate.absolute()
        if not _is_within(lexical_candidate, containing_root):
            raise ToolValidationError(
                "path must be specified within a configured local file-search root."
            )
        if _contains_reparse_component(containing_root, lexical_candidate):
            raise ToolValidationError(
                "path must not traverse a symbolic link or reparse point."
            )
        selected.append(resolved)

    if not selected:
        raise ToolValidationError(
            "path must identify an existing directory inside a configured root."
        )
    return selected


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _contains_reparse_component(root: Path, path: Path) -> bool:
    current = root
    try:
        for part in path.relative_to(root).parts:
            current /= part
            if _is_reparse_point(current.stat(follow_symlinks=False)):
                return True
    except OSError:
        return True
    return False


def _is_directory(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _is_reparse_point(entry_stat: os.stat_result) -> bool:
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(entry_stat, "st_file_attributes", 0)
    return stat.S_ISLNK(entry_stat.st_mode) or bool(attributes & reparse_attribute)


def _is_sensitive_path(name: str, *, is_directory: bool) -> bool:
    normalized = re.sub(
        r"(?<=[a-z0-9])(?=[A-Z])",
        "_",
        name,
    ).casefold()
    if normalized == ".env" or normalized.startswith(".env."):
        return True
    if _SENSITIVE_NAME.search(normalized):
        return True
    return is_directory and normalized in _EXCLUDED_DIRECTORIES or (
        not is_directory and Path(normalized).suffix in _SENSITIVE_SUFFIXES
    )


def _contains_sensitive_component(path: Path) -> bool:
    return any(
        _is_sensitive_path(part, is_directory=True)
        for part in path.parts
    )
