"""Handle the upload per HTTP / tus."""
import re
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, Response
from pydantic import BaseModel, ValidationError
from typing_extensions import Final, Literal

from . import config as c
from .dataset import Dataset
from .log import log
from .util import load_json


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

META_DATASET: Final[str] = "dataset"
META_FILENAME: Final[str] = "filename"

"""Header to be added to link an upload to a dataset."""


@routes.post(TUSD_HOOK_ROUTE)
async def tusd_hook(
    background_tasks: BackgroundTasks,
    body: TusdEvent,
    hook_name: TusdHookName = Header(...),
):
    """React to events signaled by tusd (this is registered in tusd as http hook)."""
    upl_meta = body.Upload.MetaData

    log.debug(hook_name)
    log.debug(body)

    if META_DATASET not in upl_meta:
        msg = "Exactly one dataset ID must be attached."
        log.debug(msg)
        return Response(msg, status_code=400)
    ds_id_str: str = upl_meta[META_DATASET]

    if META_FILENAME not in upl_meta:  # or len(upl_meta[META_FILENAME]) > 1:
        msg = "Exactly one filename must be attached."
        log.debug(msg)
        return Response(msg, status_code=400)
    filename: str = upl_meta[META_FILENAME]

    if filename.find("/") >= 0:
        msg = "Invalid filename: may not contain /"
        log.debug(msg)
        return Response(msg, status_code=422)

    try:
        ds_id: UUID = UUID(ds_id_str)
        ds: Dataset = Dataset.get_dataset(ds_id)
    except (ValueError, AttributeError):
        msg = f"Invalid dataset ID: {ds_id_str}"
        log.debug(msg)
        return Response(msg, status_code=422)
    except KeyError:
        msg = "No such dataset."
        log.debug(msg)
        return Response(msg, status_code=404)

    if hook_name == TusdHookName.pre_create:
        if filename in ds.files:
            msg = f"File {filename} already exists. Refused."
            log.debug(msg)
            return Response(msg, status_code=422)
        # NOTE: we cover only the trivial false schema, allowing to reject files on purpose
        # It is overkill trying to detect complex logically unsatisfiable schemas.
        if ds.profile.get_schema_for(filename) == False:
            msg = f"A file called {filename} is forbidden in this dataset."
            log.debug(msg)
            return Response(msg, status_code=422)
        return None  # 200 OK, no body

    # file complete -> import to dataset with original filename, compute checksum
    elif hook_name == TusdHookName.post_finish:
        assert body.Upload.Storage is not None
        uplloc: Path = body.Upload.Storage.Path.resolve()
        if (
            uplloc.parent != c.conf().metador_push.tusd_datadir.resolve()
        ):  # security check
            msg = "File location does not match tusd_datadir."
            log.debug(msg)
            return Response(msg, status_code=422)

        renamed: Path = uplloc.parent / filename
        log.debug(f"Upl: {uplloc} -> {renamed}")
        assert uplloc.is_file()
        uplloc.rename(renamed)
        ds.import_file(renamed)
        Path(str(uplloc) + ".info").unlink()  # remove .info file
        background_tasks.add_task(ds.compute_checksum, filename)


# Tusd cleanup helpers:


def is_tusd_file(p: Path) -> bool:
    """
    Check whether filename looks like something tusd could have created.

    Used to filter files for cleanup to avoid deleting something wrong.
    """
    return re.match("^[0-9a-f]{32}(\\.info)?$", p.name) is not None


def get_tusd_garbage(paths: Iterable[Path], dsets: Set[str]) -> Set[Path]:
    """
    Return list of garbage files given a list of filepaths and a list of known datasets.

    The filepaths should be existing data and .info files (i.e., contents of the tusd
    data directory), the datasets should be the currently existing non-completed datasets.
    This function will ignore filenames that look not like what tusd creates and also
    ignore .info files that cannot be parsed successfully.

    Side effects: Tries to load the .info files from file system
    """
    candidates = set(map(str, filter(is_tusd_file, paths)))  # keep plausible filenames
    # separate .info and the (partial) data files
    ifiles = set(filter(lambda p: p.find("info") >= 0, candidates))
    dfiles = candidates - ifiles
    # collect "unpaired" files
    garbage = {dfile for dfile in dfiles if dfile + ".info" not in ifiles}
    garbage = garbage.union({ifile for ifile in ifiles if ifile[:-5] not in dfiles})
    # add "stale" uploads
    for ifile in ifiles - garbage:
        upl_meta = None
        try:
            upl_meta = TusdUpload.parse_obj(load_json(ifile))
        except (JSONDecodeError, ValidationError):
            continue  # does not look like tusd upload info metadata
        if upl_meta is not None and "dataset" in upl_meta.MetaData:
            if upl_meta.MetaData["dataset"] in dsets:
                continue  # existing dataset -> still relevant
        garbage.add(ifile)
        garbage.add(ifile[:-5])
    return set(map(Path, garbage))
