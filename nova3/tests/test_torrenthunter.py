import json
import unittest
import urllib.parse
from typing import Any, Dict, List, Mapping
from unittest import mock

from engines import torrenthunter as plugin

# pyright: reportPrivateUsage=false


# pylint: disable=protected-access

PRINTED: List[Dict[str, Any]] = []


TORZNAB_XML = """\
<rss xmlns:torznab="http://torznab.com/schemas/2015/feed">
  <channel>
    <item>
      <title>Ubuntu 24.04 Desktop</title>
      <link>https://example.test/ubuntu.torrent</link>
      <guid>https://example.test/details/1</guid>
      <size>5000000000</size>
      <pubDate>Tue, 23 Jul 2024 12:00:00 +0000</pubDate>
      <torznab:attr name="magneturl"
        value="magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&amp;dn=Ubuntu" />
      <torznab:attr name="seeders" value="42" />
      <torznab:attr name="peers" value="50" />
    </item>
  </channel>
</rss>
"""


class TorrentHunterTests(unittest.TestCase):
    def setUp(self) -> None:
        PRINTED.clear()
        printer = mock.patch.object(plugin, "prettyPrinter", PRINTED.append)
        printer.start()
        self.addCleanup(printer.stop)

    def test_parses_torznab_result_and_category(self) -> None:
        source = {
            "name": "Test Indexer",
            "type": "torznab",
            "url": "https://example.test/api?existing=yes",
            "api_key": "secret",
        }
        with mock.patch.object(plugin, "_request_text", return_value=TORZNAB_XML) as request:
            results = plugin._torznab(source, "ubuntu+linux", "movies", 5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["seeds"], 42)
        self.assertEqual(results[0]["leech"], 8)
        self.assertEqual(results[0]["size"], "5000000000 B")
        requested_url = request.call_args.args[0]
        self.assertIn("existing=yes", requested_url)
        self.assertIn("apikey=secret", requested_url)
        self.assertIn("cat=2000", requested_url)
        self.assertIn("q=ubuntu+linux", requested_url)

    def test_dedupe_prefers_better_seeded_duplicate(self) -> None:
        first = {
            "link": "magnet:?xt=urn:btih:0123456789ABCDEF0123456789ABCDEF01234567",
            "name": "Ubuntu",
            "size": "100 B",
            "seeds": 2,
            "pub_date": 1,
        }
        second = dict(first, seeds=20)
        self.assertEqual(plugin._dedupe_key(first), plugin._dedupe_key(second))
        self.assertGreater(plugin._quality(second, "ubuntu"), plugin._quality(first, "ubuntu"))

    def test_search_isolates_source_failure_and_prints_success(self) -> None:
        config = dict(plugin.DEFAULT_CONFIG)
        config["sources"] = [
            {"name": "Broken", "type": "torznab", "url": "https://broken.test"},
            {"name": "Working", "type": "torrentscsv", "url": "https://working.test"},
        ]
        item = {
            "link": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
            "name": "Ubuntu",
            "size": "100 B",
            "seeds": 5,
            "leech": 1,
            "engine_url": "https://working.test",
            "desc_link": "https://working.test/1",
            "pub_date": 10,
            "_source": "Working",
        }

        def adapter(
            source: Mapping[str, Any], *_args: Any
        ) -> List[Dict[str, Any]]:
            if source["name"] == "Broken":
                raise OSError("offline")
            return [dict(item)]

        with mock.patch.object(
            plugin, "_load_config", return_value=config
        ), mock.patch.object(
                plugin, "_load_state", return_value={"sources": {}, "cache": {}}
        ), mock.patch.object(plugin, "_save_state"), mock.patch.dict(
            plugin.ADAPTERS,
            {"torznab": adapter, "torrentscsv": adapter},
            clear=True,
        ):
            plugin.torrenthunter().search("ubuntu")

        self.assertEqual(len(PRINTED), 1)
        self.assertEqual(PRINTED[0]["name"], "Ubuntu [Working]")

    def test_example_configuration_is_valid(self) -> None:
        self.assertTrue(plugin.DEFAULT_CONFIG["sources"])
        self.assertTrue(
            any(source["enabled"] for source in plugin.DEFAULT_CONFIG["sources"])
        )
        self.assertEqual(
            next(
                source
                for source in plugin.DEFAULT_CONFIG["sources"]
                if source["name"] == "Prowlarr"
            )["type"],
            "prowlarr",
        )

    def test_parses_prowlarr_json_and_uses_api_key_header(self) -> None:
        source = {
            "name": "Prowlarr",
            "type": "prowlarr",
            "url": "http://127.0.0.1:9696/api/v1/search",
            "api_key": "secret",
        }
        payload = json.dumps(
            [
                {
                    "title": "Ubuntu Desktop",
                    "magnetUrl": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
                    "size": 100,
                    "seeders": 9,
                    "leechers": 2,
                    "infoUrl": "https://example.test/details",
                    "publishDate": "2024-07-23T12:00:00Z",
                    "indexer": "Example",
                }
            ]
        )
        with mock.patch.object(plugin, "_request_text", return_value=payload) as request:
            results = plugin._prowlarr(source, "ubuntu", "all", 5)

        self.assertEqual(results[0]["_source"], "Example")
        self.assertEqual(request.call_args.kwargs["headers"], {"X-Api-Key": "secret"})

    def test_duplicate_magnets_merge_unique_trackers(self) -> None:
        primary = (
            "magnet:?xt=urn%3Abtih%3A0123456789abcdef0123456789abcdef01234567"
            "&tr=udp%3A%2F%2Ftracker-one"
        )
        alternative = (
            "magnet:?xt=urn%3Abtih%3A0123456789abcdef0123456789abcdef01234567"
            "&tr=udp%3A%2F%2Ftracker-two"
        )
        merged = plugin._merge_magnets(primary, [alternative, primary])
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(merged).query))
        self.assertIn("xt", query)
        self.assertEqual(merged.count("tr="), 2)

    def test_fresh_cache_avoids_second_network_search(self) -> None:
        config = dict(plugin.DEFAULT_CONFIG)
        config["sources"] = [
            {"name": "Working", "type": "torrentscsv", "url": "https://working.test"}
        ]
        state: Dict[str, Any] = {"sources": {}, "cache": {}}
        item = {
            "link": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
            "name": "Ubuntu",
            "size": "100 B",
            "seeds": 5,
            "leech": 1,
            "engine_url": "https://working.test",
            "desc_link": "https://working.test/1",
            "pub_date": 10,
            "_source": "Working",
        }
        adapter = mock.Mock(return_value=[item])
        with mock.patch.object(
            plugin, "_load_config", return_value=config
        ), mock.patch.object(
            plugin, "_load_state", return_value=state
        ), mock.patch.object(
            plugin, "_save_state"
        ), mock.patch.dict(
            plugin.ADAPTERS, {"torrentscsv": adapter}, clear=True
        ):
            plugin.torrenthunter().search("ubuntu")
            plugin.torrenthunter().search("ubuntu")

        self.assertEqual(adapter.call_count, 1)

    def test_query_variants_normalize_and_relax_release_terms(self) -> None:
        variants = plugin._query_variants(
            "Example.Show.S01E02.2025.1080p.WEB-DL.x265"
        )
        self.assertEqual(variants[0], "Example.Show.S01E02.2025.1080p.WEB-DL.x265")
        self.assertIn("Example Show S01E02 2025 1080p WEB-DL x265", variants)
        self.assertTrue(any("1x02" in variant for variant in variants))
        self.assertTrue(any("1080p" not in variant and "x265" not in variant for variant in variants))
        self.assertTrue(any("2025" not in variant for variant in variants))

    def test_adaptive_search_stops_when_exact_query_meets_target(self) -> None:
        calls: List[str] = []

        def adapter(
            _source: Mapping[str, Any],
            query: str,
            _category: str,
            _timeout: float,
        ) -> List[Dict[str, Any]]:
            calls.append(query)
            return [
                {
                    "link": f"magnet:?xt=urn:btih:{number:040x}",
                    "name": f"Example {number}",
                    "size": "1 B",
                    "seeds": 1,
                    "pub_date": 1,
                }
                for number in range(3)
            ]

        source = {
            "_adaptive": {
                "enabled": True,
                "target_unique_results": 3,
                "max_extra_queries": 3,
            }
        }
        results = plugin._search_with_expansion(
            adapter, source, "Example.Show.1080p", "all", 5
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(calls, ["Example.Show.1080p"])

    def test_adaptive_search_expands_when_results_are_scarce(self) -> None:
        calls: List[str] = []

        def adapter(
            _source: Mapping[str, Any],
            query: str,
            _category: str,
            _timeout: float,
        ) -> List[Dict[str, Any]]:
            calls.append(query)
            number = len(calls)
            return [
                {
                    "link": f"magnet:?xt=urn:btih:{number:040x}",
                    "name": query,
                    "size": "1 B",
                    "seeds": 1,
                    "pub_date": 1,
                }
            ]

        source = {
            "_adaptive": {
                "enabled": True,
                "target_unique_results": 10,
                "max_extra_queries": 2,
            }
        }
        plugin._search_with_expansion(
            adapter, source, "Example.Movie.2025.1080p", "movies", 5
        )
        self.assertEqual(len(calls), 3)
        self.assertNotEqual(calls[0], calls[1])


if __name__ == "__main__":
    unittest.main()
