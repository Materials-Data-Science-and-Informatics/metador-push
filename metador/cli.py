"""
Utility CLI for the application.
"""

from pathlib import Path
from typing import Optional

import typer
import uvicorn  # type: ignore

from . import __pkg_path__, __version__
from . import config as c
from .log import patch_uvicorn_log_format
from .orcid.auth import orcid_redir
from .upload import TUSD_HOOK_ROUTE

app = typer.Typer()


@app.command()
def version() -> None:
    """Print current version."""

    print(__version__)


@app.command()
def default_conf() -> None:
    """Output a default metador.toml file.
    It contains  all available configuration options."""

    print(open(c.DEF_CONFIG_FILE, "r").read(), end="")


@app.command()
def tusd_hook_url(config: Optional[Path] = None) -> None:
    """
    Output the route to construct a hook path for tusd.
    """

    c.init_conf(config)  # correct result depends on configured metador.site
    print(c.conf().metador.site + TUSD_HOOK_ROUTE)


@app.command()
def orcid_redir_url(config: Optional[Path] = None) -> None:
    """
    URL that should be registered as the ORCID API redirect.
    """

    c.init_conf(config)  # correct result depends on configured metador.site
    print(orcid_redir(c.conf().metador.site))


@app.command()
def run(config: Optional[Path] = None) -> None:  # pragma: no cover
    """Serve application using uvicorn."""

    c.init_conf(config)

    # add date and time to uvicorn log
    patch_uvicorn_log_format()
    # run server. if reload is active, it watches for changes in the Python code.
    # The templates and static files can be changed on runtime anyway.
    # If you want to change a conf and reload, just "touch" a Python file forcing reload
    uvicorn.run(
        "metador.server:app",
        host=c.conf().uvicorn.host,
        port=c.conf().uvicorn.port,
        reload=c.conf().uvicorn.reload,
        reload_dirs=[__pkg_path__],
    )


if __name__ == "__main__":  # pragma: no cover
    app()
