"""
Helper functions for ORCID authentication, based on the following guide:
https://info.orcid.org/documentation/api-tutorials/api-tutorial-get-and-authenticated-orcid-id/
"""

import httpx

import metador.config as config

# add subdomain of sandbox if the option is selected
SANDBOX = "sandbox." if bool(config.get("orcid", "sandbox")) else ""
# Production/Sandbox ORCID URL prefix for OAuth
ORCID_OAUTH_PREF = f"https://{SANDBOX}orcid.org/oauth"


def get_orcid_redir() -> str:
    """
    Returns an URL that is supposed to be reachable by the client and registered
    as a valid redirect for use with the ORCID API client credentials.
    """

    return str(config.get("metador", "site")) + str(
        config.get("metador", "orcid-auth-route")
    )


def userauth_url() -> str:
    """
    Construct an URL for login via ORCID for the user to click on.
    For this to work, you must first register your Metadir instance in
    the developer tools in the ORCID account.
    Input: -
    Output: URL for frontend use.
    """

    auth_url = ORCID_OAUTH_PREF + "/authorize"
    auth_url += "?response_type=code&scope=/authenticate"

    orcid_cid = config.get("orcid", "client_id")
    orcid_redir = get_orcid_redir()

    return f"{auth_url}&client_id={orcid_cid}&redirect_uri={orcid_redir}"


def redeem_code(code: str) -> str:
    """
    Input: the 6-digit code from ORCID
    Output: Bearer token from ORCID certifying that the user logged into ORCID.
    """

    hdrs = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    dat = {
        "client_id": config.get("orcid", "client_id"),
        "client_secret": config.get("orcid", "client_secret"),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": get_orcid_redir(),
    }

    r = httpx.post(ORCID_OAUTH_PREF + "/token", headers=hdrs, data=dat)
    return r.json()
