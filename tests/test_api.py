"""Tests for the backend API."""
from uuid import UUID, uuid1

import pytest
from httpx import URL

from metador_push.config import conf
from metador_push.dataset import Dataset
from metador_push.orcid import get_auth, init_auth
from metador_push.orcid.mock import MOCK_TOKEN
from metador_push.profile import Profile


@pytest.fixture
def auth_cookie(test_config):
    """Initialize auth if necessary, fake-auth as a user, return cookie."""
    try:
        get_auth()
    except RuntimeError:
        init_auth(
            test_config.metador_push.site,
            test_config.orcid,
            test_config.metador_push.data_dir,
        )

    cookies = {}
    cookies["session_id"] = get_auth().new_session(MOCK_TOKEN)
    return cookies


@pytest.mark.asyncio
async def test_backend_sanity_check(auth_cookie, async_client, test_config):
    """Test the trivial routes and restricted access to backend."""
    # works without auth
    res = await async_client.get("/favicon.ico")
    assert res.status_code == 200

    # this is important for frontend
    res = await async_client.get("/site-base")
    assert res.json() == test_config.metador_push.site

    res = await async_client.get("/tusd-endpoint")
    assert res.json() == test_config.metador_push.tusd_endpoint

    # invalid -> should return SPA
    res = await async_client.get("/invalid/route")
    assert res.text.find("bundle.js") >= 0

    # try the "hello backend" route
    res = await async_client.get("/api/")
    assert res.status_code == 403
    res = await async_client.get("/api/", cookies=auth_cookie)
    assert res.status_code == 200

    # try invalid backend routes
    res = await async_client.get("/api/invalid/route")
    assert res.status_code == 403
    res = await async_client.get("/api/invalid/route", cookies=auth_cookie)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_profile_routes(auth_cookie, async_client, test_profiles):
    """Test routes concerned with getting profiles."""
    async_client.base_url = URL(str(async_client.base_url) + "/api")
    async_client.cookies = auth_cookie

    # list of profiles
    res = (await async_client.get("/profiles")).json().keys()
    for p in ["anything", "empty", "example", "unsat"]:
        assert p in res

    # get invalid profile
    res = await async_client.get("/profiles/invalid")
    assert res.status_code == 404

    # get valid profile
    res = await async_client.get("/profiles/example")
    assert Profile.parse_obj(res.json()) == Profile.get_profile("example")


@pytest.mark.asyncio
async def test_dataset_routes(auth_cookie, async_client, test_datasets):
    """Test routes concerned with querying datasets in general."""
    async_client.base_url = URL(str(async_client.base_url) + "/api")
    async_client.cookies = auth_cookie

    # create dataset with invalid or missing profile
    res = await async_client.post("/datasets")
    assert res.status_code == 422
    res = await async_client.post("/datasets?profile=invalid")
    assert res.status_code == 404

    # create a dataset
    res = await async_client.post("/datasets?profile=anything")
    assert res.status_code == 200
    ds_id = UUID(res.json())
    ds = Dataset.get_dataset(ds_id)
    assert ds.id == ds_id
    assert ds.creator is not None

    # get existing datasets
    res = await async_client.get("/datasets")
    assert str(ds_id) in res.json()

    # pretend auth is disabled and we're not authenticated
    # then we should get empty list of datasets
    get_auth().orcid_conf.enabled = False
    async_client.cookies = {}

    res = await async_client.get("/datasets")
    assert res.json() == []

    # pretend auth is enabled but we're not authenticated
    get_auth().orcid_conf.enabled = True
    res = await async_client.get("/datasets")
    assert res.status_code == 403

    # restore auth cookie for further tests
    async_client.cookies = auth_cookie

    # try to get invalid dataset
    res = await async_client.get(f"/datasets/{uuid1()}")
    assert res.status_code == 404

    # try to get the created dataset
    res = await async_client.get(f"/datasets/{ds_id}")
    assert Dataset.parse_obj(res.json()) == ds

    # get dataset metadata
    res = await async_client.get(f"/datasets/{ds_id}/meta")
    assert res.json() is None

    # store some to dataset metadata
    res = await async_client.put(f"/datasets/{ds_id}/meta", json={"key": "value"})
    assert res.status_code < 400

    # retrieve it back
    res = await async_client.get(f"/datasets/{ds_id}/meta")
    assert res.json() == {"key": "value"}

    # validate (anything goes, should have no errors -> null -> None)
    res = await async_client.get(f"/datasets/{ds_id}/meta/validate")
    assert res.json() is None

    # delete this dataset
    res = await async_client.delete(f"/datasets/{ds_id}")
    assert res.json() is None

    # delete it again
    res = await async_client.delete(f"/datasets/{ds_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_file_routes(
    auth_cookie, async_client, test_datasets, dummy_file, mock_http_postproc
):
    """Test routes concerning files, metadata and competion of a dataset."""
    async_client.base_url = URL(str(async_client.base_url) + "/api")
    async_client.cookies = auth_cookie

    res = await async_client.post("/datasets?profile=example")
    ds_id = UUID(res.json())
    ds = Dataset.get_dataset(UUID(res.json()))

    # no files in new dataset
    res = await async_client.get(f"/datasets/{ds_id}/files")
    assert res.json() == {}

    # put some file (we bypass the API here, actual upload is tested in test_upload)
    file = dummy_file("document.txt")
    ds.import_file(file)

    res = await async_client.get(f"/datasets/{ds_id}/files")
    assert "document.txt" in res.json()

    res = await async_client.get(f"/datasets/{ds_id}/files/document.txt/checksum")
    assert res.json() is None

    res = await async_client.get(f"/datasets/{ds_id}/files/document.txt/meta")
    assert res.json() is None

    res = await async_client.get(f"/datasets/{ds_id}/files/document.txt/meta/validate")
    assert res.json() != ""  # has validation errors

    # compute checksum
    ds.compute_checksum("document.txt")

    res = await async_client.get(f"/datasets/{ds_id}/files/document.txt/checksum")
    assert len(res.json()) > 0

    res = await async_client.get(f"/datasets/{ds_id}/files")
    chksum = res.json()["document.txt"]
    assert chksum is not None

    # add metadata
    metadata = {"authorName": "John Doe", "authorEmail": "au@th.or"}
    res = await async_client.put(
        f"/datasets/{ds_id}/files/document.txt/meta", json=metadata
    )
    assert res.json()  # == True

    res = await async_client.get(f"/datasets/{ds_id}/files/document.txt/meta/validate")
    assert res.json() is None  # no validation errors

    # rename file
    res = await async_client.patch(
        f"/datasets/{ds_id}/files/document.txt/rename-to/new.txt"
    )
    assert res.json()  # == True

    res = await async_client.get(f"/datasets/{ds_id}/files")
    assert "document.txt" not in res.json()
    assert "new.txt" in res.json()

    res = await async_client.patch(
        f"/datasets/{ds_id}/files/document.txt/rename-to/new.txt"
    )
    assert res.status_code == 404

    res = await async_client.get(f"/datasets/{ds_id}/files/document.txt/checksum")
    assert res.status_code == 404

    res = await async_client.get(f"/datasets/{ds_id}/files/new.txt/checksum")
    assert res.json() == chksum

    # delete file
    res = await async_client.delete(f"/datasets/{ds_id}/files/new.txt")
    assert res.status_code < 400
    res = await async_client.delete(f"/datasets/{ds_id}/files/new.txt")
    assert res.status_code == 404

    # enable postprocessing hook (to see that it is called)
    conf().metador_push.completion_hook = mock_http_postproc[0]

    # try to complete dataset (root metadata is missing)
    res = await async_client.put(f"/datasets/{ds_id}")
    assert res.status_code == 422

    # add root metadata
    rootmeta = {"validNumber": 42}
    res = await async_client.put(f"/datasets/{ds_id}/meta", json=rootmeta)
    assert res.json()  # == True

    # sanity-check
    res = await async_client.get(f"/datasets/{ds_id}/files")
    assert res.json() == {}
    res = await async_client.get(f"/datasets/{ds_id}/meta")
    assert res.json() == rootmeta

    # try to complete dataset (should succeed)
    res = await async_client.put(f"/datasets/{ds_id}")
    assert res.status_code == 200

    # ret = await asyncio.wait_for(mock_http_postproc[1].get(), timeout=1)
    # assert ret.event == "new_dataset"

    # now it's gone
    res = await async_client.put(f"/datasets/{ds_id}")
    assert res.status_code == 404
