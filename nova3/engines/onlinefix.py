# VERSION: 1.1
# AUTHORS: caiocinel, Bioux1, kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Online-Fix community torrent index snapshot, last updated May 2025.
Original public Hydra feed first, explicitly dated backup if unavailable; not native site login.
No account or local server. Availability and coverage depend on the index owner.
"""
import json
import re
import sys
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class onlinefix:
    url = 'https://online-fix.me/'
    name = 'Online-Fix (public index; May 2025 backup)'
    supported_categories = {'all': 'all', 'games': 'all'}
    live_api_url = 'https://hydralinks.cloud/sources/onlinefix.json'
    backup_api_url = 'https://raw.githubusercontent.com/voip1337/hydralinks-backup/e608f22d5516cc71b1de16aba2d1a7a21a26f402/onlinefix.json'

    def search(self, what, cat='all'):
        if cat not in self.supported_categories:
            return
        words = unquote(what).casefold().split()
        if not words:
            return
        rows = None
        backup = False
        last_error = None
        for source in (self.live_api_url, self.backup_api_url):
            try:
                with urlopen(Request(source, headers={'User-Agent': 'qBittorrent/onlinefix'}), timeout=12) as response:
                    payload = response.read(16 * 1024 * 1024 + 1)
                    if len(payload) > 16 * 1024 * 1024:
                        raise ValueError('index response too large')
                    payload = json.loads(payload)
                candidates = payload.get('downloads') if isinstance(payload, dict) else None
                if not isinstance(payload, dict) or payload.get('name') != 'onlinefix' or not isinstance(candidates, list):
                    raise ValueError('invalid community index')
                rows = candidates
                backup = source == self.backup_api_url
                break
            except (URLError, OSError, ValueError) as error:
                last_error = error
        if rows is None:
            print(self.name + ': ' + type(last_error).__name__, file=sys.stderr)
            return
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            title, uris = row.get('title'), row.get('uris')
            if not isinstance(title, str) or not all(word in title.casefold() for word in words) or not isinstance(uris, list):
                continue
            for uri in uris:
                if not isinstance(uri, str) or not uri.startswith('magnet:?'):
                    continue
                hashes = [xt[9:].lower() for xt in parse_qs(urlsplit(uri).query).get('xt', []) if xt.lower().startswith('urn:btih:')]
                if not hashes or not re.fullmatch(r'[0-9a-f]{40}|[a-z2-7]{32}', hashes[0]) or hashes[0] in ('0' * 40, 'a' * 32) or hashes[0] in seen:
                    continue
                published = -1
                date = row.get('uploadDate')
                if isinstance(date, str):
                    try:
                        stamp = datetime.fromisoformat(date.replace('Z', '+00:00'))
                        if stamp.tzinfo is None:
                            stamp = stamp.replace(tzinfo=timezone.utc)
                        published = int(stamp.timestamp())
                    except (ValueError, OverflowError, OSError):
                        pass
                seen.add(hashes[0])
                prettyPrinter({'link': uri, 'name': title + (' [index May 2025]' if backup else ''), 'size': row.get('fileSize', '-1'),
                               'seeds': '-1', 'leech': '-1', 'engine_url': self.url,
                               'desc_link': self.url, 'pub_date': published})
                break
