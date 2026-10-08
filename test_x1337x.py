"""Local HTTP search contract: no public site, browser or runtime download."""
import contextlib
import importlib.util
import io
import sys
import threading
import time
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

OUTPUT = []
printer = types.ModuleType("novaprinter")
printer.prettyPrinter = OUTPUT.append
sys.modules["novaprinter"] = printer
spec = importlib.util.spec_from_file_location("x1337x", Path(__file__).with_name("x1337x.py"))
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
MAGNET = "magnet:?xt=urn:btih:" + "0123456789abcdef0123456789abcdef01234567"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.requests.append(self.path)
        if self.path == self.server.search_path:
            body = '''<table><tr><td><a href="/torrent/1/good/">Dream Scenario</a></td>
                <td class="seeds">15</td><td class="leeches">2</td><td class="size">1.5 GB</td></tr>
                <tr><td><a href="/torrent/2/bad/">Invalid link</a></td>
                <td class="seeds">10</td><td class="leeches">1</td><td class="size">1 GB</td></tr></table>'''
        elif self.path == "/torrent/1/good/":
            body = '<a href="' + MAGNET + '">Magnet</a>'
        elif self.path == "/torrent/2/bad/":
            body = '<a href="magnet:?xt=urn:btih:not-a-hash">Magnet</a>'
        else:
            self.send_error(404)
            return
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class PluginTests(unittest.TestCase):
    def setUp(self):
        OUTPUT.clear()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.requests = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.engine = plugin.x1337x()
        self.engine.url = "http://127.0.0.1:{}".format(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_qbittorrent_escaped_query_and_invalid_magnet(self):
        self.server.search_path = "/search/Dream%20Scenario%20%D1%81%D0%BE%D0%BD%20C%2B%2B/1/"
        with contextlib.redirect_stderr(io.StringIO()) as diagnostics:
            self.engine.search("Dream%20Scenario%20%D1%81%D0%BE%D0%BD%20C%2B%2B")
        self.assertEqual(self.server.requests[0], self.server.search_path)
        self.assertEqual(len(OUTPUT), 1)
        self.assertEqual(OUTPUT[0]["link"], MAGNET)
        self.assertEqual(OUTPUT[0]["size"], 1610612736)
        self.assertEqual((OUTPUT[0]["seeds"], OUTPUT[0]["leech"]), (15, 2))
        self.assertIn("cannot resolve", diagnostics.getvalue())

    def test_category_does_not_fetch_the_unused_general_search(self):
        self.server.search_path = "/category-search/Dream%20Scenario/Movies/1/"
        with contextlib.redirect_stderr(io.StringIO()):
            self.engine.search("Dream%20Scenario", "movies")
        self.assertEqual(len(OUTPUT), 1)
        self.assertEqual(self.server.requests, [self.server.search_path, "/torrent/1/good/", "/torrent/2/bad/"])

    def test_expired_search_never_starts_another_network_request(self):
        self.engine.deadline = time.monotonic() - 1
        with patch.object(plugin, "urlopen", side_effect=AssertionError("request after deadline")):
            with self.assertRaises(TimeoutError):
                self.engine._get("/torrent/3/late/")


if __name__ == "__main__":
    unittest.main()
