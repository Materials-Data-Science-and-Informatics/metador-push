"""
Metador profile management.
"""

from typing import Union, List, Dict, Final, Optional, NamedTuple, Mapping, Any
from pathlib import Path
import re
import json

from json.decoder import JSONDecodeError
from pydantic import BaseModel

from . import pkg_res
from .log import log
from .config import conf
from .util import critical_exit, UnsafeJSON, validate_json

#: file suffix for json schemas
SCHEMA_SUF: Final[str] = ".schema.json"

#: file suffix for dataset profiles
PROFILE_SUF: Final[str] = ".profile.json"

#: JSON Schema of JSON Schema to check schemas (we use Draft 7 like jsonschema)
JSONSCHEMA_SCHEMA = json.load(open(pkg_res("schemas/draft-07" + SCHEMA_SUF), "r"))

#: JSON Schema the profiles are checked against
PROFILE_SCHEMA = json.load(open(pkg_res("schemas/metador_profile" + SCHEMA_SUF), "r"))

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
        schemaref = entry["schema"]
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


class PatternSchema(NamedTuple):
    """
    A pairing representing that the schema is to be applied,
    if the pattern matches the whole file path.
    """

    pattern: str
    jsonSchema: UnsafeJSON


class Profile(BaseModel):
    """
    Class holding a profile representation from a loaded *.profile.json file.

    It also includes references to all relevant JSON Schemas.
    """

    #: Name is extracted from filename (i.e. NAME.profile.json)
    name: str

    title: str

    schemas: Dict[str, UnsafeJSON] = {}

    patterns: List[PatternSchema] = []
    rootSchema: UnsafeJSON = None
    fallbackSchema: UnsafeJSON = None

    @classmethod
    def assemble(cls, filename: str):
        """
        Given a profile file, construct a self-contained profile from the loaded
        JSON profiles and schemas.
        """

        profile: Mapping[str, Any] = get_profile_json(filename)

        name = re.sub(PROFILE_SUF + "$", "", str(filename))

        title = profile["title"]
        rootSchema = schema_filename(profile["rootSchema"])
        fallbackSchema = schema_filename(profile["fallbackSchema"])

        schemas = {}
        patterns = []
        for pat in profile["patterns"]:
            # add schema if not yet added
            schemaref = schema_filename(pat["schema"])
            schemaval = schema_content(schemaref)
            schemas[schemaref] = schemaval
            # add regex entry
            patterns.append((pat["pattern"], schemaref))

        return cls(
            name=name,
            title=title,
            rootSchema=rootSchema,
            fallbackSchema=fallbackSchema,
            schemas=schemas,
            patterns=patterns,
        )

    def get_schema_for(self, filepath: Optional[str]) -> UnsafeJSON:
        """
        Given a filepath, return first schema where pattern completely matches,
        or otherwise the fallback schema.

        If no path given, returns the root schema.
        """

        if filepath is None:
            return self.rootSchema
        for pat in self.patterns:
            pmatch = re.match(pat.pattern, filepath)
            if pmatch and pmatch.group(0) == filepath:
                return pat.jsonSchema
        return self.fallbackSchema


#: global storage of assembled profiles, ready to be copied into datasets
_profiles: Dict[str, Profile] = {}


def get_profiles() -> List[str]:
    """Return a list a available profiles (i.e., after they have been loaded)."""

    return list(sorted(_profiles.keys()))


def get_profile(name: str) -> Profile:
    """Return a profile given its name."""

    return _profiles[name]


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
