import pytest

from ..engines import piratebay


def test_piratebay(capfd: pytest.CaptureFixture[str]) -> None:
    engine = piratebay.piratebay()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0
