# VERSION: 2.27
# AUTHORS: Douman (custparasite@gmx.se)
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Dict, List, Tuple, Union

from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter


class torlock:
    url = "https://www.torlock.com"
    name = "TorLock"
    supported_categories = {'all': 'all',
                            'anime': 'anime',
                            'software': 'software',
                            'games': 'game',
                            'movies': 'movie',
                            'music': 'music',
                            'tv': 'television',
                            'books': 'ebooks',
                            'documentary': 'documentary'}

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    class MyHtmlParser(HTMLParser):
        """ Sub-class for parsing results """
        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)
            self.url = url
            self.article_found = False  # true when <article> with results is found
            self.item_found = False
            self.item_bad = False  # set to True for malicious links
            self.current_item: Dict[str, Any] = {}  # dict for found item
            self.item_name: Union[str, None] = None  # key's name in current_item dict
            self.page_items = 0
            self.parser_class = {"td": "pub_date",
                                 "ts": "size",
                                 "tul": "seeds",
                                 "tdl": "leech"}

        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Union[str, None]]]) -> None:
            params = dict(attrs)

            if self.item_found:
                if tag == "td":
                    param_class = params["class"]
                    if param_class is not None:
                        self.item_name = self.parser_class.get(param_class)
                        if self.item_name:
                            self.current_item[self.item_name] = ""

            elif self.article_found and tag == "a":
                link = params.get("href")
                if link is not None:
                    if link.startswith("/torrent"):
                        self.current_item["desc_link"] = "".join((self.url, link))
                        self.current_item["link"] = "".join((self.url, "/tor/",
                                                             link.split('/')[2], ".torrent"))
                        self.current_item["engine_url"] = self.url
                        self.item_found = True
                        self.item_name = "name"
                        self.current_item["name"] = ""
                        self.item_bad = "rel" in params and params["rel"] == "nofollow"

            elif tag == "article":
                self.article_found = True
                self.current_item = {}

        def handle_data(self, data: str) -> None:
            if self.item_name:
                self.current_item[self.item_name] += data

        def handle_endtag(self, tag: str) -> None:
            if tag == "article":
                self.article_found = False
            elif self.item_name and (tag == "a" or tag == "td"):
                self.item_name = None
            elif self.item_found and tag == "tr":
                self.item_found = False
                if not self.item_bad:
                    try:
                        # Date seems like it can be Today, Yesterday, or M/D/YYYY (Timezone unknown)
                        pub_date = self.current_item["pub_date"]
                        if pub_date == "Today":
                            date = datetime.now()
                        elif pub_date == "Yesterday":
                            date = datetime.now() - timedelta(days=1)
                        elif re.match(r"\d{1,2}/\d{1,2}/\d{4}", pub_date):
                            date = datetime.strptime(pub_date, '%m/%d/%Y')
                        elif re.match(r"\d+\s+days?\s+ago", pub_date):
                            days_ago = int(re.match(r"(\d+)", pub_date).group(1))
                            date = datetime.now() - timedelta(days=days_ago)
                        else:
                            date = datetime.now()
                        date = date.replace(hour=0, minute=0, second=0, microsecond=0)
                        self.current_item["pub_date"] = int(date.timestamp())
                    except Exception:
                        self.current_item["pub_date"] = -1
                    prettyPrinter(self.current_item)  # type: ignore[arg-type] # refactor later
                    self.page_items += 1
                self.current_item = {}

    def search(self, query: str, cat: str = 'all') -> None:
        """ Performs search """
        query = query.replace("%20", "-")
        category = self.supported_categories[cat]

        for page in range(1, 5):
            parser = self.MyHtmlParser(self.url)
            page_url = f"{self.url}/{category}/torrents/{query}.html?sort=seeds&page={page}"
            html = retrieve_url(page_url)
            parser.feed(html)
            parser.close()
            if parser.page_items < 20:
                break
