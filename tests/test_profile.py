"""Tests for Profile class."""

from pathlib import Path

import pytest

import metador_push.profile as profile
from metador_push.profile import TRIV_FALSE, TRIV_TRUE, Profile
from metador_push.util import load_json


def test_load_get_profiles(test_config, tmp_path):
    """Try loading profiles from (non-)existing directories."""
    # non-existing dir
    with pytest.raises(SystemExit):
        Profile.load_profiles(Path("non-existing dir"))

    # empty dir
    with pytest.raises(SystemExit):
        Profile.load_profiles(tmp_path)

    # load our embedded profiles (this will persist as long as the module is loaded)
    Profile.load_profiles(test_config.metador_push.profile_dir)

    # test that profile directory loads properly
    prs = Profile.get_profiles()
    for p in ["anything", "empty", "example", "unsat"]:
        assert p in prs

    assert Profile.get_profile("empty") is not None
    with pytest.raises(KeyError):
        Profile.get_profile("non-existing profile")


def test_get_schema_for(test_config):
    """Check that resolving embedded/external schemas works correctly."""
    pr = Profile.get_profile("example")

    # should be false.schema.json, which is embedded as true (ignoring the external one)
    assert pr.get_schema_for("Some image.jpg") == True
    # should be true.schema.json, which is loaded and is true
    assert pr.get_schema_for("some Movie.mp4") == True
    # should also be case-insensitive
    assert pr.get_schema_for("some Movie.Mp4") == True
    assert pr.get_schema_for("Some IMAGE.JPG") == True
    # should be fallback schema, which is __FALSE__ which is false
    assert pr.get_schema_for("some-website.htm") == False
    # test that the match is complete and not somewhere in path -> should fallback (false)
    assert pr.get_schema_for("some.txt.document") == False
    # should be the loaded generic schema
    assert pr.get_schema_for("some document.txt") == pr.schemas["generic.schema.json"]
    # should be the rootSchema which is embedded
    assert pr.get_schema_for(None) == pr.schemas["embeddedSchema"]


def test_get_schema_json(test_config):
    """Try loading invalid or missing schemas."""
    # not existing file
    with pytest.raises(SystemExit):
        Profile.get_schema_json("not_existing_file")
    # invalid JSON schema
    with pytest.raises(SystemExit):
        Profile.get_schema_json("invalid.schema.json")
    # invalid JSON
    with pytest.raises(SystemExit):
        Profile.get_schema_json("broken.schema.json.file")


def test_get_profile_json(test_config):
    """Try loading invalid or missing profiles."""
    with pytest.raises(SystemExit):
        Profile.get_profile_json("non-existing profile")

    with pytest.raises(SystemExit):
        Profile.get_profile_json("invalid.schema.json")

    # add something to cache, retrieve it back
    profile._profiles_json["dummy"] = {"a": "b"}
    assert Profile.get_profile_json("dummy") == {"a": "b"}

    # now try force-loading the thing (should fail instead of return, as not existing)
    with pytest.raises(SystemExit):
        Profile.get_profile_json("dummy", True)


def test_profile_load(test_config):
    """Check that the profiles are assembled correctly."""
    pr = Profile.get_profile("example")

    # these are always there
    assert TRIV_TRUE in pr.schemas
    assert TRIV_FALSE in pr.schemas

    # check that all referenced schemas are actually embedded
    assert pr.rootSchema in pr.schemas
    assert pr.fallbackSchema in pr.schemas
    for pat in pr.patterns:
        assert pat.useSchema in pr.schemas

    # check that the embedded schema is actually the one loaded from file
    genericSchema = load_json(
        test_config.metador_push.profile_dir / "generic.schema.json"
    )
    assert pr.schemas["generic.schema.json"] == genericSchema

    # simple check what we expect to see there: the always present trivial ones,
    # the schemas embedded directly in the profile in the schemas dict,
    # and the schemas in other json files referenced in the profile
    assert pr.schemas.keys() == {
        TRIV_TRUE,
        TRIV_FALSE,
        "embeddedSchema",
        "generic.schema.json",
        "true.schema.json",
        "false.schema.json",
        "transitive.schema.json",
    }

    # check that the embedded schema wins over loaded from file
    assert pr.schemas["false.schema.json"] == True


def test_schema_save_load(test_config, tmp_path):
    """Test serializing and loading back (might be of interest for post-proc)."""
    pr = Profile.get_profile("example")
    pr.save(tmp_path / "example_dump.profile.json")
    pr2 = Profile.load(str(tmp_path / "example_dump.profile.json"))
    assert pr == pr2
