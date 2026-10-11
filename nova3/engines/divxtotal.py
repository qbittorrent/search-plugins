# VERSION: 2.0
# AUTHORS: BurningMop (burning.mop@yandex.com), kalpakprod

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

import re
import sys
import time
from html import unescape
from html.parser import HTMLParser
from urllib.parse import unquote, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from helpers import download_file
from novaprinter import prettyPrinter


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.current = [dict(attrs), []]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            attrs, text = self.current
            self.links.append((attrs, ' '.join(''.join(text).split())))
            self.current = None


class divxtotal:
    url = 'https://divxtotal.foo'
    name = 'DivxTotal'
    supported_categories = {'all': 'all'}

    def fetch(self, path):
        target = urljoin(self.url, path)
        parts = urlsplit(target)
        if parts.scheme != 'https' or parts.hostname != urlsplit(self.url).hostname:
            raise ValueError('off-site route')
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        with urlopen(Request(target, headers={'User-Agent': 'Mozilla/5.0', 'Referer': self.url + '/'}), timeout=min(12, remaining)) as response:
            if urlsplit(response.geturl()).hostname != parts.hostname:
                raise ValueError('unexpected redirect')
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('response too large')
            return data.decode(response.headers.get_content_charset() or 'utf-8')

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat != 'all':
            return
        self.deadline = time.monotonic() + 75
        seen = set()
        try:
            # shortcut: first native search page, extend pagination when needed.
            document = self.fetch('/?' + urlencode({'s': query}))
            for row in re.findall(r'<tr\b[^>]*>.*?</tr>', document, re.S):
                cells = re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.S)
                if len(cells) < 4:
                    continue
                topics = Links()
                topics.feed(cells[0])
                for attrs, title in topics.links:
                    topic = urljoin(self.url, attrs.get('href', ''))
                    if not title or not all(word.casefold() in title.casefold() for word in query.split()) or topic in seen or not re.match(r'/(?:peliculas(?:-hd)?|series|programas|musica)/[^/]+/', urlsplit(topic).path):
                        continue
                    detail = self.fetch(topic)
                    downloads = Links()
                    downloads.feed(detail)
                    for link_attrs, _ in downloads.links:
                        link = urljoin(self.url, link_attrs.get('href', ''))
                        parts = urlsplit(link)
                        if parts.scheme != 'https' or parts.hostname != urlsplit(self.url).hostname:
                            continue
                        if parts.path != '/download_tt.php' and not parts.path.endswith('.torrent'):
                            continue
                        size = unescape(re.sub('<[^>]+>', '', cells[3])).strip().replace(',', '.')
                        prettyPrinter({'link': link, 'name': title, 'size': size if re.fullmatch(r'[0-9.]+\s*[KMGT]?B', size, re.I) else '-1',
                                       'seeds': '-1', 'leech': '-1', 'pub_date': '-1',
                                       'engine_url': self.url, 'desc_link': topic})
                        seen.add(topic)
                        break
                    if len(seen) >= 20:
                        return
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)

    def download_torrent(self, info):
        parts = urlsplit(info)
        if parts.scheme != 'https' or parts.hostname != urlsplit(self.url).hostname or (parts.path != '/download_tt.php' and not parts.path.endswith('.torrent')):
            raise ValueError('invalid download route')
        print(download_file(info))
