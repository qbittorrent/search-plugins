# VERSION: 1.1
# AUTHORS: mauricci; kalpakprod (current native public JSON API)
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Native TorrentFunk public API; no key, account, browser or external package."""
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen
from novaprinter import prettyPrinter


class torrentfunk:
    url = 'https://www.torrentfunk.com'
    name = 'TorrentFunk'
    supported_categories = {'all': None, 'movies': 1, 'tv': 3, 'music': 2,
                            'games': 4, 'anime': 6, 'software': 5}

    @staticmethod
    def infohash(link):
        if urlparse(link).scheme != 'magnet':
            raise ValueError('not a magnet')
        for value in parse_qs(urlparse(link).query).get('xt', []):
            match = re.fullmatch(r'urn:btih:([0-9a-fA-F]{40})', value)
            if match and match[1] != '0' * 40:
                return match[1].lower()
        raise ValueError('invalid native magnet')

    def fetch(self, parameters):
        target = self.url + '/api/search.json?' + urlencode(parameters)
        directory = Path(__file__).with_suffix('.data') / 'api-cache'
        cache = directory / (hashlib.sha256(target.encode()).hexdigest() + '.json')
        try:
            stored = json.loads(cache.read_text())
            if 0 <= time.time() - stored['fetched'] < 900:
                return stored['data']
        except (OSError, ValueError, KeyError, TypeError):
            pass
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        with urlopen(Request(target, headers={'User-Agent': 'qBittorrent-search-plugin/1.1'}), timeout=min(12, remaining)) as response:
            if urlparse(response.geturl()).hostname != urlparse(self.url).hostname:
                raise ValueError('unexpected API redirect')
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('API response too large')
            result = json.loads(data)
        if not isinstance(result, dict) or result.get('status') != 'ok' or not isinstance(result.get('results'), list):
            raise ValueError('native API error')
        # The native API asks clients not to repeat search requests within 15 minutes.
        path = None
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory, delete=False) as temp:
                path = Path(temp.name)
                json.dump({'fetched': time.time(), 'data': result}, temp)
            os.replace(path, cache); path = None
        except OSError:
            pass  # A read-only engine directory must not hide valid native results.
        finally:
            if path is not None:
                path.unlink(missing_ok=True)
        return result

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        if len(query) > 100:
            print(self.name + ': native query limit is 100 characters', file=sys.stderr)
            return
        parameters = {'q': query, 'limit': 100, 'page': 1}
        category = self.supported_categories[cat]
        if category is not None:
            parameters['category'] = category
        self.deadline = time.monotonic() + 90; hashes = set()
        try:
            # Native documented limit: page * limit cannot exceed 1000.
            for page in range(1, 11):
                parameters['page'] = page
                response = self.fetch(parameters)
                if response.get('status') != 'ok' or not isinstance(response.get('results'), list):
                    raise ValueError('native API error')
                if response.get('page') != page or response.get('limit') != 100:
                    raise ValueError('unexpected native page')
                total = response.get('total_found')
                if not isinstance(total, int) or total < 0:
                    raise ValueError('invalid native result count')
                for item in response['results']:
                    if not isinstance(item, dict):
                        continue
                    link = item.get('magnet', '')
                    if not isinstance(link, str):
                        continue
                    try:
                        key = self.infohash(link)
                    except (ValueError, TypeError):
                        continue
                    detail = item.get('url', ''); parts = urlparse(detail)
                    name = item.get('name', ''); size = item.get('size_bytes', -1)
                    if key != str(item.get('infohash', '')).lower() or key in hashes or not isinstance(name, str) or not name:
                        continue
                    if parts.scheme != 'https' or parts.hostname != urlparse(self.url).hostname or not re.fullmatch(r'/torrent/\d+/[^/]+\.html', parts.path):
                        continue
                    if category is not None and item.get('category_id') != category:
                        continue
                    hashes.add(key)
                    seeds = item.get('seeds', -1); added = item.get('added', -1); leech = item.get('peers', -1)
                    prettyPrinter({'link': link, 'name': name, 'size': size if isinstance(size, int) and size >= 0 else -1,
                                   'seeds': seeds if isinstance(seeds, int) and seeds >= 0 else -1,
                                   # Native Torznab peers = JSON seeds + JSON peers; JSON peers are leechers.
                                   'leech': leech if isinstance(leech, int) and leech >= 0 else -1, 'engine_url': self.url, 'desc_link': detail,
                                   'pub_date': added if isinstance(added, int) and added >= 0 else -1})
                if page * 100 >= min(total, 1000) or not response['results']:
                    break
        except (OSError, ValueError, TypeError, KeyError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)

    def download_torrent(self, link):
        target = link if link.startswith('magnet:?') else unquote(link)
        self.infohash(target)
        print(target + ' ' + target)
