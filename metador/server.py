"""
Main file for the Metador backend.
"""

import uuid

from fastapi import FastAPI, Request, Header
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from metador.hookmodel import TusdEvent, TusdHookName
import metador.orcid as orcid
from metador.config import conf
from metador import pkg_res

app = FastAPI()

# serve static files
app.mount("/static", StaticFiles(directory=pkg_res("static")), name="static")


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")


# location of templates
templates = Jinja2Templates(directory=pkg_res("templates"))


@app.post(conf.metador.tusd_endpoint)
async def tusd_hook(body: TusdEvent, hook_name: TusdHookName = Header(...)):
    print(hook_name, body)
    return "TODO"


@app.get(conf.metador.orcid_redir_route)
async def orcid_auth(code: str):
    return orcid.redeem_code(code)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    tmpl_vars = {
        "request": request,
        "orcid_userauth_url": orcid.userauth_url(),
    }
    return templates.TemplateResponse("index.html", tmpl_vars)


def fresh_dataset() -> str:
    """
    Generate a new UUID not currently used for an existing dataset.
    Create a directory for it, return the UUID.
    """
    # TODO: check staging and completed directory
    fresh_uuid = str(uuid.uuid4())
    return fresh_uuid


@app.get("/new")
def new():  # NOTE: not async, the "fresh_dataset" is critical section (free uuid check)
    """Creates a new dataset directory, redirects to its upload/annotation page."""
    return RedirectResponse(url=f"/dataset/{fresh_dataset()}")


@app.get("/upload/{dataset}", response_class=HTMLResponse)
async def read_item(dataset: str, request: Request):
    tmpl_vars = {
        "request": request,
        "tusd_endpoint": conf.metador.tusd_endpoint,
        "dataset": dataset,
    }
    return templates.TemplateResponse("dataset.html", tmpl_vars)
