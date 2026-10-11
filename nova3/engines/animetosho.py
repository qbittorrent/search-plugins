# VERSION: 1.01
# AUTHORS: ALAA_BRAHIM
# LICENSING INFORMATION

#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

# CONTRIBUTORS: kalpakprod (current feed, bounded transport and validation)
import json
import re
import sys
from urllib.error import URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class animetosho:
    url = 'https://animetosho.org'
    name = 'Anime Tosho'
    supported_categories = {'all': 'all', 'anime': 'anime'}

    def search(self, what, cat='all'):
        if cat not in self.supported_categories:
            return
        query = unquote(what).strip()
        if not query:
            return
        try:
            request = Request('https://feed.animetosho.xyz/json?' + urlencode({'q': query}),
                              headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'identity'})
            with urlopen(request, timeout=20) as response:
                data = response.read(4 * 1024 * 1024 + 1)
                if len(data) > 4 * 1024 * 1024:
                    raise ValueError('feed response too large')
                rows = json.loads(data)
            if not isinstance(rows, list):
                raise ValueError('invalid feed response')
        except (URLError, OSError, ValueError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
            return
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            magnet, title = row.get('magnet_uri'), row.get('title')
            match = re.match(r'^magnet:\?xt=urn:btih:([0-9a-fA-F]{40}|[A-Za-z2-7]{32})(?:&|$)', magnet) if isinstance(magnet, str) else None
            if not match or match[1] == '0' * 40 or match[1].lower() in seen or not isinstance(title, str) or not title.strip():
                continue
            try:
                size = int(row['total_size']) if row.get('total_size') is not None else -1
                seeds = int(row['seeders']) if row.get('seeders') is not None else -1
                leech = int(row['leechers']) if row.get('leechers') is not None else -1
                published = int(row['timestamp']) if row.get('timestamp') is not None else -1
            except (ValueError, TypeError, OverflowError):
                continue
            seen.add(match[1].lower())
            prettyPrinter({'link': magnet, 'name': title, 'size': size, 'seeds': seeds,
                           'leech': leech, 'pub_date': published, 'engine_url': self.url,
                           'desc_link': row.get('link') or self.url})
