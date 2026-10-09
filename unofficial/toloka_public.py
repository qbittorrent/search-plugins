# VERSION: 0.1
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Toloka: anonymous search of the public index used by Lampac NextGen.

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


class toloka_public:
    url = 'https://toloka.to'
    name = 'Toloka (public Lampac index)'
    supported_categories = {'all': 'all', 'movies': '2000', 'tv': '5000'}
    # ponytail: public default from Lampac ModInit.cs; update if its operator moves.
    api_url = 'http://ns3bg91xvuqfvq9h.cfhttp.top/api/v2.0/indexers/all/results'
    tracker = 'toloka'

    def search(self, what, cat='all'):
        if cat not in self.supported_categories:
            return
        params = {'query': unquote(what)}
        if cat != 'all':
            params['category[]'] = self.supported_categories[cat]
        request = Request(self.api_url + '?' + urlencode(params), headers={'User-Agent': 'qBittorrent/toloka_public'})
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read())
            rows = payload.get('Results') if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise ValueError('invalid public-index response')
        except (URLError, OSError, ValueError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
            return
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
