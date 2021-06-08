"""
Globally accessible location for the configuration.
"""

from typing import Optional, Any, List
import os
import sys

import toml

import metador

# default config
def_config = toml.load(os.path.join(metador.__basepath__, "metador.def.toml"))

# user config (init as default, overwritten by passed config file)
config = def_config


def read_user_config(conf: str) -> None:
    """Tries to parse the given config file and attach it to the global scope."""

    global config

    try:
        config = toml.load(conf)
    except FileNotFoundError:
        print(f"Configuration file {conf} does not exist or cannot be opened!")
        sys.exit(1)
    except toml.TomlDecodeError as err:
        print(f"Error while parsing TOML config file: {str(err)}")
        sys.exit(1)


def _get_nested(conf, keys: List[str]) -> Optional[Any]:
    """Helper function. Takes a dict-like object and tries to access the value
    located behind the given sequence of keys. Returns None on failure."""

    try:
        cur = conf
        for key in keys:
            cur = cur[key]
        return cur
    except KeyError:
        return None


def get(*keys: str) -> Optional[Any]:
    """Try to get config value from user config. If missing, return default."""

    return _get_nested(config, list(keys)) or _get_nested(def_config, list(keys))
