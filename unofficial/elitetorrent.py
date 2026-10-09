# VERSION: 1.7
# CONTRIBUTORS: kalpakprod
# AUTHORS: iordic (iordicdev@gmail.com)
import re
import base64
import codecs
import sys
import time
from html import unescape
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen
from datetime import datetime
from html.parser import HTMLParser

from novaprinter import prettyPrinter
from helpers import download_file


def retrieve_url(url, timeout=15):
    with urlopen(Request(url, headers={'User-Agent': 'curl/8.18.0'}), timeout=timeout) as response:
        return unescape(response.read().decode('utf-8'))


MAX_DEPTH = 10

def deobfuscate_magnet(obfuscated):
    try:
        for i in range(MAX_DEPTH):
            obfuscated = base64.b64decode(obfuscated)
            decoded_value = codecs.decode(obfuscated.decode(encoding='utf-8'), 'rot_13')
            if 'magnet' in decoded_value:
                return decoded_value
    except:
        return None

def format_info(info):
    info['title'] = info['title'].group(0).lstrip('<h1>Descargar').rstrip('por torrent</h1>').strip() if info['title'] is not None else None
    info['link'] = next((magnet for encoded in (info['link'] or [])
                         if (magnet := deobfuscate_magnet(encoded[2:].rstrip('"')))
                         and re.match(r'^magnet:\?xt=urn:btih:[0-9a-fA-F]{40}(?:&|$)', magnet)), None)
    info['size'] = info['size'].group(0).split("</b>")[1].strip() if info['size'] is not None else '0'
    info['quality'] = info['quality'].group(0).lstrip('Calidad:</b>').strip() if info['quality'] is not None else None
    info['language'] = info['language'].group(0).lstrip('Idioma:</b>').strip() if info['language'] is not None else None
    date = info['date'].group(0).split('</b>', 1)[-1].strip() if info['date'] is not None else ''
    info['date'] = date if re.fullmatch(r'\d{2,4}-\d{2}-\d{2,4}', date) else -1
    info['seeds'] = info['seeds'].group(0).split(":")[-1].strip() if info['seeds'] is not None else -1
    info['leech'] = info['leech'].group(0).split(":")[-1].strip() if info['leech'] is not None  else -1
    
    info['formatted_name'] = info['title'] or ''
    info['formatted_name'] += ' [{}]'.format(info['language']) if info['language'] is not None else ''
    info['formatted_name'] += ' {} '.format(info['quality']) if info['quality'] is not None else ''
    info['formatted_name'] += '({})'.format(info['date']) if info['date'] is not None else ''

class elitetorrent(object):
    url = 'https://www.elitetorrent.com'
    name = 'Elitetorrent'
    # Page has only movies and tv series. Search box has no filters
    supported_categories = {'all': '0', 'movies': 'peliculas', 'tv': 'series'}

    def __init__(self):
        self.pages_limit = 2     # Limit of pages, more pages increase the time it takes

    def download_torrent(self, info):
        """ Unused :( """
        print(download_file(info))

    def search(self, what, cat='all'):
        deadline = time.monotonic() + 90
        query = urlencode({'s': unquote(what)})
        search_url = self.url + '/?' + query
        try:
            html = retrieve_url(search_url)
        except (OSError, ValueError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
            return
        number_pages = 1 if '/peliculas/' in html or '/series/' in html else 0

        # Get number of pages
        if "paginacion" in html:
            pages = re.findall(r'<a.*?class="pagina.*?</a>', html)
            if len(pages) > 0:
                last_page = pages[-1]
                last_page = re.findall(r'page/.*?/', last_page)[0]
                last_page = last_page.replace('/', '').replace('page', '')
                number_pages = int(last_page)

        # Only one page but there are results
        elif "Resultado de buscar" in html:
            number_pages = 1

        # Set number of pages depending by limit
        number_pages = number_pages if number_pages < self.pages_limit else self.pages_limit

        links = []
        
        for page in range(1, number_pages + 1):
            # Each page's url looks like: https://www.example.com/page/[1-9]*/?s=WHAT
            if page == 1:
                html = html.replace('\n', '')
            else:
                remaining = deadline - time.monotonic()
                if remaining < 1:
                    break
                url = self.url + '/page/' + str(page) + '/?' + query
                try:
                    html = retrieve_url(url, min(15, remaining)).replace('\n', '')
                except (OSError, ValueError):
                    break
            # I hate regex, check if selected category is films or tv, if its 'all' get both
            pattern = r'({0}/series/.*?/|{0}/peliculas/.*?/)'.format(self.url) if cat == "all" \
                        else r'{0}/{1}/.*?/'.format(self.url, self.supported_categories[cat])
            # Get all ocurrencies
            items = re.findall(pattern, html)
            for item in items:
                if item not in links:
                    links.append(item)

        for i in links:
            # Visiting individual results to get its attributes makes it so slow
            remaining = deadline - time.monotonic()
            if remaining < 1:
                break
            try:
                data = retrieve_url(i, min(15, remaining)).replace('\n', '')
            except (OSError, ValueError):
                continue
            info = {}
            info['title'] = re.search(r'<h1>Descargar .+ por torrent</h1>', data)
            info['link'] = re.findall(r'i=[-A-Za-z0-9+/]+={0,3}(?=[&\"\'])', data)
            info['size'] = re.search(r'Tama.?o:</b>\s*[0-9.]+\s*[KGM T]+B', data)
            info['quality'] = re.search(r'Calidad:</b> [0-9\.a-z\-]+', data)
            info['language'] = re.search(r'Idioma:</b>[a-zA-Zñ\ ]+', data)
            info['date'] = re.search(r'Fecha:</b>[\ 0-9\-]+', data)
            info['seeds'] = re.search(r'<b>Semillas</b>:[\ 0-9]*', data)
            info['leech'] = re.search(r'<b>Clientes</b>:[\ 0-9]*', data)
            format_info(info)                

            if info['title'] is None or info['link'] is None:
                continue    # decoding has failed, skip           

            pub_date = info['date']
            if pub_date != -1:
                try:
                    date_format = '%Y-%m-%d' if len(pub_date.split('-')[0]) == 4 else '%d-%m-%Y'
                    pub_date = round(datetime.timestamp(datetime.strptime(pub_date, date_format)))
                except ValueError:
                    pub_date = -1

            item = {
                'seeds' : int(info['seeds']) if str(info['seeds']).lstrip('-').isdigit() else -1,
                'leech' : int(info['leech']) if str(info['leech']).lstrip('-').isdigit() else -1,
                'name' : info['formatted_name'],
                'size' : info['size'],
                'desc_link' : i,
                'engine_url' : self.url,
                'link' : info['link'],
                'pub_date' : pub_date
            }
            # Prints in this format: link|name|size|seeds|leech|engine_url|desc_link|pub_date
            prettyPrinter(item)

# MIT License
# 
# Copyright (c) 2020 iordic
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
