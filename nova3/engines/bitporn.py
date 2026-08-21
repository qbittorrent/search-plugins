# VERSION: 1.00
# BitPorn search plugin for qBittorrent.
# Uses only Python's standard library.

from __future__ import print_function

import html
import os
import re
import sys
import tempfile
import time
from http.cookiejar import Cookie, CookieJar
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import BaseHandler, HTTPError, ProxyHandler, Request, URLError, build_opener


class bitporn(object):
    url = "https://bitporn.eu"
    name = "BitPorn"
    supported_categories = {
        "all": "all",
    }

    def __init__(self):
        self.cookie_file = os.environ.get("BITPORN_COOKIE_FILE", "")
        self.search_url = os.environ.get(
            "BITPORN_SEARCH_URL", self.url + "/torrents?search={query}&page={page}"
        )
        self.timeout = int(os.environ.get("BITPORN_TIMEOUT", "30"))
        # qBittorrent may inherit a dead system proxy from its launcher. BitPorn
        # should use the active network/VPN route directly.
        self.opener = build_opener(ProxyHandler({}))
        self._load_cookies()

    def _load_cookies(self):
        paths = []
        if self.cookie_file:
            paths.append(self.cookie_file)
        paths.extend([
            os.path.join(os.path.dirname(__file__), "bitporn.eu_cookies.txt"),
            os.path.expandvars(r"%USERPROFILE%\Downloads\bitporn.eu_cookies.txt"),
        ])
        path = next((p for p in paths if p and os.path.isfile(p)), "")
        if not path:
            return

        jar = CookieJar()
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                fields = line.split("\t")
                if len(fields) >= 7:
                    domain, flag, cookie_path, secure, expires, name, value = fields[:7]
                    try:
                        jar.set_cookie(Cookie(
                            version=0,
                            name=name,
                            value=value,
                            port=None,
                            port_specified=False,
                            domain=domain,
                            domain_specified=domain.startswith("."),
                            domain_initial_dot=domain.startswith("."),
                            path=cookie_path or "/",
                            path_specified=True,
                            secure=secure.upper() == "TRUE",
                            expires=int(expires) if expires.isdigit() else None,
                            discard=False,
                            comment=None,
                            comment_url=None,
                            rest={},
                            rfc2109=False,
                        ))
                    except (TypeError, ValueError):
                        continue
                elif "=" in line:
                    # Also accept a single raw Cookie header exported by a browser.
                    for pair in line.split(";"):
                        if "=" not in pair:
                            continue
                        name, value = pair.strip().split("=", 1)
                        jar.set_cookie(Cookie(
                            0, name, value, None, False, "bitporn.eu", False,
                            False, "/", True, False, None, None, {}, False
                        ))
        self.opener = build_opener(ProxyHandler({}))
        self.opener.add_handler(_CookieHandler(jar))

    def _request(self, target, accept="text/html,application/xhtml+xml"):
        request = Request(target, headers={
            "Accept": accept,
            "Accept-Language": "en-GB,en;q=0.9",
            "User-Agent": "Mozilla/5.0 qBittorrent BitPorn search plugin",
            "Referer": self.url + "/",
        })
        return self.opener.open(request, timeout=self.timeout).read()

    def search(self, query, category="all"):
        try:
            query = query.replace("+", " ").strip()
            # BitPorn currently serves 25 rows per page. Keep a bounded page
            # window so a broad query does not make qBittorrent hang forever.
            for page in range(1, 11):
                target = self.search_url.format(
                    query=quote_plus(query), page=page
                )
                body = self._request(target).decode("utf-8", "replace")
                if _looks_like_login(body):
                    raise RuntimeError("BitPorn authentication expired; refresh the cookie file")
                results = _parse_results(body, target)
                for result in results:
                    result["engine_url"] = self.url
                    self._pretty_print(result)
                if not results:
                    break
        except (HTTPError, URLError, OSError, RuntimeError) as error:
            print("BitPorn: %s" % error, file=sys.stderr)

    def download_torrent(self, url):
        try:
            body = self._request(url, "text/html,application/x-bittorrent,*/*")
            if _looks_like_torrent(body):
                source_url = url
                torrent_body = body
            else:
                page = body.decode("utf-8", "replace")
                links = re.findall(
                    r"href=[\"']([^\"']+)[\"']", page, flags=re.IGNORECASE
                )
                download_url = next(
                    (urljoin(url, link) for link in links
                     if ".torrent" in link.lower() or "download" in link.lower()),
                    "",
                )
                if not download_url:
                    raise RuntimeError("no torrent download link found")
                torrent_body = self._request(
                    download_url, "application/x-bittorrent,*/*"
                )
                source_url = download_url
            if not _looks_like_torrent(torrent_body):
                raise RuntimeError("BitPorn returned a web page instead of a torrent")
            handle = tempfile.NamedTemporaryFile(prefix="bitporn_", suffix=".torrent", delete=False)
            handle.write(torrent_body)
            handle.close()
            print("%s %s" % (handle.name, source_url))
        except (HTTPError, URLError, OSError, RuntimeError) as error:
            print("BitPorn download: %s" % error, file=sys.stderr)

    def _pretty_print(self, result):
        values = [
            result.get("link", ""), result.get("name", ""),
            str(result.get("size", -1)), str(result.get("seeds", -1)),
            str(result.get("leech", -1)), result.get("engine_url", self.url),
            result.get("desc_link", result.get("link", "")),
            str(result.get("pub_date", -1)),
        ]
        print("|".join(value.replace("|", " ") for value in values))


class _CookieHandler(BaseHandler):
    def __init__(self, jar):
        self.jar = jar

    def http_request(self, request):
        self.jar.add_cookie_header(request)
        return request

    https_request = http_request


def _looks_like_login(body):
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    return bool(re.search(r"account-login|name=[\"']password[\"']|sign\s*in", text, re.I))


def _looks_like_torrent(body):
    return isinstance(body, bytes) and body.startswith(b"d") and b"announce" in body[:4096]


def _parse_results(body, page_url):
    results = []
    seen = set()
    pattern = re.compile(
        r"<a[^>]+href=[\"']([^\"']*/torrents?/\d+[^\"']*)[\"'][^>]*>(.*?)</a>",
        re.I | re.S,
    )
    for match in pattern.finditer(body):
        link = urljoin(page_url, html.unescape(match.group(1)))
        torrent_id = re.search(r"/torrents?/([0-9]+)", link, re.I)
        if not torrent_id or torrent_id.group(1) in seen:
            continue
        seen.add(torrent_id.group(1))
        name = re.sub(r"<[^>]+>", " ", match.group(2))
        name = re.sub(r"\s+", " ", html.unescape(name)).strip()
        row_start = body.rfind("<tr", 0, match.start())
        row_end = body.find("</tr>", match.end())
        row = body[row_start:row_end + 5] if row_start >= 0 and row_end >= 0 else body[match.start():match.end()]
        context = re.sub(r"<[^>]+>", " ", row)
        context = re.sub(r"\s+", " ", context)
        size = _size_bytes(context)
        seeds = _class_number(row, "seeders")
        leech = _class_number(row, "leechers")
        results.append({
            "link": link,
            "name": name or "BitPorn torrent %s" % torrent_id.group(1),
            "size": size,
            "seeds": seeds,
            "leech": leech,
            "desc_link": link,
            "pub_date": int(time.time()),
        })
    return results


def _number_after(text, expression):
    match = re.search(expression + r"\s*(\d[\d,]*)", text, re.I)
    return match.group(1).replace(",", "") if match else -1


def _class_number(row, class_name):
    match = re.search(
        r"class=[\"'][^\"']*" + re.escape(class_name)
        + r"[^\"']*[\"'][^>]*>(.*?)</td>",
        row, re.I | re.S,
    )
    if not match:
        return -1
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    number = re.search(r"\d[\d,]*", text)
    return number.group(0).replace(",", "") if number else -1


def _size_bytes(text):
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(TiB|GiB|MiB|KiB|TB|GB|MB|KB)", text, re.I)
    if not match:
        return -1
    value = float(match.group(1).replace(",", "."))
    multiplier = {
        "KB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4,
        "KIB": 1024, "MIB": 1024 ** 2, "GIB": 1024 ** 3, "TIB": 1024 ** 4,
    }
    return int(value * multiplier[match.group(2).upper()])
