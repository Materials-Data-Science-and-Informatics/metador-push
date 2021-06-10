"""
Helper functions for ORCID authentication, based on the following guide:
https://info.orcid.org/documentation/api-tutorials/api-tutorial-get-and-authenticated-orcid-id/
"""

from typing import Literal

import httpx

from metador.config import conf
import metador.config as c

from pydantic import BaseModel


class OrcidBearerToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    refresh_token: str
    expires_in: int
    scope: str
    name: str
    orcid: str


def orcid_oauth_pref() -> str:
    """Returns the oauth API entry point with or without sandbox, depending on config."""

    sbx = "sandbox." if conf().orcid.sandbox else ""
    return f"https://{sbx}orcid.org/oauth"


def get_orcid_redir() -> str:
    """
    Returns an URL that is supposed to be reachable by the client and registered
    as a valid redirect for use with the ORCID API client credentials.
    """

    return conf().metador.site + c.ORCID_REDIR_ROUTE


def userauth_url() -> str:
    """
    Construct an URL for login via ORCID for the user to click on.
    For this to work, you must first register your Metadir instance in
    the developer tools in the ORCID account.
    Input: -
    Output: URL for frontend use.
    """

    auth_url = orcid_oauth_pref() + "/authorize"
    auth_url += "?response_type=code&scope=/authenticate"

    orcid_cid = conf().orcid.client_id
    orcid_redir = get_orcid_redir()

    return f"{auth_url}&client_id={orcid_cid}&redirect_uri={orcid_redir}"


def redeem_code(code: str) -> OrcidBearerToken:
    """
    Input: the 6-digit code from ORCID
    Output: Bearer token from ORCID certifying that the user logged into ORCID.
    """

    hdrs = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    dat = {
        "client_id": conf().orcid.client_id,
        "client_secret": conf().orcid.client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": get_orcid_redir(),
    }

    r = httpx.post(orcid_oauth_pref() + "/token", headers=hdrs, data=dat)
    # return r.json()
    return OrcidBearerToken.parse_obj(r.json())


def revoke_token(tok: OrcidBearerToken) -> bool:
    """Invalidate an access token. Return success value."""

    hdrs = {"Accept": "application/json"}
    dat = {
        "client_id": conf().orcid.client_id,
        "client_secret": conf().orcid.client_secret,
        "token": tok.access_token,
    }
    r = httpx.post(orcid_oauth_pref() + "/revoke", headers=hdrs, data=dat)
    if r.status_code != 200:
        print("ORCID token revoke failed! This is strange, but not a problem.")
        return False
    return True
