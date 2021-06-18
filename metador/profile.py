"""
Metador profile management.
"""

from typing import Union, List, Mapping, Any, Dict, Tuple, Final, Optional
from pathlib import Path
import os
import re
import json
from json.decoder import JSONDecodeError
import jsonschema
from jsonschema.exceptions import ValidationError

from . import pkg_res
from .config import conf
from .util import critical_exit

#: JSON primitives
JSON_v = Union[str, int, float, bool, None]

#: Superficial JSON type (not recursive!) to silence mypy
UnsafeJSON = Union[JSON_v, List[JSON_v], Mapping[str, Any]]

#: JSON Schema of JSON Schema to check schemas (we use Draft 7 like jsonschema)
jsonschema_schema = json.load(open(pkg_res("schemas/draft-07.schema.json"), "r"))

#: JSON Schema the profiles are checked against
profile_schema = json.load(open(pkg_res("schemas/metador_profile.schema.json"), "r"))

# load all profiles and schemas and check they are valid

profile_dir: Final[Path] = conf().metador.profile_dir
if not os.path.isdir(profile_dir):
    critical_exit(f"Profile directory {profile_dir} does not exist!")

profile_fnames = os.listdir(profile_dir)
profile_filenames = list(filter(lambda x: x.endswith(".profile.json"), profile_fnames))
if len(profile_fnames) == 0:
    critical_exit(f"No profiles (*.profile.json) found in {profile_dir}!")

#: Schema filename -> schema content
schemas = {}

#: Profile name (without ext) -> profile content
profiles = {}


def validate_json(instance: UnsafeJSON, schema: UnsafeJSON) -> Optional[str]:
    """Validate JSON against JSON Schema, on success return None, otherwise error."""
    try:
        jsonschema.validate(instance, schema)
        return None
    except ValidationError as e:
        return e.message


for pr_filename in profile_filenames:
    name = re.sub(".profile.json$", "", pr_filename)
    content = json.load(open(profile_dir / pr_filename, "r"))

    # check profile itself
    errmsg = validate_json(content, profile_schema)
    if errmsg is not None:
        critical_exit(f"Invalid profile {pr_filename}: {errmsg}")

    # Extract, load and check schemas referenced in profiles
    for entry in content["patterns"]:
        schemaref = entry["schema"]
        if type(schemaref) == str:
            if not os.path.isfile(profile_dir / schemaref):
                critical_exit(
                    f"{pr_filename}: Could not open schema file '{schemaref}'!"
                )

            schema = None
            try:
                schema = json.load(open(profile_dir / schemaref, "r"))
            except JSONDecodeError:
                critical_exit(f"{pr_filename}: Cannot parse schema file '{schemaref}'!")

            if validate_json(schema, jsonschema_schema) is not None:
                critical_exit(f"{pr_filename}: {schemaref} is not a valid JSON Schema!")

            if schemaref not in schemas:
                schemas[schemaref] = schema

    profiles[name] = content

print(profiles, schemas)


# load all profiles, link them up with the schemas from the store


class Profile:
    """
    Class holding a profile loaded from a *.profile.json file.

    It also includes references to all relevant JSON Schemas.
    """

    def __init__(self, filename: str) -> None:
        self.profile: UnsafeJSON = None

        self.schemas: Dict[str, UnsafeJSON] = {}

        self.title: str = ""

        self.rootSchema: UnsafeJSON = None

        self.fallbackSchema: UnsafeJSON = None

        self.patterns: List[Tuple[str, Union[bool, str]]] = []

    # TODO: add to_json from_json (for use inside dataset)
    # probably need override for pattern entry serialization
