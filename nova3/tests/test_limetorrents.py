import pytest

from ..engines import limetorrents


def test_limetorrents(capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    magnet = 'magnet:?xt=urn:btih:' + '0123456789abcdef0123456789abcdef01234567'
    search_url = 'https://www.limetorrents.fun/search/all/Ubuntu/seeds/1/'
    detail_url = 'https://www.limetorrents.fun/ubuntu.html'
    document = '''<table class="table2"><tr bgcolor="#F4F4F4">
        <td><a href="/ubuntu.html">Ubuntu 26.04</a></td><td>1 day</td>
        <td>1.5 GB</td><td>42</td><td>3</td></tr></table>'''
    requested: list[str] = []

    def site(url: str) -> str:
        requested.append(url)
        if url == search_url:
            return document
        assert url == detail_url
        return '<a href="' + magnet + '">download</a>'

    monkeypatch.setattr(limetorrents, 'retrieve_url', site)
    engine = limetorrents.limetorrents()
    engine.search('Ubuntu')
    output = capfd.readouterr()
    assert output.err == ''
    fields = output.out.strip().split('|')
    assert len(fields) == 8
    assert fields[0] == detail_url
    assert fields[1] == 'Ubuntu 26.04'
    assert fields[2:5] == ['1610612736', '42', '3']
    engine.download_torrent(fields[0])
    output = capfd.readouterr()
    assert output.out.strip() == magnet + ' ' + detail_url
    assert requested == [search_url, detail_url]
