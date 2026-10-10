import pytest

from ..engines import torrentproject


def test_torrentproject(capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    search_url = 'https://torrentproject.cc/browse?t=Ubuntu&p=0'
    detail_url = 'https://torrentproject.cc/t3-123/ubuntu-torrent.html'
    magnet = 'magnet:?xt=urn:btih:' + '0123456789abcdef0123456789abcdef01234567'
    document = '''<div id="similarfiles"><div><span>
        <a href="/t3-123/ubuntu-torrent.html">Ubuntu 26.04</a><span>Apps</span></span>
        <span>42</span><span>3</span><span>2026-10-01 12:00:00</span><span>1.5 GB</span></div></div>
        <div id="navcnt"></div>'''
    requested: list[str] = []

    def site(url: str) -> str:
        requested.append(url)
        if url == search_url:
            return document
        assert url == detail_url
        return '<a href="https://example.org/?url=magnet%3A%3Fxt%3Durn%3Abtih%3A' + '0123456789abcdef0123456789abcdef01234567' + '">download</a>'

    monkeypatch.setattr(torrentproject, 'retrieve_url', site)
    engine = torrentproject.torrentproject()
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


def test_direct_magnet_keeps_encoded_query_values(
    capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    magnet = 'magnet:?xt=urn:btih:' + 'a' * 40 + '&dn=A%26B&tr=https%3A%2F%2Fexample.org%2Fannounce%3Fa%3D1%26b%3D2'

    def site(url: str) -> str:
        return '<a href="' + magnet + '">download</a>'

    monkeypatch.setattr(torrentproject, 'retrieve_url', site)
    torrentproject.torrentproject().download_torrent('https://torrentproject.cc/topic')
    output = capfd.readouterr()
    assert output.err == ''
    assert output.out.strip() == magnet + ' https://torrentproject.cc/topic'
