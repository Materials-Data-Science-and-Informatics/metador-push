"""
Main file for the Metador backend.
"""

from typing import Final

from fastapi import FastAPI, Request, Header
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from metador.hookmodel import TusdEvent, TusdHookName
import metador.config as config
from metador import pkg_res


app = FastAPI()

# serve static files
app.mount("/static", StaticFiles(directory=pkg_res("static")), name="static")


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")


# location of templates
templates = Jinja2Templates(directory=pkg_res("templates"))

# save as string constant, as it will be exposed from cli
TUSD_HOOK_ROUTE: Final[str] = "/tusd-events"


@app.post(TUSD_HOOK_ROUTE)
async def tusd_hook(body: TusdEvent, hook_name: TusdHookName = Header(...)):
    print(hook_name, body)
    return "TODO"


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    tmpl_vars = {"request": request, "tusd_endpoint": config.get("tusd", "endpoint")}
    return templates.TemplateResponse("upload.html", tmpl_vars)
