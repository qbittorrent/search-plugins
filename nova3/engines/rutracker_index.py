# VERSION: 0.3
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""RuTracker: anonymous search of the public index used by Lampac NextGen.

No tracker account or locally deployed server is required. This is indexed
search, not a live authenticated tracker.php search. Public index availability
and crawl coverage determine results. The upstream default currently uses HTTP:
queries are public but not encrypted in transit. Do not put credentials in them.
API contract: lampac-nextgen/lampac, Modules/JacRed/Engine/WebApi.cs (AGPL-3.0).
"""

import json
import re
import sys
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class rutracker_index:
    url = 'https://rutracker.org'
    name = 'RuTracker (public indices)'
    supported_categories = {'all': 'all', 'movies': '2000', 'tv': '5000', 'software': '4000'}
    knaben_categories = {'movies': 3000000, 'tv': 2000000, 'software': 4000000}
    # ponytail: public default from Lampac ModInit.cs; update if its operator moves.
    api_url = 'http://ns3bg91xvuqfvq9h.cfhttp.top/api/v2.0/indexers/all/results'
    tracker = 'rutracker'

    def search(self, what, cat='all'):
        if cat not in self.supported_categories:
            return
        query = unquote(what).strip()
        if not query:
            return
        params = {'query': query}
        if cat != 'all':
            params['category[]'] = self.supported_categories[cat]
        rows = []
        if cat != 'software':
            try:
                request = Request(self.api_url + '?' + urlencode(params), headers={'User-Agent': 'qBittorrent/rutracker_index'})
                with urlopen(request, timeout=20) as response:
                    payload = json.loads(response.read(4 * 1024 * 1024))
                if not isinstance(payload, dict) or not isinstance(payload.get('Results'), list):
                    raise ValueError('invalid primary index response')
                rows = payload['Results']
            except (URLError, OSError, ValueError):
                pass
        if self.emit(rows):
            return
        # A movie/TV index cannot cover software; the fallback must retain exact RuTracker origin.
        body = {'query': query, 'search_field': 'title', 'order_by': 'seeders',
                'order_direction': 'desc', 'from': 0, 'size': 100,
                'hide_unsafe': True, 'hide_xxx': True}
        if cat != 'all':
            # Knaben IDs are not the primary index's Torznab category IDs.
            body['categories'] = [self.knaben_categories[cat]]
        try:
            request = Request('https://api.knaben.org/v1', data=json.dumps(body).encode(),
                              headers={'User-Agent': 'qBittorrent/rutracker_index', 'Content-Type': 'application/json'})
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read(4 * 1024 * 1024))
            if not isinstance(payload, dict) or not isinstance(payload.get('hits'), list):
                raise ValueError('invalid broader index response')
            rows = []
            for row in payload['hits']:
                if not isinstance(row, dict) or str(row.get('tracker', '')).casefold() != 'rutracker.org':
                    continue
                magnet = row.get('magnetUrl')
                if not isinstance(magnet, str) or not magnet.startswith('magnet:?'):
                    infohash = row.get('hash')
                    if not isinstance(infohash, str) or not re.fullmatch(r'[0-9a-fA-F]{40}', infohash):
                        continue
                    magnet = 'magnet:?xt=urn:btih:' + infohash
                rows.append({'Tracker': 'rutracker', 'MagnetUri': magnet, 'Title': row.get('title'),
                             'Details': row.get('details') or row.get('link') or self.url,
                             'Size': row.get('bytes') if row.get('bytes') is not None else -1,
                             'Seeders': row.get('seeders') if row.get('seeders') is not None else -1,
                             'Peers': row.get('peers') if row.get('peers') is not None else -1,
                             'PublishDate': row.get('date') or row.get('lastSeen')})
            self.emit(rows)
        except (URLError, OSError, ValueError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)

    def emit(self, rows):
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            trackers = {value.strip().lower() for value in str(row.get('Tracker', '')).split(',')}
            if self.tracker not in trackers:
                continue
            magnet = row.get('MagnetUri', '')
            title = row.get('Title')
            details = row.get('Details', '')
            if not isinstance(magnet, str) or not magnet.startswith('magnet:?') or not isinstance(title, str) or not title.strip():
                continue
            values = parse_qs(urlsplit(magnet).query).get('xt', [])
            hashes = [value[9:] for value in values if value.lower().startswith('urn:btih:')]
            if urlsplit(magnet).scheme != 'magnet' or not hashes:
                continue
            infohash = hashes[0].lower()
            if not re.fullmatch(r'(?:[0-9a-f]{40}|[a-z2-7]{32})', infohash) or infohash == '0' * 40 or infohash in seen:
                continue
            if not isinstance(details, str):
                continue
            try:
                target = urlsplit(details)
                if target.scheme not in ('http', 'https') or not target.hostname:
                    continue
            except ValueError:
                continue
            try:
                size = int(row.get('Size', -1))
                seeds = int(row.get('Seeders', -1))
                leech = int(row.get('Peers', -1))
            except (ValueError, TypeError, OverflowError):
                continue
            published = -1
            date = row.get('PublishDate')
            if isinstance(date, str):
                try:
                    stamp = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    published = int(stamp.timestamp())
                except (ValueError, OverflowError, OSError):
                    pass
            seen.add(infohash)
            prettyPrinter({'link': magnet, 'name': title, 'size': size, 'seeds': seeds,
                           'leech': leech, 'engine_url': self.url, 'desc_link': details,
                           'pub_date': published})
        return len(seen)
