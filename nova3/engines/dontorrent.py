# VERSION: 2.1
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Native public DonTorrent search and its normal download-button protocol."""
import hashlib
import json
import re
import sys
import time
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.parse import quote, unquote, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

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


class dontorrent:
    url = 'https://dontorrent.moi'
    name = 'DonTorrent'
    supported_categories = {'all': 'all'}

    def __init__(self):
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def fetch(self, path, data=None, json_body=False, timeout=15):
        target = urljoin(self.url, path)
        parts = urlsplit(target)
        if parts.scheme != 'https' or parts.hostname != urlsplit(self.url).hostname:
            raise ValueError('off-site route')
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': self.url + '/'}
        if json_body:
            headers['Content-Type'] = 'application/json'
        with self.opener.open(Request(target, data=data, headers=headers), timeout=timeout) as response:
            if urlsplit(response.geturl()).hostname != parts.hostname:
                raise ValueError('unexpected redirect')
            result = response.read(4 * 1024 * 1024 + 1)
            if len(result) > 4 * 1024 * 1024:
                raise ValueError('response too large')
            return result.decode(response.headers.get_content_charset() or 'utf-8')

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat != 'all':
            return
        deadline = time.monotonic() + 75
        seen = set()
        page = 1
        pages = 1
        try:
            while page <= pages:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('search deadline reached')
                document = self.fetch('/buscar', urlencode({'valor': query, 'Buscar': 'Buscar', 'p': page}).encode(), timeout=min(15, remaining))
                controls = [int(value) for value in re.findall(r'buscarPagina\(([0-9]+)\)', document)]
                if controls:
                    pages = max(pages, max(controls))
                parser = Links()
                parser.feed(document)
                for attrs, title in parser.links:
                    path = attrs.get('href', '')
                    if not re.fullmatch(r'/(?:pelicula|serie|documental|juego|musica)/[0-9]+/[^?#]+', path) or not title or path in seen:
                        continue
                    if not all(word.casefold() in title.casefold() for word in query.split()):
                        continue
                    seen.add(path)
                    topic = urljoin(self.url, path)
                    prettyPrinter({'link': topic, 'name': title, 'size': '-1', 'seeds': '-1',
                                   'leech': '-1', 'pub_date': '-1', 'engine_url': self.url, 'desc_link': topic})
                page += 1
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)

    def download_torrent(self, info):
        parts = urlsplit(info)
        if parts.scheme != 'https' or parts.hostname != urlsplit(self.url).hostname or not re.fullmatch(r'/(?:pelicula|serie|documental|juego|musica)/[0-9]+/[^?#]+', parts.path):
            raise ValueError('invalid topic route')
        parser = Links()
        parser.feed(self.fetch(info))
        buttons = [attrs for attrs, _ in parser.links if 'protected-download' in attrs.get('class', '').split()]
        if not buttons:
            raise ValueError('no native download button')
        for attrs in buttons:
            content_id = attrs.get('data-content-id', '')
            tabla = attrs.get('data-tabla', '')
            if not content_id.isdigit() or not re.fullmatch(r'[a-z_]+', tabla):
                raise ValueError('invalid download button')
            def post(body):
                result = json.loads(self.fetch('/api_validate_pow.php', json.dumps(body).encode(), True))
                if not isinstance(result, dict) or result.get('success') is not True:
                    raise ValueError('native download requires verification or is unavailable')
                return result
            challenge = post({'action': 'generate', 'content_id': int(content_id), 'tabla': tabla}).get('challenge')
            if not isinstance(challenge, str) or not challenge or len(challenge) > 1024:
                raise ValueError('invalid challenge')
            deadline = time.monotonic() + 5
            for nonce in range(1000000):
                if time.monotonic() >= deadline:
                    raise TimeoutError('native work budget exhausted')
                if hashlib.sha256((challenge + str(nonce)).encode()).hexdigest().startswith('000'):
                    break
            else:
                raise TimeoutError('native work budget exhausted')
            result = post({'action': 'validate', 'challenge': challenge, 'nonce': nonce})
            download = result.get('download_url')
            if not isinstance(download, str):
                raise ValueError('no download URL')
            download = quote(urljoin(self.url + '/', download), safe=':/?&=+%')
            parts = urlsplit(download)
            if parts.scheme != 'https' or parts.hostname != urlsplit(self.url).hostname:
                raise ValueError('unexpected download host')
            print(download_file(download))
            return
