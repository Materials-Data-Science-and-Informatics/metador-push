"""Functions for calling postprocessing after dataset completion."""

import subprocess
from pathlib import Path
from urllib import parse

import httpx
from pydantic import BaseModel

from .log import log


class DatasetNotification(BaseModel):
    """The kind of JSON object sent to HTTP postprocessing endpoint as notification."""

    event: str = "new_dataset"
    location: str  # cannot use Path here, httpx can't handle it


async def notify_endpoint(endpoint: str, ds_location: Path) -> bool:
    """Notify an endpoint via POST request about new complete dataset at ds_location."""
    dat = DatasetNotification(location=str(ds_location))
    try:
        async with httpx.AsyncClient() as client:
            await client.post(endpoint, json=dat.dict())
    except httpx.RequestError as e:
        log.error(f"Failed notifying postprocessing endpoint: {e}")
        return False
    return True


def launch_script(command: str, ds_location: Path) -> bool:
    """Run a script with dataset location as extra argument and forget it."""
    try:
        subprocess.Popen(command.split() + [str(ds_location)], start_new_session=True)
    except FileNotFoundError as e:
        log.error(f"Failed running postprocessing script: {e}")
        return False
    return True


async def pass_to_postprocessing(target: str, ds_location: Path) -> bool:
    """If target is a HTTP(S) URL, issue a POST, else interpret as command and run it."""
    if parse.urlsplit(target).scheme.find("http") >= 0:
        log.debug(f"Notify postprocessing http hook {target}")
        ret = await notify_endpoint(target, ds_location)
        return ret
    else:
        log.debug(f"Launch postprocessing script {target}")
        return launch_script(target, ds_location)
