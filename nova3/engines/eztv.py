#VERSION: 1.15
# AUTHORS: nindogo
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

from html.parser import HTMLParser

import random
import http.cookiejar
import urllib.request
import urllib.parse

from novaprinter import prettyPrinter

policy = http.cookiejar.DefaultCookiePolicy()
global_cookie_jar = http.cookiejar.CookieJar(policy)

def random_user_agent():
    _USER_AGENT_TPL = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/%s Safari/537.36'
    _CHROME_VERSIONS = (
        '90.0.4430.212',
        '90.0.4430.24',
        '90.0.4430.70',
        '90.0.4430.72',
        '90.0.4430.85',
        '90.0.4430.93',
        '91.0.4472.101',
        '91.0.4472.106',
        '91.0.4472.114',
        '91.0.4472.124',
        '91.0.4472.164',
        '91.0.4472.19',
        '91.0.4472.77',
        '92.0.4515.107',
        '92.0.4515.115',
        '92.0.4515.131',
        '92.0.4515.159',
        '92.0.4515.43',
        '93.0.4556.0',
        '93.0.4577.15',
        '93.0.4577.63',
        '93.0.4577.82',
        '94.0.4606.41',
        '94.0.4606.54',
        '94.0.4606.61',
        '94.0.4606.71',
        '94.0.4606.81',
        '94.0.4606.85',
        '95.0.4638.17',
        '95.0.4638.50',
        '95.0.4638.54',
        '95.0.4638.69',
        '95.0.4638.74',
        '96.0.4664.18',
        '96.0.4664.45',
        '96.0.4664.55',
        '96.0.4664.93',
        '97.0.4692.20',
    )
    return _USER_AGENT_TPL % random.choice(_CHROME_VERSIONS)

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

    def retrieve_url(self, url, data=None):
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(global_cookie_jar))
        opener.addheaders = [('User-Agent', random_user_agent())]
        if not data:
            req = urllib.request.Request(url)
        else:
            req = urllib.request.Request(url, data=data)

        with opener.open(req) as response:
            parsed = urllib.parse.urlparse(response.url)
            self.url = parsed.scheme + "://" + parsed.hostname
            return response.read().decode('utf-8')

    def search(self, what, cat='all'):

        _ = self.retrieve_url(self.url)

        data = {'layout':'def_wlinks'}
        data = urllib.parse.urlencode(data).encode('utf-8')
        
        query = self.url + '/search/' + what.replace('%20', '-')
        eztv_html = self.retrieve_url(query, data)

        eztv_parser = self.MyHtmlParser(self.url)
        eztv_parser.feed(eztv_html)
        eztv_parser.close()


if __name__ == '__main__':
    eztv_se = eztv()
    eztv_se.search('Acre', 'all')
