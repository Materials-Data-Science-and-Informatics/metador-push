import os

import toml

import metador
import metador.config as c


def test_global_def_conf():
    """Test that the unmodified global config instance is found in the conf variable."""

    assert c.Conf().dict() == c.conf().dict()


def test_toml_pydantic_consistent():
    """
    Verify that the defaults in the example config file are exactly the same
    as in the actual internally used Pydantic model.
    (Ideally the defaults would be templated into the TOML file, but
    this is not high on the priority list.)
    """

    # this should raise no exceptions
    tomlconf = toml.load(os.path.join(metador.__basepath__, "metador.def.toml"))
    # loading toml defaults onto the builtin defaults should make no difference
    # as we have Extra.forbid in the pydantic model,
    # the other direction should be ok too (no unknown fields are there)
    loadedConf = c.Conf().parse_obj(tomlconf)
    assert loadedConf == c.conf()
