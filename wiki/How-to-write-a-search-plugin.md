qBittorrent provides a search engine plugins management system.
Thanks to this, you can *easily* write your own plugins to look for torrents in your favorite Bittorrent search engines and extend qBittorrent integrated search engine.

* All you need is some motivation and some knowledge of [Python language](https://www.python.org).
* **The minimum supported python version is specified [here](https://github.com/qbittorrent/qBittorrent/blob/master/INSTALL#L21-L23), make sure your plugin can work with it and every later versions.**
* **Only import libraries from [Python Standard Library](https://docs.python.org/3/library/index.html)**. \
  Third party libraries (such as those installed from [PyPI](https://pypi.org/)) are ***not*** guaranteed to be present in user's environment.
* You are encouraged to ensure good quality of your plugin: [Python Code Quality: Tools & Best Practices](https://realpython.com/python-code-quality/). \
  For example, here is how the official plugins are checked: [ci.yaml](https://github.com/qbittorrent/search-plugins/blob/60a3f4d9c97a5d1f94e75789a72ee054044c5802/.github/workflows/ci.yaml#L29-L44).


# INDEX
## [Plugins Specification](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin#plugins-specification-1)

### 1.1 [Search Results Format](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin/#search-results-format)

### 1.2 [Python Class File Structure](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin/#python-class-file-structure)

### 1.3 [Parsing Results From Web Pages](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin/#parsing-results-from-web-pages)

## [Understanding The Code](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin#understanding-the-code-1)

### 2.1 [PrettyPrinter Helper Function](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin#prettyprinter-helper-function)

### 2.2 [Retrieve_URL Helper Function](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin#retrieve_url-helper-function)

### 2.3 [Download_File helper Function](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin#download_file-helper-function)

## [Testing & Finalizing Your Code](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin#testing--finalizing-your-code-1)

### 3.1 [Code Examples](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin/#code-examples)

### 3.2 [Testing Your Plugin](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin#testing-your-plugin)

### 3.3 [Install Your Plugin](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin#install-your-plugin)

### 3.4 [Publish Your Plugin](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin#publish-your-plugin)

### 3.5 [Notes](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin#notes)


# Plugins Specification

*⚠️The plugin communicate data back to qBittorrent via stdout and that means you must NOT print debug/error messages to stdout under any circumstances. You can print the debug/error messages to stderr instead.*

## Search Results Format
First, you must understand that a qBittorrent search engine plugin is actually a Python class file whose task is to contact a search engine website (e.g. [The Pirate Bay](https://www.thepiratebay.org)), parse the results displayed by the web page and print them on stdout with the following syntax:
```
link|name|size|seeds|leech|engine_url|desc_link|pub_date
```

One search result per line.

For example:
```
magnet:?xt=urn:btih:5F5E8848426129AB63CB4DB717BB54193C1C1AD7&dn=ubuntu-20.04.6-desktop-amd64.iso|ubuntu-20.04.6-desktop-amd64.iso|4351463424|15|2|https://thepiratebay.org|https://thepiratebay.org/description.php?id=72774917|1696870394
magnet:?xt=urn:btih:07053761979D09DEAD94D09E8326DB919797B078&dn=ubuntu-10.04-server-i386.iso|ubuntu-10.04-server-i386.iso|700413952|1|0|https://thepiratebay.org|https://thepiratebay.org/description.php?id=5551290|1273547377
```

## Python Class File Structure
Your plugin should be named "engine_name.py", in lowercase and without spaces nor any special characters.
You'll also need the other files for the project ([Link](https://github.com/qbittorrent/qBittorrent/tree/master/src/searchengine/nova3))

The Files Are:

```
-> nova2.py # the main search engine script which calls the plugins
-> nova2dl.py # standalone script called by qBittorrent to download a torrent using a particular search plugin
-> helpers.py # contains helper functions you can use in your plugins such as retrieve_url() and download_file()
-> novaprinter.py # contains some useful functions like prettyPrint(my_dict) to display your search results
-> socks.py # Required by helpers.py. This module provides a standard socket-like interface.
```


Here is the basic structure of engine_name.py:
```python
#VERSION: 1.00
# AUTHORS: YOUR_NAME (YOUR_MAIL)
# LICENSING INFORMATION

from html.parser import HTMLParser
from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter
# some other imports if necessary

class engine_name(object):
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
    supported_categories = {
        'all': '0',
        'anime': '7',
        'games': '2',
        'movies': '6',
        'music': '1',
        'software': '3',
        'tv': '4'
    }

    def __init__(self):
        """
        Some initialization
        """

    def download_torrent(self, info):
        """
        Providing this function is optional.
        It can however be interesting to provide your own torrent download
        implementation in case the search engine in question does not allow
        traditional downloads (for example, cookie-based download).
        """
        print(download_file(info))

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what, cat='all'):
        """
        Here you can do what you want to get the result from the search engine website.
        Everytime you parse a result line, store it in a dictionary
        and call the prettyPrint(your_dict) function.

        `what` is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        `cat` is the name of a search category in ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv')
        """
```

**PLEASE note that the filename (without .py extension) must be identical to the class name. Otherwise, qBittorrent will refuse to install it!**

## Parsing Results from Web Pages
After downloading the content of the web page containing the results (using `retrieve_url()`), you will want to parse it in order to create a `dict` per search result and call `prettyPrint(your_dict)` function to display it on stdout (in a format understandable by qBittorrent).

In order to parse the pages, you can use the following python modules (not exhaustive):
* **[ADVISED METHOD]** [HTMLParser](https://docs.python.org/2/library/htmlparser.html) / [html.parser](https://docs.python.org/3/library/html.parser.html): Builtin python parser which replaces deprecated SGMLParser. Mostly similar to the SMGLParser
* `xml.dom.minidom`: XML parser. Be careful, this parser is very sensitive and the website must be fully XHTML compliant for this to work.
* `re`: If you like using regular expressions (regex)

Note that the size is in provided bytes.

To achieve this task we provide several helper functions such as `prettyPrinter()`.

# Understanding The Code
## `prettyPrinter()` helper function
In fact, you don't really need to pay attention to the output syntax because we provide a function for this called `prettyPrinter(dictionary)`. You can import it using the following command:
```python
from novaprinter import prettyPrinter
```

You must pass to this function a dictionary containing the following keys (value should be `-1` if you do not have the info):
* `link` => A string corresponding the the download link (the .torrent file or magnet link)
* `name` => A unicode string corresponding to the torrent's name (i.e: "Ubuntu Linux v6.06")
* `size` => A string corresponding to the torrent size (i.e: "6 MB" or "200 KB" or "1.2 GB"...)
* `seeds` => The number of seeds for this torrent (as a string)
* `leech` => The number of leechers for this torrent (a a string)
* `engine_url` => The search engine url (i.e: https://www.mininova.org)
* `desc_link` => A string corresponding to the description page for the torrent
* `pub_date` => A unix timestamp corresponding to published date of the torrent (i.e: 1696870394)

## `retrieve_url()` helper function
The `retrieve_url()` method takes an URL as parameter and returns the content of the URL as a string.<br />
This function is useful to get the search results from a Bittorrent search engine site. All you need to do is to pass the properly formatted URL to the function (the URL usually include GET parameters relative to search tokens, category, sorting, page number).

```python
from helpers import retrieve_url
dat = retrieve_url(self.url + '/search?q=%s&c=%s&o=52&p=%d' % (what, self.supported_categories[cat], i))
```

## `download_file()` helper function
The `download_file()` functions takes as a parameter the URL to a torrent file. This function will download the torrent to a temporary location and print on stdout:
```shell
path_to_temporary_file url
```

It prints two values separated by a space:
* The path to the downloaded file (usually in /tmp folder)
* The URL from which the file was downloaded

Here is an example:
```python
from helpers import retrieve_url, download_file
print download_file(url)
> /tmp/esdzes https://www.mininova.org/get/123456
```
# Testing & Finalizing Your Code

## Code Examples
Do not hesitate to use the official search engine plugins as an example. They are available [here](https://github.com/qbittorrent/search-plugins/tree/master/nova3/engines).
* kickasstorrents.py uses json module
* torrentreactor.py uses HTMLParser module

## Testing Your Plugin
Before installing your plugin (in Qbittorrent) you can test run the plugin while debugging it. Hence, we advise that you download [these files](https://github.com/qbittorrent/qBittorrent/tree/master/src/searchengine/nova3).

You will get the following structure:
```
your_search_engine
-> nova2.py # the main search engine script which calls the plugins
-> nova2dl.py # standalone script called by qBittorrent to download a torrent using a particular search plugin
-> helpers.py # contains helper functions you can use in your plugins such as retrieve_url() and download_file()
-> novaprinter.py # contains some useful functions like prettyPrint(my_dict) to display your search results
-> socks.py # Required by helpers.py. This module provides a standard socket-like interface.
```

Put your plugin in `engines/` folder ( %localappdata%\qBittorrent\nova3\engines\ ) and then in CMD execute nova2.py script like this:
```shell
..\nova2.py your_search_engine_name category search_tokens
# e.g.: ..\nova2.py mininova all kubuntu linux
# e.g.: ..\nova2.py btjunkie books ubuntu
```

A successful result will output:
```
DEBUG:root:C:\users\user\appdata\local\qbittorrent\nova3\qbt\qbt
the app will start listing links it finds in the following format:
link|name|size|#seeds|#leechers|engine|page url
```

## Install Your Plugin
1. Go to search tab in main window, click on "Search engines..." button.
2. Then, a new window will pop up, containing the list of installed search engine plugins.
3. Click on "Install a new one" at the bottom and select your `*.py` python script on you filesystem.<br />
If everything goes well, qBittorrent should notify you that it was successfully installed and your plugin should appear in the list.

## Publish Your Plugin
Once you managed to write a search engine plugin for qBittorrent that works, feel free to post it on [this](https://plugins.qbittorrent.org) wiki page so that the other users can use it too.<br />
If you are lucky, your plugin may also be included in the [official repository](https://github.com/qbittorrent/search-plugins).

## Notes
* As a convention, it is advised that you print the results sorted by number of seeds (the most seeds at the top) because these are usually the most interesting torrents.
* Please note that search engines usually display results on several pages. Hence, it is better to parse all these pages to get all results. All official plugins have multipage support.
* Some search engines do not provide all the informations required by `prettyPrinter()`. If it is the case, set `-1` as value for the given key (i.e.: `torrent_info['seeds'] = -1`)
* Plugins packaged in a python are no longer directly installable since qBittorrent v2.0.0. You must provide qBittorrent with the python file.
