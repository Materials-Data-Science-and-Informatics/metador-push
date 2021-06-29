"""
Globally accessible location for the configuration.
"""

import os
import sys
from enum import Enum
from pathlib import Path
from typing import Final, Optional

import toml
from pydantic import BaseModel, Extra, ValidationError

from . import __basepath__
from .log import init_logger, log
from .orcid import auth

################################################################

# some constants not exposed to the user

DEF_CONFIG_FILE: Final[Path] = __basepath__ / "metador.def.toml"
"""Default name of config file, used e.g. by CLI to provide the user a skeleton."""

CONFFILE_ENVVAR: Final[str] = "METADOR_CONF"
"""Environment variable name to pass or store config location (needed for restarts!)"""

################################################################
# Models for configuration that is available to user.
# For more info about the fields, see the default TOML file.


class LogLevel(str, Enum):
    """The default logging log levels, as an Enum for parsing."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ChecksumTool(str, Enum):
    """The supported checksum tools."""

    SHA256SUM = "sha256sum"
    SHA512SUM = "sha512sum"


class LogConf(BaseModel):
    """Configuration of the used logger."""

    class Config:
        extra = Extra.forbid

    level: LogLevel = LogLevel.INFO
    file: Optional[Path] = None


class MetadorConf(BaseModel):
    """Configuration of the Metador server itself."""

    class Config:
        extra = Extra.forbid

    site: str = "http://localhost:8000"

    tusd_endpoint: str = "http://localhost:1080/files/"

    incomplete_expire_after: int = 48

    # TODO: could use DirectoryPath, but then need some more fancy testing setup
    profile_dir: Path = Path("profiles")
    data_dir: Path = Path("metador_data")

    checksum_tool: ChecksumTool = ChecksumTool.SHA256SUM

    completion_hook: Optional[Path] = None

    log: LogConf = LogConf()


class UvicornConf(BaseModel):
    """
    The host and port used by uvicorn for binding.
    These are only respected if you launch your application using `metador-cli run`.
    """

    class Config:
        extra = Extra.forbid

    host: str = "0.0.0.0"
    port: int = 8000

    # auto-reload on file changes. good for development
    reload: bool = False


class Conf(BaseModel):
    """The complete application configuration."""

    class Config:
        extra = Extra.forbid

    orcid: auth.OrcidConf = auth.OrcidConf()
    metador: MetadorConf = MetadorConf()
    uvicorn: UvicornConf = UvicornConf()


_conf: Conf
"""
The actual config variable singleton. We hide it, because once imported
somewhere else, the call-site won't see a redefinition (that we need to do at runtime).
"""


################################################################


def read_user_config(conffile: Path) -> Conf:
    """
    Tries to parse the given config file and attach it to the global scope.
    Called when the server is started up.
    """

    global _conf
    try:
        userconf = toml.load(conffile)
        return Conf().parse_obj(userconf)  # override defaults from user config
    except FileNotFoundError:
        log.critical(
            f"Configuration file {conffile} does not exist or cannot be opened!"
        )
        sys.exit(1)
    except toml.TomlDecodeError as err:
        log.critical(f"Error while parsing config file {conffile}: {str(err)}")
        sys.exit(1)
    except ValidationError as err:
        log.critical(f"Error while parsing config file {conffile}: {str(err)}")
        sys.exit(1)


def init_conf(conffile: Optional[Path] = None) -> None:
    """
    Load config from passed filename, or else from environment variable,
    or else the built-in defaults.

    This must be called with an argument by the CLI entry point,
    to put the passed config filename "into the loop".
    """

    global _conf

    init_logger()  # bootstrap default logger (will be re-configured by user conf)

    # Trick: to preserve between auto-reloads,
    # store the provided config file into an environment variable!

    # If we get a filename passed, it always overrides the env var
    if conffile:
        os.environ[CONFFILE_ENVVAR] = str(conffile)

    # load the config from filename stored in env var
    if CONFFILE_ENVVAR in os.environ:
        log.info(f"(Re-)Loading configuration from {os.environ[CONFFILE_ENVVAR]}")
        _conf = read_user_config(Path(os.environ[CONFFILE_ENVVAR]))
    else:
        log.warning("No configuration file passed, using defaults.")
        _conf = Conf()


def conf() -> Conf:
    """
    Access the configuration object only through this object.
    It ensures that the user-provided configuration works correctly,
    even surviving auto-reloads of the application.
    """

    global _conf
    try:
        _conf

    # the config vanished because uvicorn restarted the app:
    except NameError:
        init_conf()  # reload configuration

    return _conf


def reset_conf() -> None:
    """Unload config (useful for testing)."""

    global _conf

    if CONFFILE_ENVVAR in os.environ:
        del os.environ[CONFFILE_ENVVAR]

    try:
        del _conf
    except NameError:
        pass
