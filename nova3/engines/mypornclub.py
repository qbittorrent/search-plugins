# VERSION: 1.3
# AUTHORS: BurningMop; kalpakprod (native metadata-only search and browser fallback)
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Native MyPornClub metadata search; automatic private browser, no account.
No video/image requests or external video webseed scraping; shared first bootstrap
about 1.3 GB. Only published native magnets are returned.
"""
import contextlib
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
from pathlib import Path
from urllib.parse import unquote, quote, urlparse, urljoin, parse_qs
from urllib.request import Request, urlopen

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
        print("MyPornClub: first launch downloads a private browser runtime; this can take several minutes", file=sys.stderr)
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
                    if route.request.resource_type in ('image', 'media'):
                        route.abort()
                    elif host in allowed or host == 'challenges.cloudflare.com':
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
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs))


class Cards(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows = []; self.row = None; self.depth = 0
        self.row_depth = 0; self.span_depth = 0; self.capture = None
        self.label = ''; self.title = None; self.skip_i = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs); classes = attrs.get('class', '').split()
        if tag == 'div':
            self.depth += 1
            if 'torrent_element' in classes:
                self.row = {'path': '', 'name': '', 'fields': {}}; self.row_depth = self.depth
        if self.row is None:
            return
        if tag == 'a' and not self.row['path'] and 'linkadd' not in classes:
            path = urlparse(attrs.get('href', '')).path
            if re.fullmatch(r'/t/[A-Za-z0-9]+', path):
                self.row['path'] = path; self.title = ''; self.skip_i = 0
        if tag == 'i' and self.title is not None:
            self.skip_i += 1
        if tag == 'span':
            self.span_depth += 1
            if 'teis' in classes or 'teiv' in classes:
                self.capture = ['label' if 'teis' in classes else 'value', self.span_depth, '']

    def handle_data(self, data):
        if self.title is not None and not self.skip_i:
            self.title += data
        if self.capture is not None:
            self.capture[2] += data

    def handle_endtag(self, tag):
        if self.row is not None:
            if tag == 'i' and self.skip_i:
                self.skip_i -= 1
            if tag == 'a' and self.title is not None:
                self.row['name'] = ' '.join(self.title.split()); self.title = None
            if tag == 'span':
                if self.capture is not None and self.capture[1] == self.span_depth:
                    kind, _, text = self.capture
                    if kind == 'label':
                        self.label = text.strip().strip('[]:').lower()
                    else:
                        self.row['fields'][self.label] = ' '.join(text.split())
                    self.capture = None
                self.span_depth -= 1
            if tag == 'div' and self.depth == self.row_depth:
                if self.row['path'] and self.row['name']:
                    self.rows.append(self.row)
                self.row = None; self.title = None; self.capture = None; self.span_depth = 0
        if tag == 'div':
            self.depth -= 1


class mypornclub:
    url = 'https://myporn.club'
    name = 'MyPornClub'
    supported_categories = {'all': 'all'}

    @staticmethod
    def infohash(link):
        if urlparse(link).scheme != 'magnet':
            raise ValueError('not a native magnet')
        for value in parse_qs(urlparse(link).query).get('xt', []):
            match = re.fullmatch(r'urn:btih:([0-9a-fA-F]{40})', value)
            if match and match[1] != '0' * 40:
                return match[1].lower()
        raise ValueError('invalid native magnet')

    def native_url(self, path):
        target = urljoin(self.url, unescape(path))
        if urlparse(target).scheme != 'https' or urlparse(target).hostname != urlparse(self.url).hostname:
            raise ValueError('off-site metadata route')
        return target

    def fetch(self, path, kind):
        target = self.native_url(path); document = ''; remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('search deadline reached')
        def valid(text):
            return 'torrents_list' in text if kind == 'listing' else bool(re.search(r'href=["\x27]magnet:', text))
        if self.browser is None:
            try:
                with urlopen(Request(target, headers={'User-Agent': 'Mozilla/5.0'}), timeout=min(5, remaining)) as response:
                    self.native_url(response.geturl()); data = response.read(4 * 1024 * 1024 + 1)
                    if len(data) > 4 * 1024 * 1024:
                        raise ValueError('response too large')
                    document = data.decode(response.headers.get_content_charset() or 'utf-8')
            except (OSError, ValueError, LookupError):
                pass
        if not valid(document):
            if self.browser is None:
                started = time.monotonic()
                self.browser = CamoufoxBrowser(Path(__file__).parent, 60, 900)
                self.deadline += time.monotonic() - started
            document = self.browser.fetch(target, min(45, max(1, self.deadline - time.monotonic())))
        if not valid(document):
            raise ValueError('unrecognized native metadata document')
        return document

    def search(self, what, cat='all'):
        query = unquote(what).strip()
        if not query or cat != 'all':
            return
        query = re.sub(r'\s+', '-', query)
        target = self.url + '/s/' + quote(query, safe='')
        self.browser = None; self.deadline = time.monotonic() + 240
        pages = set(); topics = set(); hashes = set()
        try:
            while target and target not in pages:
                pages.add(target); document = self.fetch(target, 'listing')
                cards = Cards(); cards.feed(document)
                for card in cards.rows:
                    if card['path'] in topics:
                        continue
                    topics.add(card['path']); detail = Links(); detail.feed(self.fetch(card['path'], 'detail'))
                    for attrs in detail.links:
                        link = attrs.get('href', '')
                        try:
                            key = self.infohash(link)
                        except (ValueError, TypeError):
                            continue
                        if key in hashes:
                            continue
                        hashes.add(key); fields = card['fields']; size = fields.get('size', '-1')
                        if not re.fullmatch(r'[0-9.,]+\s*(?:KB|MB|GB|TB|KiB|MiB|GiB|TiB)', size, re.I):
                            size = '-1'
                        seed = fields.get('seeders', '').replace(',', ''); leech = fields.get('leechers', '').replace(',', '')
                        prettyPrinter({'link': link, 'name': card['name'], 'size': size,
                                       'seeds': int(seed) if seed.isdigit() else -1,
                                       'leech': int(leech) if leech.isdigit() else -1,
                                       'desc_link': self.native_url(card['path']), 'engine_url': self.url, 'pub_date': -1})
                links = Links(); links.feed(document)
                next_page = next((attrs['href'] for attrs in links.links if 'pagpn' in attrs.get('class', '').split() and attrs.get('href')), '')
                if not next_page:
                    selected = next((attrs for attrs in links.links if 'pagsel' in attrs.get('class', '').split()), None)
                    if selected:
                        current = urlparse(selected.get('href', '')).path.rsplit('/', 1)[-1]
                        if current.isdigit():
                            next_page = next((attrs['href'] for attrs in links.links
                                              if 'pagn' in attrs.get('class', '').split() and
                                              urlparse(attrs.get('href', '')).path.rsplit('/', 1)[-1] == str(int(current) + 1)), '')
                target = self.native_url(next_page) if next_page else ''
        except (OSError, ValueError, LookupError) as error:
            print(self.name + ': ' + type(error).__name__, file=sys.stderr)
        finally:
            if self.browser:
                self.browser.close()

    def download_torrent(self, link):
        target = link if link.startswith('magnet:?') else unquote(link)
        self.infohash(target); print(target + ' ' + target)


if __name__ == '__main__' and '--camoufox-worker' in sys.argv:
    camoufox_worker(int(sys.argv[-1]))
