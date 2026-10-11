# VERSION: 1.4
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""TheRarBg native catalogue, not the original RARBG service.
Current site routes and HTML were inspected directly; standard library only.
"""
import html
import re
import sys
import time
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class therarbg:
    url = 'https://therarbg.com'
    name = 'The RarBg'
    supported_categories = {'all': '', 'movies': 'Movies', 'tv': 'TV', 'games': 'Games',
                            'music': 'Music', 'anime': 'Anime', 'software': 'Apps', 'books': 'Other'}

    def fetch(self, path):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        target = urljoin(self.url, path)
        parts = urlsplit(target)
        if parts.scheme != 'https' or parts.netloc != urlsplit(self.url).netloc:
            raise ValueError('off-site route')
        target = parts._replace(path=quote(parts.path, safe='/%:')).geturl()
        with urlopen(Request(target, headers={'User-Agent': 'Mozilla/5.0'}), timeout=min(15, remaining)) as response:
            if urlsplit(response.geturl()).netloc != parts.netloc:
                raise ValueError('unexpected redirect')
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('response too large')
            document = data.decode(response.headers.get_content_charset() or 'utf-8')
        if re.search(r'cf-chl-|just a moment|captcha', document, re.I):
            raise ValueError('browser verification required')
        return document

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        self.deadline = time.monotonic() + 30
        route = '/get-posts/keywords:' + quote(query, safe='')
        if cat != 'all':
            route += ':category:' + self.supported_categories[cat]
        route += ':order:-se/'
        terms = re.findall(r'\w+', query.casefold())
        seen = set()
        try:
            document = self.fetch(route)
            for row in re.findall(r'<tr\b[^>]*>.*?</tr>', document, re.S):
                topic = re.search(r'<a\b[^>]*href=["\x27](/post-detail/[^"\x27]+)["\x27][^>]*>(.*?)</a>', row, re.S)
                if not topic or topic[1] in seen:
                    continue
                title = html.unescape(re.sub('<[^>]+>', '', topic[2])).strip()
                words = set(re.findall(r'\w+', title.casefold()))
                if not all(term in words for term in terms):
                    continue
                seen.add(topic[1])
                detail = self.fetch(topic[1])
                magnet = re.search(r'href=["\x27](magnet:\?xt=urn:btih:([0-9a-fA-F]{40}|[A-Za-z2-7]{32})(?:&[^"\x27]*)?)["\x27]', detail)
                if not magnet or magnet[2] == '0' * 40:
                    raise ValueError('topic has no valid magnet')
                seeds = re.search(r'<td[^>]*style="color: green"[^>]*>([\d,]+)</td>', row)
                leech = re.search(r'<td[^>]*style="color: red"[^>]*>([\d,]+)</td>', row)
                size = re.search(r'<td[^>]*style="text-align: left;"[^>]*data-order="(\d+)"', row)
                date = re.search(r'<td class="hideCell" data-order="(\d+)"', row)
                prettyPrinter({'link': html.unescape(magnet[1]), 'name': title,
                               'size': int(size[1]) if size else -1,
                               'seeds': int(seeds[1].replace(',', '')) if seeds else -1,
                               'leech': int(leech[1].replace(',', '')) if leech else -1,
                               'pub_date': int(date[1]) if date else -1,
                               'engine_url': self.url, 'desc_link': urljoin(self.url, topic[1])})
                if len(seen) >= 20:
                    break
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
