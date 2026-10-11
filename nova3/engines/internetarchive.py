# VERSION: 0.1
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Internet Archive public BitTorrent search, standalone and account-free.
Uses the documented advancedsearch contract and explicit btih metadata.
HTTPS is attempted first; canonical HTTP fallback exposes public query terms.
No private item, login, locally deployed server or torrent payload is requested.
"""
import json
import re
import sys
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class internetarchive:
    url = 'https://archive.org'
    name = 'Internet Archive (public torrent API)'
    supported_categories = {'all': '', 'books': 'texts', 'music': 'audio',
                            'movies': 'movies', 'tv': 'movies', 'software': 'software'}

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        literal = query.replace('\\', '\\\\').replace('"', '\\"')
        expression = 'title:("' + literal + '") AND format:("Archive BitTorrent")'
        if cat != 'all':
            expression += ' AND mediatype:(' + self.supported_categories[cat] + ')'
        params = {'q': expression, 'fl[]': 'identifier,title,mediatype,item_size,btih,publicdate',
                  'rows': 50, 'output': 'json'}
        suffix = '/advancedsearch.php?' + urlencode(params)
        rows = None
        for base in ('https://archive.org', 'http://archive.org'):
            try:
                with urlopen(Request(base + suffix, headers={'User-Agent': 'qBittorrent/internetarchive'}), timeout=8) as response:
                    data = response.read(4 * 1024 * 1024 + 1)
                    if len(data) > 4 * 1024 * 1024:
                        raise ValueError('response too large')
                    payload = json.loads(data)
                result = payload.get('response') if isinstance(payload, dict) else None
                if not isinstance(result, dict) or not isinstance(result.get('docs'), list):
                    raise ValueError('invalid archive response')
                rows = result['docs']
                break
            except (URLError, OSError, ValueError):
                continue
        if rows is None:
            print(self.name + ': public search unavailable', file=sys.stderr)
            return
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            infohash, title, identifier = row.get('btih'), row.get('title'), row.get('identifier')
            if not isinstance(infohash, str) or not re.fullmatch(r'[0-9a-fA-F]{40}', infohash) or infohash == '0' * 40 or infohash.lower() in seen:
                continue
            if not isinstance(title, str) or not title.strip() or not isinstance(identifier, str) or not identifier:
                continue
            try:
                size = int(row.get('item_size', -1))
            except (ValueError, TypeError, OverflowError):
                continue
            published = -1
            date = row.get('publicdate')
            if isinstance(date, str):
                try:
                    stamp = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    published = int(stamp.timestamp())
                except (ValueError, OverflowError, OSError):
                    pass
            seen.add(infohash.lower())
            prettyPrinter({'link': 'magnet:?xt=urn:btih:' + infohash.lower() + '&' + urlencode({'dn': title}),
                           'name': title, 'size': size, 'seeds': '-1', 'leech': '-1',
                           'pub_date': published, 'engine_url': self.url,
                           'desc_link': self.url + '/details/' + quote(identifier, safe='')})
