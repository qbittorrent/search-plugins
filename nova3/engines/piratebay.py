# VERSION: 4.0
# AUTHORS: Anonymous (version 4.0)
# ORIGINAL AUTHOR: Fabien Devaux (fab@gnux.info)
# ORIGINAL CONTRIBUTORS: Christophe Dumez (chris@qbittorrent.org)
#                        Arthur (custparasite@gmx.se)
#                        Diego de las Heras (ngosang@hotmail.es)
# DESCRIPTION: The Pirate Bay search plugin for qBittorrent
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the author nor the names of its contributors may be
#      used to endorse or promote products derived from this software without
#      specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""The Pirate Bay search provider for qBittorrent, version 4.0.

Reading guide:
    1. Imports: standard-library tools and qBittorrent's own helpers.
    2. Configuration: request limits, category mapping, and magnet trackers.
    3. Result handling: validate, filter, normalize, deduplicate, and sort.
    4. Provider: qBittorrent metadata, API requests, and search entry points.

Search flow:
    search() -> _fetch() -> collect_results() -> prettyPrinter()

All searches go to APIBay. Pirate Bay URLs identify the provider and open
torrent description pages. qBittorrent receives results through stdout;
diagnostics go through logging to stderr.
"""

# ---------------------------------------------------------------------------
# 1. Imports
# ---------------------------------------------------------------------------

from __future__ import annotations

import gzip
import html
import http.client
import json
import logging
import re
import time
import urllib.error
import urllib.request
import zlib
from typing import Any, Iterable, cast
from urllib.parse import unquote, urlencode

# The nova runner configures its SOCKS proxy through helpers. Keep its socket
# configuration intact: urllib uses the same configured sockets.
import helpers
from novaprinter import SearchResults, prettyPrinter

# Retain the compatibility reference used by upstream plugins for this import.
helpers.htmlentitydecode  # pylint: disable=pointless-statement # noqa: B018


# ---------------------------------------------------------------------------
# 2. Configuration
# ---------------------------------------------------------------------------

# Do not use print() for diagnostics: stdout is qBittorrent's result protocol.
logger = logging.getLogger(__name__)

# APIBay supplies 40-character hexadecimal BitTorrent v1 info hashes.
HASH_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")

# Timeout applies to socket operations, not the total duration of a search.
# MAX_ATTEMPTS includes the initial request; 2 means one possible retry.
REQUEST_TIMEOUT = 10
MAX_ATTEMPTS = 2
RETRY_DELAY = 0.5

# qBittorrent category key -> (descriptive label, APIBay parent ID).
# Keys such as "movies" are defined by qBittorrent and cannot be freely renamed.
# Labels explain our combined groups; they do not rename qBittorrent's UI labels.
# Parent IDs include every child in their hundred range: 200 includes 200-299.
# IDs are strings for request metadata; matching converts them to integers.
# Parent 0 means All, and must be omitted from the outgoing API request.
# qBittorrent has no Adult filter, so Adult is available through All in the UI.
CATEGORIES = {
    "music": ("Music & Audio", "100"),
    "movies": ("Movies & TV", "200"),
    "software": ("Software & Apps", "300"),
    "games": ("Video Games", "400"),
    "adult": ("Adult Content", "500"),
    "books": ("Books, Images & Other", "600"),
    "all": ("All Categories", "0"),
}

# Retained from the original 3.10 provider; edit here to customize trackers.
TRACKERS = (
    "udp://tracker.internetwarriors.net:1337/announce",
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://p4p.arenabg.ch:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://www.torrent.eu.org:451/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://retracker.lanta-net.ru:2710/announce",
    "udp://open.stealth.si:80/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.tiny-vps.com:6969/announce",
)


# ---------------------------------------------------------------------------
# 3. Result handling: APIBay records -> qBittorrent result dictionaries
# ---------------------------------------------------------------------------

def nonnegative_int(value: object) -> int:
    """Return an API integer, or qBittorrent's unknown marker."""
    # Accept integer strings, but avoid turning True into 1 or truncating floats.
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return -1
    try:
        number = int(value)
    except ValueError:
        return -1
    return number if number >= 0 else -1


def matches_category(torrent: object, category: str) -> bool:
    """Match the entire parent range, or accept any category for All."""
    if not isinstance(torrent, dict) or category not in CATEGORIES:
        return False
    record = cast(dict[str, Any], torrent)
    parent_id = int(CATEGORIES[category][1])
    if parent_id == 0:
        return True
    category_id = nonnegative_int(record.get("category"))
    # For example: 205 // 100 == 200 // 100, so TV belongs to the video parent.
    # Missing/invalid categories become -1 and cannot match a valid parent.
    return category_id // 100 == parent_id // 100


def normalize_torrent(torrent: object) -> SearchResults | None:
    """Convert a valid APIBay record into a qBittorrent result."""
    if not isinstance(torrent, dict):
        return None

    record = cast(dict[str, Any], torrent)

    # ID, hash, and title are essential. APIBay's no-results marker uses ID 0;
    # a zero hash is also unusable even if the rest of the record looks valid.
    torrent_id = nonnegative_int(record.get("id"))
    info_hash = record.get("info_hash")
    if (
        torrent_id <= 0
        or not isinstance(info_hash, str)
        or not HASH_PATTERN.fullmatch(info_hash)
        or info_hash == "0" * 40
    ):
        return None

    name = record.get("name")
    if not isinstance(name, str):
        return None
    # Decode titles only after parsing JSON. Keep each stdout record on one line.
    name = html.unescape(name).replace("\r", " ").replace("\n", " ").strip()
    if not name:
        return None

    # dn supplies the display name; repeated tr parameters supply trackers.
    # urlencode keeps title punctuation and Unicode from breaking the magnet.
    magnet_params = [("dn", name)] + [("tr", tracker) for tracker in TRACKERS]
    # Optional statistics use -1 when unknown, preserving otherwise useful hits.
    return {
        "link": "magnet:?xt=urn:btih:" + info_hash.upper() + "&" + urlencode(magnet_params),
        "name": name,
        "size": nonnegative_int(record.get("size")),
        "seeds": nonnegative_int(record.get("seeders")),
        "leech": nonnegative_int(record.get("leechers")),
        "engine_url": "https://thepiratebay.org/",
        "desc_link": "https://thepiratebay.org/description.php?id=" + str(torrent_id),
        "pub_date": nonnegative_int(record.get("added")),
    }


def collect_results(collections: Iterable[object], category: str = "all") -> list[SearchResults]:
    """Filter, normalize, deduplicate, and sort API results."""
    unique: dict[str, SearchResults] = {}
    for collection in collections:
        if not isinstance(collection, list):
            continue
        records = cast(list[object], collection)
        for torrent in records:
            if not matches_category(torrent, category):
                continue
            result = normalize_torrent(torrent)
            if result is None:
                continue
            # Hashes identify the same torrent regardless of casing or listing ID.
            # Keep the duplicate advertising more seeds; ties keep the first hit.
            info_hash = str(cast(dict[str, Any], torrent)["info_hash"]).upper()
            existing = unique.get(info_hash)
            if existing is None or int(result["seeds"]) > int(existing["seeds"]):
                unique[info_hash] = result

    # Compare seeds numerically: "100" should sort ahead of "20". Unknown (-1)
    # follows zero-seed results, which remain available to the user.
    return sorted(unique.values(), key=lambda item: int(item["seeds"]), reverse=True)


# ---------------------------------------------------------------------------
# 4. qBittorrent provider: metadata, network requests, and search entry points
# ---------------------------------------------------------------------------

class piratebay:
    """Class name must match this script's filename for qBittorrent discovery."""

    # Human-facing site and result description pages; searches do not use it.
    url = "https://thepiratebay.org/"
    # JSON search endpoint, used for both category searches and fallback searches.
    api_url = "https://apibay.org/"
    name = "The Pirate Bay"

    # qBittorrent reads these class attributes to discover supported filters.
    # Exclude Adult because its fixed category enumeration does not recognize it.
    supported_categories = {
        category: group[1] for category, group in CATEGORIES.items() if category != "adult"
    }

    def _fetch(self, query: str, category_id: str | None = None) -> list[object]:
        """Fetch JSON without HTML rewriting, retrying only transport failures."""
        params = {"q": query}
        # Sending cat=0 returned no results in testing. All must omit cat entirely.
        if category_id not in (None, "0"):
            params["cat"] = category_id
        request = urllib.request.Request(
            self.api_url + "q.php?" + urlencode(params),
            headers={
                # A simple browser-like header; no browser or JavaScript runs.
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
        )

        response: http.client.HTTPResponse
        for attempt in range(MAX_ATTEMPTS):
            try:
                # The context manager closes the response even if reading fails.
                with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                    data = response.read()
                    charset = response.headers.get_content_charset() or "utf-8"
                    encoding = response.headers.get("Content-Encoding", "").lower()
            except urllib.error.HTTPError as exc:
                # Rate limits and server errors may be transient. Other HTTP
                # errors (such as 403/404) stop this request without a retry.
                retryable = exc.code == 429 or 500 <= exc.code < 600
                logger.warning("APIBay HTTP error (%s): %s", category_id or "all", exc)
                exc.close()
            except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
                retryable = True
                logger.warning("APIBay connection failed (%s): %s", category_id or "all", exc)
            else:
                try:
                    # Some servers send gzip without declaring it in the header.
                    if encoding == "gzip" or data[:2] == b"\x1f\x8b":
                        data = gzip.decompress(data)
                    # Parse raw JSON first. HTML-unescaping the full response can
                    # introduce unescaped quotes and corrupt otherwise valid JSON.
                    collection = json.loads(data.decode(charset))
                except (OSError, EOFError, ValueError, LookupError, zlib.error) as exc:
                    logger.warning("Invalid APIBay JSON (%s): %s", category_id or "all", exc)
                    return []
                if not isinstance(collection, list):
                    logger.warning("Invalid APIBay response type (%s)", category_id or "all")
                    return []
                records = cast(list[object], collection)
                return records

            # Only transport failures reach here; invalid payloads return above.
            if not retryable or attempt + 1 == MAX_ATTEMPTS:
                return []
            time.sleep(RETRY_DELAY)
        return []

    def parseJSON(self, collection: object) -> None:
        """Compatibility entry point for callers with an already decoded list."""
        for result in collect_results([collection]):
            prettyPrinter(result)

    def search(self, what: object, cat: str = "all") -> None:
        """qBittorrent entry point: receive an escaped query and category key.

        Fetch the selected parent once and filter its records locally. If no
        usable matches remain, try All once with the same local filter. APIBay's
        limited result batches mean this does not guarantee exhaustive coverage.
        """
        if not isinstance(what, str):
            return
        # nova2 uses quote(), so a literal '+' must not become a space here.
        query = unquote(what).strip()
        if not query:
            return
        if cat not in CATEGORIES:
            logger.warning("Unsupported category: %s", cat)
            return

        # Tuple position 1 is the API parent ID; position 0 is the readable label.
        results = collect_results([self._fetch(query, CATEGORIES[cat][1])], cat)
        if not results and cat != "all":
            # Broaden the request, but keep the user's selected parent filter.
            results = collect_results([self._fetch(query)], cat)
        for result in results:
            # qBittorrent's helper formats the fields into its stdout protocol.
            prettyPrinter(result)
