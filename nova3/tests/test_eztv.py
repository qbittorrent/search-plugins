import io
import json
import urllib.request
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from ..engines import eztv


def test_eztv(capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []

    def api(request: Request, timeout: int = 20) -> io.BytesIO:
        parsed = urlparse(request.full_url)
        query = parse_qs(parsed.query)
        requests.append(request.full_url)
        if parsed.hostname == 'api.tvmaze.com':
            assert query == {'q': ['The Last of Us']}
            payload: object = [{'show': {'externals': {'imdb': 'tt3581920'}}}]
        else:
            assert query['imdb_id'] == ['3581920']
            page = int(query['page'][0])
            rows = [
                {'id': 1, 'season': '2', 'episode': '7', 'seeds': 3},
                {'id': 2, 'season': '1', 'episode': '7', 'seeds': 5},
            ] if page == 1 else [{'id': 3, 'season': '2', 'episode': '7', 'seeds': 8}]
            payload = {
                'torrents_count': 101,
                'torrents': [dict(row, imdb_id='3581920', title='The Last of Us S02E07 1080p',
                                  size_bytes='1024', peers=2, date_released_unix=1748221717,
                                  magnet_url='magnet:?xt=urn:btih:' + 'a' * 40) for row in rows],
            }
        return io.BytesIO(json.dumps(payload).encode())

    def blocked_html(*args: object, **kwargs: object) -> str:
        return ''

    # A blocked HTML endpoint is an external boundary, not the fallback under test.
    monkeypatch.setattr(eztv, 'retrieve_url', blocked_html)
    monkeypatch.setattr(urllib.request, 'urlopen', api)
    eztv.eztv().search('The%20Last%20of%20Us%20S02E07%201080p', 'tv')
    output = capfd.readouterr()
    assert output.err == ''
    rows = [line.split('|') for line in output.out.splitlines()]
    assert len(requests) == 3
    assert len(rows) == 2
    assert all(len(row) == 8 for row in rows)
    assert [row[3] for row in rows] == ['8', '3']
    assert rows[0][0] == 'magnet:?xt=urn:btih:' + 'a' * 40
    assert rows[0][2] == '1024'
    assert rows[0][6] == 'https://eztvx.to/ep/3/'
    assert rows[0][7] == '1748221717'
