import pytest

from ..engines import eztv


def test_eztv(capfd: pytest.CaptureFixture[str]) -> None:
    engine = eztv.eztv()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0
