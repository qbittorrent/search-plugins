# VERSION: 1.04
# AUTHORS: Phuong Tran, kalpakprod
# Native Sukebei Nyaa standalone parser repair; metadata only, no external parser package.
import base64
import math
import re
import sys
import time
from html import unescape
from urllib.parse import unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class nyaa:
    url = 'https://sukebei.nyaa.si'
    name = 'Sukebei Nyaa (standalone repair)'
    supported_categories = {'all': '0_0', 'anime': '1_1', 'books': '1_4', 'games': '1_3',
                            'pictures': '1_5', 'movies': '2_2', 'tv': '2_2'}

    def rows(self, document, query):
        document = re.sub(r'<!--.*?-->', '', document, flags=re.S)
        seen = set()
        for row in re.findall(r'<tr\b[^>]*>.*?</tr>', document, re.S):
            cells = re.findall(r'<td\b[^>]*>.*?</td>', row, re.S)
            if len(cells) < 8:
                continue
            topic = re.search(r'<a\b[^>]*href=["\x27](/view/[0-9]+)["\x27][^>]*>(.*?)</a>', row, re.S)
            magnet = re.search(r'(magnet:\?xt=urn:btih:([0-9A-Fa-f]{40}|[A-Za-z2-7]{32})(?:&[^"\x27<>\s]*)?)', unescape(row))
            if not topic or not magnet or magnet[2].upper() in ('0' * 40, 'A' * 32) or magnet[2].upper() in seen:
                continue
            title = unescape(re.sub('<[^>]+>', '', topic[2])).strip()
            if not title or not all(word.casefold() in title.casefold() for word in query.split()):
                continue
            size = unescape(re.sub('<[^>]+>', '', cells[-5])).strip()
            date = re.search(r'data-timestamp=["\x27]([0-9]+)["\x27]', cells[-4])
            seeds = re.sub('<[^>]+>', '', cells[-3]).strip().replace(',', '')
            leech = re.sub('<[^>]+>', '', cells[-2]).strip().replace(',', '')
            seen.add(magnet[2].upper())
            yield {'link': magnet[1], 'name': title, 'size': size or '-1',
                   'seeds': seeds if seeds.isdigit() else '-1', 'leech': leech if leech.isdigit() else '-1',
                   'pub_date': int(date[1]) if date else -1, 'engine_url': self.url,
                   'desc_link': self.url + topic[1]}

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        deadline = time.monotonic() + 75
        page = 1
        pages = 1
        seen = set()
        try:
            while page <= pages:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('search deadline reached')
                target = self.url + '/?' + urlencode({'f': '0', 'c': self.supported_categories[cat], 'q': query, 'p': page})
                with urlopen(Request(target, headers={'User-Agent': 'Mozilla/5.0'}), timeout=min(12, remaining)) as response:
                    if urlparse(response.geturl()).hostname != urlparse(self.url).hostname:
                        raise ValueError('unexpected redirect')
                    data = response.read(4 * 1024 * 1024 + 1)
                    if len(data) > 4 * 1024 * 1024:
                        raise ValueError('response too large')
                    document = data.decode(response.headers.get_content_charset() or 'utf-8')
                if 'torrent-list' not in document:
                    raise ValueError('no native table')
                if page == 1:
                    info = re.search(r'Displaying results [0-9]+-([0-9,]+) out of ([0-9,]+) results', document)
                    if info:
                        per_page = int(info[1].replace(',', ''))
                        pages = math.ceil(int(info[2].replace(',', '')) / per_page) if per_page else 1
                for result in self.rows(document, query):
                    value = re.match(r'magnet:\?xt=urn:btih:([A-Fa-f0-9]{40}|[A-Za-z2-7]{32})', result['link'])[1]
                    key = base64.b32decode(value.upper()).hex() if len(value) == 32 else value.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    prettyPrinter(result)
                page += 1
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
