import pytest

from ..engines import solidtorrents


def test_solidtorrents(capfd: pytest.CaptureFixture[str]) -> None:
    engine = solidtorrents.solidtorrents()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0
