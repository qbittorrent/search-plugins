# VERSION: 0.6
# AUTHORS: qbit-search-plugins contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Single-file qBittorrent plugin with private, automatic Camoufox bootstrap.

Public forum indexing, not RuTracker's authenticated tracker.php search.
"""
import contextlib
import datetime
import hashlib
import html
import json
import os
import platform
import queue
import re
import signal
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

# Do not require qBittorrent modules in the isolated browser worker.
if "--camoufox-worker" not in sys.argv:
    from novaprinter import prettyPrinter

# QuickParse map from jacred-fdb/jacred (AGPL-3.0).
FORUMS = {
    "movies": [549, 22, 1666, 941, 1950, 2090, 2221, 2091, 2092, 2093, 2200, 2540,
               934, 505, 124, 1457, 2199, 313, 312, 1247, 2201, 2339, 140, 252,
               7, 718, 1940, 271, 272, 775, 1543, 101, 100, 572, 84, 2343, 930,
               2365, 208, 539, 209, 1213, 4, 1577],
    "tv": [921, 815, 1460, 498, 842, 235, 242, 819, 1531, 721, 1102, 1120,
           1214, 489, 387, 9, 81, 119, 1803, 266, 193, 1690, 1459, 1463, 825,
           1248, 1288, 325, 534, 694, 704, 915, 1939, 2366, 189, 1171, 812,
           920, 911, 2100, 1669, 2393, 625, 1949, 173, 820, 1242, 717, 2412],
    "anime": [1105, 2491, 1389, 33, 1106],
}


def text(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", value))).strip()


def size_bytes(value):
    match = re.fullmatch(r"([\d.,]+)\s*(B|KB|MB|GB|TB|КБ|МБ|ГБ|ТБ)", value, re.I)
    if not match:
        return -1
    units = {"B": 0, "KB": 1, "КБ": 1, "MB": 2, "МБ": 2,
             "GB": 3, "ГБ": 3, "TB": 4, "ТБ": 4}
    return int(float(match[1].replace(",", ".")) * 1024 ** units[match[2].upper()])


def parse_listing(document):
    rows = []
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', document, re.S | re.I):
        title = re.search(r'<a\b[^>]*\bid=["\']tt-(\d+)["\'][^>]*>(.*?)</a>', row, re.S | re.I)
        if not title:
            continue
        def field(cls):
            match = re.search(r'class=["\'][^"\']*\b' + cls + r'\b[^"\']*["\'][^>]*>(.*?)</(?:a|span)>', row, re.S | re.I)
            return text(match[1]) if match else ""
        name = text(title[2])
        if not name:
            continue
        seeds, leech = field("seedmed"), field("leechmed")
        rows.append((int(title[1]), name, size_bytes(field("dl-stub")),
                     int(seeds) if seeds.isdigit() else -1,
                     int(leech) if leech.isdigit() else -1))
    if not rows and not re.search(r'<table\b[^>]*class=["\'][^"\']*\bvf-table\b[^"\']*\bvf-tor\b', document, re.I):
        raise ValueError("Not a RuTracker forum page (challenge or login page)")
    return rows


def parse_topic(document):
    for href in re.findall(r'\bhref=["\'](magnet:[^"\']+)["\']', document, re.I):
        magnet = html.unescape(href)
        if re.search(r'(?:\?|&)xt=urn:btih:(?:[0-9a-f]{40}|[a-z2-7]{32})(?:&|$)', magnet, re.I):
            date = re.search(r'class=["\']p-link small["\'][^>]*>([^<]+)</a>', document)
            published = -1
            if date:
                try:
                    dt = datetime.datetime.strptime(date[1].strip(), "%d-%b-%y %H:%M")
                    published = int(dt.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=3))).timestamp())
                except ValueError:
                    pass
            return magnet, published
    raise ValueError("Topic has no public magnet (challenge, login or removed torrent)")


UV_VERSION = "0.12.23"
UV_ASSETS = {
    "Linux-x86_64": ("uv-x86_64-unknown-linux-gnu.tar.gz", "9167d72b3319674b6303c4cbe071854bba13ebdf3d76b1a7cbdc175471fb66d6"),
    "Linux-aarch64": ("uv-aarch64-unknown-linux-gnu.tar.gz", "6524bd338177ed50d035d39354e12545e993bbeba2ecbddf0480c5b3a81d313f"),
    "Darwin-x86_64": ("uv-x86_64-apple-darwin.tar.gz", "960da44cb4b73685206ddd250b19e0a117fa41095710c1038f081f5cb613efb4"),
    "Darwin-arm64": ("uv-aarch64-apple-darwin.tar.gz", "50487ae565ccd96e499056b4674d438f4c53170202617b4c759defe0c6a1b544"),
    "Windows-AMD64": ("uv-x86_64-pc-windows-msvc.zip", "75d05de6762778c31ee183398de7dd15093fad0ed90b1f236d8205ea5ec00c90"),
}


def install_uv(directory, timeout):
    key = platform.system() + "-" + platform.machine()
    if key not in UV_ASSETS:
        raise OSError("No bundled Camoufox bootstrap for " + key)
    asset, checksum = UV_ASSETS[key]
    runtime = directory / ("uv-" + UV_VERSION) / key
    runtime.mkdir(parents=True, exist_ok=True)
    executable = runtime / ("uv.exe" if os.name == "nt" else "uv")
    archive = runtime / asset
    # Verify the downloaded archive also when reusing its cached executable.
    if archive.is_file():
        with archive.open("rb") as source:
            digest = hashlib.sha256(source.read()).hexdigest()
        if digest != checksum:
            raise ValueError("Cached uv archive SHA-256 mismatch")
    else:
        print("RuTracker: first launch downloads a private browser runtime; this can take several minutes", file=sys.stderr)
        with tempfile.NamedTemporaryFile(dir=str(runtime), delete=False) as output:
            temporary = Path(output.name)
            try:
                deadline = time.monotonic() + timeout
                with urlopen("https://github.com/astral-sh/uv/releases/download/" + UV_VERSION + "/" + asset, timeout=30) as response:
                    digest = hashlib.sha256()
                    while True:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("uv download timed out")
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        output.write(chunk)
                output.close()
                if digest.hexdigest() != checksum:
                    raise ValueError("uv release SHA-256 mismatch")
                os.replace(str(temporary), str(archive))
            finally:
                if temporary.exists():
                    temporary.unlink()
    # Extract only the required executable, never arbitrary archive paths.
    if asset.endswith(".zip"):
        with zipfile.ZipFile(archive) as package:
            member = next(name for name in package.namelist() if Path(name).name == "uv.exe")
            payload = package.read(member)
    else:
        with tarfile.open(archive, "r:gz") as package:
            member = next(item for item in package.getmembers() if Path(item.name).name == "uv" and item.isfile())
            payload = package.extractfile(member).read()
    if executable.is_file() and executable.read_bytes() == payload:
        return executable
    with tempfile.NamedTemporaryFile(dir=str(runtime), delete=False) as output:
        temporary = Path(output.name)
        output.write(payload)
    temporary.chmod(0o700)
    os.replace(str(temporary), str(executable))
    return executable


class CamoufoxBrowser:
    """JSON-lines IPC to this same file under a private managed Python."""

    def __init__(self, directory, startup_seconds, download_seconds):
        self.process = None
        self.reader = None
        self.messages = queue.Queue()
        data = directory / "rutracker_public.data"
        data.mkdir(parents=True, exist_ok=True)
        uv = install_uv(data, download_seconds)
        env = os.environ.copy()
        # Keep downloads out of the owner's normal Python/browser profiles.
        env.update({"UV_CACHE_DIR": str(data / "uv-cache"),
                    "UV_PYTHON_INSTALL_DIR": str(data / "python"),
                    "UV_PYTHON_PREFERENCE": "only-managed",
                    "XDG_CACHE_HOME": str(data / "cache"),
                    "PYTHONUNBUFFERED": "1"})
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        try:
            self.process = subprocess.Popen([
                str(uv), "run", "--no-project", "--isolated", "--python", "3.13",
                "--with", "camoufox==0.5.8", "--with", "playwright==1.62.0",
                "python", str(Path(__file__).resolve()), "--camoufox-worker",
                str(startup_seconds),
            ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", env=env, cwd=str(data),
                start_new_session=(os.name == "posix"))
            def read_messages():
                for line in self.process.stdout:
                    try:
                        self.messages.put(json.loads(line))
                    except ValueError:
                        self.messages.put({"error": "Worker protocol error"})
                self.messages.put({"error": "Camoufox worker exited; check available disk and native browser libraries"})
            self.reader = threading.Thread(target=read_messages, daemon=True)
            self.reader.start()
            reply = self.receive(download_seconds)
            if not reply.get("ready"):
                raise OSError(reply.get("error", "Camoufox startup failed"))
        except BaseException:
            self.close()
            raise

    def receive(self, timeout):
        try:
            reply = self.messages.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError("Camoufox worker timed out") from None
        if reply.get("error"):
            raise OSError(reply["error"])
        return reply

    def fetch(self, url, timeout):
        try:
            self.process.stdin.write(json.dumps({"url": url, "timeout": timeout}) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError):
            raise OSError("Camoufox worker disconnected") from None
        try:
            return self.receive(timeout + 5)["html"]
        except TimeoutError:
            # A late reply must never be used for a different torrent topic.
            self.close()
            raise

    def close(self):
        if self.process is None:
            return
        try:
            self.process.stdin.close()  # EOF lets the worker close browser + driver.
            self.process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            if os.name == "posix":
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(self.process.pid, signal.SIGKILL)
                else:
                    self.process.kill()
                self.process.wait(timeout=5)
        finally:
            self.process.stdout.close()
            if self.reader is not None:
                self.reader.join(timeout=2)
            self.process = None


def camoufox_worker(startup_seconds):
    protocol = sys.stdout
    # Upstream bootstrap messages and fingerprint downloads must never corrupt
    # qBittorrent results/IPC or leak cookies. Keep all upstream stdout private.
    def send(value):
        protocol.write(json.dumps(value, ensure_ascii=False) + "\n")
        protocol.flush()
    try:
        with open(os.devnull, "w") as quiet, contextlib.redirect_stdout(quiet):
            from camoufox.sync_api import Camoufox, NewContext
            from playwright.sync_api import Error as BrowserError
            with Camoufox(headless=True, os=["linux"], humanize=True,
                          disable_coop=True, block_webrtc=True,
                          i_know_what_im_doing=True, main_world_eval=True,
                          config={"forceScopeAccess": True},
                          timeout=startup_seconds * 1000) as browser:
                context = NewContext(browser, os="linux", locale="en-US", timezone_id="Europe/London")
                page = context.new_page()
                send({"ready": True})
                for line in sys.stdin:
                    try:
                        request = json.loads(line)
                        url, seconds = request["url"], request["timeout"]
                        deadline = time.monotonic() + seconds
                        page.goto(url, wait_until="domcontentloaded", timeout=max(1, int(seconds * 1000)))
                        clean = 0
                        last_click = time.monotonic()
                        while time.monotonic() < deadline:
                            try:
                                document = page.content()
                                active = (re.search(r"just a moment|один момент|verify you are human|please wait", page.title(), re.I)
                                          or re.search(r"cf_chl_opt|cf-browser-verification|orchestrate/chl_page", document, re.I))
                                clean = 0 if active else clean + 1
                                if clean >= 2:
                                    if urlparse(page.url).hostname != urlparse(url).hostname:
                                        raise ValueError("Unexpected redirect")
                                    send({"html": document})
                                    break
                                if active and time.monotonic() - last_click >= 3:
                                    last_click = time.monotonic()
                                    # TRAWL strategy: frame checkbox, then keyboard.
                                    clicked = False
                                    for frame in page.frames:
                                        if "challenges.cloudflare.com" not in frame.url:
                                            continue
                                        for selector in ('[role="checkbox"]', 'input[type="checkbox"]', '.ctp-checkbox-label'):
                                            candidate = frame.locator(selector).first
                                            if candidate.is_visible():
                                                candidate.click(timeout=500)
                                                clicked = True
                                                break
                                        if clicked:
                                            break
                                    if not clicked:
                                        page.keyboard.press("Tab")
                                        page.keyboard.press("Space")
                            except BrowserError:
                                clean = 0  # DOM/context may be replaced mid-challenge.
                            page.wait_for_timeout(min(300, max(1, int((deadline - time.monotonic()) * 1000))))
                        else:
                            raise TimeoutError("Cloudflare challenge timed out")
                    except Exception as error:
                        # No raw upstream exception: may contain challenge tokens.
                        send({"error": "Camoufox request failed: " + type(error).__name__})
    except Exception as error:
        send({"error": "Camoufox startup failed: " + type(error).__name__})


class rutracker_public:
    url = "https://rutracker.org"
    name = "RuTracker Public (Camoufox local index)"
    supported_categories = {"all": "all", "movies": "movies", "tv": "tv", "anime": "anime"}

    def __init__(self):
        self.directory = Path(__file__).resolve().parent
        self.config = {
            "solver_url": "", "startup_seconds": 60, "download_seconds": 900,
            "timeout_seconds": 60, "search_seconds": 90,
            "pages_per_search": 4, "pages_per_forum": 3, "result_limit": 25,
            "request_delay": 2, "magnet_ttl_seconds": 3600, "forums": FORUMS,
        }
        config_path = self.directory / "rutracker_public.json"
        if config_path.exists():
            with config_path.open(encoding="utf-8") as stream:
                self.config.update(json.load(stream))
        for key in ("timeout_seconds", "search_seconds", "pages_per_search", "pages_per_forum", "result_limit", "magnet_ttl_seconds", "startup_seconds", "download_seconds"):
            if not isinstance(self.config[key], int) or self.config[key] < 1:
                raise ValueError("Invalid setting: " + key)
        if not isinstance(self.config["request_delay"], (int, float)) or self.config["request_delay"] < 0:
            raise ValueError("Invalid request_delay")
        endpoint = urlparse(self.config["solver_url"])
        if self.config["solver_url"] and (endpoint.scheme not in ("http", "https") or not endpoint.netloc):
            raise ValueError("Invalid solver_url")
        self.solver_url = self.config["solver_url"]
        self.browser = None
        self.last_request = 0
        self.deadline = 0

    def stop_solver(self):
        if self.browser is not None:
            try:
                self.browser.close()
            finally:
                self.browser = None

    def browser_fetch(self, url, timeout):
        if self.browser is None:
            started = time.monotonic()
            print("RuTracker: starting private Camoufox headless", file=sys.stderr)
            self.browser = CamoufoxBrowser(self.directory, self.config["startup_seconds"], self.config["download_seconds"])
            self.deadline += time.monotonic() - started
        remaining = self.deadline - time.monotonic() - 1
        if remaining <= 0:
            raise TimeoutError("Search time budget exhausted")
        try:
            return self.browser.fetch(url, min(timeout, remaining))
        except (OSError, TimeoutError):
            self.stop_solver()
            raise

    def fetch(self, path):
        remaining = self.deadline - time.monotonic()
        if remaining <= 1:
            raise TimeoutError("Search time budget exhausted")
        delay = max(0, self.last_request + self.config["request_delay"] - time.monotonic())
        if delay + 1 >= remaining:
            raise TimeoutError("Search time budget exhausted")
        time.sleep(delay)
        timeout = min(self.config["timeout_seconds"], self.deadline - time.monotonic() - 1)
        url = self.url + path
        self.last_request = time.monotonic()
        if self.solver_url:
            payload = {"cmd": "request.get", "url": url, "maxTimeout": int(timeout * 1000)}
            request = Request(self.solver_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=timeout + 1) as response:
                envelope = json.load(response)
            solution = envelope.get("solution", {})
            if envelope.get("status") != "ok" or solution.get("status") != 200:
                raise ValueError("FlareSolverr failed to fetch RuTracker HTML")
            if urlparse(solution.get("url", self.url)).hostname != urlparse(self.url).hostname:
                raise ValueError("Unexpected RuTracker redirect")
            return solution.get("response", "")
        if self.browser is not None:
            return self.browser_fetch(url, timeout)
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=min(10, timeout)) as response:
                if urlparse(response.url).hostname != urlparse(self.url).hostname:
                    raise ValueError("Unexpected RuTracker redirect")
                document = response.read().decode(response.headers.get_content_charset() or "cp1251", errors="replace")
            if not re.search(r"cf_chl_opt|orchestrate/chl_page|<title>\s*Just a moment", document, re.I):
                return document
        except HTTPError as error:
            if error.code not in (403, 503):
                raise
        return self.browser_fetch(url, timeout)

    def database(self):
        db = sqlite3.connect(str(self.directory / "rutracker_public.sqlite3"), timeout=5)
        db.execute("CREATE TABLE IF NOT EXISTS torrents (id INTEGER PRIMARY KEY, title TEXT, size INTEGER, seeds INTEGER, leech INTEGER, category TEXT, forum INTEGER, magnet TEXT, checked REAL DEFAULT 0, published INTEGER DEFAULT -1)")
        db.execute("CREATE TABLE IF NOT EXISTS cursors (category TEXT PRIMARY KEY, position INTEGER)")
        return db

    def refresh(self, db, category):
        forums = self.config["forums"]
        categories = list(forums) if category == "all" else [category]
        slots = [(cat, int(forum), page) for cat in categories for forum in forums.get(cat, []) for page in range(self.config["pages_per_forum"])]
        if not slots:
            raise ValueError("No forums configured for this category")
        cursor = db.execute("SELECT position FROM cursors WHERE category=?", (category,)).fetchone()
        position = (cursor[0] if cursor else 0) % len(slots)
        for _ in range(min(self.config["pages_per_search"], len(slots))):
            if self.deadline - time.monotonic() < 2:
                break
            cat, forum, page = slots[position]
            rows = parse_listing(self.fetch("/forum/viewforum.php?f={}&start={}".format(forum, page * 50)))
            for topic_id, title, size, seeds, leech in rows:
                db.execute("""INSERT INTO torrents(id,title,size,seeds,leech,category,forum)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    checked=CASE WHEN torrents.title<>excluded.title OR torrents.size<>excluded.size THEN 0 ELSE torrents.checked END,
                    title=excluded.title,size=excluded.size,seeds=excluded.seeds,leech=excluded.leech,
                    category=excluded.category,forum=excluded.forum""", (topic_id, title, size, seeds, leech, cat, forum))
            position = (position + 1) % len(slots)
            db.execute("INSERT OR REPLACE INTO cursors VALUES(?,?)", (category, position))
            db.commit()
        count = db.execute("SELECT count(*) FROM torrents").fetchone()[0]
        print("RuTracker: local index has {} topics; partial coverage, cursor {}/{}".format(count, position, len(slots)), file=sys.stderr)

    def search(self, what, cat="all"):
        tokens = unquote(what).casefold().split()
        if not tokens or cat not in self.supported_categories:
            return
        db = self.database()
        try:
            try:
                self.solver_url = self.config["solver_url"]
                self.deadline = time.monotonic() + self.config["search_seconds"]
                self.refresh(db, cat)
            except (OSError, ValueError, TimeoutError) as error:
                print("RuTracker: index refresh failed ({}); searching cached topics".format(type(error).__name__), file=sys.stderr)
                if not self.solver_url:
                    print("RuTracker: " + str(error), file=sys.stderr)
            query = "SELECT id,title,size,seeds,leech,magnet,checked,published FROM torrents"
            args = ()
            if cat != "all":
                query += " WHERE category=?"
                args = (cat,)
            candidates = [row for row in db.execute(query, args) if all(token in row[1].casefold() for token in tokens)]
            candidates.sort(key=lambda row: row[3], reverse=True)
            for row in candidates[:self.config["result_limit"]]:
                topic_id, title, size, seeds, leech, magnet, checked, published = row
                if not magnet or time.time() - checked >= self.config["magnet_ttl_seconds"]:
                    try:
                        magnet, published = parse_topic(self.fetch("/forum/viewtopic.php?t={}".format(topic_id)))
                        db.execute("UPDATE torrents SET magnet=?,checked=?,published=? WHERE id=?", (magnet, time.time(), published, topic_id))
                        db.commit()
                    except (OSError, ValueError, TimeoutError) as error:
                        print("RuTracker: cannot resolve topic {} ({})".format(topic_id, type(error).__name__), file=sys.stderr)
                        continue
                prettyPrinter({"link": magnet, "name": title, "size": size, "seeds": seeds, "leech": leech,
                               "engine_url": self.url, "desc_link": self.url + "/forum/viewtopic.php?t={}".format(topic_id), "pub_date": published})
        finally:
            db.close()
            self.stop_solver()


if __name__ == "__main__" and "--camoufox-worker" in sys.argv:
    camoufox_worker(int(sys.argv[-1]))
