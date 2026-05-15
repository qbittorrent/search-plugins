# VERSION: 1.0
# AUTHORS: Hydracker Team (contact@hydracker.com)

# LICENSING INFORMATION
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
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
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import json
import os
import urllib.request
import xml.etree.ElementTree
from datetime import datetime
from http.cookiejar import CookieJar
from typing import Any, Dict, Union
from urllib.parse import unquote, urlencode

import helpers
from novaprinter import prettyPrinter


CONFIG_FILE = 'hydracker.json'
CONFIG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), CONFIG_FILE)
CONFIG_DATA: Dict[str, Any] = {
    'api_key': 'YOUR_API_KEY_HERE',
    'url': 'https://hydracker.com',
}


def load_configuration() -> None:
    global CONFIG_DATA
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            CONFIG_DATA = json.load(f)
    except ValueError:
        CONFIG_DATA['malformed'] = True
    except Exception:
        save_configuration()

    if any(item not in CONFIG_DATA for item in ['api_key', 'url']):
        CONFIG_DATA['malformed'] = True


def save_configuration() -> None:
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        f.write(json.dumps(CONFIG_DATA, indent=4, sort_keys=True))


load_configuration()


class hydracker:
    name = 'Hydracker'
    url = CONFIG_DATA['url'].rstrip('/')
    api_key = CONFIG_DATA['api_key']
    supported_categories = {
        'all': None,
        'anime': ['5070'],
        'books': ['7000'],
        'games': ['1000'],
        'movies': ['2000', '2010', '2020', '2030', '2040', '2045', '2050', '2060'],
        'music': ['3000', '3030', '3040'],
        'software': ['4000'],
        'tv': ['5000', '5020', '5030', '5040', '5045', '5050', '5080'],
    }

    def download_torrent(self, download_url: str) -> None:
        if download_url.startswith('magnet:?'):
            print(download_url + " " + download_url)
            return
        print(helpers.download_file(download_url))

    def search(self, what: str, cat: str = 'all') -> None:
        what = unquote(what)
        category = self.supported_categories[cat.lower()]

        if 'malformed' in CONFIG_DATA:
            self._error("malformed configuration file", what)
            return

        if self.api_key == "YOUR_API_KEY_HERE":
            self._error("api key error", what)
            return

        params = [('apikey', self.api_key), ('q', what), ('limit', '100')]
        if category is not None:
            params.append(('cat', ','.join(category)))
        query_url = f"{self.url}/api/v1/torznab/api?{urlencode(params)}"

        response = self._get(query_url)
        if response is None:
            self._error("connection error", what)
            return

        try:
            root = xml.etree.ElementTree.fromstring(response)
        except xml.etree.ElementTree.ParseError:
            self._error("invalid response", what)
            return

        channel = root.find('channel')
        if channel is None:
            return

        for item in channel.findall('item'):
            res: Dict[str, Any] = {}

            title_el = item.find('title')
            if title_el is None or not title_el.text:
                continue
            res['name'] = title_el.text

            link_el = item.find('link')
            if link_el is None or not link_el.text:
                continue
            res['link'] = link_el.text

            size_el = item.find('size')
            res['size'] = -1 if size_el is None or size_el.text is None else f"{size_el.text} B"

            res['seeds'] = self._attr_int(item, 'seeders')
            peers = self._attr_int(item, 'peers')
            res['leech'] = peers - res['seeds'] if res['seeds'] != -1 and peers != -1 else -1

            comments_el = item.find('comments')
            if comments_el is not None and comments_el.text:
                res['desc_link'] = comments_el.text
            else:
                guid_el = item.find('guid')
                res['desc_link'] = guid_el.text if guid_el is not None and guid_el.text else ''

            res['engine_url'] = self.url

            pubdate_el = item.find('pubDate')
            try:
                if pubdate_el is not None and pubdate_el.text:
                    date = datetime.strptime(pubdate_el.text, '%a, %d %b %Y %H:%M:%S %z')
                    res['pub_date'] = int(date.timestamp())
                else:
                    res['pub_date'] = -1
            except ValueError:
                res['pub_date'] = -1

            prettyPrinter({k: (v.replace('|', '%7C') if isinstance(v, str) else v) for k, v in res.items()})

    def _attr_int(self, item: xml.etree.ElementTree.Element, name: str) -> int:
        xpath = f'./{{http://torznab.com/schemas/2015/feed}}attr[@name="{name}"]'
        el = item.find(xpath)
        if el is None:
            return -1
        try:
            return int(el.attrib.get('value', '-1'))
        except ValueError:
            return -1

    def _get(self, query: str) -> Union[str, None]:
        try:
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
            return opener.open(query, timeout=30).read().decode('utf-8')
        except Exception:
            return None

    def _error(self, message: str, what: str) -> None:
        prettyPrinter({
            'link': self.url,
            'name': f"Hydracker: {message}! Edit '{CONFIG_PATH}' and set your API key. Search: '{what}'",
            'size': -1,
            'seeds': -1,
            'leech': -1,
            'engine_url': self.url,
            'desc_link': 'https://hydracker.com/account-settings',
            'pub_date': -1,
        })
