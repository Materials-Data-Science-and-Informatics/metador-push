"""Handle the upload per HTTP / tus."""
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, Response
from pydantic import BaseModel
from typing_extensions import Final, Literal

from .dataset import Dataset
from .log import log


class TusdHTTPRequest(BaseModel):
    """Request of client to tusd, passed over to us."""

    Method: str
    URI: str
    RemoteAddr: str
    Header: Dict[str, Any]


# NOTE: we don't allow S3 buckets for our purposes
class TusdStorage(BaseModel):
    """Location of the upload."""

    Type: Literal["filestore"]
    Path: Path


class TusdUpload(BaseModel):
    """Administrative information about the upload."""

    ID: str
    Size: int
    Offset: int
    IsFinal: bool
    IsPartial: bool
    SizeIsDeferred: bool
    PartialUploads: Optional[List[str]]
    MetaData: Dict[str, str]
    Storage: Optional[TusdStorage]


class TusdHookName(str, Enum):
    """One of these strings is passed in the header of the POST as Hook-Name by tusd."""

    pre_create = "pre-create"
    post_create = "post-create"
    pre_finish = "pre-finish"
    post_finish = "post-finish"
    post_terminate = "post-terminate"
    post_receive = "post-receive"


class TusdEvent(BaseModel):
    """
    Pydantic model to parse JSON passed by tusd to hook handler.

    Based on [tusd documentation](https://github.com/tus/tusd/blob/master/docs/hooks.md)
    """

    Upload: TusdUpload
    HTTPRequest: TusdHTTPRequest


routes: APIRouter = APIRouter(tags=["tusd-hook"])

TUSD_HOOK_ROUTE: Final[str] = "/tusd-events"
"""API route to handle tusd events."""

HDR_DATASET: Final[str] = "Dataset"
HDR_FILENAME: Final[str] = "Filename"

"""Header to be added to link an upload to a dataset."""


@routes.post(TUSD_HOOK_ROUTE)
async def tusd_hook(
    background_tasks: BackgroundTasks,
    body: TusdEvent,
    hook_name: TusdHookName = Header(...),
):
    """React to events signaled by tusd (this is registered in tusd as http hook)."""
    client_reqhdr = body.HTTPRequest.Header

    log.debug(hook_name)
    log.debug(body)

    if HDR_DATASET not in client_reqhdr or len(client_reqhdr[HDR_DATASET]) > 1:
        return Response("Exactly one dataset ID must be in header.", status_code=400)
    ds_id_str: str = client_reqhdr[HDR_DATASET][0]

    if HDR_FILENAME not in client_reqhdr or len(client_reqhdr[HDR_FILENAME]) > 1:
        return Response("Exactly one filename must be in header.", status_code=400)
    filename: str = client_reqhdr[HDR_FILENAME][0]

    if filename.find("/") >= 0:
        return Response("Invalid filename: may not contain /", status_code=400)

    try:
        ds_id: UUID = UUID(ds_id_str)
        ds: Dataset = Dataset.get_dataset(ds_id)
    except (ValueError, AttributeError):
        return Response(f"Invalid dataset ID: {ds_id_str}", status_code=422)
    except KeyError:
        return Response("No such dataset.", status_code=404)

    # reject files that are not in a known dataset
    # if a valid ID is given, accept (the ID is only known to the owner)
    if hook_name == TusdHookName.pre_create:
        if filename in ds.files:
            return Response(
                f"File {filename} already exists. Refused.", status_code=422
            )
        return None  # 200 OK, no body

    # file complete -> import to dataset with original filename, compute checksum
    elif hook_name == TusdHookName.post_finish:
        assert body.Upload.Storage is not None
        uplloc: Path = body.Upload.Storage.Path
        renamed: Path = uplloc.parents[0] / filename
        log.debug(f"Upl: {uplloc} -> {renamed}")
        assert uplloc.is_file()
        uplloc.rename(renamed)
        ds.import_file(renamed)
        background_tasks.add_task(ds.compute_checksum, filename)
