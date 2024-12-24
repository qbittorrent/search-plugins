### Steps to install search plugins for qBittorrent version 3.1.10 or more recent

0. Note that python plugins/scripts are, by its nature, not considered to be safe. Therefore any use of the unofficial plugins is at your own risk. It is a good practice to audit/take a look at the plugin/script before you install.

1. Go to https://github.com/qbittorrent/search-plugins/wiki/Unofficial-search-plugins
     1. Under `Download` column, click on the appropriate `Download` link
     1. Save the `.py` file into a temporary location on your local storage

1. Using qBittorrent
     Using the main window, click on `View` -> `Search Engine` to show search tab
     ![screenshot](https://user-images.githubusercontent.com/14078661/51446055-a4431080-1cf3-11e9-8180-1994bdcbb672.png)
     1. Go to the `Search tab`
     1. Click on `Search plugins...` button. Which is located around the bottom right side.
     1. The `Search plugins` window will open. It shows a list of installed search engine plugins.
          1. Click on `Install a new one` button <br>
             ![screenshot](https://user-images.githubusercontent.com/14078661/51446120-bf625000-1cf4-11e9-98e1-b7e8b771c457.png))
          1. The `Plugin source` window will open
               1. Click on `Local file` button
               1. Navigate to the `.py` file you downloaded in the step above. Select the `.py` file.
               1. If successful the following message will be display
                     > <PLUGIN.NAME> search engine plugin was successfully installed.
               1. If not successful the following message will be display
                     > <PLUGIN.NAME> search engine plugin could not be installed.
                    1. Using [this page](https://github.com/qbittorrent/search-plugins/wiki/Unofficial-search-plugins) under the `Comment` column, double check that your system meets the minimum requirements for each search plugin. Maybe your present system does not have the requirements.
          1. Click on `Close` button
1. You can delete the `.py` file from your temporary location on your local storage, as it is no longer needed.
1. Optionally, you can use the `Search plugins` window to Enable or Deactivate search plugins, or check for updates.
1. Done. You have successfully installed a new search plugin for qBittorrent.
