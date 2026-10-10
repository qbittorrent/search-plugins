# VERSION: 0.1
# Nyaa-origin releases from the reachable Tsukihime public index; not live Nyaa search.
# AUTHORS: dominc8
# CONTRIBUTORS: kalpakprod
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import json
import re
import sys
import time
from urllib.error import URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class nyaasi_public:
    url = 'https://nyaa.si'
    name = 'Nyaa.si (Tsukihime public index)'
    supported_categories = {'all': '0', 'anime': '7'}

    def fetch(self, path, timeout):
        request = Request('https://api.tsukihime.org' + path, headers={'User-Agent': 'curl/8.18.0'})
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())

    def search(self, what, cat='all'):
        if cat not in self.supported_categories:
            return
        deadline = time.monotonic() + 90
        try:
            response = self.fetch('/v1/search/torrents?' + urlencode({'q': unquote(what)}), 15)
            rows = response.get('results') if isinstance(response, dict) else None
            if not isinstance(rows, list):
                raise ValueError('invalid search response')
        except (URLError, OSError, ValueError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
            return
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            nyaa_id = row.get('nyaa_id')
            if not isinstance(nyaa_id, int) or nyaa_id <= 0:
                continue
            infohash = row.get('btih', '')
            title = row.get('name')
            torrent_id = row.get('id')
            if not isinstance(infohash, str) or not re.fullmatch(r'[0-9a-fA-F]{40}', infohash) or infohash == '0' * 40 or infohash.lower() in seen:
                continue
            if not isinstance(title, str) or not title or not isinstance(torrent_id, int):
                continue
            magnet = 'magnet:?xt=urn:btih:' + infohash + '&dn=' + quote(title, safe='')
            seeds = leech = -1
            remaining = deadline - time.monotonic()
            if remaining > 1:
                try:
                    details = self.fetch('/v1/torrents/' + str(torrent_id), min(15, remaining))
                    trackers = details.get('trackers') if isinstance(details, dict) else None
                    live = [item for item in trackers if isinstance(item, dict) and not item.get('error')
                            and isinstance(item.get('seeders'), int) and isinstance(item.get('leechers'), int)] if isinstance(trackers, list) else []
                    if live:
                        seeds = sum(item['seeders'] for item in live)
                        leech = sum(item['leechers'] for item in live)
                    for item in live:
                        address = item.get('url')
                        if isinstance(address, str) and urlsplit(address).scheme in ('udp', 'http', 'https'):
                            magnet += '&tr=' + quote(address, safe='')
                except (URLError, OSError, ValueError):
                    pass  # Valid search hash remains usable when optional tracker stats fail.
            size = row.get('totalsize', -1)
            published = row.get('source_date', -1)
            if not isinstance(size, int) or not isinstance(published, int):
                continue
            seen.add(infohash.lower())
            prettyPrinter({'link': magnet, 'name': title, 'size': size, 'engine_url': self.url,
                           'desc_link': self.url + '/view/' + str(nyaa_id), 'pub_date': published,
                           'seeds': seeds, 'leech': leech})
