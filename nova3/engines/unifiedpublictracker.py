# VERSION: 3.4
# AUTHORS: Unified — consolidated public tracker plugin
# LICENCE: GPL-3.0

import re
import json
import html as html_module
from urllib.parse import quote, quote_plus

from helpers import retrieve_url
from novaprinter import prettyPrinter, SearchResults


def _nn(name):
    name = re.sub(r"<[^>]+>", " ", str(name))
    name = html_module.unescape(name)
    return " ".join(name.split())


def _sz(text):
    if not text:
        return "-1"
    text = html_module.unescape(str(text)).strip()
    m = re.search(r"([\d,.]+)\s*([KMGTPE]?B)", text, re.I)
    if m:
        return "{} {}".format(m.group(1).replace(",", ""), m.group(2))
    return text.replace(",", "") if text else "-1"


def _extract_magnet_hash(magnet):
    if not magnet:
        return None
    m = re.search(r'urn:btih:([a-fA-F0-9]{40}|[a-fA-F0-9]{32})', magnet)
    return m.group(1).lower() if m else None


class unifiedpublictracker(object):
    url = "https://github.com/qbittorrent/search-plugins"
    name = "Unified Public Tracker"
    supported_categories = {"all": "0"}

    def search(self, what, cat="all"):
        seen_hashes = set()
        engines = [
            self._bitsearch, self._thepiratebay, self._rutor,
            self._nyaa, self._solidtorrents, self._dmhy,
            self._yts, self._eztv, self._academictorrents,
        ]
        for fn in engines:
            try:
                for r in fn(what):
                    link = r.get("link", "")
                    h = _extract_magnet_hash(link)
                    if h:
                        if h in seen_hashes:
                            continue
                        seen_hashes.add(h)
                    if link:
                        prettyPrinter(SearchResults(**r))
            except Exception:
                pass

    def download_torrent(self, info):
        from helpers import download_file
        print(download_file(info))

    # ── YTS ────────────────────────────────────────────────────────────
    def _yts(self, what):
        results = []
        from urllib.parse import urlencode
        params = {"query_term": what, "page": 1, "sort_by": "seeds", "order_by": "desc", "limit": 50}
        data = None
        for domain in ["https://yts.mx", "https://yts.am", "https://yts.lt"]:
            url = "{}/api/v2/list_movies.json?{}".format(domain, urlencode(params))
            try:
                data = retrieve_url(url)
            except Exception:
                data = None
            if data:
                break
        if not data:
            return results
        resp = json.loads(data)
        for movie in resp.get("data", {}).get("movies", []):
            for t in movie.get("torrents", []):
                results.append({
                    "link": t.get("url", ""),
                    "name": "{} [{}]".format(movie.get("title_long", "?"), t.get("quality", "?")),
                    "size": t.get("size", "-1"),
                    "seeds": int(t.get("seeds", 0)),
                    "leech": int(t.get("peers", 0)),
                    "engine_url": "https://yts.mx/",
                    "desc_link": movie.get("url", "https://yts.mx/"),
                })
        return results

    # ── BitSearch ──────────────────────────────────────────────────────
    def _bitsearch(self, what):
        results = []
        for page in range(1, 4):
            url = "https://bitsearch.to/api/v1/search?q={}&page={}&sort=seeders".format(quote(what), page)
            data = retrieve_url(url)
            if not data:
                break
            resp = json.loads(data)
            torrents = resp.get("results", [])
            if not torrents:
                break
            for t in torrents:
                ih = t.get("infohash", "")
                results.append({
                    "link": "magnet:?xt=urn:btih:{}&dn={}".format(ih, quote_plus(t.get("title", ""))),
                    "name": _nn(t.get("title", "?")),
                    "size": _sz("{} B".format(t.get("size", 0))),
                    "seeds": int(t.get("seeders", 0)),
                    "leech": int(t.get("leechers", 0)),
                    "engine_url": "https://bitsearch.to/",
                    "desc_link": "https://bitsearch.to/torrent/{}".format(t.get("id", "")),
                })
        return results

    # ── ThePirateBay ───────────────────────────────────────────────────
    def _thepiratebay(self, what):
        results = []
        from urllib.parse import urlencode
        url = "https://apibay.org/q.php?" + urlencode({"q": what, "cat": "0"})
        data = retrieve_url(url)
        if not data:
            return results
        resp = json.loads(data)
        if not isinstance(resp, list):
            return results
        for t in resp:
            if t.get("id") == "0":
                continue
            ih = t.get("info_hash", "")
            results.append({
                "link": "magnet:?xt=urn:btih:{}&dn={}".format(ih, quote_plus(t.get("name", ""))),
                "name": _nn(t.get("name", "?")),
                "size": _sz("{} B".format(t.get("size", "-1"))),
                "seeds": int(t.get("seeders", 0)),
                "leech": int(t.get("leechers", 0)),
                "engine_url": "https://thepiratebay.org/",
                "desc_link": "https://apibay.org/t.php?id={}".format(t.get("id", "")),
            })
        return results

    # ── Rutor ──────────────────────────────────────────────────────────
    def _rutor(self, what):
        results = []
        base = "https://rutor.info"
        for page in range(3):
            url = "{}/search/{}/0/000/2/{}".format(base, page, quote(what))
            html = retrieve_url(url)
            if not html:
                break
            idx = html.find('<div id="index">')
            if idx < 0:
                break
            chunk = html[idx:]
            rows = re.findall(r'<tr class="(gai|tum)">(.*?)</tr>', chunk, re.S)
            if not rows:
                break
            for _, row in rows:
                m_mag = re.search(r'href="(magnet:\?[^"]+)"', row)
                m_link = re.search(r'href="(/torrent/\d+/[^"]*)"[^>]*>\s*(.*?)\s*</a>', row, re.S)
                m_size = re.search(r'<td[^>]*align="right">\s*([\d.,]+(?:\s|&nbsp;)*[KMGTPE]?B)', row, re.I)
                m_green = re.search(r'<span class="green">.*?(\d+)</span>', row, re.S)
                m_red = re.search(r'<span class="red">.*?(\d+)</span>', row, re.S)
                if m_mag and m_link:
                    results.append({
                        "link": m_mag.group(1),
                        "name": _nn(m_link.group(2)),
                        "size": _sz(m_size.group(1)) if m_size else "-1",
                        "seeds": int(m_green.group(1)) if m_green else -1,
                        "leech": int(m_red.group(1)) if m_red else -1,
                        "engine_url": base + "/",
                        "desc_link": base + m_link.group(1),
                    })
        return results

    # ── Nyaa ───────────────────────────────────────────────────────────
    def _nyaa(self, what):
        results = []
        base = "https://nyaa.si"
        for page in range(1, 4):
            url = "{}/?f=0&c=0_0&q={}&p={}&s=seeders&o=desc".format(base, quote(what), page)
            html = retrieve_url(url)
            if not html:
                break
            rows = re.findall(r'<tr class="(?:default|success|danger)">.*?</tr>', html, re.S)
            if not rows:
                break
            for row in rows:
                m_name = re.search(r'<a[^>]*title="(.*?)"[^>]*>.*?</a>', row)
                m_link = re.search(r'href="(magnet:\?[^"]+)"', row)
                m_size = re.search(r'<td[^>]*class="text-center[^"]*">([\d,.]+\s*[KMGTPE]?iB)</td>', row, re.I)
                m_seeds = re.findall(r'<td[^>]*class="text-center"[^>]*>(\d+)</td>', row)
                m_desc = re.search(r'<a[^>]*href="(/view/[^"]*)"[^>]*title="', row)
                if m_name and m_link:
                    results.append({
                        "link": m_link.group(1),
                        "name": _nn(m_name.group(1)),
                        "size": _sz(m_size.group(1)) if m_size else "-1",
                        "seeds": int(m_seeds[0]) if m_seeds else -1,
                        "leech": int(m_seeds[1]) if len(m_seeds) > 1 else -1,
                        "engine_url": base + "/",
                        "desc_link": base + m_desc.group(1) if m_desc else base + "/",
                    })
        return results

    # ── SolidTorrents ──────────────────────────────────────────────────
    def _solidtorrents(self, what):
        results = []
        base = "https://solidtorrents.to"
        for page in range(1, 4):
            url = "{}/search?q={}&page={}".format(base, quote_plus(what), page)
            html = retrieve_url(url)
            if not html:
                break
            entries = re.findall(
                r'<a[^>]*href="(/torrent/[^"]+)"[^>]*>\s*(.*?)\s*</a>.*?'
                r'<span[^>]*>\s*([\d,.]+\s*[KMGTPE]?B)\s*</span>.*?'
                r'text-green-600">.*?<span[^>]*>(\d+)</span>.*?'
                r'text-red-600">.*?<span[^>]*>(\d+)</span>.*?'
                r'href="(magnet:\?[^"]+)"',
                html, re.S,
            )
            if not entries:
                break
            for href, name, size, seeds, leech, magnet in entries:
                magnet = html_module.unescape(magnet)
                results.append({
                    "link": magnet,
                    "name": _nn(name),
                    "size": _sz(size),
                    "seeds": int(seeds),
                    "leech": int(leech),
                    "engine_url": base + "/",
                    "desc_link": base + href,
                })
        return results

    # ── DMHY ───────────────────────────────────────────────────────────
    def _dmhy(self, what):
        results = []
        base = "https://share.dmhy.org"
        for page in range(1, 4):
            url = "{}/topics/list?keyword={}&page={}".format(base, quote_plus(what), page)
            html = retrieve_url(url)
            if not html:
                break
            rows = re.findall(r'<tr[^>]*class="[^"]*"[^>]*>.*?</tr>', html, re.S)
            if not rows:
                break
            for row in rows:
                m_link = re.search(r'href="(magnet:\?[^"]+)"', row)
                if not m_link:
                    continue
                m_name = re.search(r'<td class="title">\s*.*?<a[^>]*href="/topics/view/[^"]*"[^>]*>\s*(.*?)\s*</a>', row, re.S)
                m_size = re.search(r'<td[^>]*>\s*([\d,.]+\s*[KMGTPE]?B)\s*</td>', row, re.I)
                m_seeds = re.search(r'<td[^>]*>\s*(\d+)\s*</td>', row)
                if m_name:
                    name = re.sub(r'<[^>]+>', '', m_name.group(1))
                    name = html_module.unescape(name).strip()
                    results.append({
                        "link": m_link.group(1),
                        "name": name,
                        "size": _sz(m_size.group(1)) if m_size else "-1",
                        "seeds": int(m_seeds.group(1)) if m_seeds else -1,
                        "leech": -1,
                        "engine_url": base + "/",
                        "desc_link": base + "/",
                    })
        return results

    # ── EZTV ───────────────────────────────────────────────────────────
    def _eztv(self, what):
        results = []
        keywords = [t.lower() for t in re.split(r"\s+", what.replace(".", " ").replace("-", " ").strip()) if t]
        kw_res = [re.compile(r'(?<![a-z0-9])' + re.escape(k) + r'(?![a-z0-9])') for k in keywords]
        for page in range(1, 4):
            url = "https://eztvx.to/api/get-torrents?limit=100&page={}&Keywords={}".format(
                page, quote_plus(what))
            data = retrieve_url(url)
            if not data:
                break
            resp = json.loads(data)
            torrents = resp.get("torrents", [])
            if not torrents:
                break
            for t in torrents:
                title = t.get("title", "").lower()
                if kw_res and not all(r.search(title) for r in kw_res):
                    continue
                sb = int(t.get("size_bytes", -1))
                sz = "-1" if sb < 0 else ("{:.1f} MB".format(sb / (1024 ** 2)) if sb < 1024 ** 3 else "{:.2f} GB".format(sb / (1024 ** 3)))
                results.append({
                    "link": t.get("magnet_url") or t.get("torrent_url", ""),
                    "name": title,
                    "size": sz,
                    "seeds": int(t.get("seeds", 0)),
                    "leech": int(t.get("peers", 0)),
                    "engine_url": "https://eztvx.to",
                    "desc_link": t.get("episode_url", "https://eztvx.to"),
                })
            if len(results) >= 200 or len(torrents) < 100:
                break
        return results

    # ── AcademicTorrents ───────────────────────────────────────────────
    def _academictorrents(self, what):
        results = []
        import xml.etree.ElementTree as ET
        data = retrieve_url("https://academictorrents.com/rss.xml")
        if not data:
            return results
        root = ET.fromstring(data)
        terms = [t.lower() for t in re.split(r"%20|\s", str(what)) if t]
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            if not any(t in title.lower() for t in terms):
                continue
            link = item.findtext("link", "")
            infohash = ""
            for enc in item.findall("enclosure"):
                u = enc.get("url", "")
                if u.endswith(".torrent"):
                    infohash = u.split("/")[-1].replace(".torrent", "")
            size = item.findtext("size", "") or "-1"
            results.append({
                "link": "https://academictorrents.com/download/{}.torrent".format(infohash) if infohash else link,
                "name": title,
                "size": size,
                "seeds": -1,
                "leech": -1,
                "engine_url": "https://academictorrents.com/",
                "desc_link": link,
            })
        return results
