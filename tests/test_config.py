"""Tests for application configuration."""

from pathlib import Path

import pytest
import toml

import metador_push
import metador_push.config as c


def test_global_def_conf(testutils, test_config):
    """Test that the unmodified global config instance is found in the conf variable."""
    save_conf = test_config

    testutils.reset_conf()
    assert c.Conf().dict() == c.conf().dict()
    c._conf = save_conf


def test_read_user_config_failures(tmp_path):
    """Try reading invalid configurations."""
    with pytest.raises(SystemExit):
        c.read_user_config(Path("non existing"))

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


def test_toml_pydantic_consistent(testutils, test_config):
    """
    Verify that the defaults in the example config file.

    They must be exactly the same as in the actual internally used Pydantic model.
    (Ideally the defaults would be templated into the TOML file, but
    this is not high on the priority list.)
    """
    save_conf = test_config
    testutils.reset_conf()

    # this should raise no exceptions
    tomlconf = toml.load(metador_push.pkg_res("metador-push.def.toml"))

    # loading toml defaults onto the builtin defaults should make no difference
    # as we have Extra.forbid in the pydantic model,
    # the other direction should be ok too (no unknown fields are there)
    loadedConf = c.Conf().parse_obj(tomlconf)
    assert loadedConf == c.conf()

    c._conf = save_conf
