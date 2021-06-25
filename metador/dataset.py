"""
Dataset management and serialization.
"""

from __future__ import annotations

import json
import re
import subprocess
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
    metadata: UnsafeJSON = None


class DatasetInfo(BaseModel):
    """Reduced form of Dataset that is used to create dataset.json file."""

    #: Creator of the dataset (also only person allowed to edit, if set)
    creator: Optional[OrcidStr]

    #: Creation time
    created: datetime

    #: copy of the profile embedded into dataset
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

    def upload_filepath(self, filename: str) -> Path:
        """Return the filepath where a file with a certain name must be."""
        return self.upload_dir(self.id) / filename

    def is_expired(self) -> bool:
        """Returns true if dataset is expired according to current config."""

        age_hours = (datetime.now() - self.created).total_seconds() / 3600
        return age_hours > conf().metador.incomplete_expire_after

    def save(self) -> None:
        """Serialize the current state into a file."""

        with open(Dataset.persist_filename(self.id), "w") as file:
            file.write(self.json())
            file.flush()

    def validate_metadata(self, file: Optional[str]) -> Optional[str]:
        """Validate a file of given name, or the root metadata otherwise."""

        metadata = self.files[file].metadata if file else self.rootMeta
        return util.validate_json(metadata, self.profile.get_schema_for(file))

    def validate(self) -> Dict[str, Optional[str]]:
        """
        Validate the dataset, collect error messages.

        On success, the returned dict is empty, otherwise it contains
        the error message per file (empty filename = root metadata validation result).
        """

        errors: Dict[str, Optional[str]] = {}
        err = self.validate_metadata(None)
        if err is not None:
            errors[""] = err  # dataset "root" metadata errors

        # file-specific metadata
        for name in self.files.keys():
            err = self.validate_metadata(name)
            if err is not None:
                errors[name] = err

        return errors

    ####

    def delete_file(self, name: str) -> bool:
        """Delete file and its data, if it exists."""

        filepath = self.upload_filepath(name)
        if name not in self.files:
            log.warning(f"Cannot delete non-existing file {name} from {self.id}")
            return False

        if filepath.is_file():
            filepath.unlink()  # delete file
        else:
            log.critical(f"Referenced file {name} does non-exist in {self.id}")

        del self.files[name]  # remove data attached to file
        self.save()
        return True

    def import_file(self, filepath: Path) -> bool:
        """
        Move file from provided location into dataset.

        Return True if file exists, can be moved, and won't overwrite existing file.
        """

        target = self.upload_filepath(filepath.name)

        if filepath.name in self.files or target.is_file():
            log.error(f"Cannot import file {filepath}, file with that name exists!")
            return False

        if not filepath.is_file():
            log.error(f"File {filepath} cannot be imported, not a file!")
            return False

        filepath.rename(target)
        self.files[filepath.name] = FileInfo()

        self.save()
        return True

    def compute_checksum(self, filename: str) -> bool:
        """
        Run checksum tool on file and assign checksum.
        """
        filepath = self.upload_filepath(filename)

        if filename not in self.files or not filepath.is_file():
            log.error(f"Cannot compute checksum for {filename}, file does not exist!")
            return False

        try:
            ret = subprocess.run(
                [self.checksumTool, filepath],
                check=True,
                capture_output=True,
                encoding="utf-8",
            ).stdout.split()
            assert ret[1] == filepath  # sanity-check
            file_checksum = ret[0]
            self.files[filename].checksum = file_checksum
        except subprocess.CalledProcessError:
            log.error(f"Failed {self.checksumTool} on {filepath}: non-zero exit code!")
            return False

        self.save()
        return True

    def set_metadata(self, filename: Optional[str], metadata: UnsafeJSON) -> bool:
        """
        Assign provided metadata to file (or dataset root, if filename=None).

        No validation is done at this step. Fails only if file does not exist.
        """

        if filename is not None and filename not in self.files:
            log.error(f"Cannot assign metadata to {filename}, file does not exist!")
            return False

        if filename is None:
            self.rootMeta = metadata
        else:
            self.files[filename].metadata = metadata

        self.save()
        return True

    def rename_file(self, name: str, new_name: str) -> bool:
        """
        Try to rename an existing file to a new free filename.

        Returns True on success, i.e. file and its data exists and new name is free.
        """

        if name == new_name:
            log.info(f"Rename {name}->{new_name} in {self.id}: nothing to do.")
            return True

        if name not in self.files:
            log.warning(f"Cannot rename non-existing file {name} from {self.id}")
            return False
        if new_name in self.files:
            log.warning(
                f"Cannot rename {name}->{new_name} in {self.id}, target exists!"
            )
            return False

        oldpath = self.upload_filepath(name)
        newpath = self.upload_filepath(new_name)

        if not oldpath.is_file():
            log.error(f"File {oldpath} does not exists, although referenced!")
            return False
        if newpath.is_file():
            log.error(f"File {newpath} exists, but not referenced! Abort rename.")
            return False

        oldpath.rename(newpath)
        self.files[new_name] = self.files[name]
        del self.files[name]

        self.save()
        return True

    ####

    def complete(self) -> Optional[Path]:
        """
        Validate metadata and check that all checksums are present.

        On success, remove files and data from 'staging' directory
        and produce the directory in the 'complete' directory. Return path.
        """

        global _datasets
        global _ds_uuids

        val_errors = self.validate()
        if len(val_errors) != 0:
            log.error(f"Cannot complete dataset, validation failed: {val_errors}")
            return None

        for file, dat in self.files.items():
            if dat.checksum is None:
                log.error(f"Cannot complete dataset, missing checksum for {file}")
                return None

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
            if dat.metadata is not None:
                with open(target_dir / (filename + METADATA_SUF), "w") as outfile:
                    json.dump(dat.metadata, outfile)
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

        # TODO: store the profile

        _ds_uuids.remove(self.id)
        del _datasets[self.id]

        log.info(f"Dataset {self.id} completed.")
        return target_dir

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
    """Load datasets for which a persistence file exists."""

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
    """
    Return a dataset if it exists and is not expired (throws if it does not exist).

    If it is expired, it is cleaned up and treated like it does not exist.
    This is better than giving it out, as a cleaning job could delete it any moment.
    """

    ds = _datasets[ds_id]
    if ds.is_expired():
        ds.delete()
        raise KeyError
    return ds


load_datasets()
