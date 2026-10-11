# VERSION: 2.1
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Native Torrent9 search on the maintained www7.torrent9.to domain.
Current routes/table/detail magnets were inspected; no account or server.
This is an independent parser, not an import shim over the obsolete plugin.
"""
import html
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class torrent9:
    url = 'https://www7.torrent9.to'
    name = 'Torrent9'
    supported_categories = {'all': 'all'}

    def fetch(self, path):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        target = urljoin(self.url, path)
        if urlsplit(target).hostname != urlsplit(self.url).hostname or urlsplit(target).scheme != 'https':
            raise ValueError('off-site route')
        with urlopen(Request(target, headers={'User-Agent': 'Mozilla/5.0'}), timeout=min(12, remaining)) as response:
            if urlsplit(response.geturl()).hostname != urlsplit(self.url).hostname:
                raise ValueError('unexpected redirect')
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('response too large')
            return data.decode(response.headers.get_content_charset() or 'utf-8')

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat != 'all':
            return
        self.deadline = time.monotonic() + 60
        try:
            document = self.fetch('/search_torrent/' + quote(query.replace(' ', '-'), safe='') + '.html')
            seen = set()
            for row in re.findall(r'<tr\b[^>]*>.*?</tr>', document, re.S):
                cells = re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.S)
                if len(cells) < 5:
                    continue
                topic = re.search(r'<a\b[^>]*href=["\x27](/torrent/[^"\x27]+)["\x27][^>]*>(.*?)</a>', cells[0], re.S)
                if not topic or topic[1] in seen:
                    continue
                title = html.unescape(re.sub('<[^>]+>', '', topic[2])).strip()
                if not title:
                    continue
                detail = self.fetch(topic[1])
                magnet = re.search(r'(magnet:\?xt=urn:btih:([0-9a-fA-F]{40}|[A-Za-z2-7]{32})(?:&[^"\x27<>\s]*)?)', detail)
                if not magnet or magnet[2] == '0' * 40:
                    raise ValueError('topic has no valid magnet')
                size = html.unescape(re.sub('<[^>]+>', '', cells[2])).strip()
                size = re.sub(r'([KMGT])o\b', r'\1B', size, flags=re.I).replace(',', '.')
                seeds = re.sub('<[^>]+>', '', cells[3]).strip()
                leech = re.sub('<[^>]+>', '', cells[4]).strip()
                date = re.sub('<[^>]+>', '', cells[1]).strip()
                published = -1
                try:
                    published = int(datetime.strptime(date, '%d/%m/%Y').replace(tzinfo=timezone.utc).timestamp())
                except ValueError:
                    pass
                seen.add(topic[1])
                prettyPrinter({'link': html.unescape(magnet[1]), 'name': title,
                               'size': size or '-1', 'seeds': seeds if seeds.isdigit() else '-1',
                               'leech': leech if leech.isdigit() else '-1',
                               'pub_date': published, 'engine_url': self.url,
                               'desc_link': urljoin(self.url, topic[1])})
                if len(seen) >= 20:
                    break
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
