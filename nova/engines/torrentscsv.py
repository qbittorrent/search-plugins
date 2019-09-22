#VERSION: 1.0
# AUTHORS: Dessalines

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

import json
try:
    # python3
    from urllib.parse import urlencode, unquote
except ImportError:
    # python2
    from urllib import urlencode, unquote

# qBt
from novaprinter import prettyPrinter
from helpers import retrieve_url


class torrentscsv(object):
    url = 'https://torrents-csv.ml'
    name = 'torrents-csv'
    supported_categories = {'all': '1;4;14;15;16;17;21;22;42;18;19;\
            41;27;28;29;30;31;32;40;23;24;25;26;33;34;43;44;45;46;\
            47;48;49;50;51;52'}

    def search(self, what, cat='all'):
        base_url = "https://torrents-csv.ml/service/search?%s"

        # get response json
        what = unquote(what)
        params = urlencode({'q': what,
                            'size': 100})
        fetch_url = base_url % params
        response = retrieve_url(fetch_url)
        j = json.loads(response)

        # parse results
        for result in j:
            res = {'link': downloadLink(result),
                   'name': result['name'],
                   'size': str(result['size_bytes']) + " B",
                   'seeds': result['seeders'],
                   'leech': result['leechers'],
                   'engine_url': self.url,
                   'desc_link': fetch_url}
            prettyPrinter(res)


def downloadLink(res):
    return "magnet:?xt=urn:btih:{}&dn={}\
            &tr=udp://tracker.coppersurfer.tk:6969/announce\
            &tr=udp://tracker.open-internet.nl:6969/announce\
            &tr=udp://tracker.leechers-paradise.org:6969/announce\
            &tr=udp://tracker.internetwarriors.net:1337/announce\
            &tr=udp://tracker.opentrackr.org:1337/announce\
            &tr=udp://9.rarbg.to:2710/announce\
            &tr=udp://9.rarbg.me:2710/announce\
            &tr=http://tracker3.itzmx.com:6961/announce\
            &tr=http://tracker1.itzmx.com:8080/announce\
            &tr=udp://exodus.desync.com:6969/announce\
            &tr=udp://explodie.org:6969/announce\
            &tr=udp://ipv4.tracker.harry.lu:80/announce\
            &tr=udp://denis.stalker.upeer.me:6969/announce\
            &tr=udp://tracker.torrent.eu.org:451/announce\
            &tr=udp://tracker.tiny-vps.com:6969/announce\
            &tr=udp://thetracker.org:80/announce\
            &tr=udp://open.demonii.si:1337/announce\
            &tr=udp://tracker4.itzmx.com:2710/announce\
            &tr=udp://tracker.cyberia.is:6969/announce\
            &tr=udp://retracker.netbynet.ru:2710/announce"\
            .format(res['infohash'], res['name'])
