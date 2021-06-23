"""
Main functionality of Metador backend, independent of HTTP routing.

It exposes the interface to handle datasets, files and metadata.
"""

from pathlib import Path
from typing import Final

from .config import conf
from .util import critical_exit

#: Directory name for non-completed datasets
STAGING_DIR_NAME: Final[str] = "staging"

#: Directory name for completed datasets that can be handled by post-processing
COMPLETE_DIR_NAME: Final[str] = "complete"


def staging_dir() -> Path:
    """Return directory for incomplete datasets (editable by client)."""

    return conf().metador.data_dir / STAGING_DIR_NAME


def complete_dir() -> Path:
    """Return directory for complete datasets (handled by post-processing)."""

    return conf().metador.data_dir / COMPLETE_DIR_NAME


def prepare_dirs() -> None:
    """Create directory structure for datasets at location specified in config."""

    data_dir = conf().metador.data_dir
    if not data_dir.is_dir():
        critical_exit(f"Configured data directory '{data_dir}' does not exist!")

    if not staging_dir().is_dir():
        staging_dir().mkdir()
    if not complete_dir().is_dir():
        complete_dir().mkdir()
