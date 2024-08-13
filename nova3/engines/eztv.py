#VERSION: 1.15
# AUTHORS: nindogo
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

import io
import gzip
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from novaprinter import prettyPrinter
from helpers import htmlentitydecode

# Some sites blocks default python User-agent
headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0'}

# We must implement our own retrieve_url because helpers.py versions prior to 1.49 did not 
# support POST requests. That version is taken from helpers.py 1.45
def retrieve_url(url, data=None):
    """ Return the content of the url page as a string """
    req = urllib.request.Request(url, data, headers)
    try:
        response = urllib.request.urlopen(req)
    except urllib.error.URLError as errno:
        print(" ".join(("Connection error:", str(errno.reason))))
        return ""
    dat = response.read()
    # Check if it is gzipped
    if dat[:2] == b'\x1f\x8b':
        # Data is gzip encoded, decode it
        compressedstream = io.BytesIO(dat)
        gzipper = gzip.GzipFile(fileobj=compressedstream)
        extracted_data = gzipper.read()
        dat = extracted_data
    info = response.info()
    charset = 'utf-8'
    try:
        ignore, charset = info['Content-Type'].split('charset=')
    except Exception:
        pass
    dat = dat.decode(charset, 'replace')
    dat = htmlentitydecode(dat)
    # return dat.encode('utf-8', 'replace')
    return dat


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

    def search(self, what, cat='all'):
        query = self.url + '/search/' + what.replace('%20', '-')
        eztv_html = retrieve_url(query, b"layout=def_wlinks")

        eztv_parser = self.MyHtmlParser(self.url)
        eztv_parser.feed(eztv_html)
        eztv_parser.close()


if __name__ == '__main__':
    eztv_se = eztv()
    eztv_se.search('Acre', 'all')
