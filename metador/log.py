from typing import Final, Optional

import re
import sys
import logging
from logging import Formatter, Logger
from pathlib import Path

from colorlog import ColoredFormatter

from uvicorn.config import LOGGING_CONFIG


# see https://docs.python.org/3/library/logging.html#logrecord-attributes

FMT_DATE: Final[str] = "%Y-%m-%d %H:%M:%S"
FMT_TIME: Final[str] = "%(asctime)s.%(msecs)03d"
FMT_LOC: Final[str] = " (%(filename)s:%(lineno)s)"

# we allow color commands in non-empty < .. >
META_FMT: Final[str] = (
    f"{FMT_TIME} <log_color>%(levelname)8s " f"<blue>{FMT_LOC}<reset>: %(message)s"
)

# substitute them depending on log target
LOG_FMT_CLR: Final[str] = re.sub(r"<(\w+)>", r"%(\g<1>)s", META_FMT)
LOG_FMT: Final[str] = re.sub(r"<\w+>", "", META_FMT)

FORMATTER_CLR: Final[Formatter] = ColoredFormatter(LOG_FMT_CLR, datefmt=FMT_DATE)
FORMATTER: Final[Formatter] = logging.Formatter(LOG_FMT, datefmt=FMT_DATE)

# our application-wide logger
log: Final[Logger] = logging.getLogger("metador")


def init_logger(
    level: str = logging.getLevelName(logging.INFO), logfile: Optional[Path] = None
):
    """Init logger for console and file output."""

    # more low-level log msgs logged by this are ignored
    log.setLevel(level)
    # reset (if already configured)
    log.handlers = []

    ch = logging.StreamHandler(sys.stderr)
    ch.setFormatter(FORMATTER_CLR)
    ch.setLevel(level)
    log.addHandler(ch)

    if logfile is not None:
        fh = logging.FileHandler(filename=str(logfile))
        fh.setFormatter(FORMATTER)
        fh.setLevel(level)
        log.addHandler(fh)


def patch_uvicorn_log_format() -> None:
    """Add date and time to uvicorn log."""

    LOGGING_CONFIG["formatters"]["access"]["fmt"] = (
        "%(asctime)s.%(msecs)03d %(levelprefix)s "
        '%(client_addr)s - "%(request_line)s" %(status_code)s'
    )
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = (
        "%(asctime)s.%(msecs)03d %(levelprefix)s " "%(message)s"
    )
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = FMT_DATE
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = FMT_DATE

    # NOTE: don't need the following, when we use colorlog for our own pretty log
    # add our own logger to the console output beside of uvicorn, with color!
    #
    # FIXME: the level here is ignored for some reason, it is basically "no filter"
    # LOGGING_CONFIG['loggers']['metador'] = {'handlers': ['default'], 'level': 'INFO'}
