# VERSION: 1.1
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""1337x search plugin for qBittorrent.

Uses the currently reachable 1337x.la mirror. Search pages contain title,
seeders, leechers and size; the detail page supplies the magnet URI.
"""
import calendar
import datetime
import html
import re
import sys
import time
from urllib.parse import quote, unquote, urljoin
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class x1337x:
    url = "https://1337x.la"
    name = "1337x"
    supported_categories = {
        "all": "all", "anime": "Anime", "games": "Games", "movies": "Movies",
        "music": "Music", "software": "Apps", "tv": "TV",
    }

    def _get(self, path):
        request = Request(urljoin(self.url + "/", path), headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.8",
        })
        remaining = getattr(self, "deadline", time.monotonic() + 30) - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("1337x search time budget exhausted")
        with urlopen(request, timeout=min(30, remaining)) as response:
            return response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")

    @staticmethod
    def _text(value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", value))).strip()

    @staticmethod
    def _size(value):
        match = re.fullmatch(r"([\d.,]+)\s*(KB|MB|GB|TB)", value.strip(), re.I)
        if not match:
            return -1
        units = {"KB": 1, "MB": 2, "GB": 3, "TB": 4}
        return int(float(match[1].replace(",", ".")) * 1024 ** units[match[2].upper()])

    @staticmethod
    def _date(value):
        # 1337x currently returns e.g. “May. 09th  '24”. Unknown dates are -1.
        match = re.search(r"([A-Z][a-z]{2})\.\s+(\d{1,2})(?:st|nd|rd|th)\s+'(\d{2})", value)
        if not match:
            return -1
        try:
            day = int(match[2])
            year = 2000 + int(match[3])
            month = datetime.datetime.strptime(match[1], "%b").month
            return calendar.timegm((year, month, day, 0, 0, 0))
        except ValueError:
            return -1

    def _topic(self, path):
        document = self._get(path)
        magnet = re.search(r'href=["\'](magnet:[^"\']+)["\']', document, re.I)
        if not magnet:
            raise ValueError("1337x topic has no magnet")
        link = html.unescape(magnet[1])
        if not re.search(r'(?:\?|&)xt=urn:btih:(?:[0-9a-f]{40}|[a-z2-7]{32})(?:&|$)', link, re.I):
            raise ValueError("1337x topic has an invalid magnet")
        return link

    def search(self, query: str, category: str = "all") -> None:
        query = unquote(query).strip()
        if not query or category not in self.supported_categories:
            return
        self.deadline = time.monotonic() + 90
        category_name = self.supported_categories[category]
        if category_name == "all":
            path = "/search/{}/{}/".format(quote(query), 1)
        else:
            path = "/category-search/{}/{}/{}/".format(quote(query), quote(category_name), 1)
        document = self._get(path)
        rows = re.findall(r'<tr>(.*?)</tr>', document, re.S | re.I)
        results = []
        for row in rows:
            link = re.search(r'<a href=["\'](/torrent/[^"\']+)["\']', row, re.I)
            title = re.search(r'<a href=["\'](/torrent/[^"\']+)["\'][^>]*>(.*?)</a>', row, re.S | re.I)
            if not link or not title:
                continue
            def field(cls):
                found = re.search(r'class=["\'][^"\']*\b' + cls + r'\b[^"\']*["\'][^>]*>(.*?)</(?:td|span)>', row, re.S | re.I)
                return self._text(found[1]) if found else ""
            name = self._text(title[2])
            if not name:
                continue
            results.append({
                "path": link[1], "name": name, "seeds": int(field("seeds")) if field("seeds").isdigit() else -1,
                "leech": int(field("leeches")) if field("leeches").isdigit() else -1,
                "size": self._size(field("size")), "pub_date": self._date(field("coll-date")),
            })
        results.sort(key=lambda item: item["seeds"], reverse=True)
        for item in results[:50]:
            if time.monotonic() >= self.deadline:
                print("1337x: search time budget exhausted; returning partial results", file=sys.stderr)
                break
            try:
                magnet = self._topic(item["path"])
            except (OSError, ValueError) as error:
                print("1337x: cannot resolve topic ({})".format(type(error).__name__), file=sys.stderr)
                continue
            prettyPrinter({
                "link": magnet, "name": item["name"], "size": item["size"],
                "seeds": item["seeds"], "leech": item["leech"], "engine_url": self.url,
                "desc_link": urljoin(self.url + "/", item["path"]), "pub_date": item["pub_date"],
            })
