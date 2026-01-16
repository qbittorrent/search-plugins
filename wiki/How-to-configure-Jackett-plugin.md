# Jackett integration for qBittorrent

**qBittorrent** comes with a few search plugins. Although these are often
sufficient for most users, those who wish to perform searches at a wider array
of indexing sites have the option of installing **[Jackett][jackett]** and
running it in tandem with qBittorrent to take advantage of its much larger
catalog of indexers (584, as of November 2025) and efficiency in retrieving results
from them. Configure the **Jackett qBittorrent plugin** (essentially, set the API key).

## What is Jackett?

As explained in the project's [README.md file][jackett-readme] (emphasis added):

> Jackett works as a proxy server: it translates queries from apps ([including]
> qBittorrent […]) into site-specific HTTP queries for any number of
> [BitTorrent] trackers, parses the HTML or JSON responses, then sends the
> results back to the requesting software. This allows for getting recent
> uploads (like RSS) and performing searches. Jackett is a single repository of
> **maintained indexer scraping and translation logic** — removing the burden
> from other apps.

More plainly, while qBittorrent is a download manager which has evolved to
include some built-in facilities for torrent discovery, Jackett is purpose-built
software designed for performing those same searches on a much larger scale. An
application such as qBittorrent can present the searches it's asked to perform
to Jackett, which broadcasts them to a user-defined list of potentially hundreds
of indexing sites all at once, and then feeds the results back as they come in.
The primary advantages to this arragement are threefold:

- As performing searches is its only function, it is much faster at conducting
  them and processing the results.
- The ability to perform searches at a much wider list indexes that is quick to
  add new sites and remove dead ones.
- It is much better at reacting to the frequent changes that occur on the
  indexer sites that arise as they work to mitigate attempts to interrupt their
  operation.

Updates to their catalog of indexers take place almost daily and it includes
hundreds of sites which never had nor were ever likely to get their own
qBittorrent search plugin.

## Installation

### Prerequisites

Jackett is built using the .NET framework and requires that you have the .NET 8
Runtime present on your system prior to installation. Microsoft provides
installer files for the runtime for [Windows][dotnet-windows-support],
[macOS][dotnet-macos-support] and [GNU/Linux][dotnet-linux-support] (click the
preceding links to see the minimum requirements for each operating system).

**[Microsoft .NET Downloads][dotnet-downloads]**

**Official .NET installation guides**:

- [Windows][dotnet-windows-install]
- [macOS][dotnet-macos-install]
- [Linux][dotnet-linux-install]

### Jackett

Once the .NET runtime is installed, follow the official documentation linked
below to install and configure Jackett.

- [Installation on Windows][install-windows]
- Installation on Linux:
  - [AMD64 (x86_64)][install-linux-amd64]
  - [ARMv7 and newer][install-linux-armv7]
  - [ARMv6 and older][install-linux-armv6]

### qBittorrent plugin

> [!NOTE]  
> The full download URL for the plugin file is
> `https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/jackett.py`

Follow these steps to manually install the plugin:

1. Launch qBittorrent and click on the Search tab (only shown when "Search
   Engine" is active in the View menu)
1. Highlight the URL shown above or right-click [this link][plugin-file] and
   **copy** it to the clipboard
1. Click the **Search plugins…** button in the bottom-right corner, then click
   **Install a new one**, and finally **Web link** as the "Search plugin source"
1. qBittorrent tries to automatically fill the input field if a URL is found on
   the clipboard, but if not, manually paste the URL there

## Configuration

> [!IMPORTANT]
> Remember to [start Jackett](https://github.com/Jackett/Jackett#supported-systems)
> first. :)

The Jackett plugin uses an external configuration file, ensuring that any
updates to the plugin file will not erase or reset your settings. The name of
the configuration file is `jackett.json` and it must reside in the same folder
as the qBittorrent search plugin files, the defaults for which are:

- **Windows:**
  - CMD syntax: `%LOCALAPPDATA%\qBittorrent\nova3\engines`
  - PowerShell syntax: `"${Env:LOCALAPPDATA}\qBittorrent\nova3\engines"`
- **Linux:**
  - `"${XDG_DATA_HOME:-$HOME/.local/share}/qBittorrent/nova3/engines"` (current)
  - `"${XDG_DATA_HOME:-$HOME/.local/share}/data/qBittorrent/nova3/engines"` (former)
  - `"${HOME}/.var/app/org.qbittorrent.qBittorrent/data/qBittorrent/nova3/engines"`
- **macOS:** `"~/Library/Application Support/qBittorrent/nova3/engines"`

If for some reason the configuration file doesn't exist, create one with the
following contents:

```json
{
    "api_key": "YOUR_API_KEY_HERE",
    "url": "http://127.0.0.1:9117",
    "tracker_first": false,
    "thread_count": 20
}
```

> [!TIP]
> If running qBittorrent in headless mode and accessing its web interface
> remotely, Jackett's default configuration to bind to the loopback address
> (127.0.0.1) must be replaced with a routable address (for instance, using DDNS
> or an IPv6 Global Unicast Address) to allow traffic to pass between it and
> qBittorrent. Additional firewall rules or port forwarding may also be needed.
> 
> The change must be made in both the Jackett UI and the plugin configuration
> file, specifically its `url` key. For example:

```diff
 {
     "api_key": "YOUR_API_KEY_HERE",
-    "url": "http://127.0.0.1:9117",
+    "url": "http://yourserver.ddnsprovider.host:9117",
     "tracker_first": false,
     "thread_count": 20
 }
```

### Configuration file properties

|  Property name  |      Initial value      |                                             Description                                             |
|:----------------|:------------------------|:----------------------------------------------------------------------------------------------------|
|    `api_key`    |   `YOUR_API_KEY_HERE`   | Jackett API Key, shown in the upper-right corner of the Jackett UI ([screenshot below][api-key-ss]) |
|      `url`      | `http://127.0.0.1:9117` | Jackett service address (without a terminating forward slash)                                       |
| `tracker_first` |         `false`         | Prepend indexer site name to each search result (takes Boolean value)                               |
| `thread_count`  |          `20`           | Maximum number of concurrent requests to Jackett (to disable concurrent requests, set value to `1`) |

## Disabling/Removing the Jackett plugin

The Jackett plugin is enabled by default in qBittorrent. However, you can
disable it or removing it entirely at any time by following these steps:

1. In the **Search** tab, click the **Search plugins…** button in the
   bottom-right corner.
1. Locate the entry named **Jackett** in the list.
1. To disable the plugin:
   - Right-click the entry and clear the checkmark from the **Enabled** option.

   Or to uninstall the plugin:
   - Right-click the entry and select **Uninstall**.
1. Click the **Close** button.

## Screenshots

### Jackett API Key

![Jackett UI screenshot showing API Key location][api-key]

### Search results

After successfully installing Jackett and integrating it with qBittorrent, the
results it provides appear as seen below.

![qBittorrent search tab with Jackett results][search-tab-results]

[jackett]: https://github.com/Jackett/Jackett "Jackett: API support for your favorite torrent trackers"
[jackett-readme]: https://github.com/Jackett/Jackett/blob/master/README.md "Jackett: README.md"
[dotnet-windows-support]: https://github.com/dotnet/core/blob/main/release-notes/8.0/supported-os.md#windows
[dotnet-macos-support]: https://github.com/dotnet/core/blob/main/release-notes/8.0/supported-os.md#macos
[dotnet-linux-support]: https://github.com/dotnet/core/blob/main/release-notes/8.0/supported-os.md#linux
[dotnet-downloads]: https://dotnet.microsoft.com/download/dotnet/8.0
[dotnet-windows-install]: https://github.com/dotnet/core/blob/main/release-notes/8.0/install-windows.md
[dotnet-macos-install]: https://github.com/dotnet/core/blob/main/release-notes/8.0/install-macos.md
[dotnet-linux-install]: https://github.com/dotnet/core/blob/main/release-notes/8.0/install-linux.md
[install-windows]: https://github.com/Jackett/Jackett#installation-on-windows
[install-linux-amd64]: https://github.com/Jackett/Jackett#installation-on-linux-amdx64
[install-linux-armv7]: https://github.com/Jackett/Jackett#installation-on-linux-armv7-or-above
[install-linux-armv6]: https://github.com/Jackett/Jackett#installation-on-linux-armv6-or-below
[plugin-file]: https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/jackett.py
[api-key-ss]: #jackett-api-key
[api-key]: https://i.imgur.com/87yZeAU.png
[search-tab-results]: https://i.imgur.com/uCawgLa.png
