# How to install search plugins for qBittorrent (v3.1.10 or later)

> ⚠️ **Security warning:** Search plugins are Python scripts (third-party code). They are not guaranteed to be safe. Install only from sources you trust, and review the script before installing.

1. Open the [unofficial plugin list](https://github.com/qbittorrent/search-plugins/wiki/Unofficial-search-plugins)
   1. Under the `Download` column, click the plugin’s `Download` link.
   2. Save the `.py` file to a temporary location on your computer.
2. In qBittorrent:
     In the main window, click `View` -> `Search Engine` to show the `Search` tab.
     ![screenshot](https://user-images.githubusercontent.com/14078661/51446055-a4431080-1cf3-11e9-8180-1994bdcbb672.png)
     1. Go to the `Search` tab.
     2. Click the `Search plugins...` button, located near the bottom-right side.
     3. The `Search plugins` window will open. It shows a list of installed search engine plugins.
          1. Click the `Install a new one` button.
             ![screenshot](https://user-images.githubusercontent.com/14078661/51446120-bf625000-1cf4-11e9-98e1-b7e8b771c457.png)
          2. The `Plugin source` window will open.
               1. Click the `Local file` button.
               2. Navigate to the `.py` file you downloaded in the step above. Select the `.py` file.
               3. If successful, the following message will be displayed:
                  > <PLUGIN.NAME> search engine plugin was successfully installed.
               4. If not successful, the following message will be displayed:
                  > <PLUGIN.NAME> search engine plugin could not be installed.

                  Using [this page](https://github.com/qbittorrent/search-plugins/wiki/Unofficial-search-plugins) under the `Comment` column, check that your system meets the minimum requirements for each search plugin. Your system may not meet the plugin requirements.
          3. Click the `Close` button.
3. You can delete the `.py` file from your temporary location on local storage, as it is no longer needed.
4. Optionally, you can use the `Search plugins` window to enable or disable search plugins, or check for updates.
5. Done. You have successfully installed a new search plugin for qBittorrent.
