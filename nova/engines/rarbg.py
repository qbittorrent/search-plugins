#VERSION: 2.10
# AUTHORS: b0nk
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

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
import time
try:
    # python3
    from urllib.parse import urlencode, unquote
except ImportError:
    # python2
    from urllib import urlencode, unquote

# qBt
from novaprinter import prettyPrinter
from helpers import retrieve_url


class rarbg(object):
    url = 'https://rarbg.to'
    name = 'RARBG'
    supported_categories = {'all': '1;4;14;15;16;17;21;22;42;18;19;41;27;28;29;30;31;32;40;23;24;25;26;33;34;43;44;45;46;47;48',  # noqa
                            'movies': 'movies',
                            'tv': 'tv',
                            'music': '1;23;24;25;26',
                            'games': '1;27;28;29;30;31;32;40',
                            'software': '1;33;34;43'}

    def search(self, what, cat='all'):
        base_url = "https://torrentapi.org/pubapi_v2.php?%s"
        app_id = "qbittorrent"

        # get token
        params = urlencode({'get_token': 'get_token', 'app_id': app_id})
        response = retrieve_url(base_url % params)
        j = json.loads(response)
        token = j['token']
        time.sleep(2.1)

        # get response json
        what = unquote(what)
        category = self.supported_categories[cat]
        params = urlencode({'mode': 'search',
                            'search_string': what,
                            'ranked': 0,
                            'category': category,
                            'limit': 100,
                            'sort': 'seeders',
                            'format': 'json_extended',
                            'token': token,
                            'app_id': 'qbittorrent'})
        response = retrieve_url(base_url % params)
        j = json.loads(response)

        # parse results
        for result in j['torrent_results']:
            res = {'link': result['download'],
                   'name': result['title'],
                   'size': str(result['size']) + " B",
                   'seeds': result['seeders'],
                   'leech': result['leechers'],
                   'engine_url': self.url,
                   'desc_link': result['info_page'] + "&app_id=" + app_id}
            prettyPrinter(res)
