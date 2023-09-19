# Version 1.0
# This script retrieves all available public plugins from the webpage since there is no "download all" option.
# It accomplishes this by parsing the webpage using BeautifulSoup to locate all .py URLs in the user-content-Plugins_for_Public_Sites table.
# If a file with the same name already exists, a suffix is added with an increment.
# Better execute this script in an empty download_directory

import requests
from bs4 import BeautifulSoup
import os

def get_target_links(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find the anchor tag with the name "user-content-Plugins_for_Public_Sites"
        target_a = soup.find("a", {"name": "user-content-Plugins_for_Public_Sites"})

        if target_a:
            # Find the next table after the anchor tag
            next_table = target_a.find_next("table")

            if next_table:
                # Find all links within the table that end with ".py"
                table_links = next_table.find_all("a", href=True)
                py_urls = [link["href"] for link in table_links if link["href"].endswith(".py")]
                return py_urls
            else:
                print("No table found after the anchor tag.")
        else:
            print("Anchor tag not found on the webpage.")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

def download_file(url, download_directory):
    try:
        # Create the download directory if it doesn't exist
        os.makedirs(download_directory, exist_ok=True)
        response = requests.get(url)
        response.raise_for_status()
        
        # Extract the file name from the URL
        file_name = os.path.basename(url)
        file_path = os.path.join(download_directory, file_name)

        # If the file already exists, add a suffix with an increment
        count = 1
        while os.path.exists(file_path):
            file_name, file_extension = os.path.splitext(file_name)
            new_file_name = f"{file_name}_{count}{file_extension}"
            file_path = os.path.join(download_directory, new_file_name)
            count += 1

        with open(file_path, "wb") as file:
            file.write(response.content)
        print(f"Downloaded {file_path}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")

def scrape_and_download(url, download_directory):
    py_urls = get_target_links(url)
    if py_urls:
        for py_url in py_urls:
            download_file(py_url, download_directory)
    else:
        print("No URLs ending with '.py' found in the table.")

if __name__ == "__main__":
    url = "https://github.com/qbittorrent/search-plugins/wiki/Unofficial-search-plugins"  # Replace with the URL of unofficial Plugins
    download_directory = "plugins"  # Replace with your desired download directory
    scrape_and_download(url, download_directory)
