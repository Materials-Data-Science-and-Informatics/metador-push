"""Tests for the backend API."""


def test_backend_sanity_check(auth_cookie, sync_client, test_config):
    # works without auth
    res = sync_client.get("/favicon.ico")
    assert res.status_code == 200

    # this is important for frontend
    res = sync_client.get("/site-base")
    assert res.json() == test_config.metador.site

    # try the "hello backend" route
    res = sync_client.get("/api/")
    assert res.status_code == 403
    res = sync_client.get("/api/", cookies=auth_cookie)
    assert res.status_code == 200

    # try invalid routes
    res = sync_client.get("/api/invalid/route")
    assert res.status_code == 403
    res = sync_client.get("/api/invalid/route", cookies=auth_cookie)
    assert res.status_code == 404


# TODO: test the backend routes, RESTfulness (idempotence, etc)
