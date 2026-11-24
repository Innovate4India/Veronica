"""Tests for the optional, isolated Tavily web-search tool."""

import json
import logging
import unittest
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from app.config import WebSearchConfig, load_web_search_config
from app.tools import ToolRegistry, ToolStatus, WebSearchTool
from app.tools.web_search import (
    TAVILY_SEARCH_ENDPOINT,
    TavilySearchProvider,
    WebSearchProviderError,
    WebSearchResult,
)

_API_KEY = "test-api-key-never-log"
_QUERY = "current Python release"


def _response(results: list[dict[str, str]]) -> Mock:
    response = Mock()
    response.read.return_value = json.dumps({"results": results}).encode()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=None)
    return response


def _provider_results(count: int) -> list[dict[str, str]]:
    return [
        {
            "title": f"Result {index}",
            "url": f"https://example.com/{index}",
            "content": f"Summary {index}",
        }
        for index in range(count)
    ]


class WebSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = WebSearchConfig(
            provider="tavily",
            api_key=_API_KEY,
            timeout_seconds=3,
        )
        self.provider = Mock()
        self.provider.search.return_value = (
            WebSearchResult("Python", "https://example.com/python", "A summary"),
        )
        self.tool = WebSearchTool(self.provider, self.config)
        self.registry = ToolRegistry()
        self.registry.register(self.tool)

    def test_valid_search_returns_compact_results(self) -> None:
        result = self.registry.execute("web_search", {"query": _QUERY})

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(
            result.data,
            {
                "query": _QUERY,
                "results": [
                    {
                        "title": "Python",
                        "url": "https://example.com/python",
                        "snippet": "A summary",
                    }
                ],
            },
        )
        self.provider.search.assert_called_once_with(_QUERY, 5)

    def test_missing_empty_and_invalid_query_are_rejected(self) -> None:
        for parameters in ({}, {"query": ""}, {"query": "  "}, {"query": 12}):
            with self.subTest(parameters=parameters):
                result = self.registry.execute("web_search", parameters)
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)
        self.provider.search.assert_not_called()

    def test_invalid_result_count_and_unexpected_parameters_are_rejected(self) -> None:
        for parameters in (
            {"query": _QUERY, "max_results": 0},
            {"query": _QUERY, "max_results": 9},
            {"query": _QUERY, "max_results": True},
            {"query": _QUERY, "unexpected": "value"},
        ):
            with self.subTest(parameters=parameters):
                result = self.registry.execute("web_search", parameters)
                self.assertEqual(result.status, ToolStatus.VALIDATION_FAILURE)
        self.provider.search.assert_not_called()

    def test_missing_api_key_returns_structured_unavailable(self) -> None:
        tool = WebSearchTool(
            self.provider,
            WebSearchConfig(provider="tavily", api_key=""),
        )
        registry = ToolRegistry()
        registry.register(tool)

        result = registry.execute("web_search", {"query": _QUERY})

        self.assertEqual(result.status, ToolStatus.UNAVAILABLE)
        self.assertEqual(
            result.error.message if result.error else None,
            "Web search is unavailable; configure TAVILY_API_KEY.",
        )
        self.provider.search.assert_not_called()

    def test_tool_caps_results_returned_by_provider(self) -> None:
        self.provider.search.return_value = tuple(
            WebSearchResult(str(index), f"https://example.com/{index}", "summary")
            for index in range(7)
        )

        result = self.registry.execute(
            "web_search",
            {"query": _QUERY, "max_results": 2},
        )

        if not isinstance(result.data, dict):
            self.fail("Successful search must return an object.")
        results = result.data.get("results")
        if not isinstance(results, list):
            self.fail("Successful search must return a results list.")
        self.assertEqual(len(results), 2)
        self.provider.search.assert_called_once_with(_QUERY, 2)

    def test_documented_tavily_request_is_bounded_and_contains_no_history(self) -> None:
        tavily = TavilySearchProvider(_API_KEY, timeout_seconds=2)
        with patch(
            "app.tools.web_search.urlopen",
            return_value=_response(_provider_results(4)),
        ) as urlopen_mock:
            results = tavily.search(_QUERY, 2)

        self.assertEqual(len(results), 2)
        request = urlopen_mock.call_args.args[0]
        body = json.loads(request.data.decode())
        self.assertEqual(
            body,
            {
                "query": _QUERY,
                "max_results": 2,
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
            },
        )
        self.assertNotIn("conversation", body)
        self.assertEqual(request.full_url, TAVILY_SEARCH_ENDPOINT)
        self.assertEqual(
            request.get_header("Authorization"),
            "".join(("Be", "arer ", _API_KEY)),
        )
        self.assertEqual(urlopen_mock.call_args.kwargs["timeout"], 2)

    def test_provider_http_failure_is_safe_and_does_not_log_api_key(self) -> None:
        provider = TavilySearchProvider(_API_KEY)
        self.tool = WebSearchTool(provider, self.config)
        registry = ToolRegistry()
        registry.register(self.tool)
        http_error = HTTPError(
            TAVILY_SEARCH_ENDPOINT,
            503,
            "unavailable",
            Message(),
            BytesIO(_API_KEY.encode()),
        )

        with patch("app.tools.web_search.urlopen", side_effect=http_error):
            with self.assertLogs("app.tools.registry", level=logging.INFO) as captured:
                result = registry.execute("web_search", {"query": _QUERY})

        self.assertEqual(result.status, ToolStatus.EXECUTION_FAILURE)
        self.assertNotIn(_API_KEY, "\n".join(captured.output))

    def test_malformed_provider_response_is_reported(self) -> None:
        provider = TavilySearchProvider(_API_KEY)
        with patch(
            "app.tools.web_search.urlopen",
            return_value=_response([{"title": "missing fields"}]),
        ):
            with self.assertRaises(WebSearchProviderError):
                provider.search(_QUERY, 1)

    def test_invalid_result_url_is_rejected_without_fetching_it(self) -> None:
        provider = TavilySearchProvider(_API_KEY)
        malformed = [{"title": "bad", "url": "file:///secret", "content": "text"}]
        with patch(
            "app.tools.web_search.urlopen",
            return_value=_response(malformed),
        ):
            with self.assertRaises(WebSearchProviderError):
                provider.search(_QUERY, 1)

    def test_provider_timeout_maps_to_registry_timeout(self) -> None:
        provider = TavilySearchProvider(_API_KEY)
        self.tool = WebSearchTool(provider, self.config)
        registry = ToolRegistry()
        registry.register(self.tool)
        with patch("app.tools.web_search.urlopen", side_effect=TimeoutError):
            result = registry.execute("web_search", {"query": _QUERY})

        self.assertEqual(result.status, ToolStatus.TIMEOUT)

    def test_provider_truncates_large_title_and_snippet_fields(self) -> None:
        provider = TavilySearchProvider(_API_KEY)
        result_data = [
            {
                "title": "T" * 500,
                "url": "https://example.com/item",
                "content": "S" * 1000,
            }
        ]
        with patch(
            "app.tools.web_search.urlopen",
            return_value=_response(result_data),
        ):
            result = provider.search(_QUERY, 1)[0]

        self.assertEqual(len(result.title), 300)
        self.assertEqual(len(result.snippet), 600)

    def test_configuration_is_optional_and_hides_api_key_from_repr(self) -> None:
        config = load_web_search_config(
            {
                "WEB_SEARCH_PROVIDER": "TAVILY",
                "TAVILY_API_KEY": _API_KEY,
                "WEB_SEARCH_TIMEOUT_SECONDS": "4",
            }
        )

        self.assertEqual(config.provider, "tavily")
        self.assertEqual(config.api_key, _API_KEY)
        self.assertEqual(config.timeout_seconds, 4)
        self.assertNotIn(_API_KEY, repr(config))
        self.assertEqual(load_web_search_config({}).api_key, "")

    def test_configuration_rejects_unbounded_timeout_and_unknown_provider(self) -> None:
        for values in (
            {"WEB_SEARCH_TIMEOUT_SECONDS": "0"},
            {"WEB_SEARCH_TIMEOUT_SECONDS": "21"},
            {"WEB_SEARCH_PROVIDER": "arbitrary"},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    load_web_search_config(values)


if __name__ == "__main__":
    unittest.main()
