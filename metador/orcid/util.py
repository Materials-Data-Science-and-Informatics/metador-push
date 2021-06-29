"""Must to put this stuff here to avoid circular imports."""

from typing import Final, Optional

MOCK_ORCID_PREF: Final[str] = "/fakeid"
"""Endpoint for fake ORCID auth server (if used)."""

AUTH_PREF: Final[str] = "/oauth"
"""Route prefix for all auth-related things."""

ORCID_ENDPOINT: Final[str] = "/orcid"
"""Endpoint for auth redirection (visited from UI + redirected back to it from ORCID)."""


def orcid_redir(pref) -> str:
    """
    Returns a path that is supposed te be registered
    as a valid redirect for use with the ORCID API client credentials.
    """

    return pref + AUTH_PREF + ORCID_ENDPOINT


def orcid_server_pref(sandbox: bool, site_pref: Optional[str] = None) -> str:
    """
    Returns the oauth API entry point with or without sandbox, depending on config.

    When site_pref is set to a the base site prefix (it must be something starting with
    http(s)://...), it returns it with the appended minimal mock prefix.
    (Add mock_orcid to your FastAPI routes for it to work!)

    This is basically a helper to hook up the Auth instance with different servers.
    """

    if site_pref:  # if given, we want to use our own fake-server for testing
        return site_pref + MOCK_ORCID_PREF

    # use one of the two real servers
    sbx = "sandbox." if sandbox else ""
    return f"https://{sbx}orcid.org/oauth"
