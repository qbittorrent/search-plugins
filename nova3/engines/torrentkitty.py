# VERSION: 0.1
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Native public TorrentKitty magnet search; no account or external package."""
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from urllib.parse import quote, unquote, urljoin, urlparse, parse_qs
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class torrentkitty:
    url = 'https://www.torrentkitty.cam'
    name = 'TorrentKitty'
    supported_categories = {'all': 'all'}

    @staticmethod
    def text(value):
        return ' '.join(unescape(re.sub('<[^>]+>', '', value)).split())

    @staticmethod
    def infohash(link):
        if urlparse(link).scheme != 'magnet':
            raise ValueError('not a magnet')
        for value in parse_qs(urlparse(link).query).get('xt', []):
            match = re.fullmatch(r'urn:btih:([0-9a-fA-F]{40})', value)
            if match and match[1] != '0' * 40:
                return match[1].lower()
        raise ValueError('missing native infohash')

    def parse(self, document):
        table = re.search(r'<table\b[^>]*id=["\x27]archiveResult["\x27][^>]*>(.*?)</table>', document, re.S | re.I)
        if not table:
            raise ValueError('unrecognized native table; access/layout unresolved')
        rows = []
        for tr in re.findall(r'<tr\b[^>]*>.*?</tr>', table[1], re.S | re.I):
            tr = re.sub(r'<!--.*?-->', '', tr, flags=re.S)
            title = re.search(r'<td\b[^>]*class=["\x27]name["\x27][^>]*>(.*?)</td>', tr, re.S)
            detail = re.search(r'href=["\x27](/information/[0-9a-fA-F]{40})["\x27]', tr)
            magnet = re.search(r'href=["\x27](magnet:\?[^"\x27]+)["\x27]', tr)
            if not title or not detail or not magnet:
                continue
            link = unescape(magnet[1])
            try:
                key = self.infohash(link)
            except ValueError:
                continue
            if key != detail[1].rsplit('/', 1)[-1].lower():
                continue
            name = self.text(title[1])
            if not name:
                continue
            date = re.search(r'<td\b[^>]*class=["\x27]date["\x27][^>]*>(.*?)</td>', tr, re.S)
            stamp = -1
            if date:
                try:
                    stamp = int(datetime.strptime(self.text(date[1]), '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())
                except ValueError:
                    pass
            # Native size is the uploaded .torrent metadata, not the payload size.
            rows.append({'link': link, 'name': name, 'size': -1, 'seeds': -1, 'leech': -1,
                         'engine_url': self.url, 'desc_link': urljoin(self.url, detail[1]), 'pub_date': stamp})
        return rows

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        target = self.url + '/search/' + quote(query, safe='') + '/'
        pages = set(); hashes = set(); deadline = time.monotonic() + 75
        try:
            while target and target not in pages:
                pages.add(target)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('search deadline reached')
                with urlopen(Request(target, headers={'User-Agent': 'Mozilla/5.0'}), timeout=min(12, remaining)) as response:
                    if urlparse(response.geturl()).hostname != urlparse(self.url).hostname:
                        raise ValueError('unexpected redirect')
                    data = response.read(4 * 1024 * 1024 + 1)
                    if len(data) > 4 * 1024 * 1024:
                        raise ValueError('response too large')
                    document = data.decode(response.headers.get_content_charset() or 'utf-8')
                for row in self.parse(document):
                    key = self.infohash(row['link'])
                    if key not in hashes:
                        hashes.add(key); prettyPrinter(row)
                pagination = re.search(r'<div\b[^>]*class=["\x27]pagination["\x27][^>]*>(.*?)</div>', document, re.S)
                next_link = re.search(r'<a\b[^>]*href=["\x27](\d+)["\x27][^>]*>\s*(?:»|&raquo;)\s*</a>', pagination[1]) if pagination else None
                target = urljoin(target, next_link[1]) if next_link else ''
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)

    def download_torrent(self, link):
        target = link if link.startswith('magnet:?') else unquote(link)
        self.infohash(target)
        print(target + ' ' + target)
