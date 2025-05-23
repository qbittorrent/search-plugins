# VERSION: 2.5
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

from datetime import datetime
from html.parser import HTMLParser

from helpers import retrieve_url
from novaprinter import prettyPrinter


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
            self.parseDate = False
            self.column = 0
            self.torrentReady = False
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
                'desc_link': '',
                'pub_date': -1,
            }

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)

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

            if (self.foundStats and tag == 'div' and self.column == 5):
                self.parseDate = True

            if (self.foundResult and 'dl-magnet' in params.get('class', '') and tag == 'a'):
                self.torrent_info['link'] = params.get('href')
                self.foundResult = False
                self.torrentReady = True

        def handle_endtag(self, tag):
            if (self.torrentReady):
                prettyPrinter(self.torrent_info)
                self.torrentReady = False
                self.torrent_info = self.empty_torrent_info()
                self.totalResults += 1

        def handle_data(self, data):

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

            if (self.parseDate):
                try:
                    # I chose not to use strptime here because it depends on user's locale
                    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                              'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
                    [month, day, year] = data.replace(',', '').lower().split()
                    date = datetime(int(year), int(months.index(month) + 1), int(day))
                    self.torrent_info['pub_date'] = int(date.timestamp())
                except Exception:
                    self.torrent_info['pub_date'] = -1
                self.parseDate = False
                self.foundStats = False

    def request(self, searchTerm, category, page=1):
        return retrieve_url(
            self.url + '/search?q=' + searchTerm + '&category=' + category
            + '&sort=seeders&sort=desc&page=' + str(page))

    def search(self, what, cat='all'):
        category = self.supported_categories[cat]

        for page in range(1, 5):
            parser = self.TorrentInfoParser(self.url)
            parser.feed(self.request(what, category, page))
            parser.close()
            if parser.totalResults < 15:
                break
