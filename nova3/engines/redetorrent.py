# VERSION: 1.01
# AUTHORS: bebetoh, kalpakprod
# https://redetorrent.com
# pt_BR
# Conteúdo com Audio em Português (Dublado / Dual Áudio / Legendado)

import re
import sys
import time
from html.parser import HTMLParser
from typing import Dict
from urllib.parse import quote_plus, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class redetorrent:
    url = 'https://redestorrents.com'
    name = 'ApacheTorrent'
    supported_categories = {
        'all': 'all',
        'anime': 'desenhos',
        'movies': 'filmes',
        'tv': 'series',
    }

    class SearchResultsParser(HTMLParser):
        def __init__(self, base_url: str) -> None:
            super().__init__()
            self.base_url = base_url
            self.results = []
            self.link = ''
            self.card = None

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)
            if tag == 'a' and 'cover-link' in params.get('class', '').split():
                self.link = urljoin(self.base_url, params.get('href', ''))
            if tag == 'article' and 'custom-card' in params.get('class', '').split():
                self.card = {'title': params.get('data-title', '').strip(),
                             'kind': params.get('data-tipo', '').casefold().replace('é', 'e'),
                             'desc_link': self.link}

        def handle_endtag(self, tag):
            if tag == 'article' and self.card is not None:
                if self.card['title'] and urlsplit(self.card['desc_link']).hostname == urlsplit(self.base_url).hostname:
                    self.results.append(self.card)
                self.card = None
            if tag == 'a':
                self.link = ''

    class MagnetLinksParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.magnets = []
            self.depth = 0
            self.capture_depth = None
            self.context = ''

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)
            classes = params.get('class', '').split()
            if tag == 'div':
                if 'download-list' in classes:
                    self.depth = 1
                elif self.depth:
                    self.depth += 1
                if self.depth and 'download-row' in classes:
                    self.context = ''
                if self.depth and 'download-name' in classes:
                    self.capture_depth = self.depth
            if tag == 'a' and self.depth:
                href = params.get('href', '')
                if re.match(r'^magnet:\?xt=urn:btih:(?:[a-fA-F0-9]{40}|[A-Za-z2-7]{32})(?:&|$)', href) and not re.match(r'^magnet:\?xt=urn:btih:(?:0{40}|A{32})(?:&|$)', href, re.I):
                    self.magnets.append({'magnet': href, 'title': ' '.join(self.context.split())})

        def handle_data(self, data):
            if self.capture_depth is not None:
                self.context += data

        def handle_endtag(self, tag):
            if tag == 'div' and self.depth:
                if self.capture_depth == self.depth:
                    self.capture_depth = None
                self.depth -= 1

    def fetch(self, url: str) -> str:
        remaining = self.deadline - time.monotonic()
        parts = urlsplit(url)
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        if parts.scheme != 'https' or parts.hostname != urlsplit(self.url).hostname:
            raise ValueError('off-site route')
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=min(12, remaining)) as response:
            if urlsplit(response.geturl()).hostname != parts.hostname:
                raise ValueError('unexpected redirect')
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('response too large')
            return data.decode(response.headers.get_content_charset() or 'utf-8')

    def search(self, what: str, cat: str = 'all') -> None:
        self.deadline = time.monotonic() + 60
        self.seen = set()
        self.category = cat if cat in self.supported_categories else 'all'
        search_url = self._build_search_url(what, cat)

        try:
            search_html = self.fetch(search_url)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print('Rede Torrent search request failed: ' + type(exc).__name__, file=sys.stderr)
            return

        search_parser = self.SearchResultsParser(self.url)
        search_parser.feed(search_html)
        search_parser.close()

        query_words = unquote(what).strip().casefold().split()
        for result in search_parser.results:
            category_matches = self.category == 'all' or result['kind'] == self.supported_categories[self.category]
            if category_matches and all(word in result['title'].casefold() for word in query_words):
                self._print_result_magnets(result)

    def _build_search_url(self, what: str, cat: str) -> str:
        query = unquote(what).strip()

        if cat not in self.supported_categories:
            cat = 'all'

        return self.url + '/index.php?busca=' + quote_plus(query)

    def _print_result_magnets(self, result: Dict[str, str]) -> None:
        desc_link = result.get('desc_link', '')
        base_title = result.get('title', '').strip()

        if not desc_link:
            return

        try:
            details_html = self.fetch(desc_link)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print('Rede Torrent details request failed: ' + type(exc).__name__, file=sys.stderr)
            return

        magnet_parser = self.MagnetLinksParser()
        magnet_parser.feed(details_html)
        magnet_parser.close()

        for magnet_item in magnet_parser.magnets:
            magnet = magnet_item.get('magnet', '')
            magnet_title = magnet_item.get('title', '')

            if not magnet or magnet in self.seen:
                continue
            self.seen.add(magnet)

            name = self._build_result_name(base_title, magnet_title, magnet)

            torrent_info = {
                'link': magnet,
                'name': name,
                'size': '-1',
                'seeds': -1,
                'leech': -1,
                'engine_url': self.url,
                'desc_link': desc_link,
                'pub_date': -1,
            }

            prettyPrinter(torrent_info)  # type: ignore[arg-type]

    def _build_result_name(self, base_title: str, magnet_title: str, magnet: str) -> str:
        if magnet_title:
            return base_title + ' - ' + magnet_title

        magnet_name = self._extract_magnet_dn(magnet)

        if magnet_name:
            return base_title + ' - ' + magnet_name

        return base_title

    def _extract_magnet_dn(self, magnet: str) -> str:
        match = re.search(r'[?&]dn=([^&]+)', magnet)

        if not match:
            return ''

        name = unquote(match.group(1))
        name = name.replace('.', ' ')
        name = re.sub(r'\s+', ' ', name)

        return name.strip()
