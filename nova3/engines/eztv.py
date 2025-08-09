# VERSION: 1.20
# AUTHORS: nindogo
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

import http.client
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Mapping, Match, Tuple, Union

from helpers import retrieve_url
from novaprinter import prettyPrinter


class eztv:
    name = "EZTV"
    # Updated domain (as of 2025, eztv.re is more reliable)
    url = 'https://eztv.re/'
    # Add more categories if available in the future
    supported_categories = {'all': 'all', 'tv': 'tv'}

    class MyHtmlParser(HTMLParser):
        A, TD, TR, TABLE = ('a', 'td', 'tr', 'table')

        """ Sub-class for parsing results """
        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)
            self.url = url

            now = datetime.now()
            self.date_parsers: Mapping[str, Callable[[Match[str]], datetime]] = {
                r"(\d+)h\s+(\d+)m": lambda m: now - timedelta(hours=int(m[1]), minutes=int(m[2])),
                r"(\d+)d\s+(\d+)h": lambda m: now - timedelta(days=int(m[1]), hours=int(m[2])),
                r"(\d+)\s+weeks?": lambda m: now - timedelta(weeks=int(m[1])),
                r"(\d+)\s+mo": lambda m: now - timedelta(days=int(m[1]) * 30),
                r"(\d+)\s+years?": lambda m: now - timedelta(days=int(m[1]) * 365),
                r"(\d+)m": lambda m: now - timedelta(minutes=int(m[1])),
                r"(\d+)d": lambda m: now - timedelta(days=int(m[1])),
            }
            self.in_table_row = False
            self.current_item: Dict[str, Any] = {}

        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Union[str, None]]]) -> None:
            def getStr(d: Mapping[str, Any], key: str) -> str:
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
            if (self.in_table_row
                    and (data.endswith(' KB') or data.endswith(' MB') or data.endswith(' GB'))):
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
                response: http.client.HTTPResponse = urllib.request.urlopen(req)  # nosec B310
                return response.read().decode('utf-8')
            except urllib.error.URLError as errno:
                print(f"Connection error: {errno.reason}", file=sys.stderr)
            return ""

    def search(self, what: str, cat: str = 'all') -> None:
        eztv_html = self.do_query(what)

        eztv_parser = self.MyHtmlParser(self.url)
        eztv_parser.feed(eztv_html)
        eztv_parser.close()
