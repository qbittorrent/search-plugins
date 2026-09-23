# VERSION: 1.25
# AUTHORS: nindogo
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)
# LOCAL FIX: use the public TVmaze and EZTV APIs because the EZTV HTML search
# endpoint is protected by a Cloudflare challenge that Nova plugins cannot run.

import json
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote, unquote

from helpers import retrieve_url
from novaprinter import prettyPrinter


class eztv:
    name = "EZTV"
    url = "https://eztvx.to/"
    supported_categories = {"all": "all", "tv": "tv"}

    _episode_pattern = re.compile(
        r"\b(?:s(\d{1,2})e(\d{1,2})|s(\d{1,2})|(\d{1,2})x(\d{1,2}))\b",
        re.IGNORECASE,
    )
    _release_tags = re.compile(
        r"\b(?:2160p|1080p|720p|480p|4k|x264|x265|hevc|avc|bluray|"
        r"webrip|web[- .]?dl|hdtv|dvdrip|proper|repack|remux)\b",
        re.IGNORECASE,
    )

    @staticmethod
    def _json(url: str) -> Dict[str, Any]:
        payload = retrieve_url(url, unescape_html_entities=False)
        result: Dict[str, Any] = json.loads(payload) if payload else {}
        return result

    def _parse_query(self, query: str) -> Tuple[str, Optional[int], Optional[int]]:
        text = unquote(query).replace(".", " ").replace("-", " ")
        text = re.sub(r"\s+", " ", text).strip()
        match = self._episode_pattern.search(text)

        season = episode = None
        if match:
            groups = match.groups()
            if groups[0] and groups[1]:
                season, episode = int(groups[0]), int(groups[1])
            elif groups[2]:
                season = int(groups[2])
            elif groups[3] and groups[4]:
                season, episode = int(groups[3]), int(groups[4])

        title = self._episode_pattern.sub(" ", text)
        title = self._release_tags.sub(" ", title)
        title = re.sub(r"\s+", " ", title).strip()
        return title, season, episode

    def _lookup_imdb_id(self, title: str) -> Optional[str]:
        if not title:
            return None
        try:
            show = self._json(
                "https://api.tvmaze.com/singlesearch/shows?q="
                + quote(title, safe="")
            )
            imdb_id = (show.get("externals") or {}).get("imdb")
            if imdb_id:
                imdb_id = str(imdb_id)
                return imdb_id[2:] if imdb_id.startswith("tt") else imdb_id
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        return None

    @staticmethod
    def _matches_episode(
        title: str, season: Optional[int], episode: Optional[int]
    ) -> bool:
        if season is None and episode is None:
            return True

        patterns = [
            re.compile(r"\bS(\d{1,2})E(\d{1,2})\b", re.IGNORECASE),
            re.compile(r"\b(\d{1,2})x(\d{1,2})\b", re.IGNORECASE),
        ]
        found_season = found_episode = None
        for pattern in patterns:
            match = pattern.search(title)
            if match:
                found_season, found_episode = map(int, match.groups())
                break

        if season is not None and found_season != season:
            return False
        return episode is None or found_episode == episode

    def _emit(self, torrent: Dict[str, Any]) -> None:
        link = torrent.get("magnet_url") or torrent.get("torrent_url")
        if not link:
            return

        torrent_id = torrent.get("id")
        desc_link = self.url
        if torrent_id:
            desc_link = f"{self.url}ep/{torrent_id}/"

        prettyPrinter(
            {
                "link": link,
                "name": torrent.get("title") or torrent.get("filename") or "Unknown",
                "size": f"{torrent.get('size_bytes', -1)} B",
                "seeds": torrent.get("seeds", -1),
                "leech": torrent.get("peers", -1),
                "engine_url": self.url,
                "desc_link": desc_link,
                "pub_date": torrent.get("date_released_unix", -1),
            }
        )

    def search(self, what: str, cat: str = "all") -> None:
        title, season, episode = self._parse_query(what)
        imdb_id = self._lookup_imdb_id(title)
        if not imdb_id:
            return

        page = 1
        while page <= 10:
            try:
                data = self._json(
                    f"{self.url}api/get-torrents?limit=100&page={page}"
                    f"&imdb_id={quote(imdb_id, safe='')}"
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                return

            torrents = data.get("torrents") or []
            for torrent in torrents:
                torrent_title = torrent.get("title") or torrent.get("filename") or ""
                if self._matches_episode(torrent_title, season, episode):
                    self._emit(torrent)

            total = int(data.get("torrents_count") or 0)
            if not torrents or page * 100 >= total:
                break
            page += 1
