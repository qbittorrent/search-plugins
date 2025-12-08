# qBittorrent Search Engine Plugin
# Supported qBittorrent versions: 4.4+
# VERSION: 2.2
# SkTorrent.eu

import os
import re
import urllib.parse
import urllib.request
import http.cookiejar as cookielib
import tempfile 
from html.parser import HTMLParser
from novaprinter import prettyPrinter

# ==========================================================
# CHANGE ONLY THESE TWO LINES
USERNAME = "REPLACE_ME"
PASSWORD = "REPLACE_ME"
# ==========================================================

BASE_URL = "https://sktorrent.eu/torrent"
COOKIE_FILE = os.path.join(tempfile.gettempdir(), "sktorrent.cookies") 

class sktorrent(object):
    url = BASE_URL
    name = "SkTorrent"
    
    # Standard Categories (English Only to prevent errors)
    supported_categories = {
        'all': '0',
        'movies': '1',
        'tv': '16',
        'music': '2',
        'games': '18',
        'anime': '5',
        'software': '21',
        'books': '23',
        'xxx': '9'
    }

    def __init__(self):
        self.cj = cookielib.LWPCookieJar()
        if os.path.isfile(COOKIE_FILE):
            try: self.cj.load(COOKIE_FILE, ignore_discard=True, ignore_expires=True)
            except: pass
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.opener.addheaders = [("User-Agent", "Mozilla/5.0")]
        self.login()
        self.enable_hidden_categories()

    def login(self):
        try:
            self.opener.open(BASE_URL + "/torrents_v2.php", timeout=5)
            return
        except: pass
        
        data = urllib.parse.urlencode({"username": USERNAME, "password": PASSWORD}).encode()
        try:
            self.opener.open(BASE_URL + "/takelogin.php", data)
            self.cj.save(COOKIE_FILE, ignore_discard=True, ignore_expires=True)
        except: pass

    def enable_hidden_categories(self):
        # Enables xXx, Software, Mobile categories
        data = urllib.parse.urlencode({
            "predx": "x", "predp": "p", "predulozit": "ulozit"
        }).encode()
        try:
            self.opener.open(BASE_URL + "/torrents_v2.php?active=0", data, timeout=5)
        except: pass

    def download_torrent(self, url):
        try:
            data = self.opener.open(url).read()
            fd, path = tempfile.mkstemp(suffix=".torrent")
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            print(path + " " + url)
        except: pass
        
    def search(self, what, cat="all"):
        # This groups the specific SkTorrent IDs into main categories
        # Movies = CZ/SK, 3D, HD, DVD, Bluray, UHD, Dubbed, Subbed, etc.
        cat_map = {
            'all': '0',
            'movies': '1,3,14,15,19,20,28,29,31,43',
            'tv': '16,17,42',       # Series, Docs, TV Shows
            'music': '2,22,26,45',  # Music, DJ, Video, OST
            'games': '18,30,37,59,60,63', # PC, Console, Linux, Mac, VR, XXX Games
            'anime': '5',           # Cartoons
            'software': '21,27',    # Apps, Mobile
            'books': '23,24',       # Books, Spoken Word
            'xxx': '9'
        }
        
        # Get the grouped IDs based on user selection
        cat_ids = cat_map.get(cat, '0')
        page = 0
        what = urllib.parse.quote(what)
        
        while page < 5:
            url = "{0}/torrents_v2.php?search={1}&category={2}&active=0&page={3}".format(BASE_URL, what, cat_ids, page)
            try:
                html = self.opener.open(url, timeout=10).read().decode("utf-8", "ignore")
            except: break
            
            p = Parser()
            p.feed(html)
            if not p.results: break
            
            for r in p.results:
                prettyPrinter(r)
            page += 1

class Parser(HTMLParser):
    def __init__(self):
        super(Parser, self).__init__() 
        self.results = []
        self.t = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href", "").startswith("details.php"):
            m = re.search(r"id=([a-f0-9]{40})", a["href"])
            if m:
                self.t = {
                    "link": "{0}/download.php?id={1}".format(BASE_URL, m.group(1)),
                    "name": "", "size": "-1", "seeds": -1, "leech": -1,
                    "engine_url": BASE_URL,
                    "desc_link": "{0}/{1}".format(BASE_URL, a["href"])
                }

    def handle_data(self, data):
        if self.t:
            d = data.strip()
            if not self.t["name"] and d: self.t["name"] = d
            if "Velkost" in d:
                m = re.search(r"([\d.,]+\s*[KMGT]B)", d)
                if m: self.t["size"] = m.group(1).replace(",", ".")
            if d.startswith(("Odosielaju", "Odosielaju")): 
                m = re.search(r"\d+", d)
                if m: self.t["seeds"] = int(m.group(0))
            if d.startswith(("Stahuju", "Stahuju")):
                m = re.search(r"\d+", d)
                if m:
                    self.t["leech"] = int(m.group(0))
                    if self.t["name"] and self.t["size"] != "-1":
                        self.results.append(self.t)
                    self.t = None
