# VERSION: 1.4
# AUTHORS: BurningMop (burning.mop@yandex.com)

# LICENSING INFORMATION
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# CONTRIBUTORS: kalpakprod (current native category, visible controls and magnet dispatch)

import re
import sys
import time
from html import unescape
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urljoin, urlparse, parse_qs
from urllib.request import Request, urlopen
from novaprinter import prettyPrinter


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []; self.active = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.active = [dict(attrs), '']

    def handle_data(self, data):
        if self.active is not None:
            self.active[1] += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            self.links.append(self.active); self.active = None


class xxxclubto:
    url = 'https://xxxclub.to'
    name = 'XXXClub'
    supported_categories = {'all': 'all', 'pictures': '5'}

    @staticmethod
    def text(value):
        return ' '.join(unescape(re.sub('<[^>]+>', '', value)).split())

    @staticmethod
    def visible(attrs):
        return not re.search(r'display\s*:\s*none|(?:left|top)\s*:\s*-\d', attrs.get('style', ''), re.I)

    @staticmethod
    def infohash(link):
        if urlparse(link).scheme != 'magnet':
            raise ValueError('not a magnet')
        for value in parse_qs(urlparse(link).query).get('xt', []):
            match = re.fullmatch(r'urn:btih:([0-9a-fA-F]{40})', value)
            if match and match[1] != '0' * 40:
                return match[1].lower()
        raise ValueError('invalid native magnet')

    def native_url(self, path):
        target = urljoin(self.url, unescape(path))
        if urlparse(target).scheme != 'https' or urlparse(target).hostname != urlparse(self.url).hostname:
            raise ValueError('off-site native route')
        return target

    def fetch(self, path):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        target = self.native_url(path)
        with urlopen(Request(target, headers={'User-Agent': 'Mozilla/5.0', 'Referer': self.url + '/'}), timeout=min(12, remaining)) as response:
            self.native_url(response.geturl())
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('response too large')
            return data.decode(response.headers.get_content_charset() or 'utf-8')

    def listing(self, document):
        body = re.search(r'<div\b[^>]*class=["\x27]browsetableinside["\x27][^>]*>(.*?)</div>', document, re.S)
        if not body:
            raise ValueError('unrecognized native search table')
        rows = []
        for row in re.findall(r'<li\b[^>]*>.*?</li>', body[1], re.S):
            links = Links(); links.feed(re.sub(r'<!--.*?-->', '', row, flags=re.S))
            topics = [(attrs, title) for attrs, title in links.links
                      if self.visible(attrs) and re.fullmatch(r'/torrents/details/~?\d+', attrs.get('href', ''))]
            if not topics:
                continue
            attrs, title = topics[0]
            fields = {}
            for classes, value in re.findall(r'<span\b[^>]*class=["\x27]([^"\x27]+)["\x27][^>]*>(.*?)</span>', row, re.S):
                for key in ('siz', 'see', 'lee'):
                    if key in classes.split():
                        fields[key] = self.text(value)
            size = fields.get('siz', '-1')
            if not re.fullmatch(r'[0-9.,]+\s*(?:KB|MB|GB|TB|KiB|MiB|GiB|TiB)', size, re.I):
                size = '-1'
            rows.append({'name': self.text(title), 'desc_link': self.native_url(attrs['href']),
                         'size': size, 'seeds': int(fields['see'].replace(',', '')) if fields.get('see', '').replace(',', '').isdigit() else -1,
                         'leech': int(fields['lee'].replace(',', '')) if fields.get('lee', '').replace(',', '').isdigit() else -1,
                         'engine_url': self.url, 'pub_date': -1})
        return rows

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        target = self.url + '/torrents/search/' + self.supported_categories[cat] + '/' + quote(query, safe='')
        pages = set(); topics = set(); hashes = set(); self.deadline = time.monotonic() + 180
        try:
            while target and target not in pages:
                if len(pages) >= 100:
                    raise ValueError('original 100-page limit reached')
                pages.add(target); document = self.fetch(target)
                for row in self.listing(document):
                    if not row['name'] or row['desc_link'] in topics:
                        continue
                    topics.add(row['desc_link'])
                    detail = Links(); detail.feed(self.fetch(row['desc_link']))
                    for attrs, _ in detail.links:
                        link = attrs.get('href', '')
                        if not self.visible(attrs):
                            continue
                        try:
                            key = self.infohash(link)
                        except ValueError:
                            continue
                        if key not in hashes:
                            hashes.add(key); prettyPrinter(dict(row, link=link))
                pagination = re.search(r'<div\b[^>]*class=["\x27]browsepagination["\x27][^>]*>(.*?)</div>', document, re.S)
                links = Links()
                if pagination:
                    links.feed(re.sub(r'<!--.*?-->', '', pagination[1], flags=re.S))
                targets = [attrs['href'] for attrs, _ in links.links
                           if self.visible(attrs) and attrs.get('title') == 'Next Page' and attrs.get('href')]
                target = self.native_url(targets[0]) if targets else ''
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)

    def download_torrent(self, link):
        target = link if link.startswith('magnet:?') else unquote(link)
        self.infohash(target)
        print(target + ' ' + target)
