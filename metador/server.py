"""
Main file for the Metador backend.
"""

from typing import Optional

from fastapi import FastAPI, Request, Header, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import util, pkg_res, orcid
from . import config as c
from .orcid import Auth, Session
from .log import log, init_logger
from .config import conf
from .hookmodel import TusdEvent, TusdHookName

app = FastAPI()

if c.conf().orcid.use_fake:
    app.include_router(orcid.mock_orcid)

# initialize authentication based on config file
auth = Auth(c.conf().metador.site, c.conf().orcid, c.conf().metador.data_dir)
app.include_router(auth.routes)


# make HTTPException return a plain text message
# TODO: what about user-facing exceptions? need to subclass and make templated variant
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


@app.on_event("startup")
def on_startup():
    # must re-init logging here (otherwise won't work with uvicorn reload)
    init_logger(c.conf().metador.log.level.value, str(c.conf().metador.log.file))


@app.on_event("shutdown")
def on_shutdown():
    auth.dump_sessions()


# serve static files
app.mount("/static", StaticFiles(directory=pkg_res("static")), name="static")


# prevent 404 (browser always tries to get this)
@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")


# location of templates
templates = Jinja2Templates(directory=pkg_res("templates"))


@app.post(c.TUSD_HOOK_ROUTE)
async def tusd_hook(body: TusdEvent, hook_name: TusdHookName = Header(...)):
    log.debug(hook_name)
    log.debug(body)
    return "TODO"


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    session: Optional[Session] = Depends(auth.maybe_session),
):
    tmpl_vars = {
        "request": request,
        "orcid_enabled": conf().orcid.enabled,
        "signed_in": session is not None,
        # "orcid_userauth_url": auth.userauth_url(),
        "user_name": session.user_name if session else "guest",
    }
    return templates.TemplateResponse("index.html", tmpl_vars)


@app.get("/new")
def new():
    """Creates a new dataset directory, redirects to its upload/annotation page."""

    return RedirectResponse(url=f"/edit/{ util.fresh_dataset() }")


@app.get(
    "/edit/{dataset}",
    response_class=HTMLResponse,
    dependencies=[Depends(util.valid_staging_dataset)],
)
async def edit(
    request: Request,
    dataset: str,
    session: Optional[Session] = Depends(auth.get_session),
):

    tmpl_vars = {
        "request": request,
        "tusd_endpoint": conf().metador.tusd_endpoint,
        "dataset": dataset,
        "signed_in": session is not None,
        # "expire_time": state.dataset_expires_by[UUID(dataset)].strftime(
        #     "%Y-%m-%d %H:%M:%S"
        # ),
    }
    return templates.TemplateResponse("edit.html", tmpl_vars)


@app.get("/test")
def test_func():
    log.debug("debug log")
    log.info("info log")
    log.warning("warning log")
    log.error("error log")
    return "ok"
