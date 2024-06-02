#VERSION: 1.0
# AUTHORS: Alexander Georgievskiy (galeksandrp@gmail.com)
# CONTRIBUTORS:

import sys
import os
from pathlib import Path

os.environ['CONFIG_FILE'] = 'prowlarr.json'

try:
    import jackett
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.absolute()))
    import jackett

del os.environ['CONFIG_FILE']


class prowlarr(jackett.jackett):
    name = 'Prowlarr'


if __name__ == "__main__":
    jackett_se = prowlarr()
    jackett_se.search("ubuntu server", 'software')
