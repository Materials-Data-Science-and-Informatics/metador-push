"""
Utility CLI for Metador.
"""

from typing import Optional

import uvicorn  # type: ignore
import typer

import metador
import metador.config as config

app = typer.Typer()


@app.command()
def version() -> None:
    """Print current version."""

    print(metador.__version__)


@app.command()
def default_conf() -> None:
    """Output a default metador.toml file with all available configuration options."""

    with open("metador.def.toml", "r") as fin:
        print(fin.read(), end="")


@app.command()
def tusd_hook_url() -> None:
    """
    Output the route to construct a http(s) hook path for tusd.
    A prefix http(s)://host:port must be added to form a full hook endpoint URL
    passed as -hooks-http argument when starting tusd.
    This depends on your setup.
    """

    print(
        str(config.get("metador", "site"))
        + str(config.get("metador", "tusd-hook-route"))
    )


@app.command()
def orcid_redir_url() -> None:
    """
    Assuming the configuration is as desired, returns the URL that should be
    registered as a redirect URL when applying for ORCID API credentials.
    """

    print(
        str(config.get("metador", "site"))
        + str(config.get("metador", "orcid-auth-route"))
    )


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
