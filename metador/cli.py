"""
Utility CLI for Metador.
"""

from typing import Optional
import os

import uvicorn  # type: ignore
import typer

import metador
from metador.orcid import get_orcid_redir

from . import config as c
from .util import prepare_dirs

app = typer.Typer()


@app.command()
def version() -> None:
    """Print current version."""

    print(metador.__version__)


@app.command()
def default_conf() -> None:
    """Output a default metador.toml file.
    It contains  all available configuration options."""

    print(open(c.DEF_CONFIG_FILE, "r").read(), end="")


@app.command()
def tusd_hook_url(config: Optional[str] = None) -> None:
    """
    Output the route to construct a hook path for tusd.
    """

    c.init_conf(config)
    print(c.conf().metador.site + c.TUSD_HOOK_ROUTE)


@app.command()
def orcid_redir_url(config: Optional[str] = None) -> None:
    """
    URL that should be registered as the ORCID API redirect.
    """

    c.init_conf(config)
    print(get_orcid_redir())


@app.command()
def run(config: Optional[str] = None) -> None:
    """Serve application using uvicorn."""

    c.init_conf(config)
    prepare_dirs()

    # run server
    uvicorn.run(
        "metador.server:app",
        host=c.conf().uvicorn.host,
        port=c.conf().uvicorn.port,
        reload=c.conf().uvicorn.reload,
        reload_dirs=[os.path.join(metador.__basepath__, "metador")],
    )


if __name__ == "__main__":
    app()
