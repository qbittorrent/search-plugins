# VERSION: 0.1
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Search the torrentgalaxy.one mirror; not the retired torrentgalaxy.to site."""
import html
import re
import sys
import time
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urljoin
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class Listing(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.depth = 0
        self.index = -1
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        if tag == 'div' and 'tgxtablerow' in classes:
            self.row = {'cells': [], 'name': '', 'path': ''}
            self.depth = 1
            self.index = -1
            return
        if self.row is None:
            return
        if tag == 'div':
            self.depth += 1
            if self.depth == 2 and 'tgxtablecell' in classes:
                self.index += 1
                self.cell = self.index
                self.row['cells'].append('')
        if tag == 'a' and self.cell == 3 and attrs.get('href', '').startswith('/post-detail/'):
            self.row['path'] = attrs['href']
            self.row['name'] = attrs.get('title', '')

    def handle_data(self, data):
        if self.row is not None and self.cell is not None:
            self.row['cells'][self.cell] += data

    def handle_endtag(self, tag):
        if self.row is None or tag != 'div':
            return
        if self.depth == 2:
            self.cell = None
        self.depth -= 1
        if self.depth == 0:
            if self.row['path'] and self.row['name']:
                self.rows.append(self.row)
            self.row = None


class torrentgalaxy:
    url = 'https://torrentgalaxy.one'
    name = 'TorrentGalaxy (.one mirror)'
    supported_categories = {'all': '', 'movies': 'Movies', 'tv': 'TV'}

    def fetch(self, path):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Search budget exhausted')
        request = Request(urljoin(self.url + '/', path), headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=min(20, remaining)) as response:
            if response.url.split('/', 3)[2] != self.url.split('/', 3)[2]:
                raise ValueError('Unexpected mirror redirect')
            return response.read().decode('utf-8', errors='replace')

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        self.deadline = time.monotonic() + 90
        path = '/get-posts/keywords:' + quote(query, safe='')
        if cat != 'all':
            path += ':category:' + self.supported_categories[cat]
        parser = Listing()
        parser.feed(self.fetch(path + ':order:-se/'))
        tokens = re.findall(r'\w+', query.casefold())
        for row in parser.rows[:50]:
            title_words = set(re.findall(r'\w+', row['name'].casefold()))
            if not all(token in title_words for token in tokens):
                continue
            if time.monotonic() >= self.deadline:
                print('TorrentGalaxy: search budget exhausted', file=sys.stderr)
                break
            try:
                document = self.fetch(row['path'])
                match = re.search(r'href=["\'](magnet:[^"\']+)["\']', document, re.IGNORECASE)
                magnet = html.unescape(match[1]) if match else ''
                if not re.search(r'(?:\?|&)xt=urn:btih:(?:[a-f0-9]{40}|[a-z2-7]{32})(?:&|$)', magnet, re.IGNORECASE):
                    raise ValueError('Invalid magnet')
            except (OSError, ValueError) as error:
                print('TorrentGalaxy: topic failed ({})'.format(type(error).__name__), file=sys.stderr)
                continue
            cells = row['cells']
            size = re.search(r'([\d.,]+)\s*(KB|MB|GB|TB)', cells[7], re.IGNORECASE) if len(cells) > 7 else None
            amount = int(float(size[1].replace(',', '.')) * 1024 ** {'KB': 1, 'MB': 2, 'GB': 3, 'TB': 4}[size[2].upper()]) if size else -1
            peers = re.search(r'\[\s*(\d+)\s*/\s*(\d+)\s*\]', cells[10]) if len(cells) > 10 else None
            prettyPrinter({'link': magnet, 'name': row['name'], 'size': amount,
                           'seeds': int(peers[1]) if peers else -1,
                           'leech': int(peers[2]) if peers else -1, 'engine_url': self.url,
                           'desc_link': urljoin(self.url, row['path']), 'pub_date': -1})
