# VERSION: 1.04
# AUTHORS: hoanns, kalpakprod
# Native small-games.info metadata repair, default verified TLS; no invented torrent route.
import os
import sys
import time
import tempfile
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlencode, parse_qsl, unquote
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'a' and values.get('href'):
            self.links.append(values)
        if values.get('data-url'):
            self.links.append({'href': values['data-url'], 'title': ''})


def metadata_info(data):
    position = 0
    def parse():
        nonlocal position
        token = data[position:position + 1]
        if token == b'i':
            end = data.index(b'e', position)
            value = int(data[position + 1:end]); position = end + 1
            return value
        if token in (b'l', b'd'):
            position += 1
            result = [] if token == b'l' else {}
            while data[position:position + 1] != b'e':
                if token == b'l':
                    result.append(parse())
                else:
                    key = parse()
                    if not isinstance(key, bytes):
                        raise ValueError('invalid metadata key')
                    result[key] = parse()
            position += 1
            return result
        colon = data.index(b':', position)
        length = int(data[position:colon]); position = colon + 1
        if length < 0 or position + length > len(data):
            raise ValueError('invalid metadata length')
        value = data[position:position + length]; position += length
        return value
    root = parse()
    if position != len(data) or not isinstance(root, dict) or not isinstance(root.get(b'info'), dict):
        raise ValueError('not torrent metadata')
    info = root[b'info']
    if not isinstance(info.get(b'name'), bytes) or not isinstance(info.get(b'pieces'), bytes) or len(info[b'pieces']) % 20:
        raise ValueError('invalid torrent info')
    if isinstance(info.get(b'length'), int):
        size = info[b'length']
    elif isinstance(info.get(b'files'), list):
        size = sum(file[b'length'] for file in info[b'files'])
    else:
        raise ValueError('missing torrent size')
    return info[b'name'].decode('utf-8', errors='replace'), size


class smallgames:
    url = 'https://small-games.info'
    name = 'Small-Games (native metadata)'
    supported_categories = {'all': True, 'games': True}

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
        with urlopen(Request(target, headers={'User-Agent': 'Mozilla/5.0', 'Referer': self.url + '/'}), timeout=min(12, remaining)) as response:
            self.native_url(response.geturl())
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('response too large')
            return data

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        self.deadline = time.monotonic() + 75
        seen_topics = set()
        seen_files = set()
        try:
            document = self.fetch('/?' + urlencode({'go': 'search', 'search_text': query})).decode('utf-8', errors='replace')
            parser = Links(); parser.feed(document)
            for attrs in parser.links:
                target = self.native_url(attrs['href']) if attrs['href'].startswith('/') else ''
                params = dict(parse_qsl(urlsplit(target).query))
                title = attrs.get('title', '')
                if params.get('go') != 'game' or not title or not all(word.casefold() in title.casefold() for word in query.split()) or params.get('i') in seen_topics:
                    continue
                seen_topics.add(params.get('i'))
                game = self.fetch(target).decode('utf-8', errors='replace')
                downloads = Links(); downloads.feed(game)
                for link in downloads.links:
                    path = link['href']
                    parts = urlsplit(unescape(path))
                    controls = dict(parse_qsl(parts.query))
                    if parts.path != '/getTorrents.php' or controls.get('direct') != '1' or not (controls.get('fid', '').isdigit() or controls.get('gid', '').isdigit()):
                        continue
                    file_url = self.native_url(path)
                    if file_url in seen_files:
                        continue
                    seen_files.add(file_url)
                    data = self.fetch(file_url)
                    try:
                        name, size = metadata_info(data)
                    except (ValueError, KeyError, TypeError, IndexError, RecursionError):
                        continue  # Native getTorrents may return a text "No link found" for non-torrent entries.
                    prettyPrinter({'link': file_url, 'name': name, 'size': size,
                                   'seeds': '-1', 'leech': '-1', 'pub_date': -1,
                                   'engine_url': self.url, 'desc_link': target})
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)

    def download_torrent(self, info):
        parts = urlsplit(info)
        params = dict(parse_qsl(parts.query))
        if parts.path != '/getTorrents.php' or params.get('direct') != '1' or not (params.get('fid', '').isdigit() or params.get('gid', '').isdigit()):
            raise ValueError('invalid native metadata control')
        self.deadline = time.monotonic() + 30
        data = self.fetch(info)
        metadata_info(data)
        fd, path = tempfile.mkstemp(suffix='.torrent')
        with os.fdopen(fd, 'wb') as file:
            file.write(data)
        print(path + ' ' + self.native_url(info))
