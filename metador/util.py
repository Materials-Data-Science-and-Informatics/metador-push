"""General utility functions."""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set, Union
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import urlopen

from jsonschema import Draft7Validator, RefResolver
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


def load_json(filename: Union[Path, str]) -> UnsafeJSON:
    """Load JSON from a file or URL. On failure, terminate program (fatal error)."""
    if isinstance(filename, Path):
        filename = str(filename)
    parsed = urlparse(filename)

    if parsed.scheme == "":  # looks like a file
        try:
            with open(filename, "r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            critical_exit(f"Cannot load {filename}: {str(e)}")

    if parsed.scheme.find("http") == 0:  # looks like a HTTP(S) URL
        try:
            with urlopen(filename) as file:
                return json.load(file)
        except HTTPError as e:
            critical_exit(f"Cannot load {filename}: {str(e)}")

    # don't know what to do with this
    critical_exit(f"Cannot load {filename}: Unknown protocol '{parsed.scheme}'")
    return None  # make mypy happy


def validate_json(
    instance: UnsafeJSON,
    schema: UnsafeJSON,
    refSchemas: Optional[Dict[str, UnsafeJSON]] = None,
) -> Optional[str]:
    """Validate JSON against JSON Schema, on success return None, otherwise the error."""
    if refSchemas is None:
        refSchemas = {}
    try:
        resolver = RefResolver.from_schema(schema, store=refSchemas)
        validator = Draft7Validator(schema, resolver=resolver)
        validator.validate(instance)
        return None
    except ValidationError as e:
        return str(e)


def referenced_schemas(schema: UnsafeJSON) -> Set[str]:
    """Return set of referenced schemas within given schema."""
    if isinstance(schema, list):
        ret = {ref for s in schema for ref in referenced_schemas(s)}
        return ret
    elif isinstance(schema, dict):
        ret = {ref for v in schema.values() for ref in referenced_schemas(v)}
        if "$ref" in schema and isinstance(schema["$ref"], str):
            path = schema["$ref"].split("#")[0]  # without the fragment
            if len(path) > 0:  # not a local ref like #/...
                ret.add(path)
        return ret
    else:  # primitive type -> no ref
        return set()


def critical_exit(msg: str) -> None:
    """
    Show critical error message and terminate application.

    Only to be used for misconfiguration errors on startup.
    """
    log.critical(msg)
    sys.exit(1)
