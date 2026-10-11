# VERSION: 2.0
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""LinuxTracker's current /torrents/ catalogue; standard library only.
Site listing and detail magnets were checked against live HTML on 2026-10-09.
"""
import html
import re
import sys
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import unquote, urlencode, urljoin
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class linuxtracker:
    url = 'https://linuxtracker.org/'
    name = 'Linux Tracker'
    supported_categories = {'all': 'all', 'software': 'all'}

    def search(self, what, cat='all'):
        if cat not in self.supported_categories:
            return
        query = unquote(what).strip()
        if not query:
            return
        try:
            request = Request(self.url + 'torrents/?' + urlencode({'q': query}),
                              headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'identity'})
            with urlopen(request, timeout=20) as response:
                document = response.read(4 * 1024 * 1024 + 1)
                if len(document) > 4 * 1024 * 1024:
                    raise ValueError('catalogue response too large')
                document = document.decode(response.headers.get_content_charset() or 'utf-8')
            if re.search(r'cf-chl-|just a moment|captcha', document, re.I):
                raise ValueError('browser verification required')
            seen = set()
            for row in re.findall(r'<tr\b[^>]*>.*?</tr>', document, re.S):
                topic = re.search(r'<a\b[^>]*class="torrent-name"[^>]*href="(/torrents/([0-9a-f]{40})/)"[^>]*>(.*?)</a>', row, re.S)
                if not topic or topic[2] in seen:
                    continue
                name = html.unescape(re.sub('<[^>]+>', '', topic[3])).strip()
                if not name or topic[2] == '0' * 40:
                    continue
                size = re.search(r'<td\b[^>]*class="numeric muted-cell"[^>]*>([^<]+)</td>', row)
                seeds = re.search(r'<td\b[^>]*class="[^"]*\bseeds\b[^"]*"[^>]*>\s*<strong>([\d,]+)</strong>', row)
                leech = re.search(r'<td\b[^>]*class="[^"]*\bleeches\b[^"]*"[^>]*>\s*<strong>([\d,]+)</strong>', row)
                published = -1
                date = re.search(r'<td class="muted-cell">([^<]+)</td>', row)
                if date:
                    try:
                        published = int(datetime.strptime(date[1].strip(), '%b %d, %Y').replace(tzinfo=timezone.utc).timestamp())
                    except ValueError:
                        pass
                seen.add(topic[2])
                prettyPrinter({'link': 'magnet:?xt=urn:btih:' + topic[2] + '&' + urlencode({'dn': name}),
                               'name': name, 'size': size[1].strip() if size else '-1',
                               'seeds': seeds[1].replace(',', '') if seeds else '-1',
                               'leech': leech[1].replace(',', '') if leech else '-1',
                               'pub_date': published, 'engine_url': self.url,
                               'desc_link': urljoin(self.url, topic[1])})
        except (URLError, OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
