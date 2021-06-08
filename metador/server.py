"""
Main file for the Metador backend.
"""

from typing import Final

from fastapi import FastAPI, Request, Header
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from metador.hookmodel import TusdEvent, TusdHookName
import metador.orcid as orcid
import metador.config as config
from metador import pkg_res

# configurable routes related to outside service interaction
TUSD_HOOK_ROUTE: Final[str] = str(config.get("metador", "tusd-hook-route"))
ORCID_AUTH_ROUTE: Final[str] = str(config.get("metador", "orcid-auth-route"))

app = FastAPI()

# serve static files
app.mount("/static", StaticFiles(directory=pkg_res("static")), name="static")


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")


# location of templates
templates = Jinja2Templates(directory=pkg_res("templates"))


@app.post(TUSD_HOOK_ROUTE)
async def tusd_hook(body: TusdEvent, hook_name: TusdHookName = Header(...)):
    print(hook_name, body)
    return "TODO"


@app.get(ORCID_AUTH_ROUTE)
async def orcid_auth(code: str):
    return orcid.redeem_code(code)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    tmpl_vars = {
        "request": request,
        "orcid_userauth_url": orcid.userauth_url(),
    }
    return templates.TemplateResponse("index.html", tmpl_vars)


@app.get("/upload", response_class=HTMLResponse)
async def read_item(request: Request):
    tmpl_vars = {"request": request, "tusd_endpoint": config.get("tusd", "endpoint")}
    return templates.TemplateResponse("upload.html", tmpl_vars)
