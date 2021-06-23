"""
Dataset management and serialization.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Final, List, Optional, Set, Type, TypeVar
from uuid import UUID, uuid1

from pydantic import BaseModel

from . import core, util
from .config import ChecksumTool, conf
from .log import log
from .orcid.auth import OrcidStr
from .profile import Profile, UnsafeJSON

#: suffix of serialized staging dataset file
DATASET_SUF: Final[str] = ".dataset.json"

METADATA_SUF: Final[str] = "_meta.json"


def find_staging_datasets() -> List[str]:
    """Get UUIDs of datasets with serialized data in the staging directory."""

    files = list(core.staging_dir().glob("*" + DATASET_SUF))
    return list(map(lambda x: re.sub(DATASET_SUF + "$", "", x.name), files))


#: Cache of known (staging) dataset UUIDs (to avoid I/O)
_ds_uuids: Set[UUID] = set(map(UUID, find_staging_datasets()))


def fresh_dataset_id() -> UUID:
    """
    Generate a new UUID not currently used for an existing dataset.
    Create a directory file for it, return the UUID.
    """

    fresh = uuid1()
    while fresh in _ds_uuids:
        fresh = uuid1()

    _ds_uuids.add(fresh)
    return fresh


class FileInfo(BaseModel):
    """Information about an existing file."""

    #: checksum, if computed
    checksum: Optional[str] = None

    #: metadata, if attached
    meta: UnsafeJSON = None


class DatasetInfo(BaseModel):
    """Reduced form of Dataset that is used to create dataset.json file."""

    #: Creator of the dataset (also only person allowed to edit, if set)
    creator: Optional[OrcidStr]

    #: Creation time
    created: datetime

    #: copy of the profile embedded into dataset (for same reason as checksum)
    profile: Profile


T = TypeVar("T")


class Dataset(BaseModel):
    """Represents a dataset instance with files and metadata before completion."""

    #: ID of the dataset
    id: UUID

    #: Creator of the dataset (also only person allowed to edit, if set)
    creator: Optional[OrcidStr]

    #: Creation time
    created: datetime

    #: copy of the profile embedded into dataset (for same reason as checksum)
    profile: Profile

    #: fix checksum tool in a dataset (should stay consistent throughout config change)
    checksumTool: ChecksumTool

    #: Metadata about the dataset in general
    rootMeta: UnsafeJSON = None

    #: filename -> Metadata and checksum
    files: Dict[str, FileInfo] = {}

    ####

    @classmethod
    def persist_filename(cls, id) -> Path:
        """Location where metadata is stored until completion."""
        return core.staging_dir() / (str(id) + DATASET_SUF)

    @classmethod
    def upload_dir(cls, id) -> Path:
        """Location where uploaded files are stored."""
        return core.staging_dir() / str(id)

    @classmethod
    def target_dir(cls, id) -> Path:
        """Location where the dataset will go on completion."""
        return core.complete_dir() / str(id)

    ####

    def save(self) -> None:
        """Serialize the current state into a file."""

        with open(Dataset.persist_filename(self.id), "w") as file:
            file.write(self.json())
            file.flush()

    def validate(self) -> Dict[Optional[str], Optional[str]]:
        """
        Validate the dataset, collect error messages.

        On success, the returned dict is empty, otherwise it contains
        the error message per file (or None for the root metadata).
        """

        errors: Dict[Optional[str], Optional[str]] = {}
        err = util.validate_json(self.rootMeta, self.profile.get_schema_for(None))
        if err is not None:
            errors[None] = err  # dataset "root" metadata errors

        # file-specific metadata
        for file, dat in self.files.items():
            err = util.validate_json(dat.meta, self.profile.get_schema_for(file))
            if err is not None:
                errors[file] = err

        return errors

    def complete(self) -> bool:
        """
        Validate metadata and check that all checksums are present.

        On success, remove files and data from 'staging' directory
        and produce the directory in the 'complete' directory.
        """

        global _datasets
        global _ds_uuids

        val_errors = self.validate()
        if len(val_errors) != 0:
            log.error(f"Cannot complete dataset, validation failed: {val_errors}")
            return False

        for file, dat in self.files.items():
            if dat.checksum is None:
                log.error(f"Cannot complete dataset, missing checksum for {file}")
                return False

        upload_dir: Final[Path] = Dataset.upload_dir(self.id)
        target_dir: Final[Path] = Dataset.target_dir(self.id)

        # move the files
        upload_dir.rename(target_dir)

        # produce the metadata files
        if self.rootMeta is not None:
            with open(target_dir / METADATA_SUF, "w") as outfile:
                json.dump(self.rootMeta, outfile)
                outfile.flush()

        for filename, dat in self.files.items():
            if dat.meta is not None:
                with open(target_dir / (filename + METADATA_SUF), "w") as outfile:
                    json.dump(dat.meta, outfile)
                    outfile.flush()

        # create a checksum file (e.g. sha256sums.txt)
        with open(target_dir / (self.checksumTool + "s.txt"), "w") as outfile:
            for name, dat in self.files.items():
                outfile.write(f"{name}  {dat.checksum}\n")
                outfile.flush()

        # create json for remaining info that might be useful
        with open(target_dir / "dataset.json", "w") as outfile:
            dsinfo = DatasetInfo(
                creator=self.creator, created=self.created, profile=self.profile
            )
            outfile.write(dsinfo.json())
            outfile.flush()

        _ds_uuids.remove(self.id)
        del _datasets[self.id]

        log.info(f"Dataset {self.id} completed.")
        return True

    def delete(self) -> None:
        """
        IRREVERSIBLY delete information about this dataset and all its files.
        """

        upload_dir: Final[Path] = Dataset.upload_dir(self.id)
        for uploaded_file in upload_dir.glob("*"):
            uploaded_file.unlink()
        upload_dir.rmdir()

        Dataset.persist_filename(self.id).unlink()

        _ds_uuids.remove(self.id)
        del _datasets[self.id]

        log.info(f"Data of {self.id} deleted.")

    @classmethod
    def load(cls: Type[T], ds_id: UUID) -> Optional[T]:
        persist_file = Dataset.persist_filename(ds_id)
        if not persist_file.is_file():
            log.error(f"Failed loading, {str(persist_file)} not found.")
            return None

        ds = cls.parse_file(Dataset.persist_filename(ds_id))  # type: ignore
        if not Dataset.upload_dir(ds_id).is_dir():
            log.warning(f"Upload dir {ds_id} not found! This is odd. Will create one.")
            Dataset.upload_dir(ds.id).mkdir()

        # TODO: check that files in metadata refer to files in upload dir and vice versa
        return ds

    @classmethod
    def create(cls, profile: Profile, creator: Optional[OrcidStr] = None):
        """
        Creates a new dataset and create its directory + persistence file.

        Returns the dataset object.
        """

        ds = cls(
            id=fresh_dataset_id(),
            creator=creator,
            created=datetime.now(),
            profile=profile,
            checksumTool=conf().metador.checksum_tool,
        )  # type: ignore

        Dataset.upload_dir(ds.id).mkdir()  # create underlying upload directory
        ds.save()  # create underlying file
        _datasets[ds.id] = ds  # register in loaded list
        log.info(f"New dataset {ds.id} created.")
        return ds


#: In-memory rep of existing datasets
_datasets: Dict[UUID, Dataset] = {}


def load_datasets() -> None:
    global _datasets
    for ds_id in _ds_uuids:
        log.debug(f"Loading dataset {ds_id} from file.")
        ds = Dataset.load(ds_id)
        if ds is not None:
            _datasets[ds_id] = ds


def get_datasets(creator: Optional[OrcidStr] = None) -> List[UUID]:
    """Return a list of dataset ids (possibly filtered by creator)."""

    if creator is None:  # list all datasets
        return list(_datasets.keys())
    else:  # return datasets created by certain user
        return list(
            map(
                lambda x: x.id,
                filter(lambda x: x.creator == creator, _datasets.values()),
            )
        )


def get_dataset(ds_id: UUID) -> Dataset:
    """Return a dataset (throws if it does not exist)."""

    return _datasets[ds_id]


load_datasets()
