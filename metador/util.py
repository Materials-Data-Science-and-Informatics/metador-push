from .log import log
import sys


def critical_exit(msg: str) -> None:
    log.critical(msg)
    sys.exit(1)
