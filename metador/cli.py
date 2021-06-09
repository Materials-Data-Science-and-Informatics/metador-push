"""
Utility CLI for Metador.
"""

from typing import Optional
import os

import uvicorn  # type: ignore
import typer

import metador
from metador.orcid import get_orcid_redir

import metador.config as c
from metador.config import conf, read_user_config

app = typer.Typer()


@app.command()
def version() -> None:
    """Print current version."""

    print(metador.__version__)


@app.command()
def default_conf() -> None:
    """Output a default metador.toml file.
    It contains  all available configuration options."""

    print(open("metador.def.toml", "r").read(), end="")


@app.command()
def tusd_hook_url() -> None:
    """
    Output the route to construct a hook path for tusd.
    """

    print(conf.metador.site + conf.metador.tusd_hook_route)


@app.command()
def orcid_redir_url() -> None:
    """
    URL that should be registered as the ORCID API redirect.
    """

    print(get_orcid_redir())


@app.command()
def run(config: Optional[str] = None) -> None:
    """Serve application using uvicorn."""

    # read config
    if config:
        read_user_config(config)
    else:
        print("WARNING: No configuration file passed, using defaults.")

    # prepare directories for datasets
    datadir = conf.metador.data_dir
    staging = os.path.join(datadir, c.STAGING_DIR)
    complete = os.path.join(datadir, c.COMPLETE_DIR)
    if not os.path.isdir(datadir):
        os.mkdir(datadir)
    if not os.path.isdir(staging):
        os.mkdir(staging)
    if not os.path.isdir(complete):
        os.mkdir(complete)

    # run server
    uvicorn.run("metador.server:app", host=conf.uvicorn.host, port=conf.uvicorn.port)


if __name__ == "__main__":
    app()
