# VERSION: 1.25
# AUTHORS: nindogo
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)

import json
import re
from typing import Dict, List, Optional, Tuple, cast
from urllib.parse import unquote

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
    _imdb_pattern = re.compile(r"(?:tt)?(\d{7,9})", re.IGNORECASE)

    @staticmethod
    def _json(url: str) -> object:
        payload = retrieve_url(url, unescape_html_entities=False)
        return json.loads(payload) if payload else {}

    def _parse_query(self, query: str) -> Tuple[str, Optional[int], Optional[int], Optional[str]]:
        text = unquote(query).replace(".", " ").replace("-", " ")
        text = re.sub(r"\s+", " ", text).strip()
        imdb_match = self._imdb_pattern.fullmatch(text)
        if imdb_match:
            return "", None, None, imdb_match.group(1)

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
        title = re.sub(r"\s+", " ", title).strip()
        return title, season, episode, None

    @staticmethod
    def _matches_title(title: str, query: str) -> bool:
        words = re.findall(r"[a-z0-9]+", query.casefold())
        if not words:
            return True
        title_words = re.findall(r"[a-z0-9]+", title.casefold())
        iterator = iter(title_words)
        return all(any(word == candidate for candidate in iterator) for word in words)

    @classmethod
    def _matches_episode(
        cls, torrent: Dict[str, object], season: Optional[int], episode: Optional[int]
    ) -> bool:
        if season is None and episode is None:
            return True

        torrent_season = torrent.get("season")
        torrent_episode = torrent.get("episode")
        if torrent_season is None or torrent_episode is None:
            title = torrent.get("title") or torrent.get("filename")
            if not isinstance(title, str):
                return False
            match = cls._episode_pattern.search(title)
            if not match:
                return False
            groups = match.groups()
            if groups[0] and groups[1]:
                torrent_season, torrent_episode = groups[0], groups[1]
            elif groups[3] and groups[4]:
                torrent_season, torrent_episode = groups[3], groups[4]
            else:
                return False

        try:
            return (season is None or int(cast(str, torrent_season)) == season) and (
                episode is None or int(cast(str, torrent_episode)) == episode
            )
        except (TypeError, ValueError):
            return False

    def _emit(self, torrent: Dict[str, object]) -> None:
        link = torrent.get("magnet_url") or torrent.get("torrent_url")
        if not isinstance(link, str) or not link:
            return

        torrent_id = torrent.get("id")
        desc_link = f"{self.url}ep/{torrent_id}/" if torrent_id else self.url
        name = torrent.get("title") or torrent.get("filename")
        if not isinstance(name, str):
            name = "Unknown"
        prettyPrinter(
            {
                "link": link,
                "name": name,
                "size": f"{self._int(torrent.get('size_bytes'))} B",
                "seeds": self._int(torrent.get("seeds")),
                "leech": self._int(torrent.get("peers")),
                "engine_url": self.url,
                "desc_link": desc_link,
                "pub_date": self._int(torrent.get("date_released_unix")),
            }
        )

    @staticmethod
    def _int(value: object) -> int:
        try:
            return int(value) if isinstance(value, (int, str)) else -1
        except ValueError:
            return -1

    def search(self, what: str, cat: str = "all") -> None:
        title, season, episode, imdb_id = self._parse_query(what)
        if not title and imdb_id is None and season is None:
            return

        # EZTV's API only supports IMDb ID filtering. For a title query, scan
        # its recent pages and filter results locally without querying other sites.
        for page in range(1, 11):
            url = f"{self.url}api/get-torrents?limit=100&page={page}"
            if imdb_id is not None:
                url += f"&imdb_id={imdb_id}"
            try:
                response = self._json(url)
            except (TypeError, ValueError):
                return
            if not isinstance(response, dict):
                return
            data = cast(Dict[str, object], response)
            raw_torrents = data.get("torrents")
            if not isinstance(raw_torrents, list) or not raw_torrents:
                return
            torrents = cast(List[object], raw_torrents)
            for raw_torrent in torrents:
                if not isinstance(raw_torrent, dict):
                    continue
                torrent = cast(Dict[str, object], raw_torrent)
                torrent_title = torrent.get("title") or torrent.get("filename")
                if not isinstance(torrent_title, str):
                    continue
                if self._matches_title(torrent_title, title) and self._matches_episode(
                    torrent, season, episode
                ):
                    self._emit(torrent)

            total = data.get("torrents_count")
            try:
                if page * 100 >= int(cast(str, total)):
                    return
            except (TypeError, ValueError):
                return
