#VERSION: 1.0
#AUTHORS: LightDestory (https://github.com/LightDestory)

#Based on mauricci's old plguin

import re
from html.parser import HTMLParser
# qBt
from helpers import retrieve_url
from novaprinter import prettyPrinter


class ilcorsaronero(object):
    url = 'https://ilcorsaronero.link'
    name = 'Il Corsaro Nero'
    supported_categories = {'all': '0'}
    max_page = 5

    class MyHTMLParser():
        def __init__(self):
            self.url = 'https://ilcorsaronero.link'
            self.fullResData = []
            self.pageResSize = 0

        def getSingleData(self):
            return {'link': '-1', 'name': '-1', 'size': '-1', 'seeds': '-1', 'leech': '-1', 'engine_url': self.url,
                    'desc_link': ""}

        def feed(self, html):
            self.pageResSize = 0
            url_titles = self.searchTitles(html)
            for c in range(len(url_titles)):
                self.pageResSize = len(url_titles)
                data = self.getSingleData()
                data['name'] = url_titles[c][0]
                data['seeds'] = url_titles[c][1]
                data['leech'] = url_titles[c][2]
                data['size'] = url_titles[c][3]
                data['link'] = url_titles[c][4]
                prettyPrinter(data)
                self.fullResData.append(data)

        def searchTitles(self, html):
            data = []
            trs = re.findall(r'<tr class=\"odd[2]?">.*?</TR>', html)
            for tr in trs:
                url_titles = re.search(r'<A class=\"tab\" HREF=\"(.+?)\" >(.+?)?</A>.+?([0-9]+\.[0-9]+ (GB|MB)).+?[0-9A-Z]{6}\'>([0-9]+).+?[0-9A-Z]{6}\'>([0-9]+)', tr)
                if url_titles:
                    name = url_titles.group(2) if url_titles.group(2) else url_titles.group(1).split("/")[5]
                    data.append([name, url_titles.group(5), url_titles.group(6), url_titles.group(3), url_titles.group(1)])
            return data

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what, cat='all'):
        what = what.replace(' ', '+')
        parser = self.MyHTMLParser()
        # analyze six page of results (thre are 40 entries per page)
        for currPage in range(0, self.max_page):
            url = self.url + \
                '/advsearch.php?search={0}&&page={1}'.format(what, currPage)
            html = retrieve_url(url).replace("	", "").replace("\n", "").replace("\r","").replace("n/a", "0")
            parser.feed(html)
            # if there are no results exit
            if parser.pageResSize <= 0:
                break

    def download_torrent(self, download_url):
        torrent_page = retrieve_url(download_url)
        magnet_match = re.search(r'a class=\"forbtn magnet\" href=\"(.?magnet:.*?)\"', torrent_page)
        if magnet_match and magnet_match.groups():
            print(magnet_match.groups()[0] + " " + download_url)
        else:
            raise Exception('Error, please fill a bug report!')


if __name__ == "__main__":
    c = ilcorsaronero()
    c.search('fast and furious')

