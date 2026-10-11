# VERSION: 1.01
# AUTHORS: ZH (zh1140074772@gmail.com), kalpakprod
#
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

import base64
import html
import re
import sys
import time
from urllib.parse import unquote, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class dmhy:
    url = 'https://share.dmhy.org'
    name = 'DMHY (standalone native)'
    supported_categories = {'all': '0'}

    @staticmethod
    def text(value):
        return ' '.join(html.unescape(re.sub('<[^>]+>', '', value)).split())

    @classmethod
    def analyze_torrent(cls, tr_list):
        results = []
        for row in tr_list:
            cells = re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.S)
            if len(cells) < 7:
                continue
            topic = re.search(r'<a\b[^>]*href=["\x27](/topics/view/[^"\x27]+)["\x27][^>]*>(.*?)</a>', cells[2], re.S)
            magnet = re.search(r'href=["\x27](magnet:\?xt=urn:btih:([A-Fa-f0-9]{40}|[A-Za-z2-7]{32})(?:&[^"\x27<>\s]*)?)["\x27]', html.unescape(cells[3]))
            if not topic or not magnet or magnet[2].upper() in ('0' * 40, 'A' * 32):
                continue
            title = cls.text(topic[2])
            if not title:
                continue
            seeds = cls.text(cells[5]).replace(',', '')
            leech = cls.text(cells[6]).replace(',', '')
            results.append({'link': magnet[1], 'name': title, 'size': cls.text(cells[4]) or '-1',
                            'seeds': seeds if seeds.isdigit() else '-1', 'leech': leech if leech.isdigit() else '-1',
                            'pub_date': -1, 'engine_url': cls.url, 'desc_link': urljoin(cls.url, html.unescape(topic[1]))})
        return results

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        deadline = time.monotonic() + 75
        page = 1
        seen = set()
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('search deadline reached')
                url = self.url + '/topics/list/page/' + str(page) + '?' + urlencode({'keyword': query})
                with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=min(12, remaining)) as response:
                    if urlsplit(response.geturl()).hostname != urlsplit(self.url).hostname:
                        raise ValueError('unexpected redirect')
                    data = response.read(4 * 1024 * 1024 + 1)
                    if len(data) > 4 * 1024 * 1024:
                        raise ValueError('response too large')
                    document = data.decode(response.headers.get_content_charset() or 'utf-8')
                table = re.search(r'<table\b[^>]*id=["\x27]topic_list["\x27][^>]*>.*?</table>', document, re.S)
                if not table:
                    raise ValueError('no native table')
                rows = re.findall(r'<tr\b[^>]*>.*?</tr>', re.sub(r'<!--.*?-->', '', table[0], flags=re.S), re.S)
                count = 0
                for result in self.analyze_torrent(rows):
                    match = re.match(r'magnet:\?xt=urn:btih:([A-Fa-f0-9]{40}|[A-Za-z2-7]{32})(?:&|$)', result['link'])
                    infohash = base64.b32decode(match[1].upper()).hex() if len(match[1]) == 32 else match[1].lower()
                    if infohash in seen:
                        continue
                    seen.add(infohash)
                    count += 1
                    prettyPrinter(result)
                if count == 0 or '/topics/list/page/' + str(page + 1) + '?' not in html.unescape(document):
                    break
                page += 1
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
