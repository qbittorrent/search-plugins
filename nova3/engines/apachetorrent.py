# VERSION: 1.01
# AUTHORS: bebetoh, kalpakprod
# https://apachetorrent.com
# pt_BR
# Conteúdo com Audio em Português (Dublado / Dual Áudio / Legendado)

import html
import json
import re
import sys
import time
from html.parser import HTMLParser
from typing import Dict, List, Mapping, Tuple, Union
from urllib.parse import quote_plus, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

from novaprinter import prettyPrinter


class apachetorrent:
    url = 'https://apachetorrents.com'
    name = 'ApacheTorrent'
    supported_categories = {
        'all': 'all',
        'anime': 'anime',
        'movies': 'filmes',
        'tv': 'series',
    }

    class SearchResultsParser(HTMLParser):
        def __init__(self, base_url: str) -> None:
            HTMLParser.__init__(self)
            self.base_url = base_url
            self.results: List[Dict[str, str]] = []

            self.inside_card = False
            self.inside_title_link = False
            self.current_link = ''
            self.current_title = ''
            self.current_title_attr = ''

        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Union[str, None]]]) -> None:
            params = self._attrs_to_dict(attrs)

            if tag == 'div' and any(value in ('capaname', 'capa-item') for value in self._get(params, 'class').split()):
                self.inside_card = True
                self.current_link = ''
                self.current_title = ''
                self.current_title_attr = ''
                return

            if not self.inside_card:
                return

            if tag == 'a':
                href = self._get(params, 'href')
                title = self._get(params, 'title')

                if href and self._is_result_link(href):
                    self.current_link = urljoin(self.base_url, href)

                    if title:
                        self.current_title_attr = self._clean_title(title)

                    self.inside_title_link = True

        def handle_data(self, data: str) -> None:
            if self.inside_card and self.inside_title_link:
                text = self._clean_text(data)

                if text:
                    if self.current_title:
                        self.current_title += ' '
                    self.current_title += text

        def handle_endtag(self, tag: str) -> None:
            if tag == 'a' and self.inside_title_link:
                self.inside_title_link = False

            if tag == 'div' and self.inside_card:
                title = self._clean_title(self.current_title or self.current_title_attr)

                if self.current_link and title:
                    self.results.append({
                        'title': title,
                        'desc_link': self.current_link,
                    })

                self.inside_card = False
                self.current_link = ''
                self.current_title = ''
                self.current_title_attr = ''

        def _attrs_to_dict(self, attrs: List[Tuple[str, Union[str, None]]]) -> Dict[str, str]:
            result = {}

            for key, value in attrs:
                result[key] = value if value is not None else ''

            return result

        def _get(self, params: Mapping[str, str], key: str) -> str:
            return params.get(key, '')

        def _is_result_link(self, href: str) -> bool:
            if not href:
                return False

            href_lower = href.lower()

            if not href_lower.startswith('http'):
                return False

            if not href_lower.startswith(self.base_url):
                return False

            if 'baixar-torrent' not in href_lower:
                return False

            return True

        def _clean_text(self, text: str) -> str:
            text = html.unescape(text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        def _clean_title(self, title: str) -> str:
            title = self._clean_text(title)
            title = re.sub(r'\s*Download\s*$', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s+', ' ', title)
            return title.strip()

    class MagnetLinksParser(HTMLParser):
        def __init__(self) -> None:
            HTMLParser.__init__(self)
            self.magnets: List[Dict[str, str]] = []

            self.inside_download_area = False
            self.current_context = ''
            self.capture_text = False

        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Union[str, None]]]) -> None:
            params = self._attrs_to_dict(attrs)

            if tag == 'div' and params.get('id') in ('lista_links', 'download'):
                self.inside_download_area = True
                return

            if not self.inside_download_area:
                return

            if tag == 'p':
                self.capture_text = True
                self.current_context = ''

            if tag == 'a':
                href = params.get('href', '')
                title = params.get('title', '')

                if re.match(r'^magnet:\?xt=urn:btih:(?:[a-fA-F0-9]{40}|[A-Za-z2-7]{32})(?:&|$)', href) and not re.match(r'^magnet:\?xt=urn:btih:(?:0{40}|A{32})(?:&|$)', href):
                    self.magnets.append({
                        'magnet': html.unescape(href),
                        'title': self._clean_title(title or self.current_context),
                    })

        def handle_data(self, data: str) -> None:
            if self.inside_download_area and self.capture_text:
                text = self._clean_text(data)

                if text:
                    if self.current_context:
                        self.current_context += ' '
                    self.current_context += text

        def handle_endtag(self, tag: str) -> None:
            if tag == 'p' and self.capture_text:
                self.capture_text = False
                self.current_context = ''

            if tag == 'div' and self.inside_download_area:
                self.inside_download_area = False

        def _attrs_to_dict(self, attrs: List[Tuple[str, Union[str, None]]]) -> Dict[str, str]:
            result = {}

            for key, value in attrs:
                result[key] = value if value is not None else ''

            return result

        def _clean_text(self, text: str) -> str:
            text = html.unescape(text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        def _clean_title(self, title: str) -> str:
            title = self._clean_text(title)
            title = re.sub(r'^BAIXAR\s+', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s+', ' ', title)
            return title.strip()

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
            print('Apache Torrent search request failed: ' + type(exc).__name__, file=sys.stderr)
            return

        search_parser = self.SearchResultsParser(self.url)
        search_parser.feed(search_html)
        search_parser.close()

        query_words = unquote(what).strip().casefold().split()
        for result in search_parser.results:
            if all(word in result['title'].casefold() for word in query_words):
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
            print('Apache Torrent details request failed: ' + type(exc).__name__, file=sys.stderr)
            return

        if self.category != 'all':
            media = []
            for raw in re.findall(r'<script[^>]*type=["\x27]application/ld\+json["\x27][^>]*>(.*?)</script>', details_html, re.S):
                try:
                    item = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(item, dict) and item.get('@type') in ('Movie', 'TVSeries'):
                    media.append(item)
            if not any((self.category == 'movies' and item['@type'] == 'Movie')
                       or (self.category == 'tv' and item['@type'] == 'TVSeries')
                       or (self.category == 'anime' and 'Anime' in item.get('genre', [])) for item in media):
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
