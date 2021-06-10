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
    # also actually be the same
    assert tomlconf == c.conf().dict()
