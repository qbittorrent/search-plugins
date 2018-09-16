#VERSION: 2.00
#AUTHORS: Vikas Yadav (https://github.com/v1k45 | http://v1k45.com)
#CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the author nor the names of its contributors may be
#      used to endorse or promote products derived from this software without
#      specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import re
try:
    # python3
    from html.parser import HTMLParser
except ImportError:
    # python2
    from HTMLParser import HTMLParser

# qBt
from helpers import retrieve_url
from novaprinter import prettyPrinter


class leetx(object):
    url = "https://1337x.to"
    name = "1337x"
    supported_categories = {
        'all': 'All',
        'movies': 'Movies',
        'tv': 'TV',
        'music': 'Music',
        'games': 'Games',
        'anime': 'Anime',
        'software': 'Apps'
    }

    class MyHtmlParser(HTMLParser):
        A, TABLE, TR, TD, SPAN = ('a', 'table', 'tr', 'td', 'span')

        """ Sub-class for parsing results """
        def __init__(self, results, url):
            HTMLParser.__init__(self)
            self.results = results
            self.url = url

            self.current_result = {}
            self.current_item = None
            self.inside_table = False
            self.inside_row = False

        def handle_starttag(self, tag, attrs):
            # are we inside the results table body or not
            # if we are not inside the table, no need to process any further
            self.inside_table = self.inside_table or tag == self.TABLE
            if not self.inside_table:
                return

            # convert attrs tuple to dictionary
            attrs = dict(attrs)

            # for torrent name and link
            link = attrs.get('href', '')
            if tag == self.A and link.startswith('/torrent'):
                self.current_result['link'] = self.url + link
                self.current_result['desc_link'] = self.url + link
                self.current_result['engine_url'] = self.url
                self.current_item = 'name'

            # to ignore uploader name attached to the torrent size in span tag
            if tag == self.SPAN:
                self.current_item = None

            # if this is a <td> there can be seeds, leeches or size inside it.
            if tag == self.TD:
                self.inside_row = True

                # find apporipate data key using class name of td
                for item in ['seeds', 'leech', 'size']:
                    if item in attrs.get('class', ''):
                        self.current_item = item
                        break

        def handle_data(self, data):
            # if we are not inside the table, no need to process any further
            if not self.inside_table:
                return

            # do not process data if we are not inside the table body
            if self.current_item:
                prev_value = self.current_result.get(self.current_item, '')
                self.current_result[self.current_item] = prev_value + data

        def handle_endtag(self, tag):
            # are we inside the results table body or not
            # if we are not inside the table, no need to process any further
            if tag == self.TABLE:
                self.inside_table = False
            if not self.inside_table:
                return

            # exiting the table data and maybe moving td or tr element
            if self.inside_row and tag == self.TD:
                self.inside_row = False
                self.current_item = None

            # exiting the tr element, which means all necessary data for a torrent has been
            # extracted, we should save it and clean the object's state.
            if self.current_result and tag == self.TR:
                if 'size' in self.current_result:
                    self.current_result['size'] = self.current_result['size'].replace(',', '')
                prettyPrinter(self.current_result)
                self.results.append('a')
                self.current_result = {}
                self.current_item = None

    def download_torrent(self, download_url):
        # since 1337x does not provide torrent links in the search results,
        # we will have to fetch the page and extract the magnet link
        torrent_page = retrieve_url(download_url)
        magnet_match = re.search(r"href\s*\=\s*\"(magnet[^\"]+)\"", torrent_page)
        if magnet_match and magnet_match.groups():
            print(magnet_match.groups()[0] + " " + download_url)
        else:
            raise Exception('Error, please fill a bug report!')

    def search(self, what, cat='all'):
        cat = cat.lower()

        # decide which type of search to perform based on category
        search_page = "search" if cat == 'all' else 'category-search'
        search_url = "{url}/{search_page}/{search_query}/".format(
            url=self.url, search_page=search_page, search_query=what)

        # apply search category to url, if any.
        if cat != 'all':
            search_url += self.supported_categories[cat] + "/"

        # try to get 15 pages (20 * 15 = 300 results) and stop when we don't found results
        results_list = []
        parser = self.MyHtmlParser(results_list, self.url)
        page = 1
        while page < 16:
            # download the page
            html = retrieve_url(search_url + str(page) + '/')
            parser.feed(html)
            if len(results_list) < 1:
                break
            del results_list[:]
            page += 1
        parser.close()
