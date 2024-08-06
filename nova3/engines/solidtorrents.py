# VERSION: 2.2
# AUTHORS: nKlido

# LICENSING INFORMATION
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from helpers import retrieve_url
from novaprinter import prettyPrinter
from html.parser import HTMLParser
import math


class solidtorrents(object):
    url = 'https://solidtorrents.to'
    name = 'Solid Torrents'
    supported_categories = {'all': 'all', 'music': 'Audio', 'books': 'eBook'}

    class TorrentInfoParser(HTMLParser):

        def __init__(self, url):
            HTMLParser.__init__(self)
            self.url = url
            self.foundResult = False
            self.foundTitle = False
            self.parseTitle = False
            self.foundStats = False
            self.parseSeeders = False
            self.parseLeechers = False
            self.parseSize = False
            self.column = 0
            self.torrentReady = False
            self.foundSearchStats = False
            self.parseTotalResults = False
            self.totalResults = 0

            self.torrent_info = self.empty_torrent_info()

        def empty_torrent_info(self):
            return {
                'link': '',
                'name': '',
                'size': '-1',
                'seeds': '-1',
                'leech': '-1',
                'engine_url': self.url,
                'desc_link': ''
            }

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)

            if 'search-stats' in params.get('class', ''):
                self.foundSearchStats = True

            if (self.foundSearchStats and tag == 'b'):
                self.parseTotalResults = True
                self.foundSearchStats = False

            if 'search-result' in params.get('class', ''):
                self.foundResult = True
                return

            if (self.foundResult and 'title' in params.get('class', '') and tag == 'h5'):
                self.foundTitle = True

            if (self.foundTitle and tag == 'a'):
                self.torrent_info['desc_link'] = self.url + params.get('href')
                self.parseTitle = True

            if (self.foundResult and 'stats' in params.get('class', '')):
                self.foundStats = True
                self.column = -1

            if (self.foundStats and tag == 'div'):
                self.column = self.column + 1

                if (self.column == 2):
                    self.parseSize = True

            if (self.foundStats and tag == 'font' and self.column == 3):
                self.parseSeeders = True

            if (self.foundStats and tag == 'font' and self.column == 4):
                self.parseLeechers = True

            if (self.foundResult and 'dl-magnet' in params.get('class', '') and tag == 'a'):
                self.torrent_info['link'] = params.get('href')
                self.foundResult = False
                self.torrentReady = True

        def handle_endtag(self, tag):
            if (self.torrentReady):
                prettyPrinter(self.torrent_info)
                self.torrentReady = False
                self.torrent_info = self.empty_torrent_info()

        def handle_data(self, data):

            if (self.parseTotalResults):
                self.totalResults = int(data.strip())
                self.parseTotalResults = False

            if (self.parseTitle):
                if (bool(data.strip()) and data != '\n'):
                    self.torrent_info['name'] = data
                self.parseTitle = False
                self.foundTitle = False

            if (self.parseSize):
                self.torrent_info['size'] = data
                self.parseSize = False

            if (self.parseSeeders):
                self.torrent_info['seeds'] = data
                self.parseSeeders = False

            if (self.parseLeechers):
                self.torrent_info['leech'] = data
                self.parseLeechers = False
                self.foundStats = False

    def request(self, searchTerm, category, page=1):
        return retrieve_url(
            self.url + '/search?q=' + searchTerm + '&category=' + category
            + '&sort=seeders&sort=desc&page=' + str(page))

    def search(self, what, cat='all'):
        category = self.supported_categories[cat]

        parser = self.TorrentInfoParser(self.url)
        parser.feed(self.request(what, category, 1))

        totalPages = min(math.ceil(parser.totalResults / 20), 5)

        for page in range(2, totalPages + 1):
            parser.feed(self.request(what, category, page))

        parser.close()
