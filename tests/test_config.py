import os

import pytest
import toml

import metador
import metador.config as c


def test_global_def_conf():
    """Test that the unmodified global config instance is found in the conf variable."""

    assert c.Conf().dict() == c.conf().dict()

    del c._conf  # unload default config again


def test_read_user_config_failures(tmp_path):
    with pytest.raises(SystemExit):
        c.read_user_config("non existing")

    broken = tmp_path / "broken.toml"
    with open(broken, "w") as file:
        file.write("broken =")
        file.flush()

    with pytest.raises(SystemExit):
        c.read_user_config(broken)

    invalid = tmp_path / "invalid.toml"
    with open(invalid, "w") as file:
        file.write("unknown_key = 123")
        file.flush()

    with pytest.raises(SystemExit):
        c.read_user_config(invalid)


def test_toml_pydantic_consistent():
    """
    Verify that the defaults in the example config file are exactly the same
    as in the actual internally used Pydantic model.
    (Ideally the defaults would be templated into the TOML file, but
    this is not high on the priority list.)
    """

    # prevent loading from env var (which dominates if set)
    if c.CONFFILE_ENVVAR in os.environ:
        del os.environ[c.CONFFILE_ENVVAR]

    c.init_conf()  # init defaults (without path or envvar will load builtin values)

    # this should raise no exceptions
    tomlconf = toml.load(metador.pkg_res("metador.def.toml"))

    # loading toml defaults onto the builtin defaults should make no difference
    # as we have Extra.forbid in the pydantic model,
    # the other direction should be ok too (no unknown fields are there)
    loadedConf = c.Conf().parse_obj(tomlconf)
    assert loadedConf == c.conf()

    del c._conf  # unload default config again
