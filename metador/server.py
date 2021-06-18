"""
Main file for the Metador backend.
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import pkg_res, orcid, api
from .orcid import api as orcid_api
from .orcid import mock

from .config import conf
from .log import init_logger


app = FastAPI(title="Metador")

# add dummy-ORCID routes for development (they always sign in a dummy user)
if conf().orcid.use_fake:
    app.include_router(mock.routes)

# initialize authentication based on config file
orcid.init_auth(conf().metador.site, conf().orcid, conf().metador.data_dir)
app.include_router(orcid_api.routes)

# actual backend interface used by SPA
app.include_router(api.routes)


@app.on_event("startup")
def on_startup():
    # must (re-)init logging here (otherwise won't work properly with uvicorn reload)
    init_logger(conf().metador.log.level.value, str(conf().metador.log.file))


@app.on_event("shutdown")
def on_shutdown():
    # persist state to files
    orcid.get_auth().dump_sessions()


app.mount("/static", StaticFiles(directory=pkg_res("static")), name="static")

# @app.post(c.TUSD_HOOK_ROUTE)
# async def tusd_hook(body: TusdEvent, hook_name: TusdHookName = Header(...)):
#     log.debug(hook_name)
#     log.debug(body)
#     return "TODO"


@app.get("/favicon.ico", response_class=FileResponse)
def read_favicon():
    """To prevent browser 404 errors."""

    return FileResponse(pkg_res("static/favicon.ico"))


@app.get("/site-base")
async def site_base():
    """Returns the configured site prefix. Useful for correct client-side routing."""

    return conf().metador.site


# must come last
@app.get("/{anything_else:path}")
async def catch_all():
    """Catch-all redirect of unknown routes to SPA UI."""

    return FileResponse(pkg_res("static/index.html"))
