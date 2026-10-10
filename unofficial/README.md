# Repaired standalone plugins

Install any one `.py` from this directory in qBittorrent. Each file is independent;
none requires another plugin, manual pip, Docker, a tracker account or a local server.

## Anonymous Russian tracker search

- `kinozal_public.py` — Kinozal releases in the public index.
- `toloka_public.py` — Toloka releases in the public index.
- `nnmclub_public.py` — NNM-Club releases in the public index.

These implement the same client-side API flow as **Lampac NextGen**:
`Modules/JacRed/ModInit.cs` selects `typesearch=webapi`, and
`Modules/JacRed/Engine/WebApi.cs` queries `/api/v2.0/indexers/all/results`.
The default upstream was read at commit
`376680a8e4b7c61b2b11cafe370313f933089f51` of
[lampac-nextgen/lampac](https://github.com/lampac-nextgen/lampac).

**A personal tracker login is not required.** The public server already holds a
crawl/index. This does not imply that the server's own crawler is anonymous:
Lampac's Toloka controller and JacRed's Kinozal/Toloka synchronization services
use server-side login/cookies. Jackett's current `kinozal` and `kinozal-magnet`
definitions also configure login. Client access and crawler authentication are
separate concerns.

Results are filtered by exact tracker membership, including comma-separated
merged trackers, and deduplicated by a valid infohash. A merged release can have
a description link on another member tracker. Movie/TV coverage and freshness
are those of the external index, not a promise of full live-site search.

**Transport limitation:** Lampac's tested public default uses HTTP. HTTPS on that
same host was not reachable during implementation. Queries are not encrypted;
do not include credentials/private tokens in searches. Availability depends on
the external operator. No owner files or tracker credentials are uploaded.

## Other repairs

- `snowfl.py` 2.2: dedicated bounded transport with the accepted browser UA and
  Referer, qBittorrent query decoding, correctly encoded resolver paths, valid
  magnet-only output. Fork of ChocoTonic's MIT standalone source; its license is
  included in the file.
- `yourbittorrent.py` 1.4: current single-table layout, exclusion of off-site ad
  rows, accepted curl UA, and the actual download-page route to the site's
  `yt.t0r.store` torrent host. Only matching torrent IDs and bencoded metadata
  are accepted; HTML/ad pages are not saved as torrents.

- `tsukihime.py` 1.01: current API transport, Python 3.9-compatible syntax,
  bounded search, and valid search hashes retained when optional tracker stats
  return an error instead of a `trackers` array.
- `nyaasi_public.py` 0.1: Nyaa-origin releases from that reachable public index.
  Exact positive `nyaa_id` membership is required; it is not live Nyaa search and
  does not claim that the currently unreachable Nyaa host was repaired.
- `elitetorrent.py` 1.7: accepted transport, every encoded magnet candidate
  checked instead of assuming the second exists, current `&st=` link suffix,
  missing dates/peers handled without crashing. Original iordic MIT license is
  included in the file.

## Alcopac source boundary

The current [Alcopac installation documentation](https://wiki.alcopa.cc/docs/install/curl)
points to [Kirill9732/Alcopac_docker](https://github.com/Kirill9732/Alcopac_docker).
That distribution bundles Go binaries. No source-level equivalent of the
tracker-search flow was established there, so no claim of copied Alcopac logic
is made. The implemented contract comes from accessible AGPL Lampac/JacRed
sources, not binary execution or guessed API routes.
