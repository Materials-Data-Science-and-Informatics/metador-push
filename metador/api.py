from typing import Final, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from .dataset import Dataset, get_dataset, get_datasets
from .orcid import get_session
from .orcid.auth import Session
from .profile import Profile, get_profile, get_profiles

# from . import dataset
# from .config import conf

API_PREF: Final[str] = "/api"

routes: APIRouter = APIRouter(
    prefix=API_PREF, dependencies=[Depends(get_session)], tags=["backend"]
)


@routes.get("/")
def api_info():
    """Entry point into backend API."""

    # TODO: maybe give some HATEOAS navigation (possible actions...)
    return "This is the Metador backend. If you see this, then you are authenticated."


####


@routes.get("/profiles")
def get_profile_list() -> List[str]:
    """
    Return the available dataset profiles (pr_id + human readable title for UI).

    Only used for the client to select which kind of dataset they desire to create.
    """

    return get_profiles()


@routes.get("/profiles/{pr_name}")
def get_profile_instance(pr_name: str) -> Optional[Profile]:
    """Returns the profile."""

    return get_profile(pr_name)


####


DATASETS: Final[str] = "/datasets"


@routes.post(DATASETS)
def new_dataset(
    profile: str, session: Optional[Session] = Depends(get_session)
) -> UUID:
    """
    Creates a new dataset to be validated according to selected profile (query param).

    Returns its UUID as string.
    """

    prf = get_profile(profile)
    if prf is None:
        raise HTTPException(
            status_code=404, detail=f"Profile '{profile}' does not exist."
        )

    orcid = session.orcid if session else None
    ds = Dataset.create(prf, orcid)
    return ds.id


@routes.get(DATASETS)
def get_user_datasets(session: Optional[Session] = Depends(get_session)) -> List[UUID]:
    """Return list of staging dataset UUIDs owned by the user."""

    if session is None:
        return []  # if unauthenticated, do not return a list of datasets

    return get_datasets(session.orcid)


####


def dataset_exists(ds_uuid: UUID):
    """Helper dependency. requires existence of referenced dataset."""
    try:
        get_dataset(ds_uuid)
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

    return get_dataset(ds_uuid)


@ds_routes.put(
    "/{ds_uuid}",
    responses={422: {"description": "Validation failed"}},
)
def put_dataset(ds_uuid: UUID) -> bool:
    """
    Try to submit dataset. If it validates fine, passed on to subprocessing.

    If validation fails, returns 422 status code.
    """

    ds = get_dataset(ds_uuid)
    print(ds)
    return get_dataset(ds_uuid).complete()


@ds_routes.delete("/{ds_uuid}")
def del_dataset(ds_uuid: UUID):
    """IRREVERSIBLY(!!!) delete the dataset and all related data."""

    get_dataset(ds_uuid).delete()


@ds_routes.get("/{ds_uuid}/meta")
def get_dataset_metadata(ds_uuid: UUID):
    """Return currently stored dataset root metadata JSON (null if nothing stored)."""

    pass


@ds_routes.put("/{ds_uuid}/meta")
def put_dataset_metadata(ds_uuid: UUID):
    """Store a JSON file as dataset metadata (without validation)."""

    pass


@ds_routes.get("/{ds_uuid}/meta/validate")
def validate_dataset_metadata(ds_uuid: UUID):
    """
    Validate current metadata using server-side validation, according to profile.

    (The client-side validation is not authoritative.)
    """

    pass


@ds_routes.get("/{ds_uuid}/files")
def get_dataset_files(ds_uuid: UUID, format: Optional[str] = None):
    """
    Return dataset files and their corresponding checksums, if already available.

    More specifically, returns by default of format=json
    [{"filename": string, "checksum": string|null}, ...]

    Otherwise, returns a plaintext response in a format that can be used with
    a checksum tool (one file per line, file and checksum separated by 2 spaces).
    """


FILES = "/{ds_uuid}/files"
file_routes: APIRouter = APIRouter(
    prefix=FILES,
    dependencies=[],  # TODO: add "file exists" check
    responses={404: {"description": "File not found"}},
)


@file_routes.delete("/{filename}")
def del_file(filename: str):
    """
    IRREVERSIBLY delete the file, metadata and checksum from dataset, if it exists.
    """

    pass


@file_routes.get("/{filename}/checksum")
def get_file_checksum(filename: str):
    """
    Get checksum of this file (as computed by the algorithm attached to the dataset).

    Can be used for polling while waiting for hash computation of a new upload.
    """

    pass


@file_routes.patch("/{filename}/rename-to/{new_filename}")
def rename_file(filename: str, new_filename: str):
    """
    If the file exists, rename to new filename and fix all attached information.

    Client is responsible for synchronizing the local representation on success.
    """

    pass


@file_routes.get("/{filename}/meta")
def get_file_metadata(filename: str):
    """Get currently stored JSON metadata of selected file, if it exists (can be null)."""

    pass


@file_routes.put("/{filename}/meta")
def put_file_metadata(filename: str):
    """Set currently stored JSON metadata of selected file, if it exists."""

    pass


@file_routes.get("/{filename}/meta/validate")
def validate_file_metadata(filename: str):
    """
    Validate current file metadata using server-side validation, according to profile.

    (The client-side validation is not authoritative.)
    """

    pass


@file_routes.get("/{filename}/echo")
def test(ds_uuid: UUID, filename: str):
    """Test that we can inherit path parameters, yeah!"""

    return {"ds": ds_uuid, "fn": filename}


ds_routes.include_router(file_routes)
routes.include_router(ds_routes)


# must come last. need to catch this, because the "main" catch-all will just give the UI
@routes.get("/{anything_else:path}")
async def invalid_api_endpoint():
    """Catch unknown API endpoint."""

    raise HTTPException(status_code=404, detail="API endpoint not found")


# TODO: start implementing all this stuff
# TODO: foralize MetadorProfile JSON Schema
# {
#     name: string, <- local alphanumeric identifier ^\w+$
#     title: string, <- human title for this profile (optional, by default equals name)
#     rootSchema: JSONSchema,
#     patterns: [
#         {pattern: ECMA 262 regex pattern-str (implicitly /^...$/)
#          schema: JSONSchema
#          },
#         ...
#     ]
#     fallback: JSONSchema <- optional, not given = null = falsy = failure
#     metaSuffix: "_meta.json" <- optional, this is default value
# }
# the record directory must have a _meta.json file that is checked against the root
# schema, otherwise null is taken as metadata
# could turn this into json-ld later on

# JSONSchema must be a jsonschema object or a $ref string

# files are checked by first json schema whose pattern matched the filename
# for file FILENAME there must be a schema FILENAME_meta.json
# if filename is called something_meta.json, then its metadata is something_meta.json_meta.json
# what about files not matching? must be checked by fallback (true = anything goes, false = unmatching forbidden)

# todo: add checksum_tool option to config
# create Dirschema json schema and allow conf to read it