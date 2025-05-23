# VERSION: 4.11
# AUTHORS: Lima66
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import quote

from helpers import retrieve_url
from novaprinter import prettyPrinter


class limetorrents(object):
    url = "https://www.limetorrents.lol"
    name = "LimeTorrents"
    supported_categories = {'all': 'all',
                            'anime': 'anime',
                            'software': 'applications',
                            'games': 'games',
                            'movies': 'movies',
                            'music': 'music',
                            'tv': 'tv'}

    class MyHtmlParser(HTMLParser):
        """ Sub-class for parsing results """

        def error(self, message):
            pass

        A, TD, TR, HREF = ('a', 'td', 'tr', 'href')

        def __init__(self, url):
            HTMLParser.__init__(self)
            self.url = url
            self.current_item = {}  # dict for found item
            self.page_items = 0
            self.inside_table = False
            self.inside_tr = False
            self.column_index = -1
            self.column_name = None  # key's name in current_item dict
            self.columns = ["name", "pub_date", "size", "seeds", "leech"]

            now = datetime.now()
            self.date_parsers = {
                r"yesterday": lambda m: now - timedelta(days=1),
                r"last\s+month": lambda m: now - timedelta(days=30),
                r"(\d+)\s+years?": lambda m: now - timedelta(days=int(m[1]) * 365),
                r"(\d+)\s+months?": lambda m: now - timedelta(days=int(m[1]) * 30),
                r"(\d+)\s+days?": lambda m: now - timedelta(days=int(m[1])),
                r"(\d+)\s+hours?": lambda m: now - timedelta(hours=int(m[1])),
                r"(\d+)\s+minutes?": lambda m: now - timedelta(minutes=int(m[1])),
            }

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)

            if params.get('class') == 'table2':
                self.inside_table = True
            elif not self.inside_table:
                return

            if tag == self.TR and (params.get('bgcolor') == '#F4F4F4' or params.get('bgcolor') == '#FFFFFF'):  # noqa
                self.inside_tr = True
                self.column_index = -1
                self.current_item = {"engine_url": self.url}
            elif not self.inside_tr:
                return

            if tag == self.TD:
                self.column_index += 1
                if self.column_index < len(self.columns):
                    self.column_name = self.columns[self.column_index]
                else:
                    self.column_name = None

            if self.column_name == "name" and tag == self.A and self.HREF in params:
                link = params["href"]
                if link.endswith(".html"):
                    try:
                        safe_link = quote(self.url + link, safe='/:')
                    except KeyError:
                        safe_link = self.url + link
                    self.current_item["link"] = safe_link
                    self.current_item["desc_link"] = safe_link

        def handle_data(self, data):
            if self.column_name:
                if self.column_name in ["size", "seeds", "leech"]:
                    data = data.replace(',', '')
                elif self.column_name == "pub_date":
                    timestamp = -1
                    for pattern, calc in self.date_parsers.items():
                        m = re.match(pattern, data, re.IGNORECASE)
                        if m:
                            timestamp = int(calc(m).timestamp())
                            break
                    data = str(timestamp)
                self.current_item[self.column_name] = data.strip()
                self.column_name = None

        def handle_endtag(self, tag):
            if tag == 'table':
                self.inside_table = False

            if self.inside_tr and tag == self.TR:
                self.inside_tr = False
                self.column_name = None
                if "link" in self.current_item:
                    prettyPrinter(self.current_item)
                    self.page_items += 1

    def download_torrent(self, info):
        # since limetorrents provides torrent links in itorrent (cloudflare protected),
        # we have to fetch the info page and extract the magnet link
        info_page = retrieve_url(info)
        magnet_match = re.search(r"href\s*\=\s*\"(magnet[^\"]+)\"", info_page)
        if magnet_match and magnet_match.groups():
            print(magnet_match.groups()[0] + " " + info)
        else:
            raise Exception('Error, please fill a bug report!')

    def search(self, query, cat='all'):
        """ Performs search """
        query = query.replace("%20", "-")
        category = self.supported_categories[cat]

        for page in range(1, 5):
            page_url = f"{self.url}/search/{category}/{query}/seeds/{page}/"
            html = retrieve_url(page_url)
            parser = self.MyHtmlParser(self.url)
            parser.feed(html)
            parser.close()
            if parser.page_items < 20:
                break
