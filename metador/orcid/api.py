"""The routes for auth-related stuff."""

from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..log import log
from . import get_auth
from .auth import Session, SessionID
from .util import AUTH_PREF, ORCID_ENDPOINT

routes: APIRouter = APIRouter(prefix=AUTH_PREF, tags=["orcid-auth-client"])
"""Routes to be added to the app to provide the authentication flow."""


def set_paranoid_cookie(res: Response, key: str, value: str, **kwargs) -> None:
    """Set a very restrictive cookie, preventing many kinds of attacks."""
    res.set_cookie(key=key, value=value, httponly=True, samesite="strict", **kwargs)


def kill_cookie(res: Response, key: str) -> None:
    """Remove cookie by overwriting it and make it expire in a moment."""
    set_paranoid_cookie(res, key, "", max_age=2)


class AuthStatus(BaseModel):
    """
    Contains information attached to session and whether authentication is required.

    This is returned by the .../status endpoint for the client to use this information.
    """

    orcid_enabled: bool
    session: Optional[Session]


@routes.get("/status", response_model=AuthStatus)
async def get_auth_info(session_id: Optional[SessionID] = Cookie(None)):
    """Return current authentication info to the client."""
    auth = get_auth()
    return {
        "orcid_enabled": auth.orcid_conf.enabled,
        "session": auth.lookup_session(session_id),
    }


@routes.get(
    "/signout",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
)
async def sign_out(session_id: Optional[SessionID] = Cookie(None)):
    """
    Remove session as requested by user, overwriting session cookie.

    Then, redirect to homepage.
    """
    auth = get_auth()
    if session_id is not None and session_id in auth.sessions:
        log.debug(f"Removing session {session_id} by user request.")
        del auth.sessions[session_id]

    res = RedirectResponse(url="/")
    kill_cookie(res, "session_id")
    return res


@routes.get(
    ORCID_ENDPOINT,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
)
async def orcid_auth(code: Optional[str] = None, state: str = "/"):
    """
    Handle ORCID three-legged authentication.

    If no code is given, redirect to configured ORCID server.

    If code given, swap code to get authenticated ORCID of user,
    revoke the token and give out a classical Session ID in cookie instead.

    The optional state query parameter is used by the UI to remember
    the current location when clicking the Sign-in button.
    The ORCID servers pass it back to us, and we can redirect back.

    If no state given, redirection is back to homepage, otherwise to given route.
    """
    auth = get_auth()

    # no code -> redirect to orcid, which redirects back with code
    if code is None or code == "":
        return RedirectResponse(url=auth.userauth_url(state))

    # this should give us a valid token, that we revoke immediately (we don't need it)
    orcidbearer = await auth.redeem_code(code)
    await auth.revoke_token(orcidbearer)  # revoke token (if it fails, does not matter)

    allow_list = auth.allow_list
    if allow_list is not None and orcidbearer.orcid not in allow_list:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"ORCID {orcidbearer.orcid} is not allowed to use this service. "
            "Please ask the administrator to give you access.",
        )

    session_id = auth.new_session(orcidbearer)
    log.debug(f"New session: {session_id} -> {auth.sessions[session_id]}")

    res = RedirectResponse(url=state)
    maxage = auth.orcid_conf.auth_expire_after * 60
    set_paranoid_cookie(
        res,
        "session_id",
        str(session_id),
        max_age=maxage,
        secure=auth.site_prefix[:6] == "https",  # set "secure" if we're on https
    )
    return res


# must come last
@routes.get("/{anything_else:path}")
async def orcid_catch_all():
    """Catch-all redirect."""
    return Response(
        "Endpoint not found", status_code=status.HTTP_405_METHOD_NOT_ALLOWED
    )
