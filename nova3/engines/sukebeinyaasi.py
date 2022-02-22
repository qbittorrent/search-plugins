# -*- coding: utf-8 -*-
#VERSION: 1.1
#AUTHORS: Joost Bremmer (toost.b@gmail.com)
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.


try:
    from HTMLParser import HTMLParser
except ImportError:
    from html.parser import HTMLParser

# import qBT modules
try:
    from novaprinter import prettyPrinter
    from helpers import retrieve_url
except:
    pass


class sukebeinyaasi(object):
    """Class used by qBittorrent to search for torrents"""

    url = 'https://sukebei.nyaa.si'
    name = 'Sukebei.Nyaa.si'
    # defines which search categories are supported by this search engine
    # and their corresponding id. Possible categories are:
    # 'all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures',
    # 'books'
    supported_categories = {
            'all': '0_0',
            'anime': '1_0',
            'books': '3_0',
            'music': '2_0',
            'pictures': '5_0',
            'software': '6_0',
            'tv': '4_0',
            'movies': '4_0'}

    class SukebeiNyaasiParser(HTMLParser):
        """ Parses Nyaa.si browse page for search resand prints them"""
        def __init__(self, res, url):
            try:
                super().__init__()
            except:
                #  See: http://stackoverflow.com/questions/9698614/
                HTMLParser.__init__(self)

            self.engine_url = url
            self.results = res
            self.curr = None
            self.td_counter = -1

        def handle_starttag(self, tag, attr):
            """Tell the parser what to do with which tags"""
            if tag == 'a':
                self.start_a(attr)

        def handle_endtag(self, tag):
            if tag == 'td':
                self.start_td()

        def start_a(self, attr):
            params = dict(attr)
            # get torrent name
            if 'title' in params and 'class' not in params and params['href'].startswith('/view/'):
                hit = {
                        'name': params['title'],
                        'desc_link': self.engine_url + params['href']}
                if not self.curr:
                    hit['engine_url'] = self.engine_url
                    self.curr = hit
            elif 'href' in params and params['href'].startswith("magnet:?"):
                if self.curr:
                    self.curr['link'] = params['href']
                    self.td_counter += 1

        def start_td(self):
            # Keep track of timers
            if self.td_counter >= 0:
                self.td_counter += 1

            # Add the hit to the results,
            # then reset the counters for the next result
            if self.td_counter >= 5:
                self.results.append(self.curr)
                self.curr = None
                self.td_counter = -1

        def handle_data(self, data):
            # These fields matter
            if self.td_counter > 0 and self.td_counter <= 5:
                # Catch the size
                if self.td_counter == 1:
                    self.curr['size'] = data.strip()
                # Catch the seeds
                elif self.td_counter == 3:
                    try:
                        self.curr['seeds'] = int(data.strip())
                    except:
                        self.curr['seeds'] = -1
                # Catch the leechers
                elif self.td_counter == 4:
                    try:
                        self.curr['leech'] = int(data.strip())
                    except:
                        self.curr['leech'] = -1
                # The rest is not supported by prettyPrinter
                else:
                    pass

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what, cat='all'):
        """
        Retreive and parse engine search results by category and query.

        Parameters:
        :param what: a string with the search tokens, already escaped
                     (e.g. "Ubuntu+Linux")
        :param cat:  the name of a search category, see supported_categories.
        """

        url = str("{0}/?f=0&s=seeders&o=desc&c={1}&q={2}"
                  .format(self.url,
                          self.supported_categories.get(cat),
                          what))

        hits = []
        page = 1
        parser = self.SukebeiNyaasiParser(hits, self.url)
        while True:
            res = retrieve_url(url + "&p={}".format(page))
            parser.feed(res)
            for each in hits:
                prettyPrinter(each)

            if len(hits) < 75:
                break
            del hits[:]
            page += 1

        parser.close()