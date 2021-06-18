"""
Main functionality of Metador backend, independent of HTTP routing.

It exposes the interface to handle datasets, files and metadata.
"""

from typing import Final

import os

from .config import conf

#: Directory name for non-completed datasets
STAGING_DIR_NAME: Final[str] = "staging"

#: Directory name for completed datasets that can be handled by post-processing
COMPLETE_DIR_NAME: Final[str] = "complete"


def staging_dir() -> str:
    """Return directory for incomplete datasets (editable by client)."""

    return os.path.join(conf().metador.data_dir, STAGING_DIR_NAME)


def complete_dir() -> str:
    """Return directory for complete datasets (handled by post-processing)."""

    return os.path.join(conf().metador.data_dir, COMPLETE_DIR_NAME)


def prepare_dirs() -> None:
    """Create directory structure for datasets at location specified in config."""

    if not os.path.isdir(conf().metador.data_dir):
        os.mkdir(conf().metador.data_dir)
    if not os.path.isdir(staging_dir()):
        os.mkdir(staging_dir())
    if not os.path.isdir(complete_dir()):
        os.mkdir(complete_dir())


# def valid_staging_dataset(dataset: str):
#     """Check that the dataset exists."""

#     if not os.path.isdir(os.path.join(staging_dir(), dataset)):
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND, detail="No such dataset."
#         )


# def existing_datasets() -> List[str]:
#     """Get UUIDs of datasets currently in the system."""

#     return os.listdir(c.staging_dir()) + os.listdir(c.complete_dir())


# def fresh_dataset() -> UUID:
#     """
#     Generate a new UUID not currently used for an existing dataset.
#     Create a directory for it, return the UUID.
#     """

#     existing = existing_datasets()
#     fresh_uuid = uuid.uuid1()
#     while str(fresh_uuid) in existing:
#         fresh_uuid = uuid.uuid1()

#     os.mkdir(os.path.join(c.staging_dir(), str(fresh_uuid)))
#     # state.dataset_expires_by[fresh_uuid] = datetime.today() + timedelta(
#     #     hours=c.conf().metador.incomplete_expire_after
#     # )
#     return fresh_uuid
