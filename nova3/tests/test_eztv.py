import pytest

from ..engines import eztv


def test_eztv(capfd: pytest.CaptureFixture[str]) -> None:
    engine = eztv.eztv()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0


def test_eztv_api_search(monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    engine = eztv.eztv()
    urls: list[str] = []

    def fake_json(url: str) -> object:
        urls.append(url)
        return {
            "torrents_count": 2,
            "torrents": [
                {
                    "id": 1,
                    "title": "Silver Harbor S09E12 1080p",
                    "magnet_url": "magnet:?xt=urn:btih:one",
                    "size_bytes": 1024,
                    "seeds": 10,
                    "peers": 2,
                    "date_released_unix": 123,
                    "season": "9",
                    "episode": "12",
                },
                {
                    "id": 2,
                    "title": "Silver Harbor S09E13 1080p",
                    "magnet_url": "magnet:?xt=urn:btih:two",
                    "size_bytes": 2048,
                    "seeds": 5,
                    "peers": 1,
                    "date_released_unix": 456,
                    "season": "9",
                    "episode": "13",
                },
            ],
        }

    monkeypatch.setattr(eztv, "_json", fake_json)
    engine.search("silver harbor s09e12", "tv")

    captured_output = capfd.readouterr()
    assert captured_output.err == ""
    assert "Silver Harbor S09E12 1080p" in captured_output.out
    assert "Silver Harbor S09E13 1080p" not in captured_output.out
    assert urls == ["https://eztvx.to/api/get-torrents?limit=100&page=1"]


def test_eztv_imdb_id_search(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = eztv.eztv()
    urls: list[str] = []

    def fake_json(url: str) -> object:
        urls.append(url)
        return {"torrents_count": 0, "torrents": []}

    monkeypatch.setattr(eztv, "_json", fake_json)
    engine.search("Silver Harbor tt1234567")

    assert urls == ["https://eztvx.to/api/get-torrents?limit=100&page=1&imdb_id=1234567"]


def test_eztv_imdb_search_checks_all_available_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    urls: list[str] = []

    def fake_json(url: str) -> object:
        urls.append(url)
        return {"torrents_count": 1001, "torrents": [{"title": "Silver Harbor"}]}

    monkeypatch.setattr(eztv, "_json", fake_json)
    eztv.eztv().search("tt1234567")

    assert len(urls) == 11
    assert urls[-1].endswith("page=11&imdb_id=1234567")


def test_eztv_matches_unicode_titles(monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    def fake_json(_url: str) -> object:
        return {
            "torrents_count": 1,
            "torrents": [{"title": "Étoile du Nord", "magnet_url": "magnet:?xt=urn:btih:one"}],
        }

    monkeypatch.setattr(eztv, "_json", fake_json)
    eztv.eztv().search("étoile nord")

    assert "Étoile du Nord" in capfd.readouterr().out
