#VERSION: 1.1
#AUTHORS:   Gandalf (github.com/erdoukki)
#AUTHORS:   CravateRouge (github.com/CravateRouge)

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
import urllib.parse

from helpers import retrieve_url
from novaprinter import prettyPrinter


class oxtorrent(object):
    """ Search engine class """
    url = 'https://www.oxtorrent.vc'
    name = 'OxTorrent'
    supported_categories = {'all': '', 'music': 'musique', 'movies': 'films',
                            'books': 'ebook', 'software': 'logiciels', 'tv': 'series'}

    # OxTorrent's search divided into results, so we are going to set a limit
    # on how many results to read
    max_pages = 1000

    class HTMLParser:
        def __init__(self, url):
            self.url = url
            self.pageResSize = 0
            self.page_empty = 20000

        def feed(self, html):
            self.pageResSize = 0
            torrents = self.__findTorrents(html)
            resultSize = len(torrents)
            if resultSize == 0:
                return
            else:
                self.pageResSize = resultSize
            for torrent in range(resultSize):
                data = {
                    'link': urllib.parse.quote(torrents[torrent][0]),
                    'name': torrents[torrent][1],
                    'size': torrents[torrent][2],
                    'seeds': torrents[torrent][3],
                    'leech': torrents[torrent][4],
                    'engine_url': self.url,
                    'desc_link': torrents[torrent][5]
                }
                prettyPrinter(data)

        def __findTorrents(self, html):
            torrents = []
            trs = re.findall(
                r'<td .+i> <a href=\".+</a></div></td>\n<td .+\n<td .+\n<td .+</td>\n</tr>', html)
            for tr in trs:
                # Extract from the A node all the needed information
                url_titles = re.search(
                    r'<td .+i> <a href=\"(.+)\" title=.+>(.+)</a></div></td>\n<td .+\"left\">'
                    '([0-9,.]+ (TB|GB|MB|KB))</td>\n<td .+\"seeders\">.*([0-9,.]+).*</td>\n'
                    '<td .+\"leechers\">.*([0-9,.]+).*</td>\n</tr>', tr)
                if url_titles:
                    torrents.append(
                        [self.url + url_titles.group(1), url_titles.group(2), url_titles.group(3),
                         url_titles.group(5), url_titles.group(6), self.url + url_titles.group(1)])
            return torrents

    def download_torrent(self, info):
        # we have to fetch the info page and extract the magnet link
        info_page = retrieve_url(urllib.parse.unquote(info))
        magnet_match = re.search(r"window.location.href.*=.*\'(magnet[^\"]+)\';", info_page)
        if magnet_match and magnet_match.groups():
            print(magnet_match.groups()[0] + " " + info)
        else:
            raise Exception('Error, please fill a bug report!')

#    def download_torrent(self, info):
#        info_page = retrieve_url(urllib.parse.unquote(info))
#        file_link = re.search(r"window.location.href.*=.*\'(/telecharger/.+)\';", info_page)
#        torrent_url = self.url+file_link.group(1)
#        print(download_file(torrent_url))

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what, cat='all'):
        """ Performs search """
        """
        Here you can do what you want to get the result from the search engine website.
        Everytime you parse a result line, store it in a dictionary
        and call the prettyPrint(your_dict) function.

        `what` is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        `cat` is the name of a search category in ('all', 'movies', 'tv', 'music', 'games',
        'anime', 'software', 'pictures', 'books')
        """
        #prepare query. 7 is filtering by seeders
        cat = cat.lower()
        what = what.replace("%20", "+")

        parser = self.HTMLParser(self.url)
        page = 1
        while True:
            page_url = "{0}/recherche/{1}/{2}".format(self.url, what, page)
            print(page_url)
            html = retrieve_url(page_url)
            length_html = len(html)
            if page > 500 or length_html <= parser.page_empty:
                return
            parser.feed(html)
            page += 50
        parser.close()
