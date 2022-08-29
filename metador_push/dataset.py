"""
Dataset management and serialization.

The function `Dataset.load_datasets` must be called before using other functions.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid1

from pydantic import BaseModel
from typing_extensions import Final

from . import util
from .config import conf
from .log import log
from .orcid.auth import OrcidStr
from .profile import Profile, UnsafeJSON

DATASET_SUF: Final[str] = ".dataset.json"
"""Suffix of serialized staging dataset file."""

METADATA_SUF: Final[str] = "_meta.json"
"""Suffix of metadata file added to filenames of data files."""


STAGING_DIR_NAME: Final[str] = "staging"
"""Sub-directory in data dir for non-completed datasets."""

COMPLETE_DIR_NAME: Final[str] = "complete"
"""Sub-directory in data dir for completed datasets to be handled by post-processing."""


class FileInfo(BaseModel):
    """Information about an existing file."""

    checksum: Optional[str] = None
    """Checksum (according to configured algorithm), if computed."""

    metadata: UnsafeJSON = None
    """Attached metadata."""


class DatasetInfo(BaseModel):
    """Reduced form of Dataset that is used to create dataset.json file."""

    creator: Optional[OrcidStr]
    """Creator of the dataset (also only person allowed to edit, if set)."""

    created: datetime
    """Creation time."""

    profile: Profile
    """Copy of the profile embedded into dataset."""


_datasets: Dict[UUID, Dataset] = {}
"""In-memory cache of existing loaded datasets"""


class Dataset(BaseModel):
    """Represents a dataset instance with files and metadata before completion."""

    id: UUID
    """ID of the dataset."""

    creator: Optional[OrcidStr]
    """Creator of the dataset (also only person except for admins allowed to edit)."""

    created: datetime
    """Creation date and time."""

    expires: datetime
    """Expiry date and time (if not completed by then)."""

    checksumAlg: util.ChecksumAlg
    """Fix checksum tool in a dataset (should stay consistent throughout config change)."""

    profile: Profile
    """Copy of the profile embedded into dataset (for same reason as checksum)."""

    rootMeta: UnsafeJSON = None
    """Metadata about the dataset in general."""

    files: Dict[str, FileInfo] = {}
    """Filename -> Metadata + checksum"""

    ####

    @classmethod
    def _staging_dir(cls) -> Path:
        """Return directory for incomplete datasets (editable by client)."""
        return conf().metador_push.data_dir / STAGING_DIR_NAME

    @classmethod
    def _complete_dir(cls) -> Path:
        """Return directory for complete datasets (handled by post-processing)."""
        return conf().metador_push.data_dir / COMPLETE_DIR_NAME

    @classmethod
    def _persist_filename(cls, ds_id: UUID) -> Path:
        """Location where metadata is stored until completion."""
        return cls._staging_dir() / (str(ds_id) + DATASET_SUF)

    def _upload_dir(self) -> Path:
        """Location where uploaded files are stored."""
        return self._staging_dir() / str(self.id)

    def _target_dir(self) -> Path:
        """Location where the dataset will go on completion."""
        return self._complete_dir() / str(self.id)

    def _upload_filepath(self, filename: str) -> Path:
        """Return the filepath where a file with a certain name must be."""
        return self._upload_dir() / filename

    ####

    def is_expired(self, currtime: Optional[datetime] = None) -> bool:
        """Return whether the dataset is expired (wrt. given time or current time)."""
        if currtime is None:
            currtime = datetime.today()
        return currtime > self.expires

    def save(self) -> None:
        """Serialize the current state into a file."""
        util.save_json(self, self._persist_filename(self.id))

    def validate_metadata(self, file: Optional[str]) -> Optional[str]:
        """Validate a file of given name, or the root metadata otherwise."""
        metadata = self.files[file].metadata if file else self.rootMeta
        return util.validate_json(
            metadata, self.profile.get_schema_for(file), self.profile.schemas
        )

    def validate_dataset(self) -> Dict[str, str]:
        """
        Validate the dataset, collect error messages.

        On success, the returned dict is empty, otherwise it contains
        the error message per file (empty filename = root metadata validation result).
        """
        errors: Dict[str, str] = {}
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

    def delete_file(self, name: str) -> bool:
        """Delete file and its data, if it exists."""
        filepath = self._upload_filepath(name)
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
        target = self._upload_filepath(filepath.name)

        if not filepath.is_file():
            log.error(f"File {filepath} cannot be imported, not a file!")
            return False

        if filepath.name in self.files or target.is_file():
            log.error(f"Cannot import file {filepath}, file with that name exists!")
            return False

        filepath.rename(target)
        self.files[filepath.name] = FileInfo()

        self.save()
        return True

    def compute_checksum(self, filename: str) -> bool:
        """Run checksum tool on file and assign checksum."""
        filepath = self._upload_filepath(filename)

        if filename not in self.files:
            log.error(
                f"Cannot compute checksum for {filename}, no such file in dataset!"
            )
            return False

        try:
            self.files[filename].checksum = util.hashsum(filepath, self.checksumAlg)
        except FileNotFoundError:
            log.error(f"File {filepath} not found, cannot compute hashsum!")
            return False
        except ValueError:
            log.error(f"Hashing algorithm {self.checksumAlg} is not supported!")
            return False

        self.save()
        return True

    def rename_file(self, name: str, new_name: str) -> bool:
        """
        Try to rename an existing file to a new free filename.

        Returns True on success, i.e. file and its data exists and new name is free.
        """
        if name not in self.files:
            log.warning(f"Cannot rename non-existing file {name} from {self.id}")
            return False

        if name == new_name:
            log.info(f"Rename {name}->{new_name} in {self.id}: nothing to do.")
            return True

        if new_name in self.files:
            log.warning(f"Can't rename {name}->{new_name} in {self.id}, target exists!")
            return False

        oldpath = self._upload_filepath(name)
        newpath = self._upload_filepath(new_name)

        if not oldpath.is_file():
            msg = f"File {oldpath} does not exists, although referenced!"
            log.error(msg)
            raise FileNotFoundError(msg)
        if newpath.is_file():
            msg = f"File {newpath} exists, but not referenced! Abort rename."
            log.error(msg)
            raise FileExistsError(msg)

        oldpath.rename(newpath)
        self.files[new_name] = self.files[name]
        del self.files[name]

        self.save()
        return True

    ####

    def complete(self) -> Tuple[Optional[Path], Dict[str, str]]:
        """
        Validate metadata and check that all checksums are present.

        On success, remove files and data from 'staging' directory
        and produce the directory in the 'complete' directory. Return path.
        """
        global _datasets

        val_errors = self.validate_dataset()
        if len(val_errors) != 0:
            log.error(f"Cannot complete dataset, validation failed: {val_errors}")
            return (None, val_errors)

        missing_checksums = {}
        for file, dat in self.files.items():
            if dat.checksum is None:
                missing_checksums[file] = f"File checksum is missing: {file}"
        if len(missing_checksums) != 0:
            return (None, missing_checksums)

        upload_dir: Final[Path] = self._upload_dir()
        target_dir: Final[Path] = self._target_dir()

        # move the files
        upload_dir.rename(target_dir)

        # produce the metadata files
        if self.rootMeta is not None:
            with open(target_dir / METADATA_SUF, "w") as outfile:
                json.dump(self.rootMeta, outfile, indent=2)
                outfile.flush()

        for filename, dat in self.files.items():
            if dat.metadata is not None:
                with open(target_dir / (filename + METADATA_SUF), "w") as outfile:
                    json.dump(dat.metadata, outfile, indent=2)
                    outfile.flush()

        # create a checksum file (e.g. sha256sums.txt)
        with open(target_dir / (self.checksumAlg + "sums.txt"), "w") as outfile:
            for name, dat in sorted(self.files.items()):
                outfile.write(f"{name}  {dat.checksum}\n")
                outfile.flush()

        # create json for remaining info that might be useful
        with open(target_dir / "dataset.json", "w") as outfile:
            dsinfo = DatasetInfo(
                creator=self.creator, created=self.created, profile=self.profile
            )
            json.dump(json.loads(dsinfo.json()), outfile, indent=2)
            outfile.flush()

        # TODO: this is the point where we could store the profile as  e.g. dirschema

        del _datasets[self.id]

        # delete persistence file (we produced all derivative files already)
        self._persist_filename(self.id).unlink()

        log.info(f"Dataset {self.id} completed.")
        return (target_dir, {})

    def delete(self) -> None:
        """Delete information about this dataset and all its files IRREVERSIBLY."""
        upload_dir: Final[Path] = self._upload_dir()
        for uploaded_file in upload_dir.glob("*"):
            uploaded_file.unlink()
        upload_dir.rmdir()

        self._persist_filename(self.id).unlink()

        del _datasets[self.id]

        log.info(f"Data of {self.id} deleted.")

    @classmethod
    def load(cls, ds_id: UUID) -> Optional[Dataset]:
        """Load a dataset from the corresponding serialization file."""
        persist_file = Dataset._persist_filename(ds_id)
        if not persist_file.is_file():
            log.error(f"Failed loading, {str(persist_file)} not found.")
            return None

        ds = Dataset.parse_file(Dataset._persist_filename(ds_id))
        if len(ds.files) == 0 and not ds._upload_dir().is_dir():
            log.warning(f"Upload dir {ds_id} not found! This is odd. Will create one.")
            ds._upload_dir().mkdir()

        # check that for each entry the files do exist
        for fname in ds.files.keys():
            if not ds._upload_filepath(fname).is_file():
                # this really should not happen that files just vanish... real exception!
                msg = f"File {fname} referenced in dataset, but not existing!"
                log.error(msg)
                raise FileNotFoundError(msg)

        # for each additional file without an entry, create one
        for filepath in ds._upload_dir().glob("*"):
            if filepath.name not in ds.files:
                ds.files[filepath.name] = FileInfo()

        return ds

    @classmethod
    def create(cls, profile: Profile, creator: Optional[OrcidStr] = None) -> Dataset:
        """Create a new dataset and its directory + persistence file, return it."""
        now = datetime.now()
        tdiff = timedelta(hours=conf().metador_push.incomplete_expire_after)
        ds = cls(
            id=uuid1(),
            creator=creator,
            created=now,
            expires=now + tdiff,
            profile=profile,
            checksumAlg=conf().metador_push.checksum,
        )

        ds._upload_dir().mkdir()  # create underlying upload directory
        ds.save()  # create underlying file
        _datasets[ds.id] = ds  # register in loaded list
        log.info(f"New dataset {ds.id} created.")
        return ds

    @classmethod
    def load_datasets(cls) -> None:
        """Load datasets for which a persistence file exists."""
        global _datasets
        cls._prepare_dirs()
        for ds_id in cls._find_staging_datasets():
            log.debug(f"Loading dataset {ds_id} from file.")
            ds = Dataset.load(ds_id)
            if ds is not None:
                _datasets[ds_id] = ds

    @classmethod
    def cleanup_datasets(cls) -> None:
        """Remove expired datasets from cache and delete the files."""
        t = datetime.today()
        log.info("Cleaning up expired datasets...")
        expired = [v for v in _datasets.values() if v.is_expired(t)]
        for ds in expired:
            ds.delete()

    @classmethod
    def get_datasets(cls, creator: Optional[OrcidStr] = None) -> List[UUID]:
        """Return a list of dataset ids (possibly filtered by creator)."""
        t = datetime.today()
        return [
            k
            for k, v in _datasets.items()
            if not v.is_expired(t) and (creator is None or (v.creator == creator))
        ]

    @classmethod
    def get_dataset(cls, ds_id: UUID) -> Dataset:
        """
        Return a dataset if it exists and is not expired (throws if it does not exist).

        If it is expired, it is treated like it does not exist,
        as a cleaning job could delete it any moment.
        """
        ds = _datasets[ds_id]
        if ds.is_expired():
            raise KeyError
        return ds

    @classmethod
    def _prepare_dirs(cls) -> None:
        """Create directory structure for datasets at location specified in config."""
        data_dir = conf().metador_push.data_dir
        if not data_dir.is_dir():
            data_dir.mkdir()
        if not cls._staging_dir().is_dir():
            cls._staging_dir().mkdir()
        if not cls._complete_dir().is_dir():
            cls._complete_dir().mkdir()

    @classmethod
    def _find_staging_datasets(cls) -> List[UUID]:
        """Get UUIDs of datasets with serialized data in the staging directory."""
        files = list(cls._staging_dir().glob("*" + DATASET_SUF))
        return list(map(lambda x: UUID(re.sub(DATASET_SUF + "$", "", x.name)), files))
