import os
import sys
from pathlib import Path
from typing import Final

import toml

__pkg_path__: Final[Path] = Path(
    os.path.abspath(os.path.dirname(sys.modules[__name__].__file__))
)

# get root path of project (above the module dir)
__basepath__: Final[Path] = Path(os.path.abspath(os.path.dirname(__pkg_path__)))


# single source of truth for version is the pyproject.toml!
pyproject = toml.load(os.path.join(__basepath__, "pyproject.toml"))

__version__: Final[str] = pyproject["tool"]["poetry"]["version"]


def pkg_res(path: str) -> Path:
    """Return resource bundled with this package."""

    return __basepath__ / path
