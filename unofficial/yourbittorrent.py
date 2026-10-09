# VERSION: 1.4
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
# Replaces the obsolete LightDestory 1.3 layout/download adapter.

import html
import re
import sys
import tempfile
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import unquote, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class yourbittorrent:
    url = 'https://yourbittorrent.com/'
    name = 'YourBittorrent'
    supported_categories = {'all': '0', 'movies': '1', 'tv': '3', 'music': '2',
                            'games': '4', 'anime': '6', 'software': '5'}
    headers = {'User-Agent': 'curl/8.18.0'}

    def fetch(self, url):
        with urlopen(Request(url, headers=self.headers), timeout=20) as response:
            return response.read()

    def search(self, what, cat='all'):
        if cat not in self.supported_categories:
            return
        params = {'q': unquote(what).replace(' ', '-')}
        if cat != 'all':
            params['c'] = self.supported_categories[cat]
        try:
            document = self.fetch(self.url + '?' + urlencode(params)).decode('utf-8')
        except (URLError, OSError, UnicodeError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
            return
        seen = set()
        for row in re.findall(r'<tr\b[^>]*>.*?</tr>', document, re.S):
            match = re.search(r'<a\b[^>]*class="yb-tname"[^>]*href="(/torrent/\d+/[^"<>]+)"[^>]*title="([^"]+)"', row)
            if not match or match[1] in seen:
                continue
            values = {}
            for label in ('Size', 'Seed', 'Peers'):
                cell = re.search(r'<td\b[^>]*data-label="' + label + r'"[^>]*>(.*?)</td>', row, re.S)
                if cell:
                    values[label] = html.unescape(re.sub(r'<[^>]+>', '', cell[1])).strip()
            if len(values) != 3:
                continue
            name = html.unescape(re.sub(r'<[^>]+>', '', match[2])).strip()
            if not name:
                continue
            published = -1
            date = re.search(r'<time\b[^>]*datetime="(\d{4}-\d{2}-\d{2})"', row)
            if date:
                try:
                    published = int(datetime.fromisoformat(date[1]).replace(tzinfo=timezone.utc).timestamp())
                except ValueError:
                    pass
            seen.add(match[1])
            link = urljoin(self.url, html.unescape(match[1]))
            prettyPrinter({'link': link, 'name': name, 'size': values['Size'],
                           'seeds': values['Seed'].replace(',', ''), 'leech': values['Peers'].replace(',', ''),
                           'engine_url': self.url, 'desc_link': link, 'pub_date': published})

    def download_torrent(self, info):
        try:
            target = urlsplit(info)
            if target.hostname != 'yourbittorrent.com' or target.scheme != 'https':
                raise ValueError('unexpected detail host')
            match = re.match(r'/torrent/(\d+)/', target.path)
            if not match:
                raise ValueError('invalid detail path')
            torrent_id = match[1]
            document = self.fetch(self.url + '?' + urlencode({'section': 'download', 'id': torrent_id})).decode('utf-8')
            location = re.search(r'var\s+url\s*=\s*["\'](https://yt\.t0r\.store/down/' + torrent_id + r'\.torrent)["\']', document)
            if not location:
                raise ValueError('torrent download route unavailable')
            payload = self.fetch(location[1])
            if not payload.startswith(b'd') or not payload.endswith(b'e') or b'4:info' not in payload:
                raise ValueError('response is not torrent metadata')
            with tempfile.NamedTemporaryFile(prefix='qbt-yourbittorrent-', suffix='.torrent', delete=False) as output:
                output.write(payload)
            print(output.name + ' ' + info)
        except (URLError, OSError, ValueError, UnicodeError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
