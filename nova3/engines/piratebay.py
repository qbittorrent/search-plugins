#VERSION: 2.20
# AUTHORS: Fabien Devaux (fab@gnux.info)
# CONTRIBUTORS: Christophe Dumez (chris@qbittorrent.org)
#               Arthur (custparasite@gmx.se)
#               Diego de las Heras (ngosang@hotmail.es)

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

try:
    # python3
    from html.parser import HTMLParser
except ImportError:
    # python2
    from HTMLParser import HTMLParser

# qBt
from novaprinter import prettyPrinter
from helpers import download_file, retrieve_url

# Fix invalid certificate in Windows
import ssl
ssl._create_default_https_context = ssl._create_unverified_context


class piratebay(object):
    """ Search engine class """
    url = 'https://pirateproxy.live'
    name = 'The Pirate Bay'
    supported_categories = {'all': '0', 'music': '100', 'movies': '200',
                            'games': '400', 'software': '300'}

    def download_torrent(self, info):
        """ Downloader """
        print(download_file(info))

    class MyHtmlParser(HTMLParser):
        """ Parser class """
        def __init__(self, results, url):
            HTMLParser.__init__(self)
            self.results = results
            self.url = url
            self.current_item = None
            self.save_item = None
            self.result_table = False  # table with results is found
            self.result_tbody = False
            self.add_query = True
            self.result_query = False

        def handle_start_tag_default(self, attrs):
            """ Default handler for start tag dispatcher """
            pass

        def handle_start_tag_a(self, attrs):
            """ Handler for start tag a """
            params = dict(attrs)
            link = params["href"].replace(self.url, '')
            if link.startswith("/torrent"):
                self.current_item["desc_link"] = "".join((self.url, link))
                self.save_item = "name"
            elif link.startswith("magnet"):
                self.current_item["link"] = link
                # end of the 'name' item
                self.current_item['name'] = self.current_item['name'].strip()
                self.save_item = None

        def handle_start_tag_font(self, attrs):
            """ Handler for start tag font """
            for attr in attrs:
                if attr[1] == "detDesc":
                    self.save_item = "size"
                    break

        def handle_start_tag_td(self, attrs):
            """ Handler for start tag td """
            for attr in attrs:
                if attr[1] == "right":
                    if "seeds" in self.current_item.keys():
                        self.save_item = "leech"
                    else:
                        self.save_item = "seeds"
                    break

        def handle_starttag(self, tag, attrs):
            """ Parser's start tag handler """
            if self.current_item:
                dispatcher = getattr(self,
                                     "_".join(("handle_start_tag", tag)),
                                     self.handle_start_tag_default)
                dispatcher(attrs)

            elif self.result_tbody:
                if tag == "tr":
                    self.current_item = {"engine_url": self.url}

            elif tag == "table":
                self.result_table = "searchResult" == attrs[0][1]

            elif self.add_query:
                if self.result_query and tag == "a":
                    if len(self.list_searches) < 10:
                        self.list_searches.append(attrs[0][1])
                    else:
                        self.add_query = False
                        self.result_query = False
                elif tag == "div":
                    self.result_query = "center" == attrs[0][1]

        def handle_endtag(self, tag):
            """ Parser's end tag handler """
            if self.result_tbody:
                if tag == "tr":
                    if 'size' in self.current_item:
                        # clean up size
                        temp_data = self.current_item['size'].split()
                        if "Size" in temp_data:
                            indx = temp_data.index("Size")
                            self.current_item['size'] = (temp_data[indx + 1] + " "
                                                         + temp_data[indx + 2])
                        else:
                            self.current_item['size'] = -1
                        # return result
                        prettyPrinter(self.current_item)
                        self.results.append('a')
                    self.current_item = None
                elif tag == "font":
                    self.save_item = None
                elif tag == "table":
                    self.result_table = self.result_tbody = False

            elif self.result_table:
                if tag == "thead":
                    self.result_tbody = True
                elif tag == "table":
                    self.result_table = self.result_tbody = False

            elif self.add_query and self.result_query:
                if tag == "div":
                    self.add_query = self.result_query = False

        def handle_data(self, data):
            """ Parser's data handler """
            if self.save_item:
                if (self.save_item == "size" or self.save_item == "name"):
                    if self.save_item not in self.current_item:
                        self.current_item[self.save_item] = ''
                    self.current_item[self.save_item] += " " + data

                else:
                    self.current_item[self.save_item] = data
                    self.save_item = None

    def search(self, what, cat='all'):
        """ Performs search """
        cat = cat.lower()
        # try to get 10 pages (10 * 30 = 300 results) and stop when we don't found results
        results_list = []
        parser = self.MyHtmlParser(results_list, self.url)
        page = 1
        while page < 11:
            # prepare query. 7 is filtering by seeders
            page_url = "{0}/search/{1}/{2}/7/{3}".format(self.url, what, page,
                                                         self.supported_categories[cat])
            html = retrieve_url(page_url)
            parser.feed(html)
            if len(results_list) < 1:
                break
            del results_list[:]
            page += 1
        parser.close()
