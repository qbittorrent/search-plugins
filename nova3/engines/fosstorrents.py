# VERSION: 0.1
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Native FOSS Torrents software/distribution metadata search, account-free."""
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlencode, unquote, urljoin, urlsplit, parse_qsl
from urllib.request import Request, urlopen

from helpers import download_file
from novaprinter import prettyPrinter


class fosstorrents:
    url = 'https://fosstorrents.com'
    name = 'FOSS Torrents (native software)'
    supported_categories = {'all': 'all', 'software': 'software'}

    @staticmethod
    def text(value):
        return ' '.join(unescape(re.sub('<[^>]+>', '', value)).split())

    def native_url(self, path):
        target = urljoin(self.url, unescape(path))
        parts = urlsplit(target)
        if parts.scheme != 'https' or parts.hostname != urlsplit(self.url).hostname:
            raise ValueError('off-site route')
        return parts._replace(query=urlencode(parse_qsl(parts.query))).geturl()

    def fetch(self, path):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        target = self.native_url(path)
        with urlopen(Request(target, headers={'User-Agent': 'Mozilla/5.0'}), timeout=min(12, remaining)) as response:
            final = self.native_url(response.geturl())
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('response too large')
            return data.decode(response.headers.get_content_charset() or 'utf-8'), final

    def releases(self, document):
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', document, re.S)
        project = self.text(h1[1]) if h1 else ''
        match = re.match(r'^.*?Download (.+?) Torrents$', project)
        if match:
            project = match[1]
        for block in re.split(r'<div class="columns is-vcentered"[^>]*>', document)[1:]:
            heading = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.S)
            stats = re.findall(r'<div class="column is-half-mobile"[^>]*>(.*?)</div>', block, re.S)
            route = re.search(r'href="(/thankyou/[^"<>]+)"', block)
            if not heading or len(stats) < 3 or not route:
                continue
            date, architecture, size = [self.text(value) for value in stats[:3]]
            published = -1
            try:
                published = int(datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())
            except ValueError:
                pass
            yield {'name': project + ' ' + self.text(heading[1]) + ' ' + architecture,
                   'size': size, 'pub_date': published, 'landing': self.native_url(route[1])}

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        self.deadline = time.monotonic() + 75
        seen = set()
        try:
            document, final = self.fetch('/search/?' + urlencode({'query': query}))
            projects = []
            if re.match(r'/(?:distributions|software|games)/[^/]+/?$', urlsplit(final).path):
                projects.append((document, final))
            else:
                urls = list(dict.fromkeys(re.findall(r'href="(/(?:distributions|software|games)/[^"<>]+)"', document)))
                for url in urls:
                    page, final = self.fetch(url)
                    projects.append((page, final))
            for page, project_url in projects:
                for item in self.releases(page):
                    landing, _ = self.fetch(item['landing'])
                    links = re.findall(r'href="([^"]+)"', landing)
                    target = next((self.native_url(link) for link in links if urlsplit(unescape(link)).path == '/files/download.php' and any(value.endswith('.torrent') for key, value in parse_qsl(urlsplit(unescape(link)).query) if key == 'file')), None)
                    if not target or target in seen:
                        continue
                    seen.add(target)
                    prettyPrinter({'link': target, 'name': item['name'], 'size': item['size'],
                                   'seeds': '-1', 'leech': '-1', 'pub_date': item['pub_date'],
                                   'engine_url': self.url, 'desc_link': project_url})
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)

    def download_torrent(self, info):
        target = self.native_url(info)
        parts = urlsplit(target)
        if parts.path != '/files/download.php' or not any(value.endswith('.torrent') for key, value in parse_qsl(parts.query) if key == 'file'):
            raise ValueError('invalid native metadata route')
        print(download_file(target, referer=self.url + '/'))
