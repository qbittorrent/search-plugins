# VERSION: 1.7
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
from typing import Mapping
from urllib.parse import urlencode

from helpers import retrieve_url
from novaprinter import prettyPrinter


class torrentscsv:
    url = 'https://torrents-csv.com'
    name = 'torrents-csv'
    supported_categories = {'all': '', 'movies': 'movies', 'tv': 'tv', 'music': 'music', 'games': 'games', 'software': 'software'}

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

    def search(self, what: str, cat: str = 'all') -> None:
        search_url = "{}/service/search?size=100&q={}".format(self.url, what)
        desc_url = "{}/#/search/torrent/{}/1".format(self.url, what)

        # get response json
        try:
            response = retrieve_url(search_url)
            response_json = json.loads(response)
        except Exception:
            return  # Handle API failure gracefully

        # parse results
        for result in response_json.get("torrents", []):
            prettyPrinter({
                'link': self.download_link(result),
                'name': result.get('name', ''),
                'size': str(result.get('size_bytes', 0)) + " B",
                'seeds': result.get('seeders', 0),
                'leech': result.get('leechers', 0),
                'engine_url': self.url,
                'desc_link': desc_url,
                'pub_date': result.get('created_unix', -1)
            })

    def download_link(self, result: Mapping[str, str]) -> str:
        return "magnet:?xt=urn:btih:{}&{}&{}".format(
            result['infohash'], urlencode({'dn': result['name']}), self.trackers)
