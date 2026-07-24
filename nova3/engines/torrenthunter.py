# VERSION: 0.20
# AUTHORS: TorrentHunter contributors
# LICENSE: MIT
"""Fast, configurable metasearch plugin for qBittorrent.

This file is intentionally self-contained because qBittorrent installs search
plugins one Python file at a time. Configuration is read from
``torrenthunter.json`` next to this file.
"""

from __future__ import annotations

import datetime
import email.utils
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple, cast

from helpers import download_file
from novaprinter import SearchResults, prettyPrinter

VERSION = "0.2.0"
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "torrenthunter.json"
)
TORZNAB_NS = "http://torznab.com/schemas/2015/feed"
USER_AGENT = f"TorrentHunter/{VERSION} qBittorrent-search-plugin"
PRINT_LOCK = threading.Lock()
STATE_PATH = os.path.join(os.path.dirname(CONFIG_PATH), "torrenthunter.state.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "timeout_seconds": 12,
    "max_workers": 8,
    "max_results_per_source": 1000,
    "show_source_in_name": True,
    "retries": 2,
    "retry_backoff_seconds": 0.4,
    "cache_ttl_seconds": 300,
    "stale_cache_on_error": True,
    "failure_threshold": 3,
    "circuit_breaker_seconds": 300,
    "minimum_seeders": 0,
    "maximum_age_days": 0,
    "ranking": {"relevance": 1000, "seeders": 10, "freshness": 1},
    "adaptive_search": {
        "enabled": True,
        "target_unique_results": 75,
        "max_extra_queries": 3,
    },
    "sources": [
        {
            "name": "Torrents.csv",
            "type": "torrentscsv",
            "url": "https://torrents-csv.com",
            "enabled": True,
        },
        {
            "name": "Prowlarr",
            "type": "prowlarr",
            "url": "http://127.0.0.1:9696/api/v1/search",
            "api_key": "YOUR_API_KEY_HERE",
            "enabled": False,
        },
        {
            "name": "Jackett",
            "type": "torznab",
            "url": (
                "http://127.0.0.1:9117/api/v2.0/indexers/all/"
                "results/torznab/api"
            ),
            "api_key": "YOUR_API_KEY_HERE",
            "enabled": False,
        },
    ],
}

CATEGORIES = {
    "all": (),
    "anime": ("5070",),
    "books": ("7000", "8000"),
    "games": ("1000",),
    "movies": ("2000",),
    "music": ("3000",),
    "pictures": ("6000",),
    "software": ("4000",),
    "tv": ("5000",),
}


def _stderr(message: str) -> None:
    print(f"TorrentHunter: {message}", file=sys.stderr)


def _load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
                json.dump(DEFAULT_CONFIG, config_file, indent=2)
        except OSError as exc:
            _stderr(f"could not create configuration: {exc}")
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as config_file:
            raw_loaded: Any = json.load(config_file)
        if not isinstance(raw_loaded, dict):
            raise ValueError("configuration must be an object")
        loaded = cast(Dict[str, Any], raw_loaded)
        if not isinstance(loaded.get("sources"), list):
            raise ValueError("'sources' must be a list")
        merged = dict(DEFAULT_CONFIG)
        merged.update(loaded)
        return merged
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _stderr(f"invalid configuration, using defaults: {exc}")
        return dict(DEFAULT_CONFIG)


def _load_state() -> Dict[str, Any]:
    try:
        with open(STATE_PATH, encoding="utf-8") as state_file:
            raw_state: Any = json.load(state_file)
        if isinstance(raw_state, dict):
            state = cast(Dict[str, Any], raw_state)
            state.setdefault("sources", {})
            state.setdefault("cache", {})
            return state
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return {"sources": {}, "cache": {}}


def _save_state(state: Mapping[str, Any]) -> None:
    temporary = STATE_PATH + ".tmp"
    try:
        with open(temporary, "w", encoding="utf-8") as state_file:
            json.dump(state, state_file, separators=(",", ":"))
        os.replace(temporary, STATE_PATH)
    except OSError as exc:
        _stderr(f"could not save state: {exc}")
        try:
            os.unlink(temporary)
        except OSError:
            pass


def _source_id(source: Mapping[str, Any]) -> str:
    identity = f"{source.get('type')}:{source.get('url')}:{source.get('name')}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


def _cache_key(source: Mapping[str, Any], query: str, category: str) -> str:
    identity = f"{_source_id(source)}:{urllib.parse.unquote_plus(query).casefold()}:{category}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _request_text(
    url: str,
    timeout: float,
    headers: Optional[Mapping[str, str]] = None,
    retries: int = 0,
    backoff: float = 0.0,
) -> str:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml",
    }
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url,
        headers=request_headers,
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = cast(bytes, response.read())
                return data.decode("utf-8", errors="replace")
        except (OSError, urllib.error.URLError):
            if attempt >= retries:
                raise
            time.sleep(backoff * (2 ** attempt))
    raise RuntimeError("request retry loop ended unexpectedly")


def _integer(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _timestamp(value: Optional[str]) -> int:
    if not value:
        return -1
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return int(parsed.timestamp())
    except (TypeError, ValueError, OverflowError):
        try:
            parsed_iso = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(parsed_iso.timestamp())
        except (TypeError, ValueError, OverflowError):
            return -1


def _text(element: Optional[ET.Element], default: str = "") -> str:
    return element.text.strip() if element is not None and element.text else default


def _attr(item: ET.Element, name: str) -> Optional[str]:
    element = item.find(f"./{{{TORZNAB_NS}}}attr[@name='{name}']")
    return element.attrib.get("value") if element is not None else None


def _append_query(url: str, values: Iterable[Tuple[str, str]]) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.extend(values)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )


def _info_hash(link: str) -> Optional[str]:
    match = re.search(r"(?:urn:btih:|/)([A-Fa-f0-9]{40})(?:[&/?#]|$)", link)
    return match.group(1).lower() if match else None


def _normal_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip()


TECHNICAL_QUERY_TOKENS = re.compile(
    r"^(?:"
    r"\d{3,4}p|4k|"
    r"x26[45]|h26[45]|hevc|av1|10bit|"
    r"blu-?ray|b[dr]rip|web-?dl|webrip|hdtv|remux|"
    r"hdr10?\+?|dolby|vision|dv|atmos|"
    r"aac\d*|dts(?:-?hd)?|truehd|"
    r"proper|repack|extended|unrated|multi|dubbed|subbed"
    r")$",
    re.IGNORECASE,
)


def _query_variants(query: str) -> List[str]:
    exact = urllib.parse.unquote_plus(query).strip()
    variants = [exact]

    normalized = re.sub(r"[\[\]{}()\"']", " ", exact)
    normalized = re.sub(r"[._]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized and normalized.casefold() not in {item.casefold() for item in variants}:
        variants.append(normalized)

    tokens = normalized.split()
    relaxed_tokens = [token for token in tokens if not TECHNICAL_QUERY_TOKENS.match(token)]
    relaxed = " ".join(relaxed_tokens)
    if (
        len(relaxed_tokens) >= 2
        and relaxed.casefold() not in {item.casefold() for item in variants}
    ):
        variants.append(relaxed)

    tv_match = re.search(r"\bS(\d{1,2})E(\d{1,2})\b", normalized, re.IGNORECASE)
    if tv_match:
        alternate = re.sub(
            r"\bS\d{1,2}E\d{1,2}\b",
            f"{int(tv_match.group(1))}x{int(tv_match.group(2)):02d}",
            normalized,
            flags=re.IGNORECASE,
        )
        if alternate.casefold() not in {item.casefold() for item in variants}:
            variants.append(alternate)

    without_year = re.sub(r"\b(?:19|20)\d{2}\b", " ", relaxed or normalized)
    without_year = re.sub(r"\s+", " ", without_year).strip()
    if (
        len(without_year.split()) >= 2
        and without_year.casefold() not in {item.casefold() for item in variants}
    ):
        variants.append(without_year)
    return variants


def _dedupe_key(result: Mapping[str, Any]) -> str:
    info_hash = _info_hash(str(result.get("link", "")))
    if info_hash:
        return f"hash:{info_hash}"
    material = f"{_normal_name(str(result.get('name', '')))}:{result.get('size', -1)}"
    return "fallback:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _quality(result: Mapping[str, Any], query: str) -> Tuple[int, int, int]:
    words = [word for word in re.split(r"\W+", urllib.parse.unquote_plus(query).casefold()) if word]
    name = str(result.get("name", "")).casefold()
    relevance = sum(1 for word in words if word in name)
    return relevance, _integer(result.get("seeds")), _integer(result.get("pub_date"))


def _score(result: Mapping[str, Any], query: str, config: Mapping[str, Any]) -> float:
    relevance, seeds, published = _quality(result, query)
    weights = config.get("ranking", {})
    freshness_days = 0.0
    if published > 0:
        freshness_days = max(0.0, (time.time() - published) / 86400)
    return (
        relevance * float(weights.get("relevance", 1000))
        + max(0, seeds) * float(weights.get("seeders", 10))
        - freshness_days * float(weights.get("freshness", 1))
    )


def _safe_result(result: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("link", "name", "engine_url", "desc_link"):
        result[key] = str(result.get(key, "")).replace("|", "%7C").replace("\n", " ")
    for key in ("size", "seeds", "leech", "pub_date"):
        if result.get(key) in (None, ""):
            result[key] = -1
    return result


def _merge_magnets(primary: str, alternatives: Iterable[str]) -> str:
    if not primary.startswith("magnet:?"):
        return primary
    parsed = urllib.parse.parse_qsl(
        urllib.parse.urlsplit(primary).query, keep_blank_values=True
    )
    existing_trackers = {value for key, value in parsed if key == "tr"}
    for alternative in alternatives:
        if not alternative.startswith("magnet:?"):
            continue
        for key, value in urllib.parse.parse_qsl(
            urllib.parse.urlsplit(alternative).query, keep_blank_values=True
        ):
            if key == "tr" and value not in existing_trackers:
                parsed.append((key, value))
                existing_trackers.add(value)
    return "magnet:?" + urllib.parse.urlencode(parsed)


def _request_options(source: Mapping[str, Any]) -> Tuple[int, float]:
    return _integer(source.get("_retries"), 0), float(source.get("_backoff", 0.0))


def _torznab(source: Mapping[str, Any], query: str, category: str, timeout: float) -> List[Dict[str, Any]]:
    parameters = [
        ("t", "search"),
        ("q", urllib.parse.unquote_plus(query)),
        ("limit", str(_integer(source.get("_limit"), 100))),
        ("extended", "1"),
    ]
    api_key = str(source.get("api_key", "")).strip()
    if api_key and api_key != "YOUR_API_KEY_HERE":
        parameters.append(("apikey", api_key))
    categories = CATEGORIES.get(category, ())
    if categories:
        parameters.append(("cat", ",".join(categories)))
    url = _append_query(str(source["url"]), parameters)
    retries, backoff = _request_options(source)
    root = ET.fromstring(_request_text(url, timeout, retries=retries, backoff=backoff))
    results: List[Dict[str, Any]] = []
    for item in root.findall(".//item"):
        title = _text(item.find("title"))
        link = _attr(item, "magneturl") or _text(item.find("link"))
        if not title or not link:
            continue
        seeds = _integer(_attr(item, "seeders"))
        peers = _integer(_attr(item, "peers"))
        leechers = peers - seeds if peers >= 0 and seeds >= 0 else _integer(_attr(item, "leechers"))
        size = _integer(_text(item.find("size")), _integer(_attr(item, "size")))
        desc = _text(item.find("comments")) or _text(item.find("guid")) or str(source["url"])
        results.append(
            {
                "link": link,
                "name": title,
                "size": f"{size} B" if size >= 0 else -1,
                "seeds": seeds,
                "leech": leechers,
                "engine_url": str(source["url"]),
                "desc_link": desc,
                "pub_date": _timestamp(_text(item.find("pubDate"))),
                "_source": str(source.get("name", "Torznab")),
            }
        )
    return results


def _prowlarr(source: Mapping[str, Any], query: str, category: str, timeout: float) -> List[Dict[str, Any]]:
    parameters = [
        ("query", urllib.parse.unquote_plus(query)),
        ("type", "search"),
        ("limit", str(_integer(source.get("_limit"), 100))),
    ]
    categories = CATEGORIES.get(category, ())
    for category_id in categories:
        parameters.append(("categories", category_id))
    url = _append_query(str(source["url"]), parameters)
    api_key = str(source.get("api_key", "")).strip()
    headers = {"X-Api-Key": api_key} if api_key and api_key != "YOUR_API_KEY_HERE" else {}
    retries, backoff = _request_options(source)
    payload: Any = json.loads(
        _request_text(url, timeout, headers=headers, retries=retries, backoff=backoff)
    )
    items = cast(
        List[Dict[str, Any]],
        payload if isinstance(payload, list) else payload.get("records", []),
    )
    results: List[Dict[str, Any]] = []
    for item in items:
        title = str(item.get("title", ""))
        link = str(item.get("magnetUrl") or item.get("downloadUrl") or "")
        if not title or not link:
            continue
        results.append(
            {
                "link": link,
                "name": title,
                "size": f"{_integer(item.get('size'))} B" if item.get("size") else -1,
                "seeds": _integer(item.get("seeders")),
                "leech": _integer(item.get("leechers")),
                "engine_url": str(source["url"]),
                "desc_link": str(item.get("infoUrl") or item.get("guid") or source["url"]),
                "pub_date": _timestamp(item.get("publishDate")),
                "_source": str(item.get("indexer") or source.get("name", "Prowlarr")),
            }
        )
    return results


def _torrentscsv(source: Mapping[str, Any], query: str, _category: str, timeout: float) -> List[Dict[str, Any]]:
    base_url = str(source["url"]).rstrip("/")
    url = _append_query(
        f"{base_url}/service/search",
        (("size", "100"), ("q", urllib.parse.unquote_plus(query))),
    )
    retries, backoff = _request_options(source)
    payload = cast(
        Dict[str, Any],
        json.loads(_request_text(url, timeout, retries=retries, backoff=backoff)),
    )
    results: List[Dict[str, Any]] = []
    for item in cast(List[Dict[str, Any]], payload.get("torrents", [])):
        info_hash = str(item.get("infohash", ""))
        name = str(item.get("name", ""))
        if not info_hash or not name:
            continue
        magnet = "magnet:?" + urllib.parse.urlencode(
            {"xt": f"urn:btih:{info_hash}", "dn": name}
        )
        results.append(
            {
                "link": magnet,
                "name": name,
                "size": f"{_integer(item.get('size_bytes'))} B",
                "seeds": _integer(item.get("seeders")),
                "leech": _integer(item.get("leechers")),
                "engine_url": base_url,
                "desc_link": f"{base_url}/#/search/torrent/{urllib.parse.quote_plus(name)}/1",
                "pub_date": _integer(item.get("created_unix")),
                "_source": str(source.get("name", "Torrents.csv")),
            }
        )
    return results


ADAPTERS = {"torznab": _torznab, "prowlarr": _prowlarr, "torrentscsv": _torrentscsv}


def _search_with_expansion(
    adapter: Callable[
        [Mapping[str, Any], str, str, float], List[Dict[str, Any]]
    ],
    source: Mapping[str, Any],
    query: str,
    category: str,
    timeout: float,
) -> List[Dict[str, Any]]:
    variants = _query_variants(query)
    adaptive = source.get("_adaptive", {})
    enabled = bool(adaptive.get("enabled", True))
    target = max(1, _integer(adaptive.get("target_unique_results"), 75))
    extras = max(0, _integer(adaptive.get("max_extra_queries"), 3))
    selected = variants[: 1 + extras] if enabled else variants[:1]
    unique: Dict[str, Dict[str, Any]] = {}
    for number, variant in enumerate(selected):
        if number > 0 and len(unique) >= target:
            break
        for result in adapter(source, variant, category, timeout):
            key = _dedupe_key(result)
            previous = unique.get(key)
            if previous is None or _quality(result, query) > _quality(previous, query):
                unique[key] = result
    return list(unique.values())


class torrenthunter:
    url = "https://github.com/qbittorrent/search-plugins"
    name = "TorrentHunter"
    supported_categories = {name: name for name in CATEGORIES}

    def download_torrent(self, info: str) -> None:
        if info.startswith("magnet:?"):
            print(f"{info} {info}")
        else:
            print(download_file(info))

    def search(self, what: str, cat: str = "all") -> None:
        config = _load_config()
        state = _load_state()
        now = time.time()
        category = cat.lower() if cat.lower() in CATEGORIES else "all"
        enabled: List[Dict[str, Any]] = []
        for source in cast(List[Dict[str, Any]], config["sources"]):
            if source.get("enabled", True) and source.get("type") in ADAPTERS:
                enabled.append(dict(source))
        if not enabled:
            _stderr(f"no sources enabled; edit {CONFIG_PATH}")
            return

        timeout = max(1.0, float(config.get("timeout_seconds", 12)))
        per_source = max(1, int(config.get("max_results_per_source", 100)))
        cache_ttl = max(0, int(config.get("cache_ttl_seconds", 300)))
        failure_threshold = max(1, int(config.get("failure_threshold", 3)))
        breaker_seconds = max(1, int(config.get("circuit_breaker_seconds", 300)))
        for source in enabled:
            source["_retries"] = max(0, int(config.get("retries", 2)))
            source["_backoff"] = max(0.0, float(config.get("retry_backoff_seconds", 0.4)))
            source["_limit"] = per_source
            source["_adaptive"] = config.get("adaptive_search", {})

        collected: List[Dict[str, Any]] = []
        pending: List[Tuple[Dict[str, Any], str, str]] = []
        stale: Dict[str, List[Dict[str, Any]]] = {}
        for source in enabled:
            source_key = _source_id(source)
            cache_key = _cache_key(source, what, category)
            cache_entry = cast(Dict[str, Any], state["cache"].get(cache_key, {}))
            cached_results = cache_entry.get("results", [])
            if isinstance(cached_results, list):
                cached_results = cast(List[Dict[str, Any]], cached_results)
                stale[source_key] = cached_results
            else:
                cached_results = []
            if cached_results and now - float(cache_entry.get("time", 0)) <= cache_ttl:
                collected.extend(cached_results[:per_source])
                continue
            health = state["sources"].get(source_key, {})
            if float(health.get("retry_after", 0)) > now:
                _stderr(f"{source.get('name', 'source')} temporarily skipped after repeated failures")
                if config.get("stale_cache_on_error", True):
                    collected.extend(stale.get(source_key, [])[:per_source])
                continue
            pending.append((source, source_key, cache_key))

        worker_count = max(1, min(int(config.get("max_workers", 8)), len(pending) or 1))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _search_with_expansion,
                    ADAPTERS[str(source["type"])],
                    source,
                    what,
                    category,
                    max(1.0, float(source.get("timeout_seconds", timeout))),
                ): (source, source_key, cache_key)
                for source, source_key, cache_key in pending
            }
            for future in as_completed(futures):
                source, source_key, cache_key = futures[future]
                try:
                    results = future.result()[:per_source]
                    collected.extend(results)
                    state["sources"][source_key] = {
                        "failures": 0,
                        "retry_after": 0,
                        "last_success": int(now),
                    }
                    state["cache"][cache_key] = {"time": int(now), "results": results}
                except (OSError, ValueError, KeyError, ET.ParseError, urllib.error.URLError) as exc:
                    _stderr(f"{source.get('name', 'source')} failed: {exc}")
                    health = state["sources"].setdefault(source_key, {})
                    failures = int(health.get("failures", 0)) + 1
                    health.update({"failures": failures, "last_failure": int(now)})
                    if failures >= failure_threshold:
                        health["retry_after"] = int(now + breaker_seconds)
                    if config.get("stale_cache_on_error", True):
                        collected.extend(stale.get(source_key, [])[:per_source])
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    # One source must never break the others.
                    _stderr(f"{source.get('name', 'source')} unexpected failure: {exc}")

        oldest_cache = now - max(cache_ttl * 10, 86400)
        state["cache"] = {
            key: value
            for key, value in state["cache"].items()
            if float(value.get("time", 0)) >= oldest_cache
        }
        _save_state(state)

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for result in collected:
            grouped.setdefault(_dedupe_key(result), []).append(result)

        unique: List[Dict[str, Any]] = []
        for duplicates in grouped.values():
            best = max(duplicates, key=lambda item: _score(item, what, config))
            best["link"] = _merge_magnets(
                str(best["link"]), (str(item["link"]) for item in duplicates)
            )
            sources = sorted({str(item.get("_source", "source")) for item in duplicates})
            best["_source"] = ", ".join(sources)
            unique.append(best)

        minimum_seeders = int(config.get("minimum_seeders", 0))
        maximum_age_days = int(config.get("maximum_age_days", 0))
        filtered: List[Dict[str, Any]] = []
        for result in unique:
            seeds = _integer(result.get("seeds"))
            published = _integer(result.get("pub_date"))
            if 0 <= seeds < minimum_seeders:
                continue
            if maximum_age_days > 0 and published > 0:
                if now - published > maximum_age_days * 86400:
                    continue
            filtered.append(result)

        ordered = sorted(
            filtered, key=lambda item: _score(item, what, config), reverse=True
        )
        for result in ordered:
            if config.get("show_source_in_name", True):
                result["name"] = f"{result['name']} [{result.pop('_source', 'source')}]"
            else:
                result.pop("_source", None)
            with PRINT_LOCK:
                prettyPrinter(cast(SearchResults, _safe_result(result)))
