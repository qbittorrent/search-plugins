#VERSION: 1.00
# AUTHORS: Diego de las Heras (ngosang@hotmail.es)
# CONTRIBUTORS:

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

#qBt
from novaprinter import prettyPrinter
from helpers import download_file, retrieve_url


class btbit(object):
    """ Search engine class """
    url = 'https://en.btbit.org'
    name = 'BTBit'

    def download_torrent(self, info):
        """ Downloader """
        print(download_file(info))

    class MyHtmlParser(HTMLParser):
        """ Parser class """
        def __init__(self, results, url):
            HTMLParser.__init__(self)
            self.results = results
            self.url = url
            self.current_item = {}
            self.torrent_grabbing = False
            self.title_grabbing = False
            self.title_array = []
            self.metadata_grabbing = False
            self.metadata_array = []

        def handle_starttag(self, tag, attrs):
            if tag == "div":
                for attr in attrs:
                    if attr[1] == "rs":
                        self.torrent_grabbing = True
                    if attr[1] == "sbar" and self.torrent_grabbing:
                        self.metadata_grabbing = True
            elif tag == "a":
                if self.torrent_grabbing:
                    params = dict(attrs)
                    if "href" in params:
                        link = params["href"]
                        if link.startswith(self.url + "/bt/"):
                            self.current_item["desc_link"] = link
                            self.title_grabbing = True
                        elif link.startswith("magnet:"):
                            self.current_item["link"] = link

        def handle_endtag(self, tag):
            if tag == "div":
                if self.metadata_grabbing:
                    size_idx = 0
                    for meta in self.metadata_array:
                        size_idx += 1
                        if "Size" in meta:
                            break
                    self.current_item["size"] = self.metadata_array[size_idx]
                    self.current_item["name"] = ''.join(self.title_array)[1:-1]
                    self.current_item["engine_url"] = self.url
                    self.current_item["seeds"] = -1
                    self.current_item["leech"] = -1

                    prettyPrinter(self.current_item)
                    self.results.append('a')

                    # clean up
                    self.current_item = {}
                    self.torrent_grabbing = False
                    self.title_grabbing = False
                    self.title_array = []
                    self.metadata_grabbing = False
                    self.metadata_array = []
            elif tag == "a":
                if self.title_grabbing:
                    self.title_grabbing = False

        def handle_data(self, data):
            if self.title_grabbing:
                self.title_array.append(data)
            elif self.metadata_grabbing:
                self.metadata_array.append(data)

    def search(self, what, cat='all'):
        """ Performs search """
        results_list = []
        parser = self.MyHtmlParser(results_list, self.url)
        i = 1
        while i < 5:
            # "what" is already urlencoded
            html = retrieve_url(self.url + '/list/%s/%d-0-0.html' % (what, i))
            parser.feed(html)
            if len(results_list) < 1:
                break
            del results_list[:]
            i += 1
        parser.close()
