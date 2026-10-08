import json
from urllib.parse import parse_qs, urlparse

import pytest

from ..engines import torrentscsv


def test_torrentscsv(capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[str] = []

    def api(url: str) -> str:
        requested.append(url)
        return json.dumps({'torrents': [
            {'infohash': 'a' * 40, 'name': 'Ubuntu 26.04', 'size_bytes': 1024,
             'seeders': 42, 'leechers': 3, 'created_unix': 1748221717},
        ]})

    monkeypatch.setattr(torrentscsv, 'retrieve_url', api)
    torrentscsv.torrentscsv().search('Ubuntu%2026.04')
    output = capfd.readouterr()
    assert output.err == ''
    fields = output.out.strip().split('|')
    assert len(fields) == 8
    assert fields[0].startswith('magnet:?xt=urn:btih:' + 'a' * 40 + '&')
    assert fields[1] == 'Ubuntu 26.04'
    assert fields[2:5] == ['1024', '42', '3']
    assert fields[7] == '1748221717'
    assert parse_qs(urlparse(requested[0]).query) == {'size': ['100'], 'q': ['Ubuntu 26.04']}
