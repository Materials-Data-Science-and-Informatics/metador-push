"""General utility functions."""

import json
import sys
from pathlib import Path
from typing import Any, List, Mapping, Optional, Union

import jsonschema
from jsonschema.exceptions import ValidationError
from pydantic import BaseModel

from .log import log

JSON_v = Union[None, bool, int, float, str]
"""JSON primitive values."""

UnsafeJSON = Union[JSON_v, List[JSON_v], Mapping[str, Any]]
"""Superficial JSON type (not recursive!) to have at least some annotations."""

#: recursive type alias for JSON (the one we'd like to use, but makes problems)
# JSON = Union[None, bool, int, float, str, List["JSON"], Mapping[str, "JSON"]]


def save_json(obj: BaseModel, filepath: Path):
    """Store a pydantic model serialized to JSON into a file."""
    with open(filepath, "w") as file:
        file.write(obj.json())
        file.flush()


def load_json(filename: Path) -> UnsafeJSON:
    """Load JSON from a file."""
    with open(filename, "r") as file:
        return json.load(file)


def validate_json(instance: UnsafeJSON, schema: UnsafeJSON) -> Optional[str]:
    """Validate JSON against JSON Schema, on success return None, otherwise the error."""
    try:
        jsonschema.validate(instance, schema)
        return None
    except ValidationError as e:
        return e.message


def critical_exit(msg: str) -> None:
    """
    Show critical error message and terminate application.

    Only to be used for misconfiguration errors on startup.
    """
    log.critical(msg)
    sys.exit(1)
