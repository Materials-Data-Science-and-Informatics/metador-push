"""
Globally accessible location for the configuration.
"""

from typing import Final
import sys

import toml
from pydantic import BaseModel, ValidationError

################################################################

# some constants not exposed to the user

STAGING_DIR: Final[str] = "staging"
COMPLETE_DIR: Final[str] = "complete"

################################################################

# config model (overridable by user)


class MetadorConf(BaseModel):
    """Configuration of the Metador server itself."""

    site: str = "http://localhost:8000"

    tusd_endpoint: str = "http://localhost:1080/files/"

    tusd_hook_route: str = "/tusd-events"
    orcid_redir_route: str = "/orcid-auth"

    data_dir: str = "metador_datasets"


class OrcidConf(BaseModel):
    """Configuration of ORCID authentication."""

    enabled: bool = False
    sandbox: bool = False

    client_id: str = ""
    client_secret: str = ""

    whitelist_file: str = ""


class UvicornConf(BaseModel):
    """
    The host and port used by uvicorn for binding.
    These are only respected if you launch your application using `metador-cli run`.
    """

    host: str = "0.0.0.0"
    port: int = 8000


class Conf(BaseModel):
    """The complete application configuration."""

    metador: MetadorConf = MetadorConf()
    orcid: OrcidConf = OrcidConf()
    uvicorn: UvicornConf = UvicornConf()


################################################################


# default config
conf = Conf()


def read_user_config(conffile: str) -> None:
    """
    Tries to parse the given config file and attach it to the global scope.
    Called when the server is started up.
    """

    global conf
    try:
        userconf = toml.load(conffile)
        conf = conf.parse_obj(userconf)  # override defaults from user config
    except FileNotFoundError:
        print(f"Configuration file {conffile} does not exist or cannot be opened!")
        sys.exit(1)
    except toml.TomlDecodeError as err:
        print(f"Error while parsing config file {conffile}: {str(err)}")
        sys.exit(1)
    except ValidationError as err:
        print(f"Error while parsing config file {conffile}: {str(err)}")
        sys.exit(1)
