# VERSION: 0.2
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Standalone public Knaben API index; no account or local service.
Protocol checked against JacRed's KnabenApiModels and live /v1 responses.
This queries the public index, not private tracker accounts or torrent payloads.
"""
import json
import re
import sys
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class knaben:
    url = 'https://api.knaben.org'
    name = 'Knaben (public API index)'
    supported_categories = {'all': None, 'movies': 3000000, 'tv': 2000000, 'software': 4000000}

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        body = {'query': query, 'search_field': 'title', 'order_by': 'seeders',
                'order_direction': 'desc', 'from': 0, 'size': 50,
                'hide_unsafe': True, 'hide_xxx': True}
        if cat != 'all':
            body['categories'] = [self.supported_categories[cat]]
        request = Request(self.url + '/v1', data=json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json', 'User-Agent': 'qBittorrent/knaben'})
        try:
            with urlopen(request, timeout=20) as response:
                payload = response.read(4 * 1024 * 1024 + 1)
                if len(payload) > 4 * 1024 * 1024:
                    raise ValueError('response too large')
                payload = json.loads(payload)
            rows = payload.get('hits') if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise ValueError('invalid index response')
        except (URLError, OSError, ValueError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
            return
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('title'), str) or not row['title'].strip():
                continue
            magnet = row.get('magnetUrl')
            match = re.match(r'^magnet:\?xt=urn:btih:([0-9a-fA-F]{40}|[A-Za-z2-7]{32})(?:&|$)', magnet) if isinstance(magnet, str) else None
            infohash = match[1].lower() if match else str(row.get('hash', '')).lower()
            if not re.fullmatch(r'[0-9a-f]{40}|[a-z2-7]{32}', infohash) or infohash == '0' * 40 or infohash in seen:
                continue
            if not match:
                magnet = 'magnet:?xt=urn:btih:' + infohash + '&' + urlencode({'dn': row['title']})
            details = row.get('details') or row.get('link') or self.url
            if not isinstance(details, str):
                continue
            try:
                parsed = urlsplit(details)
                if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
                    continue
                size = int(row['bytes']) if row.get('bytes') is not None else -1
                seeds = int(row['seeders']) if row.get('seeders') is not None else -1
                leech = int(row['peers']) if row.get('peers') is not None else -1
            except (ValueError, TypeError, OverflowError):
                continue
            date = row.get('date') or row.get('lastSeen')
            published = -1
            if isinstance(date, str):
                try:
                    stamp = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    published = int(stamp.timestamp())
                except (ValueError, OverflowError, OSError):
                    pass
            seen.add(infohash)
            prettyPrinter({'link': magnet, 'name': row['title'], 'size': size,
                           'seeds': seeds, 'leech': leech, 'pub_date': published,
                           'engine_url': self.url, 'desc_link': details})
