"""Core backend API exposing functionality to the frontend."""

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from typing_extensions import Final

from .config import conf
from .dataset import Dataset
from .orcid import get_session
from .orcid.auth import Session
from .postprocessing import pass_to_postprocessing
from .profile import Profile

API_PREF: Final[str] = "/api"

routes: APIRouter = APIRouter(
    prefix=API_PREF, dependencies=[Depends(get_session)], tags=["backend"]
)
"""Backend routes (to be mounted by server app)."""


@routes.get("/")
def api_info():
    """Entry point into backend API."""
    return "This is the Metador backend. If you see this, then you are authenticated."


####


@routes.get("/profiles")
def get_profile_list() -> List[str]:
    """
    Return the available dataset profiles (pr_id + human readable title for UI).

    Only used for the client to select which kind of dataset they desire to create.
    """
    return Profile.get_profiles()


@routes.get("/profiles/{pr_name}")
def get_profile_instance(pr_name: str) -> Optional[Profile]:
    """Return the profile."""
    try:
        return Profile.get_profile(pr_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such profile: '{pr_name}'")


####


DATASETS: Final[str] = "/datasets"


@routes.post(DATASETS)
def new_dataset(
    profile: str, session: Optional[Session] = Depends(get_session)
) -> UUID:
    """
    Create a new dataset to be validated according to selected profile (query param).

    Returns its UUID as string.
    """
    try:
        prf = Profile.get_profile(profile)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such profile: '{profile}'")

    orcid = session.orcid if session else None
    ds = Dataset.create(prf, orcid)
    return ds.id


@routes.get(DATASETS)
def get_user_datasets(session: Optional[Session] = Depends(get_session)) -> List[UUID]:
    """Return list of staging dataset UUIDs owned by the user."""
    if session is None:
        return []  # if unauthenticated, do not return a list of datasets

    return Dataset.get_datasets(session.orcid)


####


def dataset_exists(ds_uuid: UUID):
    """Throw exception if dataset does not exist, to be used as dependency."""
    try:
        Dataset.get_dataset(ds_uuid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Dataset not found")


ds_routes: APIRouter = APIRouter(
    prefix=DATASETS,
    dependencies=[Depends(dataset_exists)],
    responses={404: {"description": "Dataset not found"}},
)


@ds_routes.get("/{ds_uuid}")
def get_existing_dataset(ds_uuid: UUID) -> Optional[Dataset]:
    """
    Return overview of current dataset.

    This includes file names, metadata, profile, schemas, etc.
    And also checksum algorithm and data file checksums.
    """
    return Dataset.get_dataset(ds_uuid)


@ds_routes.put(
    "/{ds_uuid}",
    responses={422: {"description": "Validation failed"}},
)
async def put_dataset(ds_uuid: UUID):
    """
    Try to submit dataset. If it validates fine, trigger post-processing.

    If validation fails, returns 422 status code.
    """
    path = Dataset.get_dataset(ds_uuid).complete()
    if path is None:
        return Response(
            "Cannot complete dataset, invalid metadata or missing checksums!",
            status_code=422,
        )

    compl_hook = conf().metador.completion_hook
    if compl_hook is not None:
        await pass_to_postprocessing(compl_hook, path)

    # from the user's point of view, we are done
    # the user does not care about possible problems in postprocessing
    return Response("OK", status_code=200)


@ds_routes.delete("/{ds_uuid}")
def del_dataset(ds_uuid: UUID):
    """Delete the dataset and all related data IRREVERSIBLY(!!!)."""
    return Dataset.get_dataset(ds_uuid).delete()


@ds_routes.get("/{ds_uuid}/meta")
def get_dataset_metadata(ds_uuid: UUID):
    """Return currently stored dataset root metadata JSON (null if nothing stored)."""
    return Dataset.get_dataset(ds_uuid).rootMeta


@ds_routes.put("/{ds_uuid}/meta")
def put_dataset_metadata(ds_uuid: UUID, metadata: dict = Body(...)):
    """Store a JSON file as dataset metadata (without validation)."""
    return Dataset.get_dataset(ds_uuid).set_metadata(None, metadata)


@ds_routes.get("/{ds_uuid}/meta/validate")
def validate_dataset_metadata(ds_uuid: UUID):
    """
    Validate current metadata using server-side validation, according to profile.

    (The client-side validation is not authoritative.)
    """
    return Dataset.get_dataset(ds_uuid).validate_metadata(None)


@ds_routes.get("/{ds_uuid}/files")
def get_dataset_files(ds_uuid: UUID):
    """Return dataset files and their corresponding checksums, if already available."""
    ret: Dict[str, Optional[str]] = {}
    for name, dat in Dataset.get_dataset(ds_uuid).files.items():
        ret[name] = dat.checksum
    return ret


def dataset_file_exists(ds_uuid: UUID, filename: str):
    """Raise HTTP exception if referenced file does not exist in dataset (use as dep)."""
    if filename not in Dataset.get_dataset(ds_uuid).files:
        raise HTTPException(status_code=404, detail="File not found in dataset")


FILES = "/{ds_uuid}/files"
file_routes: APIRouter = APIRouter(
    prefix=FILES,
    dependencies=[Depends(dataset_file_exists)],
    responses={404: {"description": "File not found in dataset"}},
)


@file_routes.delete("/{filename}")
def del_file(ds_uuid: UUID, filename: str):
    """Delete the file (+ checksum + metadata) IRREVERSIBLYfrom dataset, if it exists."""
    return Dataset.get_dataset(ds_uuid).delete_file(filename)


@file_routes.get("/{filename}/checksum")
def get_file_checksum(ds_uuid: UUID, filename: str):
    """
    Get checksum of this file (as computed by the algorithm attached to the dataset).

    Can be used for polling while waiting for hash computation of a new upload.
    """
    return Dataset.get_dataset(ds_uuid).files[filename].checksum


@file_routes.patch("/{filename}/rename-to/{new_filename}")
def rename_file(ds_uuid: UUID, filename: str, new_filename: str):
    """
    If the file exists, rename to new filename and fix all attached information.

    Client is responsible for synchronizing the local representation on success.
    """
    return Dataset.get_dataset(ds_uuid).rename_file(filename, new_filename)


@file_routes.get("/{filename}/meta")
def get_file_metadata(ds_uuid: UUID, filename: str):
    """Get currently stored JSON metadata of selected file, if it exists (can be null)."""
    return Dataset.get_dataset(ds_uuid).files[filename].metadata


@file_routes.put("/{filename}/meta")
def put_file_metadata(ds_uuid: UUID, filename: str, metadata: dict = Body(...)):
    """Set currently stored JSON metadata of selected file, if it exists."""
    return Dataset.get_dataset(ds_uuid).set_metadata(filename, metadata)


@file_routes.get("/{filename}/meta/validate")
def validate_file_metadata(ds_uuid: UUID, filename: str):
    """
    Validate current file metadata using server-side validation, according to profile.

    (The client-side validation is not authoritative.)
    """
    return Dataset.get_dataset(ds_uuid).validate_metadata(filename)


ds_routes.include_router(file_routes)
routes.include_router(ds_routes)


# must come last. need to catch this, because the "main" catch-all will just give the UI
@routes.get("/{anything_else:path}")
async def invalid_api_endpoint():
    """Catch unknown API endpoint."""
    raise HTTPException(status_code=404, detail="API endpoint not found")
