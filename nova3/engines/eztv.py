# VERSION: 1.25
# AUTHORS: nindogo
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

import http.client
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Mapping, Match, Tuple, Union
from urllib.parse import unquote, urlencode

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class eztv:
    name = "EZTV"
    url = 'https://eztvx.to/'
    supported_categories = {'all': 'all', 'tv': 'tv'}

    class MyHtmlParser(HTMLParser):
        A, TD, TR, TABLE = ('a', 'td', 'tr', 'table')

        """ Sub-class for parsing results """
        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)
            self.url = url

            now = datetime.now().astimezone()
            self.date_parsers: Mapping[str, Callable[[Match[str]], datetime]] = {
                r"(\d+)h\s+(\d+)m": lambda m: now - timedelta(hours=int(m[1]), minutes=int(m[2])),
                r"(\d+)d\s+(\d+)h": lambda m: now - timedelta(days=int(m[1]), hours=int(m[2])),
                r"(\d+)\s+weeks?": lambda m: now - timedelta(weeks=int(m[1])),
                r"(\d+)\s+mo": lambda m: now - timedelta(days=int(m[1]) * 30),
                r"(\d+)\s+years?": lambda m: now - timedelta(days=int(m[1]) * 365),
            }
            self.in_table_row = False
            self.current_item: Dict[str, object] = {}

        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Union[str, None]]]) -> None:
            def getStr(d: Mapping[str, Union[str, None]], key: str) -> str:
                value = d.get(key, '')
                return value if value is not None else ''

            params = dict(attrs)

            if (params.get('class') == 'forum_header_border'
                    and params.get('name') == 'hover'):
                self.in_table_row = True
                self.current_item = {}
                self.current_item['seeds'] = -1
                self.current_item['leech'] = -1
                self.current_item['size'] = -1
                self.current_item['engine_url'] = self.url
                self.current_item['pub_date'] = -1

            if (tag == self.A
                    and self.in_table_row and params.get('class') == 'magnet'):
                self.current_item['link'] = params.get('href')

            if (tag == self.A
                    and self.in_table_row and params.get('class') == 'epinfo'):
                self.current_item['desc_link'] = self.url + getStr(params, 'href')
                self.current_item['name'] = getStr(params, 'title').split(' (')[0]

        def handle_data(self, data: str) -> None:
            data = data.replace(',', '')
            if self.in_table_row and data.endswith((' KB', ' MB', ' GB')):
                self.current_item['size'] = data

            elif self.in_table_row and data.isnumeric():
                self.current_item['seeds'] = int(data)

            elif self.in_table_row:  # Check for a relative time
                for pattern, calc in self.date_parsers.items():
                    m = re.match(pattern, data)
                    if m:
                        self.current_item["pub_date"] = int(calc(m).timestamp())
                        break

        def handle_endtag(self, tag: str) -> None:
            if self.in_table_row and tag == self.TR:
                prettyPrinter(self.current_item)  # type: ignore[arg-type] # refactor later
                self.in_table_row = False

    def do_query(self, what: str) -> str:
        url = f"{self.url}/search/{what.replace('%20', '-')}"
        data = b"layout=def_wlinks"
        try:
            return retrieve_url(url, request_data=data)
        except TypeError:
            # Older versions of retrieve_url did not support request_data/POST, se we must do the
            # request ourselves...
            user_agent = 'Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0'
            req = urllib.request.Request(url, data, {'User-Agent': user_agent})
            try:
                response: http.client.HTTPResponse = urllib.request.urlopen(req)  # nosec B310 # pylint: disable=consider-using-with
                return response.read().decode('utf-8')
            except urllib.error.URLError as errno:
                print(f"Connection error: {errno.reason}", file=sys.stderr)
            return ""

    def api_json(self, url: str) -> Any:
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)

    def search_api(self, what: str) -> None:
        query = unquote(what).strip()
        episode = re.search(r'\bs(\d{1,2})(?:e(\d{1,2}))?\b', query, re.IGNORECASE)
        quality = re.search(r'\b(?:480|720|1080|2160)p\b', query, re.IGNORECASE)
        title = re.sub(r'\bs\d{1,2}(?:e\d{1,2})?\b|\b(?:480|720|1080|2160)p\b', '', query, flags=re.IGNORECASE).strip()
        if re.fullmatch(r'tt\d+', title):
            imdb = title[2:]
        else:
            matches = self.api_json('https://api.tvmaze.com/search/shows?' + urlencode({'q': title}))
            if not matches:
                return
            # TVmaze relevance resolves the title; EZTV requires an IMDb ID.
            imdb = matches[0]['show'].get('externals', {}).get('imdb')
            if not imdb:
                return
            imdb = imdb.removeprefix('tt')
        results: List[SearchResults] = []
        for page in range(1, 21):
            payload = self.api_json(self.url.rstrip('/') + '/api/get-torrents?' + urlencode({
                'imdb_id': imdb, 'limit': 100, 'page': page,
            }))
            torrents = payload.get('torrents', [])
            for item in torrents:
                if str(item.get('imdb_id')) != imdb:
                    continue
                if episode and int(item.get('season', -1)) != int(episode[1]):
                    continue
                if episode and episode[2] and int(item.get('episode', -1)) != int(episode[2]):
                    continue
                if quality and quality[0].casefold() not in item.get('title', '').casefold():
                    continue
                magnet = item.get('magnet_url', '')
                if not re.search(r'^magnet:\?xt=urn:btih:(?:[a-f0-9]{40}|[a-z2-7]{32})(?:&|$)', magnet, re.IGNORECASE):
                    continue
                results.append({
                    'link': magnet, 'name': item['title'],
                    'size': item.get('size_bytes', -1), 'seeds': item.get('seeds', -1),
                    'leech': item.get('peers', -1), 'engine_url': self.url,
                    'desc_link': self.url.rstrip('/') + '/ep/' + str(item['id']) + '/',
                    'pub_date': item.get('date_released_unix', -1),
                })
            if not torrents or page * 100 >= int(payload.get('torrents_count', 0)):
                break
        for result in sorted(results, key=lambda item: int(item['seeds']), reverse=True):
            prettyPrinter(result)

    def search(self, what: str, cat: str = 'all') -> None:
        eztv_html = self.do_query(what)
        if not eztv_html:
            try:
                self.search_api(what)
            except (urllib.error.URLError, ValueError, KeyError, TypeError) as error:
                print(f'EZTV: API fallback failed ({type(error).__name__})', file=sys.stderr)
            return
        eztv_parser = self.MyHtmlParser(self.url)
        eztv_parser.feed(eztv_html)
        eztv_parser.close()
