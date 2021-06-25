"""
Metador profile management.
"""

import re
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, Final, List, Mapping, Optional, Type, TypeVar, Union

from pydantic import BaseModel

from . import pkg_res
from .log import log
from .util import UnsafeJSON, critical_exit, load_json, save_json, validate_json

#: file suffix for json schemas
SCHEMA_SUF: Final[str] = ".schema.json"

#: file suffix for dataset profiles
PROFILE_SUF: Final[str] = ".profile.json"

#: JSON Schema of JSON Schema to check schemas (we use Draft 7 like jsonschema)
JSONSCHEMA_SCHEMA = load_json(pkg_res("draft-07" + SCHEMA_SUF))

#: JSON Schema the profiles are checked against
PROFILE_SCHEMA = load_json(pkg_res("profile" + SCHEMA_SUF))

#: fake filename / schema ref to substitute for boolean "true" schema
TRIV_TRUE: Final[str] = "__TRUE__"

#: fake filename / schema ref to substitute for boolean "false" schema
TRIV_FALSE: Final[str] = "__FALSE__"

#: variable that is set by load_profiles (from config)
PROFILE_DIR: Path

#: In-memory cache: Schema filename -> schema content. Access via get_schema
_schemas_json: Dict[str, UnsafeJSON] = {}

#: In-memory cache: Profile name (without ext) -> profile content
_profiles_json: Dict[str, Mapping[str, UnsafeJSON]] = {}

#: In-memory cache: profiles assembled from files, ready to be copied into datasets
_profiles: Dict[str, "Profile"] = {}

T = TypeVar("T")


class PatternSchema(BaseModel):
    """
    A pairing representing that the schema is to be applied,
    if the pattern matches the whole file path.
    """

    #: Regex pattern (must match full filename)
    pattern: str

    #: Schema (if not URL, resolves first to embedded schemas, then to same dir files)
    useSchema: str


class Profile(BaseModel):
    """
    Class holding a profile representation from a loaded *.profile.json file.

    It also includes references to all relevant JSON Schemas.
    """

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

    @classmethod
    def get_schema_json(
        cls, filename: str, force_reload: Optional[bool] = False
    ) -> UnsafeJSON:
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
            schema = load_json(PROFILE_DIR / filename)
        except JSONDecodeError:
            critical_exit("Cannot parse schema file '{filename}'!")

        if validate_json(schema, JSONSCHEMA_SCHEMA) is not None:
            critical_exit(f"{filename} is not a valid JSON Schema!")

        _schemas_json[filename] = schema  # cache for next access
        return schema

    def save(self, filepath: Path) -> None:
        """Serialize the current state into a file."""

        save_json(self, filepath)

    @classmethod
    def get_profile_json(
        cls, filename: str, force_reload: Optional[bool] = False
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

        content: Any = load_json(filepath)

        # check profile itself
        errmsg = validate_json(content, PROFILE_SCHEMA)
        if errmsg is not None:
            critical_exit(f"Invalid profile {filename}: {errmsg}")

        # Extract, load and check schemas referenced in profiles
        for entry in content["patterns"]:
            schemaref = entry["useSchema"]
            if type(schemaref) == str:
                cls.get_schema_json(schemaref)

        _profiles_json[filename] = content
        return content

    @classmethod
    def schema_filename(cls, val: Union[bool, str]) -> str:
        """Helper to treat trivial (bool) and non-trivial (reference str) schema uniformly."""

        if isinstance(val, str):
            return val
        return TRIV_TRUE if val else TRIV_FALSE

    @classmethod
    def schema_content(
        cls, filename: str, embedded: Optional[Dict[str, UnsafeJSON]] = None
    ) -> UnsafeJSON:
        """
        Return the schema referenced by provided filename.

        Also handles the special filenames for the trivial true/false schema,
        for consistent treatment.
        """

        if filename == TRIV_TRUE:
            return True
        elif filename == TRIV_FALSE:
            return False
        elif embedded and filename in embedded:
            return embedded[filename]
        else:
            return cls.get_schema_json(filename)

    @classmethod
    def load(cls, filename: str):
        """
        Given a profile file, construct a self-contained "normalized" profile
        from the loaded JSON profiles and schemas (i.e. load and piece together).
        """

        profile: Mapping[str, Any] = cls.get_profile_json(filename)

        title: str = profile["title"] if profile["title"] is not None else filename

        description: str = ""
        if "description" in profile:
            description = profile["description"]

        rootSchema: str = cls.schema_filename(profile["rootSchema"])
        fallbackSchema: str = cls.schema_filename(profile["fallbackSchema"])

        schemas: Dict[str, UnsafeJSON] = {TRIV_TRUE: True, TRIV_FALSE: False}
        # first copy the directly embedded ones
        if "schemas" in profile:  # optional embedded schemas
            for embName, embSchema in profile["schemas"].items():
                schemas[embName] = embSchema

        # need to embed root and fallback schemas
        schemas[rootSchema] = cls.schema_content(rootSchema, schemas)
        schemas[fallbackSchema] = cls.schema_content(fallbackSchema, schemas)

        patterns = []
        for pat in profile["patterns"]:
            # add referenced schema if not yet added
            schemaref: str = cls.schema_filename(pat["useSchema"])
            schemaval: UnsafeJSON = cls.schema_content(schemaref, schemas)
            schemas[schemaref] = schemaval
            # add regex entry
            patterns.append(PatternSchema(pattern=pat["pattern"], useSchema=schemaref))

        return cls(
            title=title,
            description=description,
            rootSchema=rootSchema,
            fallbackSchema=fallbackSchema,
            schemas=schemas,
            patterns=patterns,
        )

    @classmethod
    def load_profiles(cls, profile_dir: Path) -> None:
        """
        Load and validate raw JSON profiles from the configured directory.

        Also loads and validates the referenced JSON Schemas.
        """

        global PROFILE_DIR
        PROFILE_DIR = profile_dir

        if not PROFILE_DIR.is_dir():
            critical_exit(f"Profile directory {PROFILE_DIR} does not exist!")

        log.info(f"Loading profiles (*{PROFILE_SUF}) from '{PROFILE_DIR}'")

        pr_filenames = list(map(lambda x: x.name, PROFILE_DIR.iterdir()))
        pr_filenames = list(
            filter(lambda x: str(x).endswith(PROFILE_SUF), pr_filenames)
        )
        if len(pr_filenames) == 0:
            critical_exit(f"No profiles (*{PROFILE_SUF}) found in {PROFILE_DIR}!")

        for pr_filename in pr_filenames:
            name: str = re.sub(PROFILE_SUF + "$", "", str(pr_filename))
            profile = cls.load(pr_filename)
            _profiles[name] = profile

    @classmethod
    def get_profiles(cls) -> List[str]:
        """Return a list a available profiles (i.e., after they have been loaded)."""

        return list(sorted(_profiles.keys()))

    @classmethod
    def get_profile(cls: Type[T], name: str) -> Optional[T]:
        """Return a profile given its name."""

        if name in _profiles:
            return _profiles[name]  # type: ignore
        return None


# TODO: What about non-self-contained JSON schemas? resolve refs and make self-contained!
# - should resolve local files and eventually grab schemas from outside/metastore
# - profiles could also be loaded from metastore in addition to local ones
# - in any case, they should be pre-processed to be independent from external info
#   because we send it to the client browser that cannot just load arbitrary data.
# but in the final file we could omit the URL-linked ones, assuming the URLs are permanent
