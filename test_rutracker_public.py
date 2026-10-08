"""Offline HTTP-contract and indexing tests; no browser or internet needed."""
import contextlib
import importlib.util
import io
import json
import hashlib
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
OUTPUT = []
printer = types.ModuleType("novaprinter")
printer.prettyPrinter = OUTPUT.append
sys.modules["novaprinter"] = printer
spec = importlib.util.spec_from_file_location("rutracker_public", ROOT / "rutracker_public.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
HASH = "0123456789abcdef0123456789abcdef01234567"
MAGNET = "magnet:?xt=urn:btih:" + HASH + "&dn=Nefarious"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(payload)
        if self.server.fail:
            result = {"status": "error", "solution": {"status": 403}}
        else:
            url = payload["url"]
            if payload["cmd"] != "request.get" or not payload["maxTimeout"] > 0:
                self.send_error(400)
                return
            if url.endswith("/forum/viewforum.php?f=1950&start=0"):
                document = self.server.listing
            elif url.endswith("/forum/viewtopic.php?t=6375095"):
                document = '<a class="med magnet-link" href="' + MAGNET.replace("&", "&amp;") + '">magnet</a>'
            else:
                self.send_error(404)
                return
            result = {"status": "ok", "solution": {"status": 200, "url": url, "response": document}}
        data = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class PluginTests(unittest.TestCase):
    def setUp(self):
        OUTPUT.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.requests = []
        self.server.fail = False
        self.server.listing = (ROOT / "forum_1950.html").read_text()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.engine = plugin.rutracker_public()
        self.engine.directory = Path(self.temp.name)
        self.engine.config.update({
            "solver_url": "http://127.0.0.1:{}/v1".format(self.server.server_port),
            "forums": {"movies": [1950]}, "pages_per_search": 1,
            "pages_per_forum": 1, "request_delay": 0,
        })

    def tearDown(self):
        self.engine.stop_solver()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def search(self):
        with contextlib.redirect_stderr(io.StringIO()) as diagnostics:
            self.engine.search("%D0%9D%D0%95%D0%A4%D0%90%D0%A0%D0%98%D0%A3%D0%A1", "movies")
        return diagnostics.getvalue()

    def test_real_listing_unicode_search_magnet_and_persistent_cache(self):
        self.search()
        self.assertEqual(len(OUTPUT), 1)
        result = OUTPUT[0]
        self.assertEqual(result["link"], MAGNET)
        self.assertEqual(result["size"], int(1.46 * 1024 ** 3))
        self.assertEqual((result["seeds"], result["leech"]), (184, 9))
        self.assertIn("Нефариус / Nefarious", result["name"])
        self.assertEqual(result["desc_link"], "https://rutracker.org/forum/viewtopic.php?t=6375095")
        self.assertEqual(len(self.server.requests), 2)
        OUTPUT.clear()
        self.engine = self.fresh_engine()
        self.server.fail = True
        diagnostics = self.search()
        self.assertEqual(OUTPUT[0]["link"], MAGNET)
        self.assertIn("refresh failed", diagnostics)

    def fresh_engine(self):
        fresh = plugin.rutracker_public()
        fresh.directory = self.engine.directory
        fresh.config = self.engine.config.copy()
        return fresh

    def test_corrupt_bootstrap_archive_is_rejected_before_execution(self):
        key = "Linux-x86_64"
        asset = plugin.UV_ASSETS[key][0]
        runtime = Path(self.temp.name) / ("uv-" + plugin.UV_VERSION) / key
        runtime.mkdir(parents=True)
        (runtime / asset).write_bytes(b"not an official release")
        (runtime / "uv").write_bytes(b"must never execute")
        with patch.object(plugin.platform, "system", return_value="Linux"), patch.object(plugin.platform, "machine", return_value="x86_64"):
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                plugin.install_uv(Path(self.temp.name), 10)

    def test_verified_archive_repairs_a_corrupted_cached_executable(self):
        runtime = Path(self.temp.name) / ("uv-" + plugin.UV_VERSION) / "Linux-x86_64"
        runtime.mkdir(parents=True)
        archive = runtime / "uv-test.tar.gz"
        payload = b"a verified private executable"
        with tarfile.open(archive, "w:gz") as package:
            member = tarfile.TarInfo("release/uv")
            member.size = len(payload)
            package.addfile(member, io.BytesIO(payload))
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        executable = runtime / "uv"
        executable.write_bytes(b"corrupted executable")
        with patch.dict(plugin.UV_ASSETS, {"Linux-x86_64": (archive.name, checksum)}), patch.object(plugin.platform, "system", return_value="Linux"), patch.object(plugin.platform, "machine", return_value="x86_64"):
            result = plugin.install_uv(Path(self.temp.name), 10)
        self.assertEqual(result.read_bytes(), payload)
        self.assertTrue(result.stat().st_mode & 0o100)

    def test_worker_timeout_closes_real_process_before_another_topic(self):
        # Fake only the external browser runtime. Parent process/IPC/cleanup are real.
        executable = Path(self.temp.name) / "private-uv"
        executable.write_text("#!" + sys.executable + "\nimport sys\nprint('{\"ready\": true}', flush=True)\nfor request in sys.stdin:\n    pass\n")
        executable.chmod(0o700)
        self.engine.config["solver_url"] = ""
        self.engine.deadline = time.monotonic() + 30
        with patch.object(plugin, "install_uv", return_value=executable):
            browser = plugin.CamoufoxBrowser(self.engine.directory, 10, 10)
            process = browser.process
            self.engine.browser = browser
            with self.assertRaises(TimeoutError):
                self.engine.browser_fetch("https://rutracker.org/forum/viewtopic.php?t=1", 0.01)
        self.assertIsNone(self.engine.browser)
        self.assertIsNotNone(process.poll())

    def test_login_page_does_not_advance_the_forum_cursor(self):
        self.engine.config["forums"] = {"movies": [1950, 2090]}
        self.server.listing = '<div id="main_content"><table class="forumline"><form action="login.php">Login</form></table></div>'
        diagnostics = self.search()
        self.assertEqual(OUTPUT, [])
        self.assertIn("refresh failed", diagnostics)
        with contextlib.closing(sqlite3.connect(str(self.engine.directory / "rutracker_public.sqlite3"))) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM cursors").fetchone()[0], 0)

    def test_external_solver_never_launches_a_local_browser(self):
        with patch.object(plugin, "CamoufoxBrowser", side_effect=AssertionError("Local browser launched")):
            self.search()
        self.assertEqual(OUTPUT[0]["link"], MAGNET)

    def test_changed_torrent_never_emits_cached_old_magnet_on_fetch_failure(self):
        self.search()
        OUTPUT.clear()
        with contextlib.closing(sqlite3.connect(str(self.engine.directory / "rutracker_public.sqlite3"))) as db:
            db.execute("UPDATE torrents SET checked=0 WHERE id=6375095")
            db.commit()
        self.server.fail = True
        diagnostics = self.search()
        self.assertEqual(OUTPUT, [])
        self.assertIn("cannot resolve topic 6375095", diagnostics)

    def test_listing_change_invalidates_magnet(self):
        self.search()
        self.server.listing = self.server.listing.replace("1.46&nbsp;GB", "1.50&nbsp;GB")
        OUTPUT.clear()
        self.search()
        self.assertEqual(OUTPUT[0]["size"], int(1.5 * 1024 ** 3))
        topics = [r for r in self.server.requests if "viewtopic.php" in r["url"]]
        self.assertEqual(len(topics), 2)

    def test_challenge_is_failure_not_empty_listing_and_magnet_html_entities(self):
        with self.assertRaises(ValueError):
            plugin.parse_listing("<html><title>Just a moment...</title></html>")
        magnet, date = plugin.parse_topic('<a href="' + MAGNET.replace("&", "&amp;") + '">x</a>')
        self.assertEqual(magnet, MAGNET)
        self.assertEqual(date, -1)


if __name__ == "__main__":
    unittest.main()
