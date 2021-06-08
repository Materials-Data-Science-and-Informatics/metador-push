"""
Utility CLI for Metador.
"""

from typing import Optional

import uvicorn  # type: ignore
import typer

import metador
from metador.server import TUSD_HOOK_ROUTE
import metador.config as config

app = typer.Typer()


@app.command()
def version() -> None:
    """Print current version."""

    print(metador.__version__)


@app.command()
def default_conf() -> None:
    """Output a default metador.toml file with all available configuration options."""

    with open("metador.toml", "r") as fin:
        print(fin.read(), end="")


@app.command()
def hook_route() -> None:
    """
    Output the route to construct a http(s) hook path for tusd.
    A prefix http(s)://host:port must be added to form a full hook endpoint URL
    passed as -hooks-http argument when starting tusd.
    This depends on your setup.
    """

    print(TUSD_HOOK_ROUTE)


@app.command()
def run(conf: Optional[str] = None) -> None:
    """Serve application using uvicorn."""

    if conf:
        config.read_user_config(conf)
    else:
        print("WARNING: No configuration file passed, using defaults.")

    host = config.get("uvicorn", "host")
    port = config.get("uvicorn", "port")
    uvicorn.run("metador.server:app", host=host, port=port)


if __name__ == "__main__":
    app()
