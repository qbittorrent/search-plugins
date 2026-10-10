# Plugin verification: 8 October 2026

This is a Nova search-engine check, not a claim that every tracker works on every network.
Only real result rows count as a live result. A successful download of a Python file does not count.
Error/configuration rows and missing credentials do not count as torrent results.

The public sweep ran each plugin separately in a temporary Nova installation on Python 3.14.
No torrent payload was downloaded. Private plugins were not run with owner credentials.
Empty searches and timeouts are unresolved, not proof that a site has closed.

## Repairs with live evidence

| Plugin | Version | Repair | Live result |
| --- | --- | --- | --- |
| The Pirate Bay, official | 3.11 | Bounded API request, no JSON crash after blocked or invalid response | Previous engine returned 24 Dream Scenario results; updated error handling covered offline |
| LimeTorrents, official | 4.16 | Current `limetorrents.fun` domain instead of redirecting `.lol` | 36 Dream Scenario results |
| TorrentProject, official | 1.93 | Reachable `.cc` domain instead of broken `.com.se` | 100 Ubuntu results |
| Mikan Project | 0.5 | Removed obsolete `helpers.headers`; current RSS domain; errors in stderr | 100 Naruto results |
| The Pirate Bay with categories | 4.2 | Validated direct magnet instead of percent-encoded URL; publication date | 24 Dream Scenario results |
| TorrentDownload with categories | 2.3 | Preserve `https://` when encoding links | 24 Dream Scenario results |
| TorrentGalaxy `.one` mirror | 0.1 | New parser for current mirror listing/detail routes | 1 Dream Scenario magnet; not the original `.to` service |

`torrents-csv` returned 25 Ubuntu results. Its working search code was not changed.
Jackett has offline Torznab coverage; no configured live Jackett server was available.

## Source and access blockers

- SolidTorrents: `.to`, `.net` and `.eu` timed out on this network. No working replacement was confirmed.
- CloudTorrents: both the site and API returned Cloudflare 526 (origin TLS failure). This cannot be repaired by disabling TLS validation in a plugin.
- Cpasbien, MaxiTorrent and Torrent9: cannot import with current Nova because `helpers.headers` was removed.
- Legacy DMHY and Sukebei variants require lxml/BeautifulSoup; the working standalone alternatives remain available.
- Private trackers need configured accounts/cookies/API keys. They have not been labelled broken merely because those credentials were absent.

## Full sweep observations

The following table records the upstream-version sweep before the repairs above.
Use the repair table where its result supersedes an older observation.

| Plugin | Source version | Search | Result |
| --- | --- | --- | --- |
| 1337x | 1.1 | Matrix | 20 live rows |
| Academic Torrents | 1.4 | MNIST | 5 live rows |
| acgrip | 2.1 | Naruto | 30 live rows |
| ali213.net | 1.1 | Mario | no verified result; unresolved |
| anidex.info | 0.02 | Naruto | search failed (IndexError) |
| animetosho.org | 1.00 | Naruto | 75 live rows |
| Anime Tosho | 1.21 | Naruto | 75 live rows |
| Apache Torrent | 1.00 | Matrix | no verified result; unresolved |
| AudioBook Bay (ABB)  | 0.4 | Matrix | no verified result; unresolved |
| Bit Search | 1.3 | Matrix | no verified result; unresolved |
| bt4gprx | 2.0 | Matrix | no verified result; unresolved |
| btdig | 1.1 | Matrix | no verified result; unresolved |
| CalidadTorrent | 1.0 | Matrix | 40-second probe timed out; unresolved |
| CloudTorrents | 1.0 | Matrix | search failed (json.decoder.JSONDecodeError) |
| Cpasbien | 2.2 | not run | module import failed |
| dark-libria | 0.13 | Naruto | no verified result; unresolved |
| divxtotal | 1.0 | Matrix | search failed (IndexError) |
| DMHY | 1.00 | not run | module import failed |
| DMHY | 1.1 | Naruto | 1000 live rows |
| DODI Repacks | 1.1 | Mario | search failed (json.decoder.JSONDecodeError) |
| Dontorrent | 1.00 | Matrix | 40-second probe timed out; unresolved |
| dontorrent | 1.2 | Matrix | no verified result; unresolved |
| Elitetorrent | 1.6 | Matrix | search failed (IndexError) |
| esmeraldatorrent | 1.0 | Matrix | search failed (IndexError) |
| EZTV | 3.20 | Matrix | 1 live rows |
| FitGirl Repacks | 3.3 | Mario | no verified result; unresolved |
| GloTorrents | 1.7 | Matrix | 40-second probe timed out; unresolved |
| Gog-games | 1.0 | Mario | no verified result; unresolved |
| Kickass Torrent | 1.2 | Matrix | no verified result; unresolved |
| Linux Tracker | 1.0 | Ubuntu | no verified result; unresolved |
| MagnetDL | 1.4 | Matrix | search failed (IndexError) |
| MagnetDL with categories | 2.1 | Matrix | no verified result; unresolved |
| MaxiTorrent | 1.25 | not run | module import failed |
| MejorTorrent | 1.01 | Matrix | no verified result; unresolved |
| Mikan Project | 0.4 | not run | module import failed |
| mikanani | 1.2 | Naruto | 1000 live rows |
| My Porn Club | 1.1 | Matrix | 40-second probe timed out; unresolved |
| naranjatorrent | 1.0 | Matrix | search failed (IndexError) |
| nekoBT | 1.0 | Naruto | 16 live rows |
| Nyaa.pantsu | 1.2 | Naruto | no verified result; unresolved |
| Nyaa.si | 1.3 | Naruto | no verified result; unresolved |
| Online-Fix | 1.0 | Matrix | search failed (json.decoder.JSONDecodeError) |
| PediaTorrent | 1.00 | Matrix | search failed (IndexError) |
| PediaTorrent | 1.1 | Matrix | no verified result; unresolved |
| Pirateiro | 1.4 | Matrix | 51 live rows |
| Rede Torrent | 1.00 | Matrix | no verified result; unresolved |
| RockBox | 1.2 | Metallica | 40-second probe timed out; unresolved |
| Rutor | 1.22 | Matrix | 227 live rows |
| SkTorrent | 1.1 | Matrix | 48 live rows |
| small-games.info | 1.03 | Mario | search failed (urllib.error.HTTPError) |
| Snowfl | 1.3 | Matrix | search failed (json.decoder.JSONDecodeError) |
| Snowfl | 2.1 | Matrix | search failed (json.decoder.JSONDecodeError) |
| SolidTorrents.to | 1.0 | Matrix | no verified result; unresolved |
| SubsPlease.org | 1.1 | Naruto | 378 live rows |
| Sukebei (Nyaa) | 1.11 | Naruto | 548 live rows |
| Sukebei Nyaa | 1.03 | not run | module import failed |
| ThePirateBay | 1.1 | Matrix | 100 live rows |
| ThePirateBay with categories | 4.1 | Matrix | no verified result; unresolved |
| The RarBg | 1.3 | Matrix | no verified result; unresolved |
| TomaDivx | 1.1 | Matrix | search failed (IndexError) |
| Tokyo Toshokan | 2.3 | Naruto | 40-second probe timed out; unresolved |
| Torrent9 | 2.0 | not run | module import failed |
| TorrentClaw | 1.0 | Matrix | no verified result; unresolved |
| TorrentDownload | 1.2 | Matrix | 495 live rows |
| TorrentDownload with categories | 2.2 | Matrix | no verified result; unresolved |
| Torrent Downloads Pro | 1.1 | Matrix | 200 live rows (KeyError) |
| Torrenflix | 1.0 | Matrix | no verified result; unresolved |
| TorrentGalaxy | 0.08 | Matrix | search failed (IndexError) |
| TrahT | 1.0 | Matrix | no verified result; unresolved |
| TsukiHime | 1.00 | Matrix | search failed (KeyError) |
| UIndex | 1.0 | Matrix | no verified result; unresolved |
| XXXClub | 1.3 | Matrix | no verified result; unresolved |
| YourBittorrent | 1.3 | Matrix | search failed (IndexError) |
| YTS | 1.9 | Matrix | 24 live rows |
| YGGtracker | 1.1.0 | Matrix | search failed (json.decoder.JSONDecodeError) |
| Zooqle | 1.1 | Matrix | search failed (urllib.error.URLError) |
| BakaBT | 1.4 | not run | credentials required; live search not run |
| BitPorn | 1.00 | not run | credentials required; live search not run |
| C411 | 1.00 | not run | credentials required; live search not run |
| DanishBytes | 1.50 | not run | credentials required; live search not run |
| FileList | 1.2 | not run | credentials required; live search not run |
| GazelleGames | not read | not run | credentials required; live search not run |
| IPTorrents | 1.01 | not run | credentials required; live search not run |
| Kinozal | 2.26 | not run | credentials required; live search not run |
| Lat-Team | 1.0 | not run | credentials required; live search not run |
| LostFilm.TV | 0.22 | not run | credentials required; live search not run |
| Milkie | 1.0 | not run | credentials required; live search not run |
| nCore | 1.3 | not run | credentials required; live search not run |
| NoNaMe-Club | 2.27 | not run | credentials required; live search not run |
| Prowlarr | 2.2 | not run | credentials required; live search not run |
| Redacted | 1.00 | not run | credentials required; live search not run |
| RuTracker | 1.22 | not run | credentials required; live search not run |
| RuTracker | 2.21 | not run | credentials required; live search not run |
| [[https://rutracker.org/ RuTracker Public]] | 0.6 | not run | public browser plugin; does not require RuTracker login; qualified separately |
| SpeedApp.IO | 1.1 | not run | credentials required; live search not run |
| Tapochek | 1.1 | not run | credentials required; live search not run |
| TorrentLeech | 1.0 | not run | credentials required; live search not run |
| TR4KER | 1.00 | not run | credentials required; live search not run |
| Гуртом — торрент-толока | 1.20 | not run | credentials required; live search not run |
| UnionFansub | 2.0 | not run | credentials required; live search not run |
| UnionFansub | 1.5 | not run | credentials required; live search not run |
| YggAPI | 1.2 | not run | credentials required; live search not run |
| YggTorrent | 1.6 | not run | credentials required; live search not run |
| Zamunda.RIP | 1.1 | not run | archival record |
| UnionDHT | not read | not run | original source returns 404 (HTTPError) |
| Pornolab | not read | not run | original source returns 404 (HTTPError) |
| Nyaa.Pantsu | not read | not run | original source returns 404 (HTTPError) |
| Sukebei.Pantsu | not read | not run | original source returns 404 (HTTPError) |
| eztv (official) | 1.24 | Matrix | no verified result; unresolved |
| jackett (official) | 4.13 | not run | configured service/browser flow; separate qualification |
| limetorrents (official) | 4.15 | Matrix | 159 live rows |
| piratebay (official) | 3.10 | Matrix | 100 live rows |
| solidtorrents (official) | 2.9 | Matrix | no verified result; unresolved |
| torlock (official) | 2.31 | Matrix | no verified result; unresolved |
| torrentproject (official) | 1.92 | Matrix | no verified result; unresolved |
| torrentscsv (official) | 1.8 | Matrix | 25 live rows |

## Interpretation and remaining work

A live result validates the search/output path, not every category or later torrent payload.
Source versions are read from `# VERSION`; historical compatibility claims in the catalogue are not fresh tests.
Unresolved empty searches need a second relevant query/site inspection before archival or repair.
No owner secrets, login sessions or production qBittorrent files were used for this sweep.
