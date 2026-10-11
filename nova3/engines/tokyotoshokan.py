# VERSION: 2.4
#Author: Douman (douman@gmx.se)
#        Bruno Barbieri (brunorex@gmail.com), kalpakprod

try:
    #python3
    from html.parser import HTMLParser
except ImportError:
    #python2
    from HTMLParser import HTMLParser

from re import compile as re_compile
import re
import sys
import time
from html import unescape
from urllib.parse import unquote, urlencode, urljoin, urlsplit, parse_qs
from urllib.request import Request, urlopen

#qBt
from novaprinter import prettyPrinter
from helpers import download_file

class tokyotoshokan(object):
    url = 'https://www.tokyotosho.se'
    mirrors = ('https://www.tokyotosho.se', 'https://tokyo-tosho.net')


    def __init__(self):
        self.name = 'Tokyo Toshokan'
        self.supported_categories = {'all': '0', 'anime': '1', 'games': '14' }
        #self.supported_categories = {'all': '0', 'anime': '1', 'anime(non-english)': '10',
        #                        'manga': '3', 'drama': '8', 'music': '2',
        #                        'music video': '9', 'raw': '7', 'hentai': '4',
        #                        'eroge': '14', 'batch': '11', 'jav': '15', 'other': '5'}
        #

    def download_torrent(self, info):
        print(download_file(info))

    class MyHtmlParseWithBlackJack(HTMLParser):
        def __init__(self, url):
            HTMLParser.__init__(self)
            self.get_size_regex = re_compile(r".*Size:\s+([^ ]*)\s+.*")
            self.url = url
            self.current_item = None
            self.size_found = False
            self.name_found = False
            self.hidden_name = False
            self.stats_found = False
            self.stat_name = None

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)
            if self.current_item:
                if tag == "a":
                    if params.get("href", "").startswith("magnet"):
                        self.current_item["link"] = params["href"]
                    elif 'type' in params and params["type"] == "application/x-bittorrent":
                        self.name_found = True
                        self.current_item["name"] = ""
                    elif params.get("href", "").startswith("details"):
                        self.current_item["desc_link"] = "".join((self.url, "/", params["href"]))

                elif tag == "td" and "class" in params:
                    if params["class"] == "desc-bot":
                        self.size_found = True
                        self.current_item['size'] = 'Unknown'
                    elif params["class"] == "stats":
                        self.stats_found = True

                elif self.name_found and tag == "span" and params.get("class") == "s":
                    self.hidden_name = True

                elif self.stats_found and tag == "span":
                    self.stat_name = "leech" if "seeds" in self.current_item else "seeds"

            elif tag == "tr" and "class" in params:
                if any(value.startswith("category_") for value in params["class"].split()):
                    self.current_item = dict()
                    self.current_item["engine_url"] = self.url

        def handle_endtag(self, tag):
            if tag == "a":
                if self.name_found:
                    self.name_found = False
            elif tag == "span":
                self.hidden_name = False
                self.stat_name = None
            elif self.current_item and tag == "tr" and len(self.current_item) == 7:
                magnet = self.current_item.get("link", "")
                if re.match(r'^magnet:\?xt=urn:btih:(?:[A-Fa-f0-9]{40}|[A-Za-z2-7]{32})(?:&|$)', magnet) and not re.match(r'^magnet:\?xt=urn:btih:(?:0{40}|A{32})(?:&|$)', magnet):
                    prettyPrinter(self.current_item)
                self.current_item = None
                self.size_found = False
                self.name_found = False
                self.stats_found = False
                self.stat_name = None

        def handle_data(self, data):
            if self.name_found:
                if not self.hidden_name:
                    self.current_item["name"] += data
            elif self.size_found:
                # There can be several pieces.
                result = self.get_size_regex.search(data)
                if result:
                    self.current_item['size'] = result.group(1)
                    self.size_found = False
            elif self.stat_name:
                self.current_item[self.stat_name] = data

    def fetch(self, path):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        with urlopen(Request(urljoin(self.url + '/', path), headers={'User-Agent': 'Mozilla/5.0'}), timeout=min(12, remaining)) as response:
            if response.geturl().split('/')[2] != self.url.split('/')[2]:
                raise ValueError('unexpected redirect')
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('response too large')
            return data.decode(response.headers.get_content_charset() or 'utf-8')

    def search(self, query, cat='all'):
        if cat not in self.supported_categories or not unquote(query).strip():
            return
        self.deadline = time.monotonic() + 75
        path = '/search.php?' + urlencode({'terms': unquote(query).strip(), 'type': self.supported_categories[cat]})
        error = None
        document = None
        for mirror in self.mirrors:
            self.url = mirror
            try:
                document = self.fetch(path)
                if '<table class="listing">' not in document:
                    raise ValueError('no native listing')
                break
            except (OSError, ValueError, LookupError) as failure:
                error = failure
                document = None
        if document is None:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
            return
        parser = self.MyHtmlParseWithBlackJack(self.url)
        seen = set()
        try:
            # Keep the original five-page search window, without global state.
            for page in range(1, 6):
                table = re.search(r'<table class="listing">(.*?)</table>', document, re.S)
                if not table:
                    raise ValueError('no native listing')
                parser.feed(table[0])
                links = re.findall(r'href=["\x27]([^"\x27<>]+)["\x27]', unescape(document))
                next_path = next((link for link in links if link not in seen and 'lastid' in parse_qs(urlsplit(link).query) and parse_qs(urlsplit(link).query).get('page') == [str(page + 1)]), None)
                if next_path is None:
                    break
                seen.add(next_path)
                document = self.fetch('/search.php' + next_path if next_path.startswith('?') else next_path)
            parser.close()
        except (OSError, ValueError, LookupError) as failure:
            print(self.name + ': ' + type(failure).__name__, file=sys.stderr)
