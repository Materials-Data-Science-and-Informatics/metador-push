from typer.testing import CliRunner
from metador.cli import app
import metador
import metador.config as c

runner = CliRunner()


def test_helpers():
    def_conf = ["--config", c.DEF_CONFIG_FILE]

    res = runner.invoke(app, ["version"]).stdout.strip()
    assert res == metador.__version__

    res = runner.invoke(app, ["tusd-hook-url"]).stdout.strip()
    assert "WARNING: No configuration" in res
    res = runner.invoke(app, ["orcid-redir-url"]).stdout.strip()
    assert "WARNING: No configuration" in res

    res = runner.invoke(app, ["tusd-hook-url"] + def_conf).stdout.strip()
    assert "http://localhost:8000/tusd-events" in res
    res = runner.invoke(app, ["orcid-redir-url"] + def_conf).stdout.strip()
    assert "http://localhost:8000/orcid-auth" in res

    file = open("metador.def.toml", "r").read()
    output = runner.invoke(app, "default-conf").stdout
    assert output == file
