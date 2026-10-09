import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).parent
HASH = '0123456789abcdef0123456789abcdef01234567'


class Response:
    def __init__(self, payload):
        self.payload = payload.encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def load(stem, output):
    printer = types.ModuleType('novaprinter')
    printer.prettyPrinter = output.append
    spec = importlib.util.spec_from_file_location(stem, ROOT / 'unofficial' / (stem + '.py'))
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'novaprinter': printer}):
        spec.loader.exec_module(module)
    return module


class PublicIndexes(unittest.TestCase):
    def test_three_anonymous_searches_filter_exact_tracker_validate_hash_and_keep_metadata(self):
        for stem, tracker in [('kinozal_public', 'kinozal'), ('toloka_public', 'toloka'), ('nnmclub_public', 'nnmclub')]:
            with self.subTest(stem=stem):
                output = []
                module = load(stem, output)
                item = {'Tracker': 'rutor, ' + tracker, 'Title': 'Дюна 2021',
                        'MagnetUri': 'magnet:?xt=urn:btih:' + HASH, 'Details': 'https://example.org/topic/123',
                        'Size': 1073741824, 'Seeders': 22, 'Peers': 4, 'PublishDate': '2026-07-08T21:59:00Z'}
                rows = [dict(item, Tracker='not' + tracker), dict(item, MagnetUri='magnet:?xt=urn:btih:' + '0' * 40),
                        dict(item, Details='https://[invalid'), item, item]

                def server(request, timeout):
                    params = parse_qs(urlsplit(request.full_url).query)
                    self.assertEqual(params, {'query': ['Дюна 2021'], 'category[]': ['2000']})
                    self.assertNotIn('Authorization', dict(request.header_items()))
                    self.assertLessEqual(timeout, 20)
                    return Response(json.dumps({'Results': rows}))

                with patch.object(module, 'urlopen', server):
                    getattr(module, stem)().search('%D0%94%D1%8E%D0%BD%D0%B0%202021', 'movies')
                self.assertEqual(len(output), 1)
                self.assertEqual(output[0]['link'], 'magnet:?xt=urn:btih:' + HASH)
                self.assertEqual((output[0]['name'], output[0]['size'], output[0]['seeds'], output[0]['leech']),
                                 ('Дюна 2021', 1073741824, 22, 4))
                self.assertEqual(output[0]['pub_date'], 1783547940)

    def test_index_failure_is_diagnostic_not_torrent(self):
        output = []
        module = load('nnmclub_public', output)
        with patch.object(module, 'urlopen', return_value=Response('{"error":"unavailable"}')):
            with contextlib.redirect_stderr(io.StringIO()) as error:
                module.nnmclub_public().search('Дюна')
        self.assertEqual(output, [])
        self.assertTrue(error.getvalue())

    def test_nyaa_index_only_emits_nyaa_origin_releases(self):
        output = []
        module = load('nyaasi_public', output)
        item = {'id': 123, 'name': 'Naruto', 'btih': HASH, 'totalsize': 1073741824,
                'source_date': 1700000000, 'nyaa_id': 456}

        def server(request, timeout):
            if '/v1/search/torrents?' in request.full_url:
                return Response(json.dumps({'results': [dict(item, nyaa_id=None), item]}))
            return Response('{"trackers":[]}')

        with patch.object(module, 'urlopen', server):
            module.nyaasi_public().search('Naruto')
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]['engine_url'], 'https://nyaa.si')
        self.assertEqual(output[0]['desc_link'], 'https://nyaa.si/view/456')
        self.assertTrue(output[0]['link'].startswith('magnet:?xt=urn:btih:' + HASH))

    def test_elitetorrent_empty_encoded_links_and_first_valid_candidate(self):
        output = []
        helpers = types.ModuleType('helpers')
        helpers.download_file = lambda url: None
        with patch.dict(sys.modules, {'helpers': helpers}):
            module = load('elitetorrent', output)
        import base64
        import codecs
        magnet = 'magnet:?xt=urn:btih:' + HASH
        encoded = base64.b64encode(codecs.encode(magnet, 'rot_13').encode()).decode()
        for links, expected in [([], None), (['i=' + encoded + '"'], magnet)]:
            info = {'title': None, 'link': links, 'size': None, 'quality': None,
                    'language': None, 'date': None, 'seeds': None, 'leech': None}
            module.format_info(info)
            self.assertEqual(info['link'], expected)

    def test_tsukihime_missing_optional_stats_keeps_search_hash(self):
        output = []
        module = load('tsukihime', output)

        def server(request, timeout):
            if request.full_url == 'https://api.tsukihime.org/v1/search/torrents?q=Naruto+Shippuden':
                return Response(json.dumps({'results': [{'id': 123, 'name': 'Naruto Shippuden', 'btih': HASH,
                                                         'totalsize': 1073741824, 'source_date': 1700000000}]}))
            if request.full_url == 'https://api.tsukihime.org/v1/torrents/123':
                return Response('{"error":"expired tracker stats"}')
            self.fail('unexpected API route')

        with patch.object(module, 'urlopen', server):
            module.tsukihime().search('Naruto%20Shippuden')
        self.assertEqual(len(output), 1)
        self.assertTrue(output[0]['link'].startswith('magnet:?xt=urn:btih:' + HASH + '&dn='))
        self.assertEqual((output[0]['size'], output[0]['seeds'], output[0]['leech']), (1073741824, -1, -1))
        self.assertEqual(output[0]['pub_date'], 1700000000)

    def test_yourbittorrent_skips_ad_rows_and_resolves_new_torrent_host(self):
        output = []
        module = load('yourbittorrent', output)
        row = ('<tr><td><a class="yb-tname" href="/torrent/123/title.html" title="Dream &amp; Scenario">title</a></td>'
               '<td data-label="Size">1.4 GB</td><td><time datetime="2023-12-22">date</time></td>'
               '<td data-label="Seed">180</td><td data-label="Peers">29</td></tr>')
        advertisement = row.replace('/torrent/123/title.html', 'https://ad.example/torrent/999/fake.html')
        metadata = b'd4:infod4:name4:testee'

        def server(request, timeout):
            self.assertEqual(request.get_header('User-agent'), 'curl/8.18.0')
            url = request.full_url
            if url == 'https://yourbittorrent.com/?q=Dream-Scenario':
                return Response('<table>' + advertisement + row + '</table>')
            if url == 'https://yourbittorrent.com/?section=download&id=123':
                return Response('<script>var url = "https://yt.t0r.store/down/123.torrent";</script>')
            if url == 'https://yt.t0r.store/down/123.torrent':
                response = Response('')
                response.payload = metadata
                return response
            self.fail('unexpected download route')

        with patch.object(module, 'urlopen', server):
            engine = module.yourbittorrent()
            engine.search('Dream%20Scenario')
            self.assertEqual(len(output), 1)
            self.assertEqual((output[0]['name'], output[0]['seeds'], output[0]['leech']), ('Dream & Scenario', '180', '29'))
            with contextlib.redirect_stdout(io.StringIO()) as result:
                engine.download_torrent(output[0]['link'])
        filename, origin = result.getvalue().strip().split(' ', 1)
        try:
            self.assertEqual(Path(filename).read_bytes(), metadata)
            self.assertEqual(origin, 'https://yourbittorrent.com/torrent/123/title.html')
        finally:
            Path(filename).unlink()

    def test_snowfl_real_transport_headers_and_qbittorrent_query_encoding(self):
        output = []
        module = load('snowfl', output)

        def server(request, timeout):
            self.assertEqual(request.get_header('Referer'), 'https://snowfl.com/')
            self.assertEqual(request.get_header('User-agent'), 'Mozilla/5.0')
            url = request.full_url
            if url == 'https://snowfl.com/':
                return Response('<script src="b.min.js?v=fixture"></script>')
            if url == 'https://snowfl.com/b.min.js?v=fixture':
                return Response('findNextItem("fixture-public-id")')
            if url == 'https://snowfl.com/fixture-public-id/Dream%20Scenario/DH5kKsJw/0/SEED/NONE/0':
                return Response(json.dumps([{'name': 'Dream Scenario 2023', 'site': 'example', 'size': '1.5 GB',
                                             'seeder': 42, 'leecher': 3, 'age': '2 days',
                                             'url': 'https://example.org/topic/123',
                                             'magnet': 'magnet:?xt=urn:btih:' + HASH},
                                            {'magnet': 'magnet:?xt=urn:btih:' + '0' * 40}]))
            self.fail('unexpected request route')

        with patch.object(module, 'urlopen', server):
            module.snowfl().search('Dream%20Scenario')
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]['link'], 'magnet:?xt=urn:btih:' + HASH)
        self.assertEqual((output[0]['seeds'], output[0]['leech']), (42, 3))
        self.assertEqual(output[0]['desc_link'], 'https://example.org/topic/123')


if __name__ == '__main__':
    unittest.main()
