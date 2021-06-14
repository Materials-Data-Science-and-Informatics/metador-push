from typing import List

import os
import uuid
from uuid import UUID

from fastapi import HTTPException, status

from . import config as c


def hidden_if(bval: bool) -> str:
    return "display: none !important;" if bval else ""


def prepare_dirs() -> None:
    """Create directory structure for datasets at location specified in config."""

    datadir = c.conf().metador.data_dir
    staging = os.path.join(datadir, c.STAGING_DIR)
    complete = os.path.join(datadir, c.COMPLETE_DIR)
    if not os.path.isdir(datadir):
        os.mkdir(datadir)
    if not os.path.isdir(staging):
        os.mkdir(staging)
    if not os.path.isdir(complete):
        os.mkdir(complete)


def valid_staging_dataset(dataset: str):
    """Check that the dataset exists."""

    if not os.path.isdir(os.path.join(c.staging_dir(), dataset)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such dataset."
        )


def existing_datasets() -> List[str]:
    """Get UUIDs of datasets currently in the system."""

    return os.listdir(c.staging_dir()) + os.listdir(c.complete_dir())


def fresh_dataset() -> UUID:
    """
    Generate a new UUID not currently used for an existing dataset.
    Create a directory for it, return the UUID.
    """

    existing = existing_datasets()
    fresh_uuid = uuid.uuid1()
    while str(fresh_uuid) in existing:
        fresh_uuid = uuid.uuid1()

    os.mkdir(os.path.join(c.staging_dir(), str(fresh_uuid)))
    # state.dataset_expires_by[fresh_uuid] = datetime.today() + timedelta(
    #     hours=c.conf().metador.incomplete_expire_after
    # )
    return fresh_uuid
