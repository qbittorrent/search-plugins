#VERSION: 1.16
# AUTHORS: nindogo
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

import re
from datetime import datetime, timedelta
from html.parser import HTMLParser

from novaprinter import prettyPrinter
from helpers import retrieve_url


class eztv(object):
    name = "EZTV"
    url = 'https://eztv.re'
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
                self.current_item['pub_date'] = -1

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

            elif self.in_table_row:  # Check for a relative time
                if m := re.match(r'(\d+)h\s+(\d+)m', data):
                    date = datetime.now() - timedelta(hours=int(m.group(1)), minutes=int(m.group(2)))
                    self.current_item['pub_date'] = int(date.timestamp())
                elif m := re.match(r'(\d+)d\s+(\d+)h', data):
                    date = datetime.now() - timedelta(days=int(m.group(1)), hours=int(m.group(2)))
                    self.current_item['pub_date'] = int(date.timestamp())
                elif m := re.match(r'(\d+)\s+weeks?', data):
                    date = datetime.now() - timedelta(weeks=int(m.group(1)))
                    self.current_item['pub_date'] = int(date.timestamp())
                elif m := re.match(r'(\d+)\s+mo', data):
                    date = datetime.now() - timedelta(weeks=int(m.group(1)) * 4)
                    self.current_item['pub_date'] = int(date.timestamp())
                elif m := re.match(r'(\d+)\s+years?', data):
                    date = datetime.now() - timedelta(weeks=int(m.group(1)) * 52)
                    self.current_item['pub_date'] = int(date.timestamp())

        def handle_endtag(self, tag):
            if self.in_table_row and tag == self.TR:
                prettyPrinter(self.current_item)
                self.in_table_row = False

    def search(self, what, cat='all'):
        query = self.url + '/search/' + what.replace('%20', '-')
        eztv_html = retrieve_url(query)

        eztv_parser = self.MyHtmlParser(self.url)
        eztv_parser.feed(eztv_html)
        eztv_parser.close()


if __name__ == '__main__':
    eztv_se = eztv()
    eztv_se.search('Acre', 'all')
