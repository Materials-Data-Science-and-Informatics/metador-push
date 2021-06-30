"""
Handle the upload per HTTP / tus
"""
from enum import Enum
from typing import Any, Dict, Final, List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel

from .dataset import Dataset
from .log import log


class TusdHTTPRequest(BaseModel):
    Method: str
    URI: str
    RemoteAddr: str
    Header: Dict[str, Any]


# NOTE: we don't allow S3 buckets for our purposes
class TusdStorage(BaseModel):
    Type: Literal["filestore"]
    Path: str


class TusdUpload(BaseModel):
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


#: API route to handle tusd events
TUSD_HOOK_ROUTE: Final[str] = "/tusd-events"

routes: APIRouter = APIRouter(tags=["tusd-hook"])


@routes.post(TUSD_HOOK_ROUTE)
async def tusd_hook(body: TusdEvent, hook_name: TusdHookName = Header(...)):
    """Hook to react on events signaled by tusd."""

    log.debug(hook_name)
    log.debug(body)

    # reject files that are not in a known dataset
    # if a valid ID is given, accept (the ID is only known to the owner)
    if hook_name == TusdHookName.pre_create:
        if "Dataset" not in body.HTTPRequest.Header:
            return Response("No dataset ID given in header.", status_code=400)
        try:
            ds_id = UUID(body.HTTPRequest.Header["Dataset"])
            Dataset.get_dataset(ds_id)
        except AttributeError:
            return Response("Invalid dataset ID", status_code=422)
        except KeyError:
            return Response("No such dataset.", status_code=404)
        return None  # OK
    # file complete -> import to dataset, compute checksum
    elif hook_name == TusdHookName.post_finish:
        ds_id = UUID(body.HTTPRequest.Header["Dataset"])
        Dataset.get_dataset(ds_id)
        # TODO
