"""Safely request opening a validated web URL in the default browser."""

import re
import webbrowser
from urllib.parse import SplitResult, urlsplit, urlunsplit

from app.tools.base import JSONValue, ParameterSchema, Tool, ToolValidationError

_DOMAIN_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z")
_IPV4_PART = re.compile(r"[0-9]{1,3}\Z")
_MAX_URL_LENGTH = 2048


class OpenURLTool(Tool):
    """Open one validated HTTP(S) URL without interacting with the page."""

    @property
    def name(self) -> str:
        return "open_url"

    @property
    def description(self) -> str:
        return (
            "Use this tool only when the user explicitly asks to open or launch "
            "a website or URL in their default browser, such as 'Open YouTube', "
            "'Open GitHub', or 'Launch Google in my browser'. It opens only a "
            "validated HTTP or HTTPS URL. It does not inspect, read, click, "
            "submit, download from, or otherwise interact with the webpage. "
            "Do not use it just to answer questions about a website; use "
            "web_search for information retrieval. This tool cannot control "
            "the computer or interact with accounts."
        )

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "A complete http/https URL or a plain public website "
                        "domain such as github.com."
                    ),
                    "minLength": 1,
                    "maxLength": _MAX_URL_LENGTH,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        }

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        url = parameters.get("url")
        if not isinstance(url, str):
            raise ToolValidationError("url must be a string.")
        normalized = _normalize_and_validate_url(url)
        try:
            opened = webbrowser.open(normalized, new=2)
        except (OSError, webbrowser.Error):
            return {
                "status": "unavailable",
                "url": normalized,
                "message": "The default browser could not be requested.",
            }
        if not opened:
            return {
                "status": "unavailable",
                "url": normalized,
                "message": "The default browser did not accept the open request.",
            }
        return {
            "status": "success",
            "url": normalized,
            "message": "Requested the default browser to open the URL.",
        }


def _normalize_and_validate_url(value: str) -> str:
    candidate = value.strip()
    if not candidate or len(candidate) > _MAX_URL_LENGTH:
        raise ToolValidationError(
            f"url must be a non-empty URL of at most {_MAX_URL_LENGTH} characters."
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        raise ToolValidationError("url contains invalid control characters.")
    if any(character.isspace() for character in candidate):
        raise ToolValidationError("url must not contain whitespace.")
    if re.search(r"%(?![0-9A-Fa-f]{2})", candidate):
        raise ToolValidationError("url contains malformed percent encoding.")
    if "\\" in candidate or candidate.startswith("//"):
        raise ToolValidationError("Only valid HTTP and HTTPS website URLs are allowed.")

    parsed = _parse_url(candidate)
    if not parsed.scheme:
        if not _is_plain_domain(candidate):
            raise ToolValidationError(
                "Provide a valid http/https URL or a plain website domain."
            )
        candidate = f"https://{candidate}"
        parsed = _parse_url(candidate)

    if parsed.scheme.casefold() not in {"http", "https"}:
        raise ToolValidationError("Only http and https URLs are allowed.")
    if not parsed.netloc or not parsed.hostname:
        raise ToolValidationError(
            "The URL must contain a valid network hostname."
        )
    if parsed.username is not None or parsed.password is not None:
        raise ToolValidationError("URLs containing credentials are not allowed.")
    if not _is_valid_hostname(parsed.hostname):
        raise ToolValidationError("The URL must contain a valid network hostname.")
    try:
        port = parsed.port
    except ValueError:
        raise ToolValidationError("The URL contains an invalid port.") from None
    if port is not None and not 1 <= port <= 65535:
        raise ToolValidationError("The URL contains an invalid port.")
    return urlunsplit(
        SplitResult(
            parsed.scheme.casefold(),
            parsed.netloc,
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def _parse_url(value: str) -> SplitResult:
    try:
        return urlsplit(value)
    except ValueError:
        raise ToolValidationError("The URL is malformed.") from None


def _is_plain_domain(value: str) -> bool:
    if any(character.isspace() for character in value):
        return False
    if any(character in value for character in "@?#"):
        return False
    authority = value.split("/", 1)[0]
    if not authority or authority.startswith(".") or authority.endswith("."):
        return False
    if authority.count(":") > 1:
        return False
    host = authority.rsplit(":", 1)[0] if ":" in authority else authority
    if ":" in authority:
        port_text = authority.rsplit(":", 1)[1]
        if not port_text.isascii() or not port_text.isdigit():
            return False
        if not 1 <= int(port_text) <= 65535:
            return False
    return _is_valid_hostname(host)


def _is_valid_hostname(hostname: str) -> bool:
    host = hostname.rstrip(".")
    if not host or len(host) > 253 or "%" in host:
        return False
    if ":" in host:
        try:
            import ipaddress

            ipaddress.IPv6Address(host)
        except ValueError:
            return False
        return True
    if all(_IPV4_PART.fullmatch(part) for part in host.split(".")):
        try:
            import ipaddress

            ipaddress.IPv4Address(host)
        except ValueError:
            return False
        return True
    labels = host.split(".")
    if len(labels) < 2:
        return False
    return all(_DOMAIN_LABEL.fullmatch(label) for label in labels)
