"""
Globally accessible location for the configuration.
"""

from typing import Final, Optional, List
import sys
import os

import toml
from pydantic import BaseModel, ValidationError

import metador

################################################################

# some constants not exposed to the user

DEF_CONFIG_FILE: Final[str] = os.path.join(metador.__basepath__, "metador.def.toml")

CONFFILE_ENVVAR: Final[str] = "METADOR_CONF"

STAGING_DIR: Final[str] = "staging"
COMPLETE_DIR: Final[str] = "complete"

ORCID_REDIR_ROUTE: Final[str] = "/orcid-auth"
TUSD_HOOK_ROUTE: Final[str] = "/tusd-events"


def staging_dir() -> str:
    return os.path.join(conf().metador.data_dir, STAGING_DIR)


def complete_dir() -> str:
    return os.path.join(conf().metador.data_dir, COMPLETE_DIR)


################################################################
# config model (overridable by user)


class MetadorConf(BaseModel):
    """Configuration of the Metador server itself."""

    site: str = "http://localhost:8000"

    tusd_endpoint: str = "http://localhost:1080/files/"

    data_dir: str = "metador_datasets"
    incomplete_expire: int = 48

    logfile: str = "metador.log"


class OrcidConf(BaseModel):
    """Configuration of ORCID authentication."""

    enabled: bool = False
    sandbox: bool = False

    client_id: str = ""
    client_secret: str = ""

    allowlist_file: str = ""


class UvicornConf(BaseModel):
    """
    The host and port used by uvicorn for binding.
    These are only respected if you launch your application using `metador-cli run`.
    """

    host: str = "0.0.0.0"
    port: int = 8000

    # auto-reload on file changes. good for development
    reload: bool = False


class Conf(BaseModel):
    """The complete application configuration."""

    metador: MetadorConf = MetadorConf()
    orcid: OrcidConf = OrcidConf()
    uvicorn: UvicornConf = UvicornConf()


# The actual config variable. We hide it, because once imported
# somewhere else, the call-site won't see a redefinition (that we need to do at runtime).
# We expose the config using the methods below to have a kind of magic singleton.
_conf: Conf


################################################################


def read_user_config(conffile: str) -> Conf:
    """
    Tries to parse the given config file and attach it to the global scope.
    Called when the server is started up.
    """

    global _conf
    try:
        userconf = toml.load(conffile)
        return Conf().parse_obj(userconf)  # override defaults from user config
    except FileNotFoundError:
        print(
            f"Configuration file {conffile} does not exist or cannot be opened!",
            file=sys.stderr,
        )
        sys.exit(1)
    except toml.TomlDecodeError as err:
        print(
            f"Error while parsing config file {conffile}: {str(err)}", file=sys.stderr
        )
        sys.exit(1)
    except ValidationError as err:
        print(
            f"Error while parsing config file {conffile}: {str(err)}", file=sys.stderr
        )
        sys.exit(1)


def init_conf(conffile: Optional[str] = None) -> None:
    """
    Load config from passed filename, or else from environment variable,
    or else the built-in defaults.

    This must be called with an argument by the CLI entry point,
    to put the passed config filename "into the loop".
    """

    global _conf

    # Trick: to preserve between auto-reloads,
    # store the provided config file into an environment variable.

    # If we get a filename passed, it always overrides the env var
    if conffile:
        os.environ[CONFFILE_ENVVAR] = conffile

    # load the config from filename stored in env var
    if CONFFILE_ENVVAR in os.environ:
        print(
            f"(Re-)Loading configuration from {os.environ[CONFFILE_ENVVAR]}",
            file=sys.stderr,
        )
        _conf = read_user_config(os.environ[CONFFILE_ENVVAR])
    else:
        print("WARNING: No configuration file passed, using defaults.", file=sys.stderr)
        _conf = Conf()

    allowed_orcids(True)  # force to load the list from file


def conf() -> Conf:
    """
    Access the configuration object only through this object.
    It ensures that the user-provided configuration works correctly,
    even surviving auto-reloads of the application.
    """

    global _conf
    try:
        _conf
    except NameError:
        init_conf()

    return _conf


# in-memory cached list of allowed ORCIDs
_allowed_orcids: List[str] = []


def allowed_orcids(reload_from_file: bool = False) -> List[str]:
    """Return list of ORCIDs that should be allowed to sign in."""

    global _allowed_orcids

    # return cached by default
    if not reload_from_file:
        return _allowed_orcids

    # if reload requested and whitelist file provided, read it
    fname = conf().orcid.allowlist_file.strip()
    if fname != "":
        stripped = list(map(str.strip, open(fname, "r").readlines()))
        nonempty = list(filter(lambda x: x != "", stripped))
        noncommented = list(filter(lambda x: x[0] != "#", nonempty))
        _allowed_orcids = noncommented

    return _allowed_orcids
