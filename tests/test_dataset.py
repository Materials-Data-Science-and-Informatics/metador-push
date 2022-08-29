"""Tests for dataset class."""

import asyncio
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from metador_push import dataset, pkg_res
from metador_push.dataset import Dataset
from metador_push.postprocessing import pass_to_postprocessing
from metador_push.profile import Profile
from metador_push.util import ChecksumAlg, load_json

from .test_auth import OTHER_ORCID, SOME_ORCID
from .testutil import get_with_retries


def test_dummy_file(dummy_file):
    """Check that dummy files work as expected."""
    filepath = dummy_file("my_dummy")
    content = ""
    with open(filepath, "r") as file:
        content += file.read()

    assert filepath.name == "my_dummy"
    assert len(content) == 1024


def test_load_datasets(test_config, tmp_path):
    """Invalid data dir should throw, missing subdirs should be created."""
    # try initializing from non-existing data_dir
    tmp = test_config.metador_push.data_dir
    test_config.metador_push.data_dir = Path(tmp_path / "missing_dir")
    Dataset.load_datasets()
    test_config.metador_push.data_dir = tmp

    # now init directories, check that they are still empty
    Dataset.load_datasets()
    assert len(Dataset.get_datasets()) == 0
    assert Dataset._staging_dir().is_dir()
    assert Dataset._complete_dir().is_dir()


def test_load(test_profiles):
    """Test loading a dataset with some surprises."""
    assert Dataset.load(uuid.uuid1()) is None

    # when we create a profile, the corresponding directory and file is created
    ds = Dataset.create(Profile.get_profile("anything"), None)
    assert ds._upload_dir().is_dir()
    assert Dataset._persist_filename(ds.id).is_file()

    ds._upload_dir().rmdir()  # remove empty upload directory
    assert Dataset.load(ds.id) is not None  # loading should still work

    ds._upload_filepath("surprise").touch()  # add surprising extra file
    ds = Dataset.load(ds.id)  # loading should detect new file
    assert "surprise" in ds.files
    ds.save()

    # now the file vanishes again -> failure (registered files should not vanish)
    ds._upload_filepath("surprise").unlink()
    with pytest.raises(FileNotFoundError):
        Dataset.load(ds.id)

    ds.delete()  # clean up


def test_create_load_get(test_config, dummy_file):
    """Test general access to dataset collection."""
    pr = Profile.get_profile("example")

    # check invalid -> keyerror
    with pytest.raises(KeyError):
        Dataset.get_dataset(uuid.uuid1())

    # create a dataset and sanity-check
    ds = Dataset.create(pr, SOME_ORCID)
    assert ds.creator == SOME_ORCID

    # check the dataset is registered everywhere
    assert ds.id in dataset._datasets.keys()
    assert ds.id in Dataset.get_datasets()
    assert Dataset.get_dataset(ds.id) == ds

    # check that a persistence file also was created
    assert ds.id in Dataset._find_staging_datasets()

    # check loading from disk also works
    dataset._datasets.clear()
    Dataset.load_datasets()
    ds2 = Dataset.get_dataset(ds.id)
    assert ds2 == ds
    del ds  # this one is old, now ds2 is the real object

    # check that expired are not returned
    ds2.expires = datetime.now() - timedelta(days=1)
    assert ds2.is_expired()
    with pytest.raises(KeyError):
        Dataset.get_dataset(ds2.id)

    # check that cleanup works
    Dataset.cleanup_datasets()
    assert ds2.id not in dataset._datasets.keys()
    assert ds2.id not in Dataset.get_datasets()

    # test filtering of get_datasets by ORCID
    assert SOME_ORCID != OTHER_ORCID
    ds = Dataset.create(pr, SOME_ORCID)
    assert ds.id in Dataset.get_datasets()
    assert ds.id in Dataset.get_datasets(SOME_ORCID)
    assert ds.id not in Dataset.get_datasets(OTHER_ORCID)

    # test clean-up
    ds.import_file(dummy_file())
    ds.delete()
    assert ds.id not in Dataset.get_datasets()
    assert not ds._upload_dir().is_dir()
    assert not Dataset._persist_filename(ds.id).is_file()


def test_file_handling(test_profiles, dummy_file):
    """Test adding and removing files to datasets."""
    pr = Profile.get_profile("anything")

    ds = Dataset.create(pr, SOME_ORCID)

    file1 = dummy_file("dummy_file", "dummy_content")

    assert len(ds.files) == 0

    # try importing a file
    assert ds.import_file(file1)
    assert file1.name in ds.files
    assert not file1.is_file()
    assert ds._upload_filepath(file1.name).is_file()

    # original should not exist and therefore fail
    assert not ds.import_file(file1)
    file1.touch()
    # should still fail, because a file with that name exists
    assert not ds.import_file(file1)

    # test renaming
    assert ds.rename_file(file1.name, "my_file")
    assert "my_file" in ds.files
    assert file1.name not in ds.files
    assert not ds._upload_filepath(file1.name).is_file()
    assert ds._upload_filepath("my_file").is_file()

    # invalid source
    assert not ds.rename_file("non_existing", "my_file")
    # trivial rename
    assert ds.rename_file("my_file", "my_file")

    # surprising file existence
    ds._upload_filepath("surprise").touch()
    assert ds._upload_filepath("surprise").is_file()
    with pytest.raises(FileExistsError):
        ds.rename_file("my_file", "surprise")
    ds._upload_filepath("surprise").unlink()
    assert not ds._upload_filepath("surprise").is_file()

    # now import should work: (empty) source exists, target does not exist
    assert ds.import_file(file1)

    # but following rename must fail (my_file exists)
    assert not ds.rename_file(file1.name, "my_file")
    # file vanished -> exception
    ds._upload_filepath(file1.name).rename(ds._upload_filepath("vanished"))
    with pytest.raises(FileNotFoundError):
        ds.rename_file(file1.name, "other_name")
    ds._upload_filepath("vanished").rename(ds._upload_filepath(file1.name))

    # check both files are still there (file1 is empty, "my_file" is "dummy_content")
    assert ds.files.keys() == {file1.name, "my_file"}

    # now test checksums
    assert ds.checksumAlg == ChecksumAlg.SHA256
    assert ds.files[file1.name].checksum is None
    assert ds.files["my_file"].checksum is None

    # compute checksums
    assert not ds.compute_checksum("invalid file")
    assert ds.compute_checksum(file1.name)
    assert ds.compute_checksum("my_file")

    # check they are already stored to file
    ds2 = Dataset.load(ds.id)
    assert ds2 == ds

    # test correct hashing output
    EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    DUMMY_SHA256 = "807ac90e2ae393e32b4562a81d158a190eb4b26dd021713b82b31b1b457f3d59"
    assert ds.files[file1.name].checksum == EMPTY_SHA256
    assert ds.files["my_file"].checksum == DUMMY_SHA256

    # trigger actual error with checksum tool (missing tool, missing file...)
    ds.checksumAlg = "invalid"  # type: ignore
    assert not ds.compute_checksum(file1.name)
    ds.checksumAlg = ChecksumAlg.SHA256
    ds._upload_filepath(file1.name).unlink()  # kill file, keep entry
    assert not ds.compute_checksum(file1.name)

    assert not ds.delete_file("invalid file")
    assert ds.delete_file(file1.name)  # should work, even though real file already gone
    assert ds.delete_file("my_file")  # should also work (file + entry exists)

    # check removed files are gone
    assert len(ds.files) == 0
    assert not ds._upload_filepath(file1.name).is_file()
    assert not ds._upload_filepath("my_file").is_file()

    ds.delete()  # clean up


def test_immediate_persist_metadata(test_profiles, dummy_file):
    """Changes to metadata are stored to file immediately."""
    file1 = dummy_file()
    pr = Profile.get_profile("anything")
    ds = Dataset.create(pr, SOME_ORCID)
    ds.import_file(file1)

    ds.set_metadata(None, True)
    ds2 = Dataset.load(ds.id)
    assert ds2.rootMeta == True

    ds.set_metadata(file1.name, False)
    ds2 = Dataset.load(ds.id)
    assert ds2.files[file1.name].metadata == False
    ds.delete()


def test_unsat_profile(test_profiles):
    """Test unsatisfiable profile with dataset."""
    unsat = Profile.get_profile("unsat")
    ds = Dataset.create(unsat, SOME_ORCID)
    assert len(ds.validate_dataset()) != 0
    ds.delete()


def test_anything_profile(test_profiles, dummy_file):
    """Test trivial profile with dataset."""
    file1 = dummy_file()
    pr = Profile.get_profile("anything")
    # empty -> success
    ds = Dataset.create(pr, SOME_ORCID)
    assert len(ds.validate_dataset()) == 0
    # non-empty -> fails
    ds.import_file(file1)
    assert len(ds.validate_dataset()) == 0
    ds.delete()


def test_empty_profile(test_profiles, dummy_file):
    """Test forced empty profile with dataset."""
    file1 = dummy_file()
    pr = Profile.get_profile("empty")
    # empty -> success
    ds = Dataset.create(pr, SOME_ORCID)
    assert len(ds.validate_dataset()) == 0
    # non-empty -> fails
    ds.import_file(file1)
    assert len(ds.validate_dataset()) != 0
    ds.delete()


def test_example_dataset(test_profiles, dummy_file):
    """Test example profile with a dataset with some non-trivial constraints."""
    pr = Profile.get_profile("example")
    ds = Dataset.create(pr, SOME_ORCID)

    # check without root metadata
    assert "" in ds.validate_dataset()
    # check with invalid metadata
    ds.set_metadata(None, True)
    assert "" in ds.validate_dataset()
    ds.set_metadata(None, {"some": "key"})
    assert "" in ds.validate_dataset()
    ds.set_metadata(None, {"validNumber": "value"})
    assert "" in ds.validate_dataset()
    ds.set_metadata(None, {"validNumber": 100})
    assert "" in ds.validate_dataset()
    ds.set_metadata(None, {"validNumber": -1})
    assert "" in ds.validate_dataset()
    # check with valid metadata
    ds.set_metadata(None, {"validNumber": 0})
    assert "" not in ds.validate_dataset()

    # set metadata to invalid file
    assert not ds.set_metadata("missing file", True)

    # add unmatched file(name) (fallbackSchema=false must reject it)
    file1 = dummy_file("invalid.file")
    ds.import_file(file1)
    assert file1.name in ds.validate_dataset()
    # remove it again
    ds.delete_file(file1.name)
    assert len(ds.validate_dataset()) == 0

    # add some pattern-matched files

    # mp4 -> true.schema.json -> true
    mp4file = dummy_file("video.mp4")
    ds.import_file(mp4file)
    assert mp4file.name not in ds.validate_dataset()
    ds.set_metadata(mp4file.name, False)
    assert mp4file.name not in ds.validate_dataset()

    # jpg -> false.schema.json (embedded) -> true
    jpgfile = dummy_file("image.jpg")
    ds.import_file(jpgfile)
    assert jpgfile.name not in ds.validate_dataset()
    ds.set_metadata(jpgfile.name, False)
    assert jpgfile.name not in ds.validate_dataset()
    ds.set_metadata(jpgfile.name, None)  # no metadata for this file!

    # txt -> generic.schema.json (from file)
    txtfile = dummy_file("document.txt")
    ds.import_file(txtfile)
    assert txtfile.name in ds.validate_dataset()
    ds.set_metadata(txtfile.name, {"authorName": "John Doe"})
    assert txtfile.name in ds.validate_dataset()
    ds.set_metadata(
        txtfile.name, {"authorName": "John Doe", "authorEmail": "invalidMail"}
    )
    assert txtfile.name in ds.validate_dataset()
    ds.set_metadata(txtfile.name, {"authorName": 123, "authorEmail": "a@b.de"})
    assert txtfile.name in ds.validate_dataset()
    ds.set_metadata(txtfile.name, {"authorName": "John Doe", "authorEmail": "a@b.de"})
    assert txtfile.name not in ds.validate_dataset()
    ds.set_metadata(
        txtfile.name,
        {"authorName": "John Doe", "authorEmail": "a@b.de", "authorOrcid": "orcid"},
    )
    assert txtfile.name in ds.validate_dataset()
    assert ds.complete()[0] is None  # cannot complete with validation errors

    valid_txt_meta = {
        "authorName": "John Doe",
        "authorEmail": "a@b.de",
        "authorOrcid": "0000-0000-0000-0000",
    }
    ds.set_metadata(txtfile.name, valid_txt_meta)
    assert txtfile.name not in ds.validate_dataset()

    # missing checksums
    assert ds.complete()[0] is None
    for fname in ds.files.keys():
        ds.compute_checksum(fname)

    # now completion should work
    assert len(ds.validate_dataset()) == 0
    path, _ = ds.complete()
    assert path is not None
    assert not ds._persist_filename(ds.id).is_file()
    assert not ds._upload_dir().is_dir()
    assert path.is_dir()

    # dataset should not be listed anymore
    assert ds.id not in Dataset.get_datasets()

    # check existence/absence of expected output files
    assert path.name == str(ds.id)
    filenames = {}
    for p in path.glob("*"):
        filenames[p.name] = p

    assert "document.txt" + dataset.METADATA_SUF in filenames
    assert "video.mp4" + dataset.METADATA_SUF in filenames
    assert (
        "image.jpg" + dataset.METADATA_SUF not in filenames
    )  # metadata null -> no file
    assert dataset.METADATA_SUF in filenames
    assert "dataset.json" in filenames
    assert "sha256sums.txt" in filenames

    # check contents
    assert load_json(filenames["dataset.json"])["creator"] == SOME_ORCID  # type: ignore
    assert load_json(filenames[dataset.METADATA_SUF])["validNumber"] == 0  # type: ignore
    assert load_json(filenames["video.mp4" + dataset.METADATA_SUF]) == False
    assert load_json(filenames["document.txt" + dataset.METADATA_SUF]) == valid_txt_meta

    # sanity-check checksums
    chksums = []
    with open(filenames["sha256sums.txt"], "r") as file:
        chksums = file.readlines()
    chksums = list(map(lambda x: x.strip().split(), chksums))
    assert len(chksums) == 3
    # have entry for each data file
    assert list(map(lambda x: x[0], chksums)) == [
        "document.txt",
        "image.jpg",
        "video.mp4",
    ]
    # have non-empty checksums
    assert all(map(lambda x: x[1] != "", chksums))


@pytest.mark.asyncio
async def test_completion_hooks(test_profiles, mock_http_postproc):
    """Test the triggering of the supported types of postprocessing."""
    pp_endpoint = mock_http_postproc[0]

    pr = Profile.get_profile("anything")
    ds = Dataset.create(pr, SOME_ORCID)
    path, _ = ds.complete()
    assert path is not None

    # notif = DatasetNotification(location=str(path))
    # notif_json_str = notif.json().replace('"', '\\"')

    success = await pass_to_postprocessing(
        f"{pkg_res('tests/mock_postproc.sh')} {pp_endpoint}", path
    )
    assert success

    # test that the curl command worked
    ret = await get_with_retries(mock_http_postproc[1], None)
    assert ret is not None

    assert ret.event == "new_dataset"
    assert Path(ret.location) == path

    success = await pass_to_postprocessing("invalid script", path)
    assert not success

    success = await pass_to_postprocessing("http://invalid/endpoint", path)
    assert not success

    await pass_to_postprocessing(pp_endpoint, path)
    ret = await asyncio.wait_for(mock_http_postproc[1].get(), timeout=1)
    assert ret.event == "new_dataset"
    assert Path(ret.location) == path
