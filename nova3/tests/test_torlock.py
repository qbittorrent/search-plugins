import io
import urllib.request
from email.message import Message
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from ..engines import torlock


class Response(io.BytesIO):
    def __init__(self, document: str) -> None:
        super().__init__(document.encode())
        self.headers = Message()
        self.headers['Content-Type'] = 'text/html; charset=utf-8'


def test_torlock(capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    document = '''<article><table><tr><td><a href="/torrent/123/dream-scenario.html">Dream Scenario</a></td>
        <td class="td">10/07/2026</td><td class="ts">1.5 GB</td>
        <td class="tul">42</td><td class="tdl">3</td></tr></table></article>'''
    requests: list[str] = []

    def site(request: Request, timeout: int = 30, **kwargs: object) -> Response:
        if request.get_header('User-agent') != 'curl/8.18.0':
            raise HTTPError(request.full_url, 403, 'Forbidden', Message(), None)
        requests.append(request.full_url)
        return Response(document)

    monkeypatch.setattr(torlock, 'urlopen', site, raising=False)
    monkeypatch.setattr(urllib.request, 'urlopen', site)
    torlock.torlock().search('Dream%20Scenario', 'movies')
    output = capfd.readouterr()
    assert output.err == ''
    fields = output.out.strip().split('|')
    assert len(fields) == 8
    assert fields[0] == 'https://www.torlock.com/tor/123.torrent'
    assert fields[1] == 'Dream Scenario'
    assert fields[2:5] == ['1610612736', '42', '3']
    assert fields[6] == 'https://www.torlock.com/torrent/123/dream-scenario.html'
    assert requests == ['https://www.torlock.com/movie/torrents/Dream-Scenario.html?sort=seeds&page=1']
