nova3 Plugins
===
[![GitHub Actions CI status]][GitHub Actions link]

[GitHub Actions CI status]: https://github.com/qbittorrent/search-plugins/workflows/CI/badge.svg
[GitHub Actions link]: https://github.com/qbittorrent/search-plugins/actions

## Development Workflow

0. Prerequisite

   * A Linux-like environment
   * [Python](https://www.python.org/) installed
   * [uv](https://docs.astral.sh/uv/) installed

1. Setup development environment

   1. Setup virtual environment and dependencies
      ```shell
      uv sync
      ```

   2. Activate virtual environment
      ```shell
      source .venv/bin/activate
      ```

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
* [just - Command runner](https://just.systems/man/en/)
* [uv - Python package and project manager](https://docs.astral.sh/uv/)
