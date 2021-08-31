"""Main file for the Metador server."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing_extensions import Final

from . import api, orcid, pkg_res, upload
from .config import conf
from .dataset import Dataset
from .log import init_logger
from .orcid import api as orcid_api
from .orcid import mock
from .profile import Profile

app = FastAPI(title="Metador")
"""The main server app that collects all server routes."""

# must include routes here, because of catch-all later
# (cannot put this into on_startup)
app.include_router(mock.routes)  # mock ORCID for dev (always sign in dummy user)
app.include_router(orcid_api.routes)  # auth
app.include_router(api.routes)  # backend
app.include_router(upload.routes)  # tusd hook


async def run_cleanup_task() -> None:
    """Periodic cleanup job for expired sessions and datasets."""
    next_cleanup = datetime.today()
    while True:
        orcid.get_auth().cleanup_sessions()
        Dataset.cleanup_datasets()
        # wait until next time...
        next_cleanup = next_cleanup + timedelta(days=1)
        while datetime.today() < next_cleanup:
            await asyncio.sleep(3600)  # check every hour


cleanup_task: asyncio.Task  # reference to started cleanup task


@app.on_event("startup")
def on_startup():
    """Initialize singletons based on config."""
    # must (re-)init logging here (otherwise won't work properly with uvicorn reload)
    init_logger(conf().metador.log.level.value, conf().metador.log.file)
    # prepare stuff as configured
    orcid.init_auth(conf().metador.site, conf().orcid, conf().metador.data_dir)
    Profile.load_profiles(conf().metador.profile_dir)
    Dataset.load_datasets()

    global cleanup_task
    cleanup_task = asyncio.create_task(run_cleanup_task())


@app.on_event("shutdown")
async def on_shutdown():
    """Store transient state to files."""
    orcid.get_auth().dump_sessions()

    global cleanup_task
    cleanup_task.cancel()
    await asyncio.wait(cleanup_task)


@app.get("/site-base")
async def site_base():
    """Return the configured site prefix. Useful for correct client-side routing."""
    return conf().metador.site


@app.get("/tusd-endpoint")
async def tusd_endpoint():
    """Return the configured tusd endpoint to be used by client."""
    return conf().metador.tusd_endpoint


FRONTEND_DIR: Final[Path] = pkg_res("frontend/public")
"""Directory where the built frontend and all its files are located."""


@app.get("/")
async def home():
    """Catch-all redirect (must come last!) of all still unmatched routes to SPA UI."""
    return FileResponse(FRONTEND_DIR / "index.html")


# https://stackoverflow.com/a/68363904/432908
class SPAStaticFiles(StaticFiles):
    """Return SPA page for files that are not found (instead of 404)."""

    async def get_response(self, path: str, scope):
        """Serve file or delegate the route lookup to parent on failure."""
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            # response = await super().get_response(".", scope)
            return FileResponse(FRONTEND_DIR / "index.html")
        return response


app.mount("/", SPAStaticFiles(directory=FRONTEND_DIR), name="static")


# must come last
# @app.get("/{anything_else:path}")
# async def catch_all():
#     """Catch-all redirect (must come last!) of all still unmatched routes to SPA UI."""
#     return FileResponse(FRONTEND_DIR / "index.html")
