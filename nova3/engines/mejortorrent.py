# VERSION: 2.0
# AUTHORS: kalpakprod
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Standalone MejorTorrent search with automatic private Camoufox fallback.
No account, browser profile, pip or local server required. The browser runtime is
shared with the standalone RuTracker Public plugin when installed alongside it.
First browser bootstrap downloads about 1.3 GB; regular search needs no download.
"""
import contextlib
import base64
import hashlib
import json
import os
import platform
import queue
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile
from html import unescape
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlencode, urlparse, urljoin, parse_qs
from urllib.request import urlopen

if "--camoufox-worker" not in sys.argv:
    from novaprinter import prettyPrinter

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
        print("MejorTorrent: first launch downloads a private browser runtime; this can take several minutes", file=sys.stderr)
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
            reply = self.receive(download_seconds + startup_seconds)
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

    def download(self, topic, target, timeout):
        try:
            self.process.stdin.write(json.dumps({'url': topic, 'download_url': target, 'timeout': timeout}) + '\n')
            self.process.stdin.flush()
            reply = self.receive(timeout + 5)
            return base64.b64decode(reply['metadata'], validate=True)
        except TimeoutError:
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
            proxy_url = os.environ.get('qbt_socks_proxy')
            if proxy_url is None and os.environ.get('sock_proxy'):
                proxy_url = 'socks5h://' + os.environ['sock_proxy'].strip()
            proxy = None
            if proxy_url is not None:
                parts = urlparse(proxy_url)
                if parts.scheme not in ('socks5', 'socks5h') or not parts.hostname or not parts.port or parts.username or parts.password:
                    raise OSError('Unsupported browser proxy; direct connection refused')
                host = '[' + parts.hostname + ']' if ':' in parts.hostname else parts.hostname
                proxy = {'server': 'socks5://' + host + ':' + str(parts.port)}
            with Camoufox(proxy=proxy, headless=True, os=["linux"], humanize=True,
                          disable_coop=True, block_webrtc=True,
                          i_know_what_im_doing=True, main_world_eval=True,
                          config={"forceScopeAccess": True},
                          timeout=startup_seconds * 1000) as browser:
                context = NewContext(browser, os="linux", locale="en-US", timezone_id="Europe/London")
                allowed = set()
                def route_request(route):
                    host = urlparse(route.request.url).hostname
                    if host in allowed or host == 'challenges.cloudflare.com':
                        route.continue_()
                    else:
                        route.abort()
                # Native ad scripts were observed replacing the document with a head-only page.
                context.route('**/*', route_request)
                page = context.new_page()
                send({"ready": True})
                for line in sys.stdin:
                    try:
                        request = json.loads(line)
                        url, seconds = request["url"], request["timeout"]
                        deadline = time.monotonic() + seconds
                        allowed.add(urlparse(url).hostname)
                        page.goto(url, wait_until="domcontentloaded", timeout=max(1, int(seconds * 1000)))
                        clean = 0
                        last_click = time.monotonic()
                        while time.monotonic() < deadline:
                            try:
                                document = page.content()
                                active = (re.search(r"just a moment|один момент|verify you are human|please wait", page.title(), re.I)
                                          or re.search(r"cf_chl_opt|cf-browser-verification|orchestrate/chl_page", document, re.I))
                                clean = 0 if active else clean + 1
                                if clean >= 2 and page.locator("body").count():
                                    if urlparse(page.url).hostname != urlparse(url).hostname:
                                        raise ValueError("Unexpected redirect")
                                    if request.get('download_url'):
                                        target = request['download_url']
                                        links = Links()
                                        links.feed(document)
                                        native = {urljoin(url, attrs.get('href', '')) for attrs, _ in links.links}
                                        if target not in native or urlparse(target).hostname != urlparse(url).hostname:
                                            raise ValueError('download not linked by native topic')
                                        response = context.request.get(target, timeout=max(1, int((deadline - time.monotonic()) * 1000)))
                                        if response.status != 200 or urlparse(response.url).hostname != urlparse(url).hostname:
                                            raise ValueError('metadata request failed')
                                        if 'bittorrent' not in response.headers.get('content-type', ''):
                                            raise ValueError('not torrent metadata')
                                        data = response.body()
                                        if len(data) > 4 * 1024 * 1024 or not data.startswith(b'd') or not data.endswith(b'e') or b'4:info' not in data:
                                            raise ValueError('invalid torrent metadata')
                                        send({'metadata': base64.b64encode(data).decode()})
                                    else:
                                        send({'html': document})
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




class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.current = [dict(attrs), []]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            attrs, text = self.current
            self.links.append((attrs, ' '.join(''.join(text).split())))
            self.current = None


class mejortorrent:
    url = 'https://www47.mejortorrent.eu'
    name = 'MejorTorrent (native public)'
    supported_categories = {'all': '', 'movies': 'pelicula', 'tv': 'serie'}

    def native_url(self, path):
        target = urljoin(self.url, path)
        if urlparse(target).hostname != urlparse(self.url).hostname or urlparse(target).scheme != 'https':
            raise ValueError('off-site route')
        return target

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat not in self.supported_categories:
            return
        browser = None
        try:
            browser = CamoufoxBrowser(Path(__file__).parent, 60, 900)
            search_url = self.url + '/busqueda?' + urlencode({'q': query})
            topics = []
            known_topics = set()
            known_pages = set()
            for _ in range(10):
                document = browser.fetch(search_url, 35)
                known_pages.add(search_url)
                listing = Links()
                listing.feed(document)
                next_page = None
                for attrs, title in listing.links:
                    path = attrs.get('href', '')
                    if not path.startswith(('/', self.url)):
                        continue
                    target = self.native_url(path)
                    if 'next' in attrs.get('rel', '').split() and urlparse(target).path.startswith('/busqueda/') and target not in known_pages:
                        next_page = target
                    kind = re.match(r'/(pelicula|serie)/[0-9]+/[^/]+', urlparse(target).path)
                    if not kind or not title or target in known_topics or not all(word.casefold() in title.casefold() for word in query.split()):
                        continue
                    if cat != 'all' and kind[1] != self.supported_categories[cat]:
                        continue
                    known_topics.add(target)
                    topics.append((target, title))
                if not next_page:
                    break
                search_url = next_page
            seen = set()
            for topic, title in topics:
                detail = browser.fetch(topic, 20)
                if '/serie/' in urlparse(topic).path:
                    entries = re.findall(r'<tr\b[^>]*>.*?</tr>', detail, re.S)
                else:
                    entries = [detail]
                for entry in entries:
                    downloads = Links()
                    downloads.feed(entry)
                    for attrs, label in downloads.links:
                        path = attrs.get('href', '')
                        if not urlparse(path).path.endswith('.torrent'):
                            continue
                        target = self.native_url(path)
                        if target in seen:
                            continue
                        seen.add(target)
                        episode = ''
                        published = -1
                        archive_key = ''
                        if '/serie/' in urlparse(topic).path:
                            cells = re.findall(r'<td\b[^>]*>(.*?)</td>', entry, re.S)
                            if len(cells) > 1:
                                episode = unescape(re.sub('<[^>]+>', '', cells[1])).strip()
                            if len(cells) > 2:
                                date = unescape(re.sub('<[^>]+>', '', cells[2])).strip()
                                try:
                                    published = int(datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())
                                except ValueError:
                                    pass
                            if len(cells) > 3:
                                key = unescape(re.sub('<[^>]+>', '', cells[3])).strip()
                                if key and key.casefold() != 'sin clave':
                                    archive_key = ', password: ' + key
                        prettyPrinter({'link': target + '#' + urlencode({'topic': urlparse(topic).path}),
                                       'name': title + (' - ' + episode if episode else '') + archive_key,
                                       'size': '-1', 'seeds': '-1', 'leech': '-1', 'pub_date': published,
                                       'engine_url': self.url, 'desc_link': topic})
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
        finally:
            if browser:
                browser.close()

    def download_torrent(self, info):
        parts = urlparse(info)
        target = self.native_url(parts._replace(fragment='').geturl())
        topic_path = parse_qs(parts.fragment).get('topic', [''])[0]
        if not re.fullmatch(r'/(?:pelicula|serie)/[0-9]+/(?:[0-9]+/)?[^/]+', topic_path) or not parts.path.startswith('/torrents/') or not parts.path.endswith('.torrent'):
            raise ValueError('invalid native download reference')
        topic = self.native_url(topic_path)
        browser = CamoufoxBrowser(Path(__file__).parent, 60, 900)
        try:
            data = browser.download(topic, target, 35)
            fd, path = tempfile.mkstemp(suffix='.torrent')
            with os.fdopen(fd, 'wb') as torrent:
                torrent.write(data)
            print(path + ' ' + target)
        finally:
            browser.close()


if __name__ == '__main__' and '--camoufox-worker' in sys.argv:
    camoufox_worker(int(sys.argv[-1]))
