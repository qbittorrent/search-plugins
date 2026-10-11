# VERSION: 0.1
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Native AniLiberty (AniLibria) API search; no account, browser or server.
Search/releases/torrent contract checked against maintained integrations and
actual API responses; only public torrent metadata is requested.
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class aniliberty:
    url = 'https://aniliberty.top'
    name = 'AniLiberty (AniLibria)'
    supported_categories = {'all': 'all', 'anime': 'anime'}

    def fetch(self, path):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        request = Request(self.url + '/api/v1' + path, headers={'User-Agent': 'qBittorrent/aniliberty'})
        with urlopen(request, timeout=min(15, remaining)) as response:
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('API response too large')
            return json.loads(data)

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        self.deadline = time.monotonic() + 60
        seen = set()
        try:
            releases = self.fetch('/app/search/releases?' + urlencode({'query': query}))
            if not isinstance(releases, list):
                raise ValueError('invalid release response')
            for release in releases[:10]:
                if not isinstance(release, dict) or not isinstance(release.get('id'), int):
                    continue
                names = release.get('name')
                if not isinstance(names, dict):
                    continue
                titles = [name for name in (names.get('main'), names.get('english')) if isinstance(name, str) and name.strip()]
                if not titles:
                    continue
                title = ' / '.join(dict.fromkeys(titles))
                alias = release.get('alias')
                details = self.url + '/anime/releases/release/' + quote(alias, safe='') if isinstance(alias, str) and alias else self.url
                rows = self.fetch('/anime/torrents/release/' + str(release['id']))
                if not isinstance(rows, list):
                    raise ValueError('invalid torrent response')
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    magnet = row.get('magnet')
                    match = re.match(r'^magnet:\?xt=urn:btih:([0-9a-fA-F]{40}|[A-Za-z2-7]{32})(?:&|$)', magnet) if isinstance(magnet, str) else None
                    if not match or match[1] == '0' * 40 or match[1].lower() in seen:
                        continue
                    try:
                        size = int(row['size']) if row.get('size') is not None else -1
                        seeds = int(row['seeders']) if row.get('seeders') is not None else -1
                        leech = int(row['leechers']) if row.get('leechers') is not None else -1
                    except (ValueError, TypeError, OverflowError):
                        continue
                    published = -1
                    date = row.get('created_at') or row.get('updated_at')
                    if isinstance(date, str):
                        try:
                            stamp = datetime.fromisoformat(date.replace('Z', '+00:00'))
                            if stamp.tzinfo is None:
                                stamp = stamp.replace(tzinfo=timezone.utc)
                            published = int(stamp.timestamp())
                        except (ValueError, OverflowError, OSError):
                            pass
                    label = row.get('label')
                    name = title + ' / ' + label if isinstance(label, str) and label.strip() else title
                    seen.add(match[1].lower())
                    prettyPrinter({'link': magnet, 'name': name, 'size': size,
                                   'seeds': seeds, 'leech': leech, 'pub_date': published,
                                   'engine_url': self.url, 'desc_link': details})
                    if len(seen) >= 25:
                        return
        except (URLError, OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
