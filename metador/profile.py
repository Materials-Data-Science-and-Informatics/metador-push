"""
Metador profile management.

This module takes care of loading profiles and referenced JSON Schemas,
assembling them, returning them and providing functions to match files to schemas.

Schemas must be valid according to JSON Schema Draft 7,
Profiles must be valid according to the [Profile Schema](../../profile.schema.json).

`Profile.load_profiles` must be called with the profile directory as argument
at the start of the application.
"""
from __future__ import annotations

import collections
import re
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Mapping, Optional, Set, Union

from pydantic import BaseModel
from typing_extensions import Final

from . import pkg_res
from .log import log
from .util import (
    UnsafeJSON,
    critical_exit,
    load_json,
    referenced_schemas,
    save_json,
    validate_json,
)

SCHEMA_SUF: Final[str] = ".schema.json"
"""File suffix for json schemas."""

PROFILE_SUF: Final[str] = ".profile.json"
"""File suffix for dataset profiles"""

_JSONSCHEMA_SCHEMA = load_json(pkg_res("draft-07" + SCHEMA_SUF))
"""JSON Schema of JSON Schema to check schemas (we use Draft 7 like jsonschema)."""

_PROFILE_SCHEMA = load_json(pkg_res("profile" + SCHEMA_SUF))
"""JSON Schema the profiles are checked against"""

TRIV_TRUE: Final[str] = "__TRUE__"
"""Fake filename / schema ref to substitute for boolean "true" schema in normal-form."""

TRIV_FALSE: Final[str] = "__FALSE__"
"""Fake filename / schema ref to substitute for boolean "false" schema in normal-form."""

_PROFILE_DIR: Path
"""Variable that is set by load_profiles (from config)."""

_schemas_json: Dict[str, UnsafeJSON] = {}
"""In-memory cache: Schema filename -> schema content. Access via get_schema."""

_profiles_json: Dict[str, Mapping[str, UnsafeJSON]] = {}
"""In-memory cache: Profile name (without ext) -> profile content."""

_profiles: Dict[str, "Profile"] = {}
"""In-memory cache: profiles assembled from files, ready to be copied into datasets."""


def expand_schema_path(filename: str) -> str:
    """If passed string is not an URL, prepend profile directory to relative path/filename."""
    if filename.find("http://") == 0 or filename.find("https://") == 0:
        return filename
    return str(_PROFILE_DIR / filename)


def schema_bfs(
    name: str,
    func: Callable[[str, UnsafeJSON], Any],
    get_succ: Callable[[str], UnsafeJSON],
) -> None:
    """
    Perform BFS on the graph schemas and their successors (referenced schemas).

    Takes a schema name, a function to call for each schema, and a successor function
    that returns a schema given its name (without fragment part).
    """
    vis = set(name)
    q: Deque[str] = collections.deque()
    q.append(name)
    while not len(q) == 0:
        curr_name = q.popleft()
        curr_schema = get_succ(curr_name)
        if curr_name in vis:
            continue
        vis.add(curr_name)
        func(curr_name, curr_schema)
        for name in referenced_schemas(curr_schema):
            q.append(name)


def load_schema_refs(
    name: str, schema: UnsafeJSON, extra_schemas: Dict[str, UnsafeJSON]
) -> Set[str]:
    """
    Given a JSON schema dict, recursively load referenced schemas.

    This means, make sure that all referenced schemas are in the cache.
    Returns all direct and transitive $refs.
    """
    ret = set()

    def collect_ref(name: str, _: UnsafeJSON) -> None:
        ret.add(name)

    def get_next_schema(name: str) -> UnsafeJSON:
        return Profile.schema_content(name, extra_schemas)

    schema_bfs(name, collect_ref, get_next_schema)
    return ret


class PatternSchema(BaseModel):
    """
    Pair of a regex pattern and a schema name.

    The schema is to be applied, if the pattern matches the whole file path.
    """

    pattern: str
    """Regex pattern (must match full filename)"""

    useSchema: str
    """Schema (if not URL, resolves first to embedded schemas, then to same dir files)"""


class Profile(BaseModel):
    """
    Class holding a profile representation from a loaded *.profile.json file.

    It also includes references to all relevant JSON Schemas.
    """

    title: str
    """Human-readable title of dataset profile."""

    description: Optional[str] = ""
    """Human-readable description of dataset profile."""

    schemas: Dict[str, UnsafeJSON] = {}
    """Assembled collection of included schemas."""

    patterns: List[PatternSchema] = []
    """Mappings regex -> schema (name of schema is resolved to corresp. schema)."""

    rootSchema: str
    """Schema to use for the dataset itself (not bound to a file)."""

    fallbackSchema: str
    """Schema to use for files not matching any pattern."""

    def get_schema_for(self, filename: Optional[str]) -> UnsafeJSON:
        """
        Return first schema where pattern completely matches filename.

        Otherwise, returns the fallback schema. If no path given, returns the root schema.
        """
        if filename is None:
            return self.schemas[self.rootSchema]
        for pat in self.patterns:
            pmatch = re.match(pat.pattern, filename)
            if pmatch and pmatch.group(0) == filename:
                return self.schemas[pat.useSchema]
        return self.schemas[self.fallbackSchema]

    @classmethod
    def get_schema_json(
        cls, filename: str, force_reload: Optional[bool] = False
    ) -> UnsafeJSON:
        """
        If a schema with that name is not loaded yet, load, validate and cache.

        Return schema on success. Set `force_reload=True` to force a reload from file.
        """
        global _schemas_json

        if not force_reload and filename in _schemas_json:
            return _schemas_json[filename]

        # not cached -> load from file/URL
        schema = None
        try:
            schema = load_json(expand_schema_path(filename))
        except JSONDecodeError:
            critical_exit("Cannot parse schema file '{filename}'!")

        if validate_json(schema, _JSONSCHEMA_SCHEMA) is not None:
            critical_exit(f"{filename} is not a valid Draft 7 JSON Schema!")

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

        If loaded (and not forcing reload), returns cached version.
        This is only for loading the "raw" profile. Use 'load' to get the assembled one.
        """
        global _profiles_json

        if not force_reload and filename in _profiles_json:
            return _profiles_json[filename]

        content: Any = load_json(expand_schema_path(filename))

        # check profile itself
        errmsg = validate_json(content, _PROFILE_SCHEMA)
        if errmsg is not None:
            critical_exit(f"Invalid profile {filename}: {errmsg}")

        _profiles_json[filename] = content  # cache it
        return content

    @classmethod
    def schema_filename(cls, val: Union[bool, str]) -> str:
        """Resolve trivial (bool) and non-trivial (reference str) schemas."""
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
        Construct a self-contained profile from file (filename relative to profile dir).

        Embeds referenced schemas and produces a kind-of "normal form".
        """
        profile: Mapping[str, Any] = cls.get_profile_json(filename)

        title: str = profile["title"] if profile["title"] is not None else filename

        description: str = ""
        if "description" in profile:
            description = profile["description"]

        rootSchema: str = cls.schema_filename(profile["rootSchema"])
        fallbackSchema: str = cls.schema_filename(profile["fallbackSchema"])

        schemas: Dict[str, UnsafeJSON] = {TRIV_TRUE: True, TRIV_FALSE: False}

        toEmbed: Set[str] = set()  # additional referenced schemas that must be embedded

        # first copy the directly embedded ones
        if "schemas" in profile:  # optional embedded schemas
            for embName, embSchema in profile["schemas"].items():
                schemas[embName] = embSchema

        # collect refs from inside the embedded schemas
        for embName, embSchema in schemas.items():
            toEmbed = toEmbed.union(load_schema_refs(embName, embSchema, schemas))

        # need to also add root and fallback schemas
        schemas[rootSchema] = cls.schema_content(rootSchema, schemas)
        schemas[fallbackSchema] = cls.schema_content(fallbackSchema, schemas)
        # collect their refs, too
        toEmbed = toEmbed.union(
            load_schema_refs(rootSchema, schemas[rootSchema], schemas)
        )
        toEmbed = toEmbed.union(
            load_schema_refs(fallbackSchema, schemas[fallbackSchema], schemas)
        )

        patterns = []
        for pat in profile["patterns"]:
            # add referenced schema from pattern if not yet added
            schemaref: str = cls.schema_filename(pat["useSchema"])
            schemaval: UnsafeJSON = cls.schema_content(schemaref, schemas)
            schemas[schemaref] = schemaval
            # add regex entry
            patterns.append(PatternSchema(pattern=pat["pattern"], useSchema=schemaref))
            # collect $refs
            toEmbed = toEmbed.union(
                load_schema_refs(schemaref, schemas[schemaref], schemas)
            )

        # do not overwrite already embedded ones
        toEmbed = toEmbed.difference(schemas.keys())
        # embed missing referenced schemas
        for schema_name in toEmbed:
            schemas[schema_name] = cls.schema_content(schema_name, schemas)

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
        global _PROFILE_DIR
        _PROFILE_DIR = profile_dir

        if not _PROFILE_DIR.is_dir():
            critical_exit(f"Profile directory {_PROFILE_DIR} does not exist!")

        log.info(f"Loading profiles (*{PROFILE_SUF}) from '{_PROFILE_DIR}'")

        pr_filenames = list(map(lambda x: x.name, _PROFILE_DIR.iterdir()))
        pr_filenames = list(
            filter(lambda x: str(x).endswith(PROFILE_SUF), pr_filenames)
        )
        if len(pr_filenames) == 0:
            critical_exit(f"No profiles (*{PROFILE_SUF}) found in {_PROFILE_DIR}!")

        for pr_filename in pr_filenames:
            name: str = re.sub(PROFILE_SUF + "$", "", str(pr_filename))
            profile = cls.load(pr_filename)
            _profiles[name] = profile

    @classmethod
    def get_profiles(cls) -> List[str]:
        """
        Return a list a available profiles.

        (works only after `Profile.load_profiles` was called to initialize)
        """
        return list(sorted(_profiles.keys()))

    @classmethod
    def get_profile(cls, name: str) -> Profile:
        """
        Return a profile given its name (or raises error if no such profile).

        (Works only after `Profile.load_profiles` was called to initialize)
        """
        return _profiles[name]


class ProfileInfo(BaseModel):
    """Only the title and description of a profile (e.g. for overview)."""

    title: str
    """Human-readable title of dataset profile."""

    description: Optional[str] = ""
    """Human-readable description of dataset profile."""

    @classmethod
    def of(cls, p: Profile) -> ProfileInfo:
        """Return ProfileInfo for a given Profile."""
        return ProfileInfo.parse_obj({"title": p.title, "description": p.description})


# TODO: What about non-self-contained JSON schemas? resolve refs and make self-contained!
# - should resolve local files and eventually grab schemas from outside/metastore
# - profiles could also be loaded from metastore in addition to local ones
# - in any case, they should be pre-processed to be independent from external info
#   because we send it to the client browser that cannot just load arbitrary data.
# but in the final file we could omit the URL-linked ones, assuming the URLs are permanent
