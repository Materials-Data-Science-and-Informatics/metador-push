from typer.testing import CliRunner
from metador.cli import app
import metador

runner = CliRunner()


def test_helpers():
    url = runner.invoke(app, ["version"]).stdout.strip()
    assert url == metador.__version__
    url = runner.invoke(app, ["tusd-hook-url"]).stdout.strip()
    assert url == "http://localhost:8000/tusd-events"
    url = runner.invoke(app, ["orcid-redir-url"]).stdout.strip()
    assert url == "http://localhost:8000/orcid-auth"

    file = open("metador.def.toml", "r").read()
    output = runner.invoke(app, "default-conf").stdout
    assert output == file
