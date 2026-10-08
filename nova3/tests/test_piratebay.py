import json
from urllib.parse import parse_qs, urlparse

import pytest

from ..engines import piratebay


def test_piratebay(capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    queries: list[str] = []

    def api(self: piratebay.piratebay, url: str) -> str:
        queries.append(url)
        return json.dumps([
            {'info_hash': '0' * 40},
            {'info_hash': 'a' * 40, 'id': '123', 'name': 'Ubuntu & Debian', 'size': '1024',
             'seeders': '42', 'leechers': '3', 'added': '1748221717'},
        ])

    monkeypatch.setattr(piratebay.piratebay, 'retrieve_url', api)
    piratebay.piratebay().search('Ubuntu%20%26%20Debian')
    output = capfd.readouterr()
    assert output.err == ''
    fields = output.out.strip().split('|')
    assert len(fields) == 8
    assert fields[0].startswith('magnet:?xt=urn:btih:' + 'a' * 40 + '&')
    assert fields[2:5] == ['1024', '42', '3']
    assert fields[6] == 'https://thepiratebay.org/description.php?id=123'
    assert fields[7] == '1748221717'
    assert parse_qs(urlparse(queries[0]).query) == {'q': ['Ubuntu & Debian']}


@pytest.mark.parametrize('body', ['', '<html>Blocked</html>', '{}'])
def test_unavailable_api_never_crashes_or_prints_fake_results(
    body: str, capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    def api(self: piratebay.piratebay, url: str) -> str:
        return body

    monkeypatch.setattr(piratebay.piratebay, 'retrieve_url', api)
    piratebay.piratebay().search('Ubuntu')
    output = capfd.readouterr()
    assert output.out == ''
    assert output.err.startswith('The Pirate Bay:')
