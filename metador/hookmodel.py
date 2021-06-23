"""
Pydantic model to parse JSON passed by tusd to hook handler.
Based on description in: https://github.com/tus/tusd/blob/master/docs/hooks.md
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


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


class TusdEvent(BaseModel):
    """Such an object is passed in the body of the POST by tusd."""

    Upload: TusdUpload
    HTTPRequest: TusdHTTPRequest


class TusdHookName(str, Enum):
    """One of these strings is passed in the header of the POST as Hook-Name by tusd."""

    pre_create = "pre-create"
    post_create = "post-create"
    pre_finish = "pre-finish"
    post_finish = "post-finish"
    post_terminate = "post-terminate"
    post_receive = "post-receive"
