# VERSION: 1.8
# AUTHORS: mauricci

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Dict, List, Mapping, Tuple, Union
from urllib.parse import unquote

from helpers import retrieve_url
from novaprinter import prettyPrinter


class torrentproject:
    url = 'https://torrentproject.cc'
    name = 'TorrentProject'
    supported_categories = {'all': '0'}

    class MyHTMLParser(HTMLParser):

        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)
            self.url = url
            self.insideResults = False
            self.insideDataDiv = False
            self.pageComplete = False
            self.spanCount = -1
            self.infoMap = {
                "name": 0,
                "torrLink": 0,
                "seeds": 2,
                "leech": 3,
                "pub_date": 4,
                "size": 5,
            }
            self.fullResData: List[object] = []
            self.pageRes: List[object] = []
            self.singleResData = self.get_single_data()

        def get_single_data(self) -> Dict[str, Any]:
            return {
                'name': '-1',
                'seeds': '-1',
                'leech': '-1',
                'size': '-1',
                'link': '-1',
                'desc_link': '-1',
                'engine_url': self.url,
                'pub_date': '-1',
            }

        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Union[str, None]]]) -> None:
            def getStr(d: Mapping[str, Union[str, None]], key: str) -> str:
                value = d.get(key, '')
                return value if value is not None else ''

            attributes = dict(attrs)
            if tag == 'div' and 'nav' in getStr(attributes, 'id'):
                self.pageComplete = True
            if tag == 'div' and attributes.get('id', '') == 'similarfiles':
                self.insideResults = True
            if tag == 'div' and self.insideResults and 'gac_bb' not in getStr(attributes, 'class'):
                self.insideDataDiv = True
            elif tag == 'span' and self.insideDataDiv and 'verified' != attributes.get('title', ''):
                self.spanCount += 1
            if self.insideDataDiv and tag == 'a' and len(attrs) > 0:
                if self.infoMap['torrLink'] == self.spanCount and 'href' in attributes:
                    self.singleResData['link'] = self.url + getStr(attributes, 'href')
                if self.infoMap['name'] == self.spanCount and 'href' in attributes:
                    self.singleResData['desc_link'] = self.url + getStr(attributes, 'href')

        def handle_endtag(self, tag: str) -> None:
            if not self.pageComplete:
                if tag == 'div':
                    self.insideDataDiv = False
                    self.spanCount = -1
                    if len(self.singleResData) > 0:
                        # ignore trash stuff
                        if self.singleResData['name'] != '-1' \
                                and self.singleResData['size'] != '-1' \
                                and self.singleResData['name'].lower() != 'nome':
                            # ignore those with link and desc_link equals to -1
                            if self.singleResData['desc_link'] != '-1' \
                                    or self.singleResData['link'] != '-1':
                                try:
                                    date_string = self.singleResData['pub_date']
                                    date = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
                                    self.singleResData['pub_date'] = int(date.timestamp())
                                except Exception:
                                    pass
                                try:
                                    prettyPrinter(self.singleResData)  # type: ignore[arg-type] # refactor later
                                except Exception:
                                    print(self.singleResData)
                                self.pageRes.append(self.singleResData)
                                self.fullResData.append(self.singleResData)
                        self.singleResData = self.get_single_data()

        def handle_data(self, data: str) -> None:
            if self.insideDataDiv:
                for key, val in self.infoMap.items():
                    if self.spanCount == val:
                        curr_key = key
                        if curr_key in self.singleResData and data.strip() != '':
                            if self.singleResData[curr_key] == '-1':
                                self.singleResData[curr_key] = data.strip()
                            elif curr_key != 'name':
                                self.singleResData[curr_key] += data.strip()

    def search(self, what: str, cat: str = 'all') -> None:
        # curr_cat = self.supported_categories[cat]
        what = what.replace('%20', '+')
        # analyze first 5 pages of results
        for currPage in range(0, 5):
            url = f"{self.url}/browse?t={what}&p={currPage}"
            html = retrieve_url(url)
            parser = self.MyHTMLParser(self.url)
            parser.feed(html)
            parser.close()
            if len(parser.pageRes) < 20:
                break

    def download_torrent(self, info: str) -> None:
        """ Downloader """
        html = retrieve_url(info)
        m = re.search('href=[\'\"].*?(magnet.+?)[\'\"]', html)
        if m and len(m.groups()) > 0:
            magnet = unquote(m.group(1))
            print(magnet + ' ' + info)
