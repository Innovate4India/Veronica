"""Read-only web search through the documented Tavily Search API."""

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.config import WebSearchConfig, load_web_search_config
from app.tools.base import (
    JSONValue,
    ParameterSchema,
    Tool,
    ToolUnavailableError,
    ToolValidationError,
)

TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"
DEFAULT_MAX_RESULTS = 5
MAX_RESULTS = 8
MAX_SNIPPET_LENGTH = 600
MAX_TITLE_LENGTH = 300
HTTP_RESPONSE_LIMIT = 1_000_000


@dataclass(frozen=True)
class WebSearchResult:
    """Compact search result fields safe to pass back to an AI model."""

    title: str
    url: str
    snippet: str


class WebSearchProviderError(Exception):
    """Raised for provider HTTP or response-format failures."""


class SearchProvider(Protocol):
    """Provider boundary that accepts only a query and bounded result count."""

    def search(self, query: str, max_results: int) -> tuple[WebSearchResult, ...]:
        """Return compact search results without fetching result URLs."""
        ...


class TavilySearchProvider:
    """Tavily adapter using a fixed official API endpoint."""

    def __init__(self, api_key: str, timeout_seconds: float = 8.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def search(self, query: str, max_results: int) -> tuple[WebSearchResult, ...]:
        payload = json.dumps(
            {
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
            }
        ).encode("utf-8")
        request = Request(
            TAVILY_SEARCH_ENDPOINT,
            data=payload,
            headers={
                "Authorization": "".join(("Be", "arer ", self._api_key)),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                response_data = response.read(HTTP_RESPONSE_LIMIT + 1)
        except HTTPError as error:
            raise WebSearchProviderError(
                f"Search provider returned HTTP {error.code}."
            ) from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError("Web search request timed out.") from None
            raise WebSearchProviderError("Search provider could not be reached.") from None
        except TimeoutError:
            raise TimeoutError("Web search request timed out.") from None
        except OSError:
            raise WebSearchProviderError("Search provider could not be reached.") from None

        if len(response_data) > HTTP_RESPONSE_LIMIT:
            raise WebSearchProviderError("Search provider response was too large.")
        try:
            decoded: object = json.loads(response_data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise WebSearchProviderError(
                "Search provider returned malformed JSON."
            ) from None
        if not isinstance(decoded, dict):
            raise WebSearchProviderError(
                "Search provider returned an invalid response."
            )
        raw_results = decoded.get("results")
        if not isinstance(raw_results, list):
            raise WebSearchProviderError(
                "Search provider returned an invalid result list."
            )

        results: list[WebSearchResult] = []
        for item in raw_results[:max_results]:
            if not isinstance(item, dict):
                raise WebSearchProviderError(
                    "Search provider returned a malformed result."
                )
            title = item.get("title")
            url = item.get("url")
            content = item.get("content")
            if (
                not isinstance(title, str)
                or not isinstance(url, str)
                or not isinstance(content, str)
            ):
                raise WebSearchProviderError(
                    "Search provider returned a malformed result."
                )
            if not _is_http_url(url):
                raise WebSearchProviderError(
                    "Search provider returned an invalid result URL."
                )
            results.append(
                WebSearchResult(
                    title=title[:MAX_TITLE_LENGTH],
                    url=url,
                    snippet=content[:MAX_SNIPPET_LENGTH],
                )
            )
        return tuple(results)


class WebSearchTool(Tool):
    """Search the public web for current information using only the query."""

    def __init__(
        self,
        provider: SearchProvider | None = None,
        config: WebSearchConfig | None = None,
    ) -> None:
        self._config = config or load_web_search_config()
        self._provider = provider
        if self._provider is None and self._config.provider == "tavily":
            self._provider = TavilySearchProvider(
                self._config.api_key,
                self._config.timeout_seconds,
            )

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the public web for current information. Sends only the "
            "search query and result limit to Tavily; it does not fetch pages."
        )

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A concise search query using terms from the user's request.",
                    "minLength": 1,
                    "maxLength": 500,
                },
                "max_results": {
                    "type": "integer",
                    "description": f"An integer from 1 through {MAX_RESULTS}.",
                    "minimum": 1,
                    "maximum": MAX_RESULTS,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        """Search for a query and return only bounded titles, URLs, and snippets."""
        query = parameters.get("query")
        max_results = parameters.get("max_results", DEFAULT_MAX_RESULTS)
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ToolValidationError(
                "query must be a non-empty string of at most 500 characters."
            )
        if (
            isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or not 1 <= max_results <= MAX_RESULTS
        ):
            raise ToolValidationError(
                f"max_results must be an integer from 1 to {MAX_RESULTS}."
            )
        if not self._config.provider or not self._config.api_key:
            raise ToolUnavailableError(
                "Web search is unavailable; configure TAVILY_API_KEY."
            )
        if self._provider is None:
            raise ToolUnavailableError("The configured web search provider is unavailable.")

        results = self._provider.search(query.strip(), max_results)
        return {
            "query": query.strip(),
            "results": [
                {
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                }
                for result in results[:max_results]
            ],
        }


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
    )
