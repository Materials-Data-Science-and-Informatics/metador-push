"""
Dataset management and serialization.
"""

from __future__ import annotations
from typing import Final, List
import re

from pydantic import BaseModel

from . import core
from .profile import Profile, UnsafeJSON

# from .config import conf

#: suffix of serialized staging dataset file
DATASET_SUF: Final[str] = ".dataset.json"


class DatasetFile(BaseModel):
    """Information about an existing file."""

    name: str
    checksum: str
    meta: UnsafeJSON


class Dataset(BaseModel):
    """Represents a dataset instance with files and metadata."""

    profile: Profile
    checksumTool: str

    rootMeta: UnsafeJSON


def known_dataset_ids() -> List[str]:
    """Get UUIDs of datasets with serialized data in the staging directory."""

    files = core.staging_dir().glob("*.dataset.json")
    ids = list(map(lambda x: re.sub(".dataset.json$", "", x.name), files))
    return ids


print(known_dataset_ids())

# def fresh_dataset() -> UUID:
#     """
#     Generate a new UUID not currently used for an existing dataset.
#     Create a directory for it, return the UUID.
#     """

#     existing = existing_datasets()
#     fresh_uuid = uuid.uuid1()
#     while str(fresh_uuid) in existing:
#         fresh_uuid = uuid.uuid1()

#     os.mkdir(os.path.join(core.staging_dir(), str(fresh_uuid)))
#     # state.dataset_expires_by[fresh_uuid] = datetime.today() + timedelta(
#     #     hours=c.conf().metador.incomplete_expire_after
#     # )
#     return fresh_uuid


# def valid_staging_dataset(uuid: str):
#     """Check that the dataset exists in the staging directory."""

#     if not (core.staging_dir() / uuid).is_dir:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND, detail="No such dataset."
#         )
