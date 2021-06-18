from typing import Final, Optional

#: route prefix for all auth-related things
AUTH_PREF: Final[str] = "/oauth"

#: endpoint for auth redirection (visited from UI, later redirected back to it from ORCID)
ORCID_ENDPOINT: Final[str] = "/orcid"

#: endpoint for fake ORCID auth server (if used)
MOCK_ORCID_ENDPOINT: Final[str] = "/fakeid"


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
        return site_pref + MOCK_ORCID_ENDPOINT

    # use one of the two real servers
    sbx = "sandbox." if sandbox else ""
    return f"https://{sbx}orcid.org/oauth"
