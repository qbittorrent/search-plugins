#VERSION: 1.2
#AUTHORS: mauricci

from helpers import retrieve_url
from novaprinter import prettyPrinter
import re

from html.parser import HTMLParser
from urllib.parse import unquote


class torrentproject(object):
    url = 'https://torrentproject2.se'
    name = 'TorrentProject'
    supported_categories = {'all': '0'}

    class MyHTMLParser(HTMLParser):

        def __init__(self, url):
            HTMLParser.__init__(self)
            self.url = url
            self.insideResults = False
            self.insideDataDiv = False
            self.pageComplete = False
            self.spanCount = -1
            self.infoMap = {'name': 0, 'torrLink': 0, 'size': 5, 'seeds': 2, 'leech': 3}
            self.fullResData = []
            self.pageRes = []
            self.singleResData = self.get_single_data()

        def get_single_data(self):
            return {
                'name': '-1',
                'seeds': '-1',
                'leech': '-1',
                'size': '-1',
                'link': '-1',
                'desc_link': '-1',
                'engine_url': self.url
            }

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == 'div' and 'nav' in attributes.get('id', ''):
                self.pageComplete = True
            if tag == 'div' and attributes.get('id', '') == 'similarfiles':
                self.insideResults = True
            if tag == 'div' and self.insideResults and 'gac_bb' not in attributes.get('class', ''):
                self.insideDataDiv = True
            elif tag == 'span' and self.insideDataDiv and 'verified' != attributes.get('title', ''):
                self.spanCount += 1
            if self.insideDataDiv and tag == 'a' and len(attrs) > 0:
                if self.infoMap['torrLink'] == self.spanCount and 'href' in attributes:
                    self.singleResData['link'] = self.url + attributes['href']
                if self.infoMap['name'] == self.spanCount and 'href' in attributes:
                    self.singleResData['desc_link'] = self.url + attributes['href']

        def handle_endtag(self, tag):
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
                                    prettyPrinter(self.singleResData)
                                except Exception:
                                    print(self.singleResData)
                                self.pageRes.append(self.singleResData)
                                self.fullResData.append(self.singleResData)
                        self.singleResData = self.get_single_data()

        def handle_data(self, data):
            if self.insideDataDiv:
                for key, val in self.infoMap.items():
                    if self.spanCount == val:
                        curr_key = key
                        if curr_key in self.singleResData and data.strip() != '':
                            if self.singleResData[curr_key] == '-1':
                                self.singleResData[curr_key] = data.strip()
                            elif curr_key != 'name':
                                self.singleResData[curr_key] += data.strip()

        def feed(self, html):
            HTMLParser.feed(self, html)
            self.pageComplete = False
            self.insideResults = False
            self.insideDataDiv = False
            self.spanCount = -1

    def search(self, what, cat='all'):
        # curr_cat = self.supported_categories[cat]
        parser = self.MyHTMLParser(self.url)
        what = what.replace('%20', '+')
        # analyze first 5 pages of results
        for currPage in range(0, 5):
            url = self.url + '?t={0}&p={1}'.format(what, currPage)
            html = retrieve_url(url)
            parser.feed(html)
            if len(parser.pageRes) <= 0:
                break
            del parser.pageRes[:]
        parser.close()

    def download_torrent(self, info):
        """ Downloader """
        html = retrieve_url(info)
        m = re.search('href=[\'\"].*?(magnet.+?)[\'\"]', html)
        if m and len(m.groups()) > 0:
            magnet = unquote(m.group(1))
            print(magnet + ' ' + info)
