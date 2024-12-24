This guide will help you to configure the the new qBittorrent search engine.

## Deprecation notice

Until version 4.5.0, qBittorrent had a native search engine based on Python. qBittorrent team was in charge of checking the installation of Python and the maintenance of the [search plugins](https://github.com/qbittorrent/search-plugins) for the torrent sites. There were also [unofficial plugins](https://github.com/qbittorrent/search-plugins/wiki/Unofficial-search-plugins) maintained by the community.

Over the time, maintaining this system has become a burden due to the large number of torrent sites and the lack of developers with knowledge of Python.
Since version 4.5.0 the native search engine is replaced with a new search engine that makes calls to [Torznab compatible APIs](https://torznab.github.io/spec-1.3-draft/torznab/Specification-v1.3.html). This implies that the end user has to install additional software to perform searches in qBittorrent.

## Torznab clients

[Torznab](https://torznab.github.io/spec-1.3-draft/torznab/Specification-v1.3.html) is an API specification based on the Newznab WebAPI. The API is built around a simple XML/RSS feed with filtering and paging capabilities.

There are several software compatible with this specification. Its goal is to support as many torrent sites as possible, parse the content and convert the results into Torznab format so it can be consumed by other applications such as qBittorrent. 

These are the most popular applications:
* [Jackett](https://github.com/Jackett/Jackett): **(recommended)**. It supports more than 500 torrent sites and has the biggest user base.
* [Prowlarr](https://github.com/Prowlarr/Prowlarr): It supports the same sites as Jackett but with more modern UI.
* [NZB Hydra](https://github.com/theotherp/nzbhydra2): It includes more features but supports less torrent sites.
* [Cardigann](https://github.com/cardigann/cardigann): Some sites still work, but it is no longer maintained.

All of them work fine on qBittorrent, but we only provide instructions for Jackett.

## Jackett installation
[Jackett](https://github.com/Jackett/Jackett) is available for Windows, Linux and macOS. It's also available as Docker container and Linux distribution package.

You can find the installation instructions [here](https://github.com/Jackett/Jackett#installation-on-windows). It's really recommended to install Jackett as a system service. In this way it will start automatically when you start the computer and it will always be up to date.

Once Jackett is installed. You can open the Web UI to configure the torrent sites. The Jackett URL is usually http://127.0.0.1:9117 The next step is to set up your favorite torrent sites. Click the "Add indexer" button and follow the instructions. 

![](https://raw.githubusercontent.com/qbittorrent/search-plugins/master/docs/qbittorrent_torznab_search_1.png)

When you're done, use the "Manual search" to check that it works correctly.

![](https://raw.githubusercontent.com/qbittorrent/search-plugins/master/docs/qbittorrent_torznab_search_2.png)

## qBittorrent search engine

By default the search engine is disabled. You can enable it in "View => Search engine".

![](https://raw.githubusercontent.com/qbittorrent/search-plugins/master/docs/qbittorrent_torznab_search_3.png)

Now you will see a new tab where you can search and configure the "Indexers" (torrent sites).

![](https://raw.githubusercontent.com/qbittorrent/search-plugins/master/docs/qbittorrent_torznab_search_4.png)

You have to add the indexers one by one. The name can be anything. The Toznab URL and API Key are copied from the Jackett Web UI.

![](https://raw.githubusercontent.com/qbittorrent/search-plugins/master/docs/qbittorrent_torznab_search_5.png)

![](https://raw.githubusercontent.com/qbittorrent/search-plugins/master/docs/qbittorrent_torznab_search_6.png)

The indexers can be disabled and edited with the "right-click menu".

![](https://raw.githubusercontent.com/qbittorrent/search-plugins/master/docs/qbittorrent_torznab_search_7.png)

You can perform searches in all enabled indexers as usual.

![](https://raw.githubusercontent.com/qbittorrent/search-plugins/master/docs/qbittorrent_torznab_search_8.png)

If some indexer is not working as expected (or you don't get results at all) check the qBittorrent and Jackett logs for further details.