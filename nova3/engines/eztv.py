#VERSION: 1.15
# AUTHORS: nindogo
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from novaprinter import prettyPrinter
from helpers import retrieve_url


class eztv(object):
    name = "EZTV"
    url = 'https://eztvx.to/'
    supported_categories = {'all': 'all', 'tv': 'tv'}

    class MyHtmlParser(HTMLParser):
        A, TD, TR, TABLE = ('a', 'td', 'tr', 'table')

        """ Sub-class for parsing results """
        def __init__(self, url):
            HTMLParser.__init__(self)
            self.url = url

            self.in_table_row = False
            self.current_item = {}

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)

            if (params.get('class') == 'forum_header_border'
                    and params.get('name') == 'hover'):
                self.in_table_row = True
                self.current_item = {}
                self.current_item['seeds'] = -1
                self.current_item['leech'] = -1
                self.current_item['size'] = -1
                self.current_item['engine_url'] = self.url

            if (tag == self.A
                    and self.in_table_row and params.get('class') == 'magnet'):
                self.current_item['link'] = params.get('href')

            if (tag == self.A
                    and self.in_table_row and params.get('class') == 'epinfo'):
                self.current_item['desc_link'] = self.url + params.get('href')
                self.current_item['name'] = params.get('title').split(' (')[0]

        def handle_data(self, data):
            data = data.replace(',', '')
            if (self.in_table_row
                    and (data.endswith(' KB') or data.endswith(' MB') or data.endswith(' GB'))):
                self.current_item['size'] = data

            elif self.in_table_row and data.isnumeric():
                self.current_item['seeds'] = int(data)

        def handle_endtag(self, tag):
            if self.in_table_row and tag == self.TR:
                prettyPrinter(self.current_item)
                self.in_table_row = False

    def do_query(self, what):
        url = f"{self.url}/search/{what.replace('%20', '-')}"
        data =b"layout=def_wlinks"
        try:
            return retrieve_url(url, request_data=data)
        except TypeError:
            # Older versions of retrieve_url did not support request_data/POST, se we must do the
            # request ourselves...
            if not url.startswith("https://"): # Satisfy the linter
                return ""
            user_agent = 'Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0'
            req = urllib.request.Request(url, data, {'User-Agent': user_agent})
            try:
                response = urllib.request.urlopen(req)
                return response.read().decode('utf-8')
            except urllib.error.URLError as errno:
                print(f"Connection error: {errno.reason}")
            return ""

    def search(self, what, cat='all'):
        eztv_html = self.do_query(what)

        eztv_parser = self.MyHtmlParser(self.url)
        eztv_parser.feed(eztv_html)
        eztv_parser.close()


if __name__ == '__main__':
    eztv_se = eztv()
    eztv_se.search('Acre', 'all')
