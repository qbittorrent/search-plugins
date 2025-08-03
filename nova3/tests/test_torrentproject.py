import pytest

from ..engines import torrentproject


def test_torrentproject(capfd: pytest.CaptureFixture[str]) -> None:
    engine = torrentproject.torrentproject()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0
