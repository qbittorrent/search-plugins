from urllib.parse import parse_qs, urlparse

import pytest

from ..engines import jackett


def test_jackett(capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[str] = []
    document = '''<rss xmlns:torznab="http://torznab.com/schemas/2015/feed"><channel><item>
        <title>Ubuntu 26.04</title><jackettindexer>Example</jackettindexer><size>1024</size>
        <comments>https://example.org/topic/1</comments><pubDate>Tue, 01 Jan 2019 00:00:00 +0000</pubDate>
        <torznab:attr name="magneturl" value="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/>
        <torznab:attr name="seeders" value="42"/><torznab:attr name="peers" value="45"/>
        </item></channel></rss>'''

    def api(self: jackett.jackett, url: str) -> str:
        requested.append(url)
        return document

    monkeypatch.setattr(jackett.jackett, 'api_key', 'test-key')
    monkeypatch.setattr(jackett.jackett, 'thread_count', 1)
    monkeypatch.setattr(jackett.jackett, 'get_response', api)
    jackett.jackett().search('Ubuntu%2026.04')
    output = capfd.readouterr()
    assert output.err == ''
    fields = output.out.strip().split('|')
    assert len(fields) == 8
    assert fields[0] == 'magnet:?xt=urn:btih:' + 'a' * 40
    assert fields[1] == 'Ubuntu 26.04 [Example]'
    assert fields[2:5] == ['1024', '42', '3']
    assert fields[6] == 'https://example.org/topic/1'
    assert fields[7] == '1546300800'
    assert parse_qs(urlparse(requested[0]).query) == {'apikey': ['test-key'], 'q': ['Ubuntu 26.04']}
