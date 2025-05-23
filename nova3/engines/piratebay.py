# VERSION: 3.7
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

import datetime
import gzip
import html
import io
import json
import urllib.error
import urllib.request
from urllib.parse import unquote, urlencode

import helpers  # for setting SOCKS proxy side-effect
from novaprinter import prettyPrinter

helpers.htmlentitydecode  # dirty workaround to surpress static checkers


class piratebay(object):
    url = 'https://thepiratebay.org'
    name = 'The Pirate Bay'
    supported_categories = {
        'all': '0',
        'music': '100',
        'movies': '200',
        'games': '400',
        'software': '300'
    }

    # initialize trackers for magnet links
    trackers_list = [
        'udp://tracker.internetwarriors.net:1337/announce',
        'udp://tracker.opentrackr.org:1337/announce',
        'udp://p4p.arenabg.ch:1337/announce',
        'udp://tracker.openbittorrent.com:6969/announce',
        'udp://www.torrent.eu.org:451/announce',
        'udp://tracker.torrent.eu.org:451/announce',
        'udp://retracker.lanta-net.ru:2710/announce',
        'udp://open.stealth.si:80/announce',
        'udp://exodus.desync.com:6969/announce',
        'udp://tracker.tiny-vps.com:6969/announce'
    ]
    trackers = '&'.join(urlencode({'tr': tracker}) for tracker in trackers_list)

    def search(self, what, cat='all'):
        base_url = "https://apibay.org/q.php?%s"

        # get response json
        what = unquote(what)
        category = self.supported_categories[cat]
        params = {'q': what}
        if category != '0':
            params['cat'] = category

        # Calling custom `retrieve_url` function with adequate escaping
        data = self.retrieve_url(base_url % urlencode(params))
        response_json = json.loads(data)

        # check empty response
        if len(response_json) == 0:
            return

        # parse results
        for result in response_json:
            if result['info_hash'] == '0000000000000000000000000000000000000000':
                continue
            res = {
                'link': self.download_link(result),
                'name': result['name'],
                'size': str(result['size']) + " B",
                'seeds': result['seeders'],
                'leech': result['leechers'],
                'engine_url': self.url,
                'desc_link': self.url + '/description.php?id=' + result['id'],
                'pub_date': result['added'],
            }
            prettyPrinter(res)

    def download_link(self, result):
        return "magnet:?xt=urn:btih:{}&{}&{}".format(
            result['info_hash'], urlencode({'dn': result['name']}), self.trackers)

    def retrieve_url(self, url):
        def getBrowserUserAgent():
            """ Disguise as browser to circumvent website blocking """

            # Firefox release calendar
            # https://whattrainisitnow.com/calendar/
            # https://wiki.mozilla.org/index.php?title=Release_Management/Calendar&redirect=no

            baseDate = datetime.date(2024, 4, 16)
            baseVersion = 125

            nowDate = datetime.date.today()
            nowVersion = baseVersion + ((nowDate - baseDate).days // 30)

            return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{nowVersion}.0) Gecko/20100101 Firefox/{nowVersion}.0"

        # Request data from API
        request = urllib.request.Request(url, None, {'User-Agent': getBrowserUserAgent()})

        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError:
            return ""

        data = response.read()

        if data[:2] == b'\x1f\x8b':
            # Data is gzip encoded, decode it
            with io.BytesIO(data) as stream, gzip.GzipFile(fileobj=stream) as gzipper:
                data = gzipper.read()

        charset = 'utf-8'
        try:
            charset = response.getheader('Content-Type', '').split('charset=', 1)[1]
        except IndexError:
            pass

        dataStr = data.decode(charset, 'replace')
        dataStr = dataStr.replace('&quot;', '\\"')  # Manually escape &quot; before
        dataStr = html.unescape(dataStr)

        return dataStr
