#VERSION: 0.3
#AUTHORS: Henrik Asp (solenskiner@gmail.com)

# Copyright (c) 2019, Henrik Asp
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.

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

from novaprinter import prettyPrinter
from helpers import download_file, retrieve_url
from html.parser import HTMLParser
from functools import partial


class MyHTMLParser(HTMLParser):
    defaults = {
        "link": -1,
        "name": -1,
        "size": -1,
        "seeds": 0,
        "leech": 0,
        "engine_url": "http://academictorrents.com",
        "desc_link": -1
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = []
        self.current = self.defaults.copy()
        self.tag_stack = ['root']
        self.attrs_stack = [{}]
        self.numchild_stack = [0]
        self.data = { 'torrents':[],
                      'next_page': None }

    def handle_starttag(self, tag, attrs):
        """ Parser's start tag handler """
        dispatcher = getattr(
            self,
            "_".join(("handle_start_tag", tag)),
            partial(self.handle_start_tag_default, tag)
        )
        self.pre_handle_start_tag(tag, attrs)
        dispatcher(attrs)
        self.post_handle_start_tag(tag, attrs)

    def handle_start_tag_default(self, tag, attrs):
        pass

    def pre_handle_start_tag(self, tag, attrs):
        self.numchild_stack[-1] += 1

    def post_handle_start_tag(self, tag, attrs):
        self.tag_stack.append(tag)
        self.attrs_stack.append(dict(attrs))
        self.numchild_stack.append(0)

    def handle_endtag(self, tag):
        """ Parser's end tag handler """
        dispatcher = getattr(
            self,
            "_".join(("handle_end_tag", tag)),
            partial(self.handle_end_tag_default, tag)
        )
        self.pre_handle_end_tag(tag)
        dispatcher()
        self.post_handle_end_tag(tag,)

    def handle_end_tag_default(self, tag):
        pass

    def pre_handle_end_tag(self, tag):
        # sometimes website authors are not too careful to write valid markup
        # hence looping until we find the matching end tag,
        # and explicitly stopping if we can't find it.
        pops = 0
        while True:
            if self.tag_stack[-1] == "root":
                break
            pops += 1
            pop = self.tag_stack.pop()
            self.attrs_stack.pop()
            self.numchild_stack.pop()
            if pop == tag:
                break

    def post_handle_end_tag(self, tag):
        pass

    def handle_start_tag_tr(self, attrs):
        self.current = self.defaults.copy()

    def handle_end_tag_tr(self):
        match_torrent = ['root', 'html', 'body', 'table', 'tr']
        if self.tag_stack[:len(match_torrent)] == match_torrent:
            self.data["torrents"].append(self.current.copy())

    def handle_data(self, data):
        match_next = ['root', 'html', 'body', 'center', 'p', 'ul', 'li', 'a']
        match_torrent = ['root', 'html', 'body', 'table', 'tr']
        url = "http://academictorrents.com"

        if self.tag_stack[:len(match_next)] == match_next and "Next" in data:
            self.data["next_page"] = url + "/" + self.attrs_stack[7]["href"]

        elif self.tag_stack[:len(match_torrent)] == match_torrent:

            if self.numchild_stack[5:] == [2, 1, 1, 0]:
                download_link = url + "/download/{}.torrent"
                self.current["name"] = data
                self.current["desc_link"] = self.attrs_stack[7]["href"]
                self.current["link"] = download_link.format(
                    self.attrs_stack[7]["href"].split("/")[2]
                )

            elif self.numchild_stack[5:] == [5, 0]:
                self.current["size"] = data

            elif self.numchild_stack[5:] == [6, 1, 1, 1, 0]:
                self.current["seeds"] = data.strip("+")

            elif self.numchild_stack[5:] == [6, 2, 1, 1, 0]:
                self.current["leech"] = data.strip("+")

    def get_results(self):
        return self.data


class academictorrents(object):
    """ Search engine class """
    url = "http://academictorrents.com"
    name = "Academic Torrents"
    supported_categories = {'all': ''}

    def download_torrent(self, info):
        """ Downloader """
        print(download_file(info))

    def search(self, what, cat='all'):
        """ Performs search """
        if cat != 'all':
            return

        search_url = "http://academictorrents.com/browse.php?search={what}"

        url = search_url.format(what=what)

        while url:
            response = retrieve_url(url)
            parser = MyHTMLParser()
            parser.feed(response)
            results = parser.get_results()
            for match in results["torrents"]:
                prettyPrinter(match)
            url = results["next_page"]
