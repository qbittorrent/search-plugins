# VERSION: 3.21
# AUTHORS: DrPurp, kalpakprod

import json
import re
import sys
import time
from html import unescape
from urllib.parse import unquote, urlencode, quote
from urllib.request import Request, urlopen
from helpers import download_file
from novaprinter import prettyPrinter


class eztvx(object):
    url = 'https://eztvx.to'
    name = 'EZTVX'
    supported_categories = {
        'all': 'all',
        'tv': 'tv'
    }


    def __init__(self):
        pass

    def download_torrent(self, info):
        print(download_file(info))

    def search(self, what, cat='all'):
        if cat not in self.supported_categories:
            return
        self.deadline = time.monotonic() + 75
        self.seen = set()
        keywords = unquote(what).replace('.', ' ')
        keywords = re.sub(r'\s+', ' ', keywords).strip()

        season, episode = self._parse_season_episode(keywords)
        title = self._clean_title(keywords)
        imdb_id = self._get_imdb_id(title)

        if not title:
            return
        self.quality = re.search(r'\b(?:480|720|1080|2160)p\b', keywords, re.I)
        if imdb_id:
            self._search_by_imdb(imdb_id, season=season, episode=episode)
        else:
            self._search_by_keywords(title, season=season, episode=episode)

    def _parse_season_episode(self, keywords):
        pattern = re.compile(
            r'\b(?:'
            r's(\d{1,2})e(\d{1,2})'
            r'|s(\d{1,2})'
            r'|e(\d{1,2})'
            r'|(\d{1,2})x(\d{1,2})'
            r'|season\s*(\d{1,2})\s*episode\s*(\d{1,2})'
            r'|season\s*(\d{1,2})'
            r')\b', re.IGNORECASE
        )
        season, episode = None, None
        match = pattern.search(keywords)
        if match:
            g = match.groups()
            if g[0] and g[1]:
                season, episode = int(g[0]), int(g[1])
            elif g[2]:
                season = int(g[2])
            elif g[3]:
                episode = int(g[3])
            elif g[4] and g[5]:
                season, episode = int(g[4]), int(g[5])
            elif g[6] and g[7]:
                season, episode = int(g[6]), int(g[7])
            elif g[8]:
                season = int(g[8])
        return season, episode

    def _clean_title(self, keywords):
        episode_pattern = re.compile(
            r'\b(?:'
            r's(\d{1,2})e(\d{1,2})'
            r'|s(\d{1,2})'
            r'|e(\d{1,2})'
            r'|(\d{1,2})x(\d{1,2})'
            r'|season\s*(\d{1,2})\s*episode\s*(\d{1,2})'
            r'|season\s*(\d{1,2})'
            r')\b', re.IGNORECASE
        )
        junk_pattern = re.compile(
            r'\b(1080p|720p|480p|2160p|4k|x264|x265|hevc|avc|bluray|'
            r'webrip|web-dl|hdtv|dvdrip|proper|repack|extended|'
            r'theatrical|directors\.cut|remux)\b', re.IGNORECASE
        )
        cleaned = episode_pattern.sub('', keywords)
        cleaned = junk_pattern.sub('', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _matches_season_episode(self, title, season, episode):
        if season is None and episode is None:
            return True
        pattern = re.compile(
            r'\b(?:'
            r's(\d{1,2})e(\d{1,2})'
            r'|s(\d{1,2})'
            r'|e(\d{1,2})'
            r'|(\d{1,2})x(\d{1,2})'
            r'|season\s*(\d{1,2})\s*episode\s*(\d{1,2})'
            r'|season\s*(\d{1,2})'
            r')\b', re.IGNORECASE
        )
        s, e = None, None
        match = pattern.search(title)
        if match:
            g = match.groups()
            if g[0] and g[1]:
                s, e = int(g[0]), int(g[1])
            elif g[2]:
                s = int(g[2])
            elif g[3]:
                e = int(g[3])
            elif g[4] and g[5]:
                s, e = int(g[4]), int(g[5])
            elif g[6] and g[7]:
                s, e = int(g[6]), int(g[7])
            elif g[8]:
                s = int(g[8])
        if season is not None and episode is None:
            return s == season
        if episode is not None and season is None:
            return e == episode
        return s == season and e == episode

    def fetch(self, url, data=None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        with urlopen(Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json,text/html'}), timeout=min(12, remaining)) as response:
            payload = response.read(4 * 1024 * 1024 + 1)
            if len(payload) > 4 * 1024 * 1024:
                raise ValueError('response too large')
            return payload.decode(response.headers.get_content_charset() or 'utf-8')

    def _get_imdb_id(self, title):
        if not title:
            return None
        if re.fullmatch(r'tt[0-9]+', title):
            return title[2:]
        try:
            show = json.loads(self.fetch('https://api.tvmaze.com/singlesearch/shows?' + urlencode({'q': title})))
            imdb = show.get('externals', {}).get('imdb')
            return imdb[2:] if isinstance(imdb, str) and re.fullmatch(r'tt[0-9]+', imdb) else None
        except (OSError, ValueError, AttributeError):
            return None

    def _search_by_imdb(self, imdb_id, season=None, episode=None):
        page = 1
        while True:
            api_url = '{}/api/get-torrents?limit=100&page={}&imdb_id={}'.format(
                self.url, page, imdb_id
            )
            try:
                response = self.fetch(api_url)
                data = json.loads(response)
                if not isinstance(data, dict) or not isinstance(data.get('torrents'), list):
                    raise ValueError('invalid native API response')
            except (OSError, ValueError) as error:
                print(self.name + ': ' + type(error).__name__, file=sys.stderr)
                break

            torrents = data.get('torrents', [])
            if not torrents:
                break

            for torrent in torrents:
                title = torrent.get('title', '')
                if str(torrent.get('imdb_id')) == imdb_id and self._matches_season_episode(title, season, episode) and (not self.quality or self.quality[0].casefold() in title.casefold()):
                    self._print_result(torrent)

            total = data.get('torrents_count', 0)
            if page * 100 >= int(total) or len(torrents) < 100:
                break
            page += 1

    def _search_by_keywords(self, keywords, season=None, episode=None):
        # The native JSON API filters by IMDb, not its ignored Keywords parameter.
        try:
            document = self.fetch(self.url + '/search/' + quote(keywords.replace(' ', '-'), safe=''), b'layout=def_wlinks')
            for row in re.findall(r'<tr\b[^>]*>.*?</tr>', document, re.S):
                episode_link = re.search(r'<a[^>]*href=["\x27]([^"\x27]+)["\x27][^>]*class=["\x27]epinfo["\x27][^>]*title=["\x27]([^"\x27]+)', row)
                magnet = re.search(r'(magnet:\?xt=urn:btih:[^"\x27<>\s]+)', unescape(row))
                if not episode_link or not magnet:
                    continue
                title = unescape(episode_link[2]).split(' (')[0]
                if not all(word.casefold() in title.casefold() for word in keywords.split()) or not self._matches_season_episode(title, season, episode):
                    continue
                if self.quality and self.quality[0].casefold() not in title.casefold():
                    continue
                self._print_result({'title': title, 'magnet_url': magnet[1], 'episode_url': self.url + '/' + episode_link[1].lstrip('/')})
        except (OSError, ValueError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)

    def _print_result(self, torrent):
        link = torrent.get('magnet_url') or torrent.get('torrent_url', '')
        match = re.match(r'^magnet:\?xt=urn:btih:([A-Fa-f0-9]{40}|[A-Za-z2-7]{32})(?:&|$)', link)
        if not match or match[1].upper() in ('0' * 40, 'A' * 32) or match[1].lower() in self.seen:
            return
        self.seen.add(match[1].lower())
        seeds = str(torrent.get('seeds', -1))
        peers = str(torrent.get('peers', -1))
        result = {
            'link':       link,
            'name':       torrent.get('title', 'Unknown'),
            'size':       self._format_size(torrent.get('size_bytes', -1)),
            'seeds':      int(seeds) if seeds.isdigit() else -1,
            'leech':      int(peers) if peers.isdigit() else -1,
            'engine_url': self.url,
            'desc_link':  torrent.get('episode_url', self.url + '/ep/' + str(torrent.get('id', '')) + '/'),
            'pub_date': torrent.get('date_released_unix') or -1,
        }
        prettyPrinter(result)

    def _format_size(self, size_bytes):
        try:
            size_bytes = int(size_bytes)
        except (TypeError, ValueError):
            return '-1'
        if size_bytes < 0:
            return '-1'
        elif size_bytes < 1024 ** 2:
            return '{:.1f} KB'.format(size_bytes / 1024)
        elif size_bytes < 1024 ** 3:
            return '{:.1f} MB'.format(size_bytes / (1024 ** 2))
        else:
            return '{:.2f} GB'.format(size_bytes / (1024 ** 3))