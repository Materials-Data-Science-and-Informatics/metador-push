"""
Main file for the Metador backend.
"""

from fastapi import FastAPI, Request, Header, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from metador.hookmodel import TusdEvent, TusdHookName
import metador.orcid as orcid
import metador.util as util
from . import config as c
from .config import conf, allowed_orcids
from . import pkg_res

app = FastAPI()

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
    # print(hook_name, body)
    return "TODO"


@app.get(c.ORCID_REDIR_ROUTE)
def orcid_auth(code: str, request: Request):
    # this should give us a valid token, that we revoke immediately (we don't need it)
    orcidbearer = orcid.redeem_code(code)
    orcid.revoke_token(orcidbearer)
    if conf().orcid.allowlist_file != "" and orcidbearer.orcid not in allowed_orcids():
        tmpl_vars = {"request": request, "orcid": orcidbearer.orcid}
        return templates.TemplateResponse(
            "not-allowed.html", tmpl_vars, status_code=status.HTTP_403_FORBIDDEN
        )
    # TODO: generate session id
    # print(orcidbearer)
    return RedirectResponse(url="/")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    tmpl_vars = {
        "request": request,
        "maybe_hidden": util.hidden_if(not conf().orcid.enabled),
        "orcid_userauth_url": orcid.userauth_url(),
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
async def edit(dataset: str, request: Request):
    tmpl_vars = {
        "request": request,
        "tusd_endpoint": conf().metador.tusd_endpoint,
        "dataset": dataset,
    }
    return templates.TemplateResponse("edit.html", tmpl_vars)
