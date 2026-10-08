# VERSION: 0.5
# AUTHORS: Cycloctane (Cycloctane@octane.top)

# MIT License, Copyright (c) 2024 Cycloctane
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys
import urllib.request
from urllib.parse import unquote, urlencode
from xml.etree import ElementTree

from novaprinter import prettyPrinter


class mikan:

    name = "MikanProject"
    url = "https://mikanani.me"

    supported_categories = {'all': '', 'anime': ''}

    @classmethod
    def __request(cls, target: str) -> str:
        req = urllib.request.Request(
            cls.url + '/RSS/Search?' + urlencode({'searchstr': unquote(target)}),
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode('utf-8')

    @classmethod
    def __parse(cls, text: str) -> None:
        try:
            search_result = ElementTree.fromstring(text)
            for item in search_result.find("channel").findall("item"):
                row = {'engine_url': cls.url, 'seeds': -1, 'leech': -1}
                row['name'] = item.findtext("title")
                row['link'] = item.find("enclosure").attrib['url']
                row['size'] = item.find("enclosure").attrib['length']
                row['desc_link'] = item.findtext('link')
                prettyPrinter(row)
        except (ElementTree.ParseError, AttributeError, KeyError):
            raise Exception("parse error")

    def search(self, what: str, cat: str = 'all') -> None:
        try:
            self.__parse(self.__request(what))
        except Exception as error:
            print('Mikan: search failed ({})'.format(type(error).__name__), file=sys.stderr)
