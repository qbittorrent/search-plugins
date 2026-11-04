"""Offline regression tests using upstream's pinned auxiliary helpers."""

# Transport regression tests intentionally exercise the private request method.
# pyright: reportPrivateUsage=false
# pylint: disable=protected-access

from __future__ import annotations

import contextlib
import gzip
import http.client
import io
import json
import logging
import time
import unittest
import urllib.request
from email.message import Message
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlsplit

if TYPE_CHECKING:
    import pytest

from ..engines import piratebay as provider


def torrent(**changes: Any) -> dict[str, Any]:
    """Start with a valid API record and override only what a scenario needs."""
    record = {
        "id": "42",
        "info_hash": "abcdef0123" * 4,
        "name": "Ubuntu Linux",
        "size": "123456789",
        "seeders": "15",
        "leechers": "2",
        "added": "1696870394",
        "category": "303",
    }
    record.update(changes)
    return record


class Response(io.BytesIO):
    """An in-memory HTTP response that supports headers and automatic closure."""

    def __init__(
        self,
        payload: bytes,
        content_type: str = "application/json; charset=utf-8",
        encoding: str | None = None,
    ) -> None:
        super().__init__(payload)
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if encoding:
            self.headers["Content-Encoding"] = encoding


def json_response(value: object) -> Response:
    return Response(json.dumps(value).encode("utf-8"))


def request_parameters(request: urllib.request.Request) -> dict[str, list[str]]:
    """Read the query parameters actually sent by the provider."""
    return parse_qs(urlsplit(request.full_url).query)


def http_error(status: int) -> HTTPError:
    """Create an HTTP failure with a response body the provider must close."""
    return HTTPError("https://example.invalid", status, "test", Message(), io.BytesIO())


# Shared setup keeps network requests, delays, and result emission controlled.
class ProviderTestCase(unittest.TestCase):
    """Common fixtures for the focused unit tests below."""

    def setUp(self) -> None:
        self.engine = provider.piratebay()
        contexts = contextlib.ExitStack()
        self.addCleanup(contexts.close)
        self.warning = contexts.enter_context(patch.object(provider.logger, "warning"))
        self.sleep = contexts.enter_context(patch.object(time, "sleep"))
        self.print_result = contexts.enter_context(patch.object(provider, "prettyPrinter"))

    def printed(self) -> list[dict[str, Any]]:
        return [call.args[0] for call in self.print_result.call_args_list]


# Plugin discovery and category metadata.
class DiscoveryTests(ProviderTestCase):
    """Plugin discovery and category metadata."""

    def test_filename_and_class_match(self) -> None:
        stem = Path(provider.__file__).stem

        self.assertIs(getattr(provider, stem), provider.piratebay)
        self.assertEqual(self.engine.name, "The Pirate Bay")
        self.assertEqual(
            set(self.engine.supported_categories),
            {"all", "music", "movies", "software", "games", "books"},
        )
        self.assertNotIn("adult", self.engine.supported_categories)
        self.assertNotIn("anime", self.engine.supported_categories)


# Query encoding and request parameters.
class QueryTests(ProviderTestCase):
    """Query encoding and request parameters."""

    def test_all_omits_category_and_closes_response(self) -> None:
        response = json_response([torrent()])

        with patch.object(urllib.request, "urlopen", return_value=response) as open_url:
            self.engine.search("ubuntu")

        request = open_url.call_args.args[0]

        self.assertEqual(request_parameters(request), {"q": ["ubuntu"]})
        self.assertEqual(open_url.call_args.kwargs, {"timeout": 10})
        self.assertTrue(response.closed)
        self.assertEqual(len(self.printed()), 1)

    def test_explicit_zero_category_is_also_omitted(self) -> None:
        with patch.object(urllib.request, "urlopen", return_value=json_response([])) as open_url:
            self.engine._fetch("ubuntu", "0")

        self.assertNotIn("cat", request_parameters(open_url.call_args.args[0]))

    def test_queries_decode_exactly_once(self) -> None:
        for query in ("C++ Linux", "100% free & open", "café 日本語", "%2B literal", "a+b"):
            with self.subTest(query=query):
                with patch.object(
                    urllib.request, "urlopen", return_value=json_response([])
                ) as open_url:
                    self.engine.search(quote(query))
                params = request_parameters(open_url.call_args.args[0])

                self.assertEqual(params["q"], [query])

    def test_empty_query_and_unknown_category_make_no_request(self) -> None:
        with patch.object(urllib.request, "urlopen") as open_url:
            for query in ("", "%20%20", None, 123):
                self.engine.search(query)
            self.engine.search("ubuntu", "anime")
        open_url.assert_not_called()
        self.print_result.assert_not_called()
        self.warning.assert_called_once()


# Parent categories and the unfiltered fallback.
class CategoryTests(ProviderTestCase):
    """Parent categories and the unfiltered fallback."""

    def test_category_request_uses_parent_and_filters_locally(self) -> None:
        records = [
            torrent(name="4K movie", category="211"),
            torrent(name="4K TV episode", id="43", info_hash="b" * 40, category="212"),
            torrent(name="Linux application", id="44", info_hash="c" * 40, category="303"),
        ]
        response = json_response(records)

        with patch.object(urllib.request, "urlopen", return_value=response) as open_url:
            self.engine.search("linux", "movies")

        request = open_url.call_args.args[0]
        result_names = [result["name"] for result in self.printed()]
        self.assertEqual(request_parameters(request)["cat"], ["200"])
        self.assertCountEqual(result_names, ["4K movie", "4K TV episode"])
        open_url.assert_called_once()

    def test_category_fallback_handles_empty_unrelated_and_invalid_records(self) -> None:
        scenarios: dict[str, list[dict[str, Any]]] = {
            "empty response": [],
            "no-results marker": [{"id": "0", "name": "No results returned"}],
            "unrelated category": [torrent(category="303")],
            "invalid hash": [torrent(category="601", info_hash="0" * 40)],
        }
        fallback_records = [
            torrent(name="Linux book", category="601"),
            torrent(name="Linux application", id="43", info_hash="b" * 40, category="303"),
        ]

        for scenario, first_response in scenarios.items():
            with self.subTest(scenario=scenario):
                self.print_result.reset_mock()
                responses = [json_response(first_response), json_response(fallback_records)]

                with patch.object(urllib.request, "urlopen", side_effect=responses) as open_url:
                    self.engine.search("ubuntu", "books")

                requests = [request_parameters(call.args[0]) for call in open_url.call_args_list]
                result_names = [result["name"] for result in self.printed()]
                self.assertEqual(
                    requests,
                    [
                        {"q": ["ubuntu"], "cat": ["600"]},
                        {"q": ["ubuntu"]},
                    ],
                )
                self.assertEqual(result_names, ["Linux book"])

    def test_category_fallback_stops_after_one_unfiltered_request(self) -> None:
        with patch.object(
            urllib.request, "urlopen", side_effect=[json_response([]), json_response([])]
        ) as open_url:
            self.engine.search("ubuntu", "books")

        self.assertEqual(open_url.call_count, 2)
        self.print_result.assert_not_called()

    def test_category_boundaries(self) -> None:
        expected = {
            "books": set(range(600, 700)),
            "adult": set(range(500, 600)),
            "movies": set(range(200, 300)),
            "music": set(range(100, 200)),
            "software": set(range(300, 400)),
            "games": set(range(400, 500)),
        }
        for category, accepted in expected.items():
            with self.subTest(category=category):
                actual = {
                    value
                    for value in range(700)
                    if provider.matches_category({"category": str(value)}, category)
                }

                self.assertEqual(actual, accepted)
                self.assertFalse(provider.matches_category({}, category))
                self.assertFalse(provider.matches_category({"category": True}, category))

    def test_other_group_includes_books_images_and_other_children(self) -> None:
        accepted_categories = (601, 602, 603, 604, 605, 699)
        records = [
            torrent(
                name=f"Category {category}",
                category=str(category),
                id=str(category),
                info_hash=f"{category:040x}",
            )
            for category in (*accepted_categories, 501)
        ]

        with patch.object(self.engine, "_fetch", return_value=records):
            self.engine.search("linux", "books")

        result_names = [result["name"] for result in self.printed()]
        self.assertCountEqual(
            result_names, [f"Category {category}" for category in accepted_categories]
        )

    def test_all_includes_adult_and_other_groups(self) -> None:
        records = [
            torrent(name="Adult category result", category="501"),
            torrent(name="Other category result", category="699", info_hash="b" * 40),
        ]

        with patch.object(self.engine, "_fetch", return_value=records):
            self.engine.search("linux")

        result_names = [result["name"] for result in self.printed()]
        self.assertCountEqual(result_names, ["Adult category result", "Other category result"])

    def test_adult_parent_can_be_used_programmatically(self) -> None:
        records = [torrent(category="501"), torrent(category="601", info_hash="b" * 40)]

        with patch.object(self.engine, "_fetch", return_value=records) as fetch:
            self.engine.search("query", "adult")
        fetch.assert_called_once_with("query", "500")

        self.assertEqual(len(self.printed()), 1)


# HTTP failures, retry limits, and response cleanup.
class RequestFailureTests(ProviderTestCase):
    """HTTP failures, retry limits, and response cleanup."""

    def test_transient_http_errors_retry_once_then_succeed(self) -> None:
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                self.sleep.reset_mock()
                error = http_error(status)

                with patch.object(
                    urllib.request, "urlopen", side_effect=[error, json_response([torrent()])]
                ) as open_url:
                    self.assertEqual(len(self.engine._fetch("ubuntu")), 1)
                self.assertEqual(open_url.call_count, 2)
                self.sleep.assert_called_once_with(0.5)
                self.assertTrue(error.fp.closed)

    def test_nonretryable_http_errors_stop_immediately(self) -> None:
        for status in (400, 401, 403, 404):
            with self.subTest(status=status):
                error = http_error(status)

                with patch.object(urllib.request, "urlopen", side_effect=error) as open_url:
                    self.assertEqual(self.engine._fetch("ubuntu"), [])
                self.assertEqual(open_url.call_count, 1)
                self.assertTrue(error.fp.closed)
        self.sleep.assert_not_called()

    def test_transport_failures_retry_once_then_stop(self) -> None:
        errors = [
            URLError("offline"),
            TimeoutError("timeout"),
            OSError("reset"),
            http.client.IncompleteRead(b"{", 10),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.sleep.reset_mock()

                with patch.object(urllib.request, "urlopen", side_effect=error) as open_url:
                    self.assertEqual(self.engine._fetch("ubuntu"), [])
                self.assertEqual(open_url.call_count, 2)
                self.sleep.assert_called_once_with(0.5)

    def test_read_timeout_closes_response_and_retries(self) -> None:
        first = json_response([])
        second = json_response([torrent()])
        read_timeout = patch.object(first, "read", side_effect=TimeoutError("read timeout"))
        requests = patch.object(urllib.request, "urlopen", side_effect=[first, second])

        with read_timeout, requests as open_url:
            records = self.engine._fetch("ubuntu")

        self.assertEqual(len(records), 1)
        self.assertTrue(first.closed)
        self.assertTrue(second.closed)
        self.assertEqual(open_url.call_count, 2)

    def test_persistent_server_errors_have_a_retry_limit(self) -> None:
        errors = [http_error(503) for _ in range(2)]

        with patch.object(urllib.request, "urlopen", side_effect=errors) as open_url:
            self.assertEqual(self.engine._fetch("ubuntu"), [])
        self.assertEqual(open_url.call_count, 2)
        self.sleep.assert_called_once_with(0.5)


# JSON, compression, character sets, and title entities.
class ResponseTests(ProviderTestCase):
    """JSON, compression, character sets, and title entities."""

    def test_invalid_json_and_wrong_types_do_not_retry(self) -> None:
        for payload in (
            b"",
            b"<html>error</html>",
            b"[",
            b"{}",
            b"null",
            b'"text"',
            b"123",
            b"\xff",
        ):
            with self.subTest(payload=payload):
                self.warning.reset_mock()
                response = Response(payload)

                with patch.object(urllib.request, "urlopen", return_value=response) as open_url:
                    self.assertEqual(self.engine._fetch("ubuntu"), [])
                self.assertEqual(open_url.call_count, 1)
                self.assertTrue(response.closed)
                self.warning.assert_called_once()
        self.sleep.assert_not_called()

    def test_valid_empty_response_is_not_an_error(self) -> None:
        with patch.object(urllib.request, "urlopen", return_value=json_response([])):
            self.engine.search("no match")
        self.warning.assert_not_called()
        self.print_result.assert_not_called()

    def test_gzip_with_and_without_encoding_header(self) -> None:
        payload = gzip.compress(json.dumps([torrent()]).encode("utf-8"))
        for encoding in (None, "gzip"):
            with self.subTest(encoding=encoding):
                response = Response(payload, encoding=encoding)

                with patch.object(urllib.request, "urlopen", return_value=response):
                    self.assertEqual(len(self.engine._fetch("ubuntu")), 1)
                self.assertTrue(response.closed)

    def test_bad_or_truncated_gzip_does_not_retry(self) -> None:
        for payload in (b"not gzip", gzip.compress(b"[]")[:-5], b"\x1f\x8b\x08\x00" + b"\x00" * 20):
            with self.subTest(payload=payload):
                with patch.object(
                    urllib.request, "urlopen", return_value=Response(payload, encoding="gzip")
                ) as open_url:
                    self.assertEqual(self.engine._fetch("ubuntu"), [])
                self.assertEqual(open_url.call_count, 1)
        self.sleep.assert_not_called()

    def test_response_charset_and_invalid_charset(self) -> None:
        payload = json.dumps([torrent(name="café")], ensure_ascii=False).encode("iso-8859-1")

        with patch.object(
            urllib.request,
            "urlopen",
            return_value=Response(payload, "application/json; charset=iso-8859-1"),
        ):
            self.engine.search("café")

        self.assertEqual(self.printed()[0]["name"], "café")

        with patch.object(
            urllib.request,
            "urlopen",
            return_value=Response(b"[]", "application/json; charset=unknown-charset"),
        ):
            self.assertEqual(self.engine._fetch("ubuntu"), [])

    def test_entity_decoding_happens_after_json_parsing(self) -> None:
        name = "Linux &#34;Guide&#34; &amp; C++ &#92; paths"

        with patch.object(
            urllib.request, "urlopen", return_value=json_response([torrent(name=name)])
        ):
            self.engine.search("linux")

        self.assertEqual(self.printed()[0]["name"], 'Linux "Guide" & C++ \\ paths')


# Record validation, deduplication, sorting, and magnets.
class ResultTests(ProviderTestCase):
    """Record validation, deduplication, sorting, and magnets."""

    def test_invalid_records_do_not_hide_later_valid_results(self) -> None:
        records = [
            None,
            "not a record",
            {},
            {"id": "0", "name": "No results returned"},
            torrent(id="0"),
            torrent(id=-1),
            torrent(id=True),
            torrent(id=1.5),
            torrent(info_hash="0" * 40),
            torrent(info_hash="invalid"),
            torrent(info_hash=123),
            torrent(name=" \r\n"),
            torrent(name=None),
            torrent(id="99", name="Valid result"),
        ]

        self.engine.parseJSON(records)

        self.assertEqual([result["name"] for result in self.printed()], ["Valid result"])
        self.assertEqual(
            self.printed()[0]["desc_link"],
            "https://thepiratebay.org/description.php?id=99",
        )

    def test_unknown_statistics_keep_valid_results(self) -> None:
        record = torrent()
        for key in ("size", "seeders", "leechers", "added"):
            del record[key]
        result = provider.normalize_torrent(record)
        assert result is not None

        self.assertEqual(result["size"], -1)
        self.assertEqual(result["seeds"], -1)
        self.assertEqual(result["leech"], -1)
        self.assertEqual(result["pub_date"], -1)

        invalid_values: list[object] = [-10, "unknown", None, True, 3.7, [], {}]
        for value in invalid_values:
            with self.subTest(value=value):
                self.assertEqual(provider.nonnegative_int(value), -1)
        self.assertEqual(provider.nonnegative_int("0"), 0)

    def test_deduplicate_case_insensitively_and_sort_numerically(self) -> None:
        less_seeded = torrent(name="Less seeded listing", seeders="2")
        more_seeded = torrent(
            id="99",
            name="More seeded listing",
            info_hash=("abcdef0123" * 4).upper(),
            seeders="10",
            size="54321",
            added="1696879999",
        )
        records = [
            less_seeded,
            more_seeded,
            torrent(id="43", info_hash="b" * 40, seeders="100"),
            torrent(id="44", info_hash="c" * 40, seeders=None),
            torrent(id="45", info_hash="d" * 40, seeders="0"),
        ]

        results = provider.collect_results([records, None, {}])

        self.assertEqual([result["seeds"] for result in results], [100, 10, 0, -1])
        winning_duplicate = results[1]
        self.assertEqual(winning_duplicate["name"], "More seeded listing")
        self.assertEqual(
            winning_duplicate["desc_link"], "https://thepiratebay.org/description.php?id=99"
        )
        self.assertEqual(winning_duplicate["size"], 54321)
        self.assertEqual(winning_duplicate["pub_date"], 1696879999)

    def test_magnet_hash_title_and_all_original_trackers(self) -> None:
        name = 'Linux + 日本語 & "Guide" | 100%'
        result = provider.normalize_torrent(torrent(name=name))
        assert result is not None
        params = parse_qs(urlsplit(result["link"]).query)

        self.assertEqual(params["xt"], ["urn:btih:" + ("abcdef0123" * 4).upper()])
        self.assertEqual(params["dn"], [name])
        self.assertEqual(params["tr"], list(provider.TRACKERS))

    def test_newlines_in_titles_cannot_create_stdout_records(self) -> None:
        result = provider.normalize_torrent(torrent(name="Linux&#10;Guide\r\nEdition"))
        assert result is not None

        self.assertNotIn("\n", result["name"])
        self.assertNotIn("\r", result["name"])


# Output protocol: use the real printer and capture operating-system file descriptors.
def test_results_use_qbittorrent_output_protocol(capfd: pytest.CaptureFixture[str]) -> None:
    title = "Linux + café | Guide\r\nEdition"
    record = torrent(name=title, size=None, seeders=None, leechers=None, added=None)
    engine = provider.piratebay()

    with patch.object(urllib.request, "urlopen", return_value=json_response([record])):
        engine.search(quote(title))

    captured = capfd.readouterr()
    lines = captured.out.splitlines()
    assert captured.err == ""
    assert len(lines) == 1

    fields = lines[0].split("|")
    assert len(fields) == 8
    assert fields[0].startswith("magnet:?xt=urn:btih:")
    # Newer helpers encode titles; older helpers replace literal pipe characters.
    assert unquote(fields[1]).replace("|", " ") == "Linux + café   Guide  Edition"
    assert fields[2:5] == ["-1", "-1", "-1"]
    assert fields[5] == engine.url
    assert fields[6] == "https://thepiratebay.org/description.php?id=42"
    assert fields[7] == "-1"


def test_request_failures_use_stderr_only(capfd: pytest.CaptureFixture[str]) -> None:
    engine = provider.piratebay()

    # Keep the actual logger active, with a stderr handler instead of pytest's log capture.
    with contextlib.ExitStack() as patches:
        stderr_handler = patches.enter_context(contextlib.closing(logging.StreamHandler()))
        patches.enter_context(patch.object(provider.logger, "handlers", [stderr_handler]))
        patches.enter_context(patch.object(provider.logger, "propagate", False))
        patches.enter_context(
            patch.object(urllib.request, "urlopen", side_effect=URLError("offline"))
        )
        patches.enter_context(patch.object(time, "sleep"))

        engine.search("ubuntu")

    captured = capfd.readouterr()
    assert captured.out == ""
    assert captured.err.count("APIBay connection failed") == 2
