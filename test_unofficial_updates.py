"""Offline delivery checks for repaired unofficial plugins and the TGX mirror."""
import contextlib
import importlib.util
import io
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
OUTPUT = []
printer = types.ModuleType('novaprinter')
printer.prettyPrinter = OUTPUT.append
sys.modules['novaprinter'] = printer
helpers = types.ModuleType('helpers')
helpers.retrieve_url = lambda *args, **kwargs: ''
helpers.download_file = lambda url: url


def load(name):
    # Only intercept external qBittorrent modules while loading each standalone file.
    with patch.dict(sys.modules, {'novaprinter': printer, 'helpers': helpers}):
        spec = importlib.util.spec_from_file_location(name + '_updated', ROOT / 'unofficial' / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class Updates(unittest.TestCase):
    def setUp(self):
        OUTPUT.clear()

    def test_mikan_rss_without_removed_helpers_headers(self):
        module = load('mikan')
        xml = b'''<rss><channel><item><title>Naruto 01</title>
            <link>https://mikanani.me/Home/Episode/1</link>
            <enclosure url="https://mikanani.me/Download/1.torrent" length="1024"/>
            </item></channel></rss>'''
        requested = []

        def api(request, timeout):
            requested.append(request.full_url)
            return io.BytesIO(xml)

        with patch.object(module.urllib.request, 'urlopen', side_effect=api):
            module.mikan().search('Naruto%2001')
        self.assertEqual(requested, ['https://mikanani.me/RSS/Search?searchstr=Naruto+01'])
        self.assertEqual(OUTPUT[0]['name'], 'Naruto 01')
        self.assertEqual(OUTPUT[0]['link'], 'https://mikanani.me/Download/1.torrent')
        self.assertEqual(OUTPUT[0]['size'], '1024')

    def test_mikan_network_error_is_not_a_fake_torrent(self):
        module = load('mikan')
        with patch.object(module.urllib.request, 'urlopen', side_effect=OSError('offline')):
            with contextlib.redirect_stderr(io.StringIO()) as diagnostics:
                module.mikan().search('Naruto')
        self.assertEqual(OUTPUT, [])
        self.assertIn('search failed', diagnostics.getvalue())

    def test_piratebay_categories_emit_magnet_not_percent_encoded_url(self):
        module = load('thepiratebay')
        module.thepiratebay().parseJSON([
            {'info_hash': '0' * 40, 'id': '0', 'name': 'No results returned', 'size': '0', 'seeders': '0', 'leechers': '0', 'added': '0'},
            {'info_hash': 'a' * 40, 'id': '123', 'name': 'Ubuntu ISO', 'size': '1024',
             'seeders': '42', 'leechers': '3', 'added': '1748221717'},
        ])
        self.assertEqual(len(OUTPUT), 1)
        self.assertTrue(OUTPUT[0]['link'].startswith('magnet:?xt=urn:btih:' + 'a' * 40 + '&'))
        self.assertEqual(OUTPUT[0]['desc_link'], 'https://thepiratebay.org/description.php?id=123')
        self.assertEqual(OUTPUT[0]['pub_date'], '1748221717')

    def test_torrentdownload_keeps_url_scheme_usable(self):
        module = load('torrentdownload')
        document = '''<tr><td class="tdleft"><div class="tt-name">
            <a href="/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/Ubuntu-ISO">Ubuntu ISO</a>
            <span class="smallish">Apps</span></div></td>
            <td class="tdnormal">1 GB</td><td class="tdseed">42</td><td class="tdleech">3</td></tr>'''
        with patch.object(module, 'retrieve_url', return_value=document):
            module.torrentdownload().search('Ubuntu')
        self.assertTrue(OUTPUT)
        self.assertTrue(OUTPUT[0]['link'].startswith('https://www.torrentdownload.info/'))
        self.assertNotIn('https%3A', OUTPUT[0]['link'])

    def test_torrentgalaxy_mirror_listing_and_magnet(self):
        module = load('torrentgalaxy')
        row = '''<div class="tgxtablerow txlight">'''
        cells = ['Movies', '', '', '<div><a title="Dream Scenario 2023" href="/post-detail/1/dream/">Dream</a></div>', '', '', '', '1.5 GB', '', '', '[42/3]', 'Today']
        row += ''.join('<div class="tgxtablecell">' + value + '</div>' for value in cells) + '</div>'
        requested = []
        magnet = 'magnet:?xt=urn:btih:' + 'a' * 40

        def fetch(self, path):
            requested.append(path)
            return row if path.startswith('/get-posts/') else '<a href="' + magnet + '">magnet</a>'

        with patch.object(module.torrentgalaxy, 'fetch', fetch):
            module.torrentgalaxy().search('Dream%20Scenario')
        self.assertEqual(requested, ['/get-posts/keywords:Dream%20Scenario:order:-se/', '/post-detail/1/dream/'])
        self.assertEqual(OUTPUT[0]['link'], magnet)
        self.assertEqual(OUTPUT[0]['size'], 1610612736)
        self.assertEqual((OUTPUT[0]['seeds'], OUTPUT[0]['leech']), (42, 3))


if __name__ == '__main__':
    unittest.main()
