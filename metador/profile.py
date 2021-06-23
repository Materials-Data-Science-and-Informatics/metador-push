"""
Metador profile management.
"""

import json
import re
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, Final, List, Mapping, Optional, Type, TypeVar, Union

from pydantic import BaseModel

from . import pkg_res
from .config import conf
from .log import log
from .util import UnsafeJSON, critical_exit, load_json, validate_json

#: file suffix for json schemas
SCHEMA_SUF: Final[str] = ".schema.json"

#: file suffix for dataset profiles
PROFILE_SUF: Final[str] = ".profile.json"

#: JSON Schema of JSON Schema to check schemas (we use Draft 7 like jsonschema)
JSONSCHEMA_SCHEMA = load_json(pkg_res("schemas/draft-07" + SCHEMA_SUF))

#: JSON Schema the profiles are checked against
PROFILE_SCHEMA = load_json(pkg_res("schemas/metador_profile" + SCHEMA_SUF))

# check out profile directory and profile filenames
PROFILE_DIR: Final[Path] = conf().metador.profile_dir


#: Schema filename -> schema content. Access via get_schema
_schemas_json: Dict[str, UnsafeJSON] = {}


def get_schema_json(filename: str, force_reload: Optional[bool] = False) -> UnsafeJSON:
    """
    If a schema with that name is not loaded yet, load, validate and cache.
    (Set force_reload=True to force a reload from file.)

    Return schema on success.
    """

    global _schemas_json

    if not force_reload and filename in _schemas_json:
        return _schemas_json[filename]

    if not (PROFILE_DIR / filename).is_file():
        critical_exit(f"Could not open schema file '{filename}'!")

    schema = None
    try:
        schema = json.load(open(PROFILE_DIR / filename, "r"))
    except JSONDecodeError:
        critical_exit("Cannot parse schema file '{filename}'!")

    if validate_json(schema, JSONSCHEMA_SCHEMA) is not None:
        critical_exit(f"{filename} is not a valid JSON Schema!")

    _schemas_json[filename] = schema  # cache for next access
    return schema


#: Profile name (without ext) -> profile content
_profiles_json: Dict[str, Mapping[str, UnsafeJSON]] = {}


def get_profile_json(
    filename: str, force_reload: Optional[bool] = False
) -> Mapping[str, UnsafeJSON]:
    """
    Given the filename of a profile, load, validate cache and return it if not loaded yet.

    Also loads, validaties and caches referenced JSON Schemas.
    If loaded (and not forcing reload), returns cached version.
    """

    global _profiles_json

    if not force_reload and filename in _profiles_json:
        return _profiles_json[filename]

    filepath = PROFILE_DIR / filename
    if not filepath.is_file():
        critical_exit(f"So such profile: {filepath}")

    content = json.load(open(filepath, "r"))

    # check profile itself
    errmsg = validate_json(content, PROFILE_SCHEMA)
    if errmsg is not None:
        critical_exit(f"Invalid profile {filename}: {errmsg}")

    # Extract, load and check schemas referenced in profiles
    for entry in content["patterns"]:
        schemaref = entry["useSchema"]
        if type(schemaref) == str:
            get_schema_json(schemaref)

    _profiles_json[filename] = content
    return content


#: filename to substitute for "true" schema
TRIV_TRUE: Final[str] = "__TRUE__"

#: filename to substitute for "false" schema
TRIV_FALSE: Final[str] = "__FALSE__"


def schema_filename(val: Union[bool, str]) -> str:
    """Helper to treat trivial (bool) and non-trivial (reference str) schema uniformly."""

    if isinstance(val, str):
        return val
    return TRIV_TRUE if val else TRIV_FALSE


def schema_content(filename: str) -> UnsafeJSON:
    """
    Return the schema referenced by provided filename.

    Also handles the special filenames for the trivial true/false schema,
    for consistent treatment.
    """

    if filename == TRIV_TRUE:
        return True
    elif filename == TRIV_FALSE:
        return False
    else:
        return get_schema_json(filename)


class PatternSchema(BaseModel):
    """
    A pairing representing that the schema is to be applied,
    if the pattern matches the whole file path.
    """

    #: Regex pattern (must match full filename)
    pattern: str

    #: Schema (if not URL, resolves first to embedded schemas, then to same dir files)
    useSchema: str


T = TypeVar("T")


class Profile(BaseModel):
    """
    Class holding a profile representation from a loaded *.profile.json file.

    It also includes references to all relevant JSON Schemas.
    """

    #: Name is extracted from filename (i.e. NAME.profile.json)
    name: str

    #: Human-readable title of dataset profile
    title: str

    #: Human-readable description of dataset profile
    description: Optional[str] = ""

    #: Assembled collection of included schemas
    schemas: Dict[str, UnsafeJSON] = {}

    #: List of regex -> schema mappings (name of schema is resolved to corresp. schema)
    patterns: List[PatternSchema] = []

    rootSchema: str
    fallbackSchema: str

    @classmethod
    def assemble(cls: Type[T], filename: str) -> T:
        """
        Given a profile file, construct a self-contained profile from the loaded
        JSON profiles and schemas (i.e. load and piece together).
        """

        profile: Mapping[str, Any] = get_profile_json(filename)

        name: str = re.sub(PROFILE_SUF + "$", "", str(filename))

        title: str = profile["title"] if profile["title"] is not None else name

        description: str = ""
        if "description" in profile:
            description = profile["description"]

        rootSchema: str = schema_filename(profile["rootSchema"])
        fallbackSchema: str = schema_filename(profile["fallbackSchema"])

        schemas: Dict[str, UnsafeJSON] = {TRIV_TRUE: True, TRIV_FALSE: False}
        patterns = []
        for pat in profile["patterns"]:
            # add schema if not yet added
            schemaref: str = schema_filename(pat["useSchema"])
            schemaval: UnsafeJSON = schema_content(schemaref)
            schemas[schemaref] = schemaval
            # add regex entry
            patterns.append(PatternSchema(pattern=pat["pattern"], useSchema=schemaref))

        return cls(
            name=name,
            title=title,
            description=description,
            rootSchema=rootSchema,
            fallbackSchema=fallbackSchema,
            schemas=schemas,
            patterns=patterns,
        )  # type: ignore

    def get_schema_for(self, filepath: Optional[str]) -> UnsafeJSON:
        """
        Given a filepath, return first schema where pattern completely matches,
        or otherwise the fallback schema.

        If no path given, returns the root schema.
        """

        if filepath is None:
            return self.schemas[self.rootSchema]
        for pat in self.patterns:
            pmatch = re.match(pat.pattern, filepath)
            if pmatch and pmatch.group(0) == filepath:
                return self.schemas[pat.useSchema]
        return self.schemas[self.fallbackSchema]


#: global storage of assembled profiles, ready to be copied into datasets
_profiles: Dict[str, Profile] = {}


def get_profiles() -> List[str]:
    """Return a list a available profiles (i.e., after they have been loaded)."""

    return list(sorted(_profiles.keys()))


def get_profile(name: str) -> Optional[Profile]:
    """Return a profile given its name."""

    if name in _profiles:
        return _profiles[name]
    return None


def load_profiles() -> None:
    """
    Load and validate raw JSON profiles from the configured directory.

    Also loads and validates the referenced JSON Schemas.
    """

    if not PROFILE_DIR.is_dir():
        critical_exit(f"Profile directory {PROFILE_DIR} does not exist!")

    log.info(f"Loading profiles (*{PROFILE_SUF}) from '{PROFILE_DIR}'")

    pr_filenames = list(map(lambda x: x.name, PROFILE_DIR.iterdir()))
    pr_filenames = list(filter(lambda x: str(x).endswith(PROFILE_SUF), pr_filenames))
    if len(pr_filenames) == 0:
        critical_exit(f"No profiles (*{PROFILE_SUF}) found in {PROFILE_DIR}!")

    for pr_filename in pr_filenames:
        profile = Profile.assemble(pr_filename)
        _profiles[profile.name] = profile


load_profiles()

# TODO: What about non-self-contained JSON schemas? resolve refs and make self-contained!
# - should resolve local files and eventually grab schemas from outside/metastore
# - profiles could also be loaded from metastore in addition to local ones
# - in any case, they should be pre-processed to be independent from external info
#   because we send it to the client browser that cannot just load arbitrary data.
