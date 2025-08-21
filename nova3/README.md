nova3 Plugins
===
[![GitHub Actions CI Status](https://github.com/qbittorrent/search-plugins/workflows/CI/badge.svg)](https://github.com/qbittorrent/search-plugins/actions)

## Development Workflow

0. Prerequisite

   Make sure you have [Python](https://www.python.org/) installed.

1. Setup development environment

   Note that it is recommended to setup a [virtual environment][venv_guide] for development.

   ```shell
   pip install -r requirements_dev.txt
   ```

   [venv_guide]: https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/#create-and-use-virtual-environments

2. Run tests

   ```shell
   just test
   ```

3. Run type check

   ```shell
   just check
   ```

4. Run static analyzer

   ```shell
   just lint
   ```

5. Apply formatting

   ```shell
   just format
   ```

## References

* [How to write a search plugin](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin)
* [justfile manual](https://just.systems/man/en/)
