import pytest

from ..engines import torlock

RESULT_PAGE = """<html><body><article class="list">
<a href="/torrent/12345678/some-torrent-name">Some Torrent</a>
<table><tr>{cells}</tr></table>
</article></body></html>"""

DATA_CELLS = (
    '<td class="td">Today</td>'
    '<td class="ts">1.5 GB</td>'
    '<td class="tul">10</td>'
    '<td class="tdl">2</td>'
)


def test_torlock(capfd: pytest.CaptureFixture[str]) -> None:
    engine = torlock.torlock()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0


@pytest.mark.parametrize(
    'extra_cell',
    [
        pytest.param('<td>&nbsp;</td>', id='leading-layout-cell'),
        pytest.param('<td></td>', id='trailing-layout-cell'),
        pytest.param('<td colspan="2"></td>', id='colspan-spacer'),
    ],
)
def test_torlock_parser_tolerates_cells_without_class(
    extra_cell: str, capfd: pytest.CaptureFixture[str]
) -> None:
    """A result row may carry extra cells that have no class at all.

    Reading the class attribute as required raises KeyError('class') and
    aborts the whole search, so those cells must simply be skipped.
    """
    parser = torlock.torlock.MyHtmlParser(torlock.torlock.url)
    parser.feed(RESULT_PAGE.format(cells=extra_cell + DATA_CELLS))
    parser.close()

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert parser.page_items == 1
