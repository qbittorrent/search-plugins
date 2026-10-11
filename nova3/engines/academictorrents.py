# SPDX-License-Identifier: GPL-3.0-only
# CONTRIBUTORS: kalpakprod (first-run cache directory and request timeout)
# VERSION: 1.5
# AUTHORS: LightDestory (https://github.com/LightDestory) achernet (https://github.com/achernet)
import concurrent.futures
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from urllib import request

from helpers import retrieve_url, download_file
from novaprinter import prettyPrinter, SearchResults

DATABASE_URL = "https://academictorrents.com/database.xml"
home = str(Path.home())
system_paths = {
    "win32": f"{home}/AppData/Roaming",
    "linux": f"{home}/.local/share",
    "darwin": f"{home}/Library/Application Support",
}
cache_path = Path(f"{system_paths[sys.platform]}/qbit_plugins_data/academic_cache.xml")


class academictorrents(object):
    url = "https://academictorrents.com/"
    name = "AcademicTorrents"
    """ 
    ***TLDR; It is safer to force an 'all' research***
        AcademicTorrents categories are very specific
        qBittorrent does not provide enough categories to implement a good filtering.
    """
    supported_categories = {"all": "0"}

    def __init__(self, output=True):
        self.output = output
        self.filters = []

    def _torrent_filter(self, item) -> bool:
        title: str = item.findtext("title").lower()
        desc: str = item.findtext("description").lower()
        for f in self.filters:
            if f in title or f in desc:
                return True
        return False

    def _retrieve_database(self):
        folder_path = Path(f"{system_paths[sys.platform]}/qbit_plugins_data")
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        self._update_database_cache()
        with open(cache_path, encoding="utf-8") as f:
            lines = f.readlines()[1:]
            return ET.fromstring("".join(lines))

    def _update_database_cache(self):
        if cache_path.exists():
            current_date = str(date.today())
            with open(cache_path, encoding="utf-8") as f:
                saved_date = f.readline().rstrip()
                if current_date == saved_date:
                    return
        req = request.urlopen(DATABASE_URL, timeout=20)
        db_local_text = req.read().decode("utf-8")
        f = open(cache_path, "w", encoding="utf-8")
        f.write(f"{str(date.today())}\n")
        f.write(db_local_text)
        f.close()
        req.close()

    def resolve_search_result(self, torrent) -> SearchResults:
        data = {
            "link": f"{self.url}download/{torrent.findtext('infohash')}.torrent",
            "name": torrent.findtext("title"),
            "size": torrent.findtext("size"),
            "engine_url": self.url,
            "desc_link": torrent.findtext("link"),
        }
        torrent_desc = retrieve_url(f"{data['desc_link']}/tech")
        peer_data = re.search(
            "<tr><td>Mirrors</td><td>(\\d+)\\s*complete,\\s*(\\d+)\\s*downloading",
            torrent_desc,
        )
        if peer_data:
            data["seeds"] = int(peer_data.group(1))
            data["leech"] = int(peer_data.group(2))
        else:
            data["leech"] = -1
            data["seeds"] = -1
        added_date_data = re.search(
            "<tr><td>Added</td><td>([^<]+)</td></tr>", torrent_desc
        )
        date_str = added_date_data.group(1)
        data["pub_date"] = int(datetime.fromisoformat(date_str).timestamp())
        return SearchResults(**data)

    def download_torrent(self, info):
        print(download_file(info))

    def search(self, what, cat="all"):
        self.filters = [f.lower() for f in re.split("%20|\\s", str(what))]
        db = self._retrieve_database()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for torrent in db.findall("channel/item"):
                if self._torrent_filter(torrent):
                    futures.append(executor.submit(self.resolve_search_result, torrent))
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if self.output:
                    prettyPrinter(result)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See https://www.gnu.org/licenses/ for the full licence text.
