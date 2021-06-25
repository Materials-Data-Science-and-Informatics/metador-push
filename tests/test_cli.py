from typer.testing import CliRunner

import metador
import metador.config as c
from metador.cli import app

runner = CliRunner()


def test_helpers():
    """Check the trivial stuff. Not much to check for the CLI."""

    def_conf = ["--config", str(c.DEF_CONFIG_FILE)]

    res = runner.invoke(app, ["version"]).stdout.strip()
    assert res == metador.__version__

    res = runner.invoke(app, ["tusd-hook-url"] + def_conf).stdout.strip()
    assert "http://localhost:8000/tusd-events" in res

    res = runner.invoke(app, ["orcid-redir-url"] + def_conf).stdout.strip()
    assert "http://localhost:8000/oauth/orcid" in res

    file = open(c.DEF_CONFIG_FILE, "r").read()
    output = runner.invoke(app, "default-conf").stdout
    assert output == file
