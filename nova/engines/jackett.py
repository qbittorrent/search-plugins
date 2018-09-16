#VERSION: 2.00
# AUTHORS: ukharley
#          hannsen (github.com/hannsen)
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

import json
import os
try:
    # python3
    from urllib.parse import urlencode, unquote
    from urllib import request as urllib_request
    from http.cookiejar import CookieJar
except ImportError:
    # python2
    from urllib import urlencode, unquote
    import urllib2 as urllib_request
    from cookielib import CookieJar

# qBt
from novaprinter import prettyPrinter


###############################################################################
# load configuration from file
CONFIG_FILE = 'jackett.json'
CONFIG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), CONFIG_FILE)
CONFIG_DATA = {
    'api_key': 'YOUR_API_KEY_HERE',  # jackett api
    'tracker_first': False,          # (False/True) add tracker name to beginning of search result
    'url': 'http://127.0.0.1:9117',  # jackett url
}


def load_configuration():
    global CONFIG_PATH, CONFIG_DATA
    try:
        # try to load user data from file
        with open(CONFIG_PATH) as f:
            CONFIG_DATA = json.load(f)
    except ValueError:
        # if file exists but it's malformed we load add a flag
        CONFIG_DATA['malformed'] = True
    except Exception:
        # if file doesn't exist, we create it
        with open(CONFIG_PATH, 'w') as f:
            f.write(json.dumps(CONFIG_DATA, indent=4, sort_keys=True))

    # do some checks
    if any(item not in CONFIG_DATA for item in ['api_key', 'tracker_first', 'url']):
        CONFIG_DATA['malformed'] = True


load_configuration()
###############################################################################


class jackett(object):
    name = 'Jackett'
    url = CONFIG_DATA['url']
    api_key = CONFIG_DATA['api_key']
    supported_categories = {
        'all': None,
        'anime': ['5070'],
        'books': ['8000'],
        'games': ['1000', '4000'],
        'movies': ['2000'],
        'music': ['3000'],
        'software': ['4000'],
        'tv': ['5000'],
    }

    def search(self, what, cat='all'):
        what = unquote(what)
        category = self.supported_categories[cat.lower()]

        # check for malformed configuration
        if 'malformed' in CONFIG_DATA:
            self.handle_error("malformed configuration file", what)
            return

        # user did not change api_key, trying to get from config
        if self.api_key == "YOUR_API_KEY_HERE":
            response = self.get_response(self.url + "/api/v2.0/server/config")
            if response is None:
                self.handle_error("connection error", what)
                return
            try:
                self.api_key = json.loads(response)['api_key']
            except Exception:
                # if login password is enabled we can't get the token
                self.handle_error("api key error", what)
                return

        # prepare jackett url
        params = [
            ('apikey', self.api_key),
            ('Query', what)
        ]
        if category is not None:
            for cat_id in category:
                params.append(('Category[]', cat_id))
        params = urlencode(params)
        jacket_url = self.url + "/api/v2.0/indexers/all/results?%s" % params
        response = self.get_response(jacket_url)
        if response is None:
            self.handle_error("connection error", what)
            return

        # process search results
        response_json = json.loads(response)
        for result in response_json['Results']:
            res = {
                'size': '%d B' % result['Size'],
                'seeds': result['Seeders'],
                'leech': result['Peers'],
                'engine_url': self.url,
                'desc_link': result['Comments']
            }

            if CONFIG_DATA['tracker_first']:
                res['name'] = '[%s] %s' % (result['Tracker'], result['Title'])
            else:
                res['name'] = '%s [%s]' % (result['Title'], result['Tracker'])

            if result['MagnetUri']:
                res['link'] = result['MagnetUri']
            else:
                res['link'] = result['Link']

            prettyPrinter(res)

    def get_response(self, query):
        response = None
        try:
            # we can't use helpers.retrieve_url because of redirects
            # we need the cookie processor to handle redirects
            opener = urllib_request.build_opener(urllib_request.HTTPCookieProcessor(CookieJar()))
            response = opener.open(query).read().decode('utf-8')
        except Exception:
            pass
        return response

    def handle_error(self, error_msg, what):
        # we need to print the search text to be displayed in qBittorrent when
        # 'Torrent names only' is enabled
        prettyPrinter({
            'seeds': -1,
            'size': -1,
            'leech': -1,
            'engine_url': self.url,
            'link': self.url,
            'desc_link': 'https://github.com/qbittorrent/search-plugins/wiki/How-to-configure-Jackett-plugin',  # noqa
            'name': "Jackett: %s! Click 'Go to description' button to open help. Configuration file: '%s' Search: '%s'" % (error_msg, CONFIG_PATH, what)  # noqa
        })


if __name__ == "__main__":
    jackett_se = jackett()
    jackett_se.search("harry potter", 'movies')
