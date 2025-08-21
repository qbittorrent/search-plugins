#!/usr/bin/sh

cd "$(dirname "$0")" || exit
git clone --depth 1 https://github.com/qbittorrent/qBittorrent.git
mv qBittorrent/src/searchengine/nova3/* ./
rm -rf qBittorrent __init__.py
