"""Utility CLI for the application."""

from pathlib import Path
from typing import Optional

import typer
import uvicorn  # type: ignore

from . import __pkg_path__, __version__
from . import config as c
from .dataset import Dataset
from .log import patch_uvicorn_log_format
from .orcid.auth import orcid_redir
from .upload import TUSD_HOOK_ROUTE, get_tusd_garbage
from .util import critical_exit

app = typer.Typer()


@app.command()
def version() -> None:
    """Print current version."""
    print(__version__)


@app.command()
def default_conf() -> None:
    """
    Output a default metador-push.toml file.

    It contains all available configuration options.
    """
    print(open(c.DEF_CONFIG_FILE, "r").read(), end="")


@app.command()
def tusd_hook_url(config: Optional[Path] = None) -> None:
    """Output the route to construct a hook path for tusd."""
    c.init_conf(config)  # correct result depends on configured metador-push.site
    print(c.conf().metador_push.site + TUSD_HOOK_ROUTE)


@app.command()
def orcid_redir_url(config: Optional[Path] = None) -> None:
    """URL that should be registered as the ORCID API redirect."""
    c.init_conf(config)  # correct result depends on configured metador-push.site
    print(orcid_redir(c.conf().metador_push.site))


@app.command()
def tusd_cleanup(tusd_data_dir: Path, config: Optional[Path] = None) -> None:
    """
    Clean up abandoned downloads stored in given directory used for tusd uploads.

    More precisely, remove data files that lack an .info file and vice versa, and
    also remove files where the .info does not contain a currently staging dataset id.
    """
    if not tusd_data_dir.is_dir():
        critical_exit("Passed path is not a directory!")

    c.init_conf(config)
    Dataset.load_datasets()

    dsets = set(map(str, Dataset.get_datasets()))
    garbage = get_tusd_garbage(list(tusd_data_dir.glob("*")), dsets)

    if len(garbage) > 0:
        print("Deleting detected tusd garbage files:")
    for useless in garbage:
        print("  " + str(useless))
        useless.unlink()


@app.command()
def run(config: Optional[Path] = None) -> None:  # pragma: no cover
    """Serve application using uvicorn."""
    c.init_conf(config)

    # add date and time to uvicorn log
    patch_uvicorn_log_format()
    # run server. if reload is active, it watches for changes in the Python code.
    # The templates and static files can be changed on runtime anyway.
    # If you want to change a conf and reload, just "touch" a Python file forcing reload
    uvicorn_args = {
        # for development
        "reload": c.conf().uvicorn.reload,
        "reload_dirs": [__pkg_path__],
        # for proper deployment via reverse proxy
        "proxy_headers": True,
        "forwarded_allow_ips": "*",
    }

    if c.conf().uvicorn.socket == "":
        uvicorn_args["host"] = c.conf().uvicorn.host
        uvicorn_args["port"] = c.conf().uvicorn.port
    else:  # for use behind reverse proxy
        uvicorn_args["uds"] = c.conf().uvicorn.socket

    uvicorn.run("metador_push.server:app", **uvicorn_args)


if __name__ == "__main__":  # pragma: no cover
    app()
