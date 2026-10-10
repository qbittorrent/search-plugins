# How to Write a Search Plugin

qBittorrent provides a search engine plugin management system.
Thanks to this, you can *easily* write your own plugins to look for torrents in your favorite BitTorrent search engines and extend qBittorrent's integrated search engine.

* All you need is some motivation and some knowledge of [Python](https://www.python.org).
* **The minimum supported Python version is specified in [this file](https://github.com/qbittorrent/qBittorrent/blob/master/INSTALL#L21-L23); make sure your plugin can work with it and every later version.**
* **Only import libraries from the [Python Standard Library](https://docs.python.org/3/library/index.html)**. \
  Third party libraries (such as those installed from [PyPI](https://pypi.org/)) are ***not*** guaranteed to be present in the user's environment.
* You are encouraged to ensure good quality of your plugin: [Python Code Quality: Tools & Best Practices](https://realpython.com/python-code-quality/). \
  For example, here is how the official plugins are checked: [ci.yaml](https://github.com/qbittorrent/search-plugins/blob/60a3f4d9c97a5d1f94e75789a72ee054044c5802/.github/workflows/ci.yaml#L29-L44).

## Table of Contents

* [Plugins Specification](#plugins-specification)
  * [Search Results Format](#search-results-format)
  * [Python Class File Structure](#python-class-file-structure)
  * [Parsing Results from Web Pages](#parsing-results-from-web-pages)
* [Understanding the Code](#understanding-the-code)
  * [PrettyPrinter Helper Function](#prettyprinter-helper-function)
  * [Retrieve_URL Helper Function](#retrieve_url-helper-function)
  * [Download_File Helper Function](#download_file-helper-function)
* [Testing & Finalizing Your Code](#testing--finalizing-your-code)
  * [Code Examples](#code-examples)
  * [Testing Your Plugin](#testing-your-plugin)
  * [Install Your Plugin](#install-your-plugin)
  * [Publish Your Plugin](#publish-your-plugin)
  * [Notes](#notes)

## Plugins Specification

⚠️ **The plugin communicates data back to qBittorrent via `stdout`, which means you must NOT print debug or error messages to `stdout` under any circumstances.** \
You can print debug or error messages to `stderr` instead, or even better, use the Python [`logging`](https://docs.python.org/3/howto/logging.html) facility.

### Search Results Format

First, you must understand that a qBittorrent search engine plugin is actually a Python class file whose task is to contact a search engine website (e.g., [The Pirate Bay](https://www.thepiratebay.org)),
parse the results displayed on the webpage, and print them to `stdout` using the following syntax:

```text
link|name|size|seeds|leech|engine_url|desc_link|pub_date
```

* One search result per line.
* The `name` field might contain the delimiter character `|` and is therefore percent-encoded (since qBittorrent v5.3).
* It is strongly recommended to use the provided `novaprinter.prettyPrinter` helper function instead of formatting it manually. \
  See below for more information.

For example:

```text
magnet:?xt=urn:btih:5F5E8848426129AB63CB4DB717BB54193C1C1AD7|ubuntu-20.04.6-desktop-amd64.iso|4351463424|15|2|https://thepiratebay.org|https://thepiratebay.org/description.php?id=72774917|1696870394
magnet:?xt=urn:btih:02767050E0BE2FD4DB9A2AD6C12416AC806ED6ED|Tears%20of%20Steel%20%282012%29%201080p%20webm|571346576|24|0|https://thepiratebay.org|https://thepiratebay.org/description.php?id=7729403|1350291937
```

### Python Class File Structure

Your plugin should be named `engine_name.py`, in lowercase and without spaces or special characters.
You will also need [the other files](https://github.com/qbittorrent/qBittorrent/tree/master/src/searchengine/nova3) for the project

The files are:

```text
-> nova2.py # the main search engine script which calls the plugins
-> nova2dl.py # standalone script called by qBittorrent to download a torrent using a particular search plugin
-> helpers.py # contains helper functions you can use in your plugins such as `retrieve_url()` and `download_file()`
-> novaprinter.py # contains some useful functions like `prettyPrint()` to display your search results
-> socks.py # Required by `helpers.py`. This module provides a standard socket-like interface.
```

Here is the basic structure of `engine_name.py`:

```python
# VERSION: 1.00
# AUTHORS: YOUR_NAME (YOUR_MAIL)
# LICENSING INFORMATION

from html.parser import HTMLParser
from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter
# some other imports if necessary

class engine_name:
    """
    `url`, `name`, `supported_categories` should be static variables of the engine_name class,
     otherwise qbt won't install the plugin.

    `url`: The URL of the search engine.
    `name`: The name of the search engine, spaces and special characters are allowed here.
    `supported_categories`: What categories are supported by the search engine and their corresponding id,
    possible categories are ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv').
    """

    url = 'https://www.engine-url.org'
    name = 'Full engine name'
    supported_categories: dict[str, str] = {
        'all': '0',
        'anime': '7',
        'games': '2',
        'movies': '6',
        'music': '1',
        'software': '3',
        'tv': '4'
    }

    def __init__(self) -> None:
        """
        Some initialization
        """

    def download_torrent(self, url: str) -> None:
        """
        Providing this function is optional.
        It can however be interesting to provide your own torrent download
        implementation in case the search engine in question does not allow
        traditional downloads (for example, cookie-based download).
        """
        print(download_file(url))

    # DO NOT CHANGE the name and parameters of this function
    # This function will be called from nova2.py
    def search(self, query: str, category: str = 'all') -> None:
        """
        Here you can do what you want to get the result from the search engine website.
        Every time you parse a result line, store it in a dictionary
        and call the prettyPrint(your_dict) function.

        `query` is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        `category` is the name of a search category in ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv')
        """
```

**PLEASE note that the filename (without the `.py` extension) must be identical to the class name. Otherwise, qBittorrent will refuse to install it!**

### Parsing Results from Web Pages

After downloading the content of the web page containing the results (using `retrieve_url()`), you will want to parse it in order to create a `dict` per search result and call the `prettyPrint()` function to display it on `stdout` (in a format understandable by qBittorrent).

To parse the pages, you can use the following Python modules (non-exhaustive list):

* **[ADVISED METHOD]** [html.parser](https://docs.python.org/3/library/html.parser.html): Built-in Python parser which replaces the deprecated SGMLParser. Mostly similar to SGMLParser
* `xml.dom.minidom`: XML parser. Be careful, this parser is very sensitive and the website must be fully XHTML compliant for this to work.
* `re`: If you like using regular expressions (regex)

Note that the `size` is provided in bytes.

To achieve this task, we provide several helper functions, such as `novaprinter.prettyPrinter()`.

## Understanding the Code

### `prettyPrinter()` Helper Function

You don't really need to worry about the output syntax because we provide a helper function for this called `prettyPrinter()`. Import it with the following command:

```python
from novaprinter import prettyPrinter
```

You must pass a dictionary to this function containing the following keys (values should be `-1` if you do not have the info):

* `link` => A URL corresponding to the download link (the .torrent file or magnet link)
* `name` => A Unicode string corresponding to the torrent's name (i.e: `Ubuntu Linux v6.06`)
* `size` => A number corresponding to the torrent size (in bytes)
* `seeds` => The number of seeds for this torrent (as a string)
* `leech` => The number of leechers for this torrent (as a string)
* `engine_url` => The search engine URL (i.e., `https://www.mininova.org`)
* `desc_link` => A URL corresponding to the description page for the torrent
* `pub_date` => A Unix timestamp corresponding to the published date of the torrent (i.e., `1696870394`)

### `retrieve_url()` Helper Function

The `retrieve_url()` method takes a URL as a parameter and returns the content of the URL as a string. \
This function is useful for getting search results from a BitTorrent search engine site. All you need to do is pass the properly formatted URL to the function (the URL usually includes `GET` parameters relative to search tokens, category, sorting, and page number).

```python
from helpers import retrieve_url
dat = retrieve_url(self.url + '/search?q=%s&c=%s&o=52&p=%d' % (what, self.supported_categories[cat], i))
```

### `download_file()` Helper Function

The `download_file()` function takes the URL of a torrent file as a parameter. This function will download the torrent to a temporary location and print to `stdout`:

```shell
path_to_temporary_file url
```

It prints two values separated by a space:

* The path to the downloaded file (usually in /tmp folder)
* The URL from which the file was downloaded

Here is an example:

```python
from helpers import retrieve_url, download_file
print(download_file(url))
> /tmp/esdzes https://www.mininova.org/get/123456
```

## Testing & Finalizing Your Code

### Code Examples

Feel free to use the [official search engine plugins](https://github.com/qbittorrent/search-plugins/tree/master/nova3/engines) as examples.

### Testing Your Plugin

Before installing your plugin in qBittorrent, you can test-run and debug it. We advise that you download [these files](https://github.com/qbittorrent/qBittorrent/tree/master/src/searchengine/nova3).

You will get the following structure:

```text
your_search_engine
-> nova2.py # the main search engine script which calls the plugins
-> nova2dl.py # standalone script called by qBittorrent to download a torrent using a particular search plugin
-> helpers.py # contains helper functions you can use in your plugins such as `retrieve_url()` and `download_file()`
-> novaprinter.py # contains some useful functions like `prettyPrint()` to display your search results
-> socks.py # Required by `helpers.py`. This module provides a standard socket-like interface.
```

Put your plugin in the `engines` folder (`%localappdata%\qBittorrent\nova3\engines`) and then execute the `nova2.py` script in CMD like this:

```shell
..\nova2.py your_search_engine_name category search_tokens
# e.g.: ..\nova2.py mininova all kubuntu linux
# e.g.: ..\nova2.py btjunkie books ubuntu
```

A successful result will output:

```text
DEBUG:root:C:\users\user\appdata\local\qbittorrent\nova3\qbt\qbt
the app will start listing links it finds in the following format:
link|name|size|seeds|leech|engine_url|desc_link|pub_date
```

### Install Your Plugin

1. Go to the Search tab in the main window and click on the "Search engines..." button.
2. A new window will pop up containing the list of installed search engine plugins.
3. Click "Install a new one" at the bottom and select your `*.py` Python script on your filesystem. \
   If everything goes well, qBittorrent should notify you that it was successfully installed, and your plugin will appear in the list.

### Publish Your Plugin

Once you manage to write a working search engine plugin for qBittorrent, feel free to submit a Pull Request to the
[wiki page][unofficial-plugins-wiki] so that other users can use it too. \
How to submit a Pull Request: <https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-a-pull-request>

[unofficial-plugins-wiki]: https://github.com/qbittorrent/search-plugins/blob/master/wiki/Unofficial-search-plugins.mediawiki

### Notes

* As a convention, it is advised that you print the results sorted by number of seeds (the most seeds at the top), as these are usually the most desirable torrents.
* Please note that search engines usually display results across multiple pages. Hence, it is better to parse all these pages to get complete results. All official plugins have multi-page support.
* Some search engines do not provide all the information required by `prettyPrinter()`. If this is the case, set `-1` as the value for the given key (e.g., `torrent_info['seeds'] = -1`)
* Plugins packaged as Python archive/package are no longer directly installable since qBittorrent v2.0.0. You must provide qBittorrent with the Python file.
