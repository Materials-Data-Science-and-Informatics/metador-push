"""
Module for ORCID authentication, implemented based on the official integration guide.

The guide can be found here:
https://info.orcid.org/documentation/api-tutorials/api-tutorial-get-and-authenticated-orcid-id/

This module performs the 3-legged auth and then exchanges the authenticated ORCID for a
plain old user session. Common wisdom says that JWT should not be used for sessions.
Furthermore, the crypto makes everything more complicated. Sessions via cookies are fine.

This module supports the official production+sandbox servers and provides a mock server.
"""

import os
import sys
import re
from datetime import datetime
from typing import Literal, Optional, Dict, Annotated, Final, List, NewType
import secrets

from pydantic import (
    BaseModel,
    Field,
    FilePath,
    DirectoryPath,
    Extra,
    validate_arguments,
)
import httpx
from fastapi import APIRouter, Cookie, status, HTTPException, Depends, Response
from fastapi.responses import RedirectResponse

from .log import log

# Type alias for Pydantic checks
ORCID_PAT: str = r"\d{4}-\d{4}-\d{4}-\d{4}"
OrcidStr = Annotated[str, Field(regex=ORCID_PAT)]


class OrcidBearerToken(BaseModel):
    """A OAuth token as returned by ORCID servers."""

    token_type: Literal["bearer"]
    scope: Literal["/authenticate"]
    access_token: str
    refresh_token: str
    expires_in: int

    name: str
    orcid: OrcidStr


SessionID = NewType("SessionID", str)


class Session(BaseModel):
    """
    Our simple session after a user completed ORCID Auth.

    It just represents the fact that a user signed in successfully via ORCID
    at the specified point in time. We can decide to invalidate the session
    based on a configurable time-out.
    """

    created: datetime
    orcid: OrcidStr
    user_name: str


class Sessions(BaseModel):
    __root__: Dict[SessionID, Session]


class AuthStatus(BaseModel):
    """
    Contains information attached to session and whether authentication is required.

    This is returned by the .../status endpoint for the client to use this information.
    """

    orcid_enabled: bool
    session: Optional[Session]


class OrcidConf(BaseModel):
    """Configuration of ORCID authentication."""

    class Config:
        extra = Extra.forbid  # complain about unknown fields (likely a mistake!)

    # is authentication enabled?
    enabled: bool = False

    # use sandbox ORCID servers? use production server if False
    sandbox: bool = False

    # use fake mock servers? (overrides sandbox setting)
    use_fake: bool = False

    # API credentials
    client_id: str = ""
    client_secret: str = ""

    # minutes after which the session expires
    auth_expire_after: int = 180

    # whitelist filename
    allowlist_file: Optional[FilePath] = None


# This is for testing. Ignores everything and just plays along.
MOCK_ORCID_ENDPOINT = "/fakeid"
mock_orcid = APIRouter(prefix=MOCK_ORCID_ENDPOINT)


@mock_orcid.get(
    "/authorize",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
)
def mock_orcid_authorize(redirect_uri: str):
    """Redirects back to given URI with a dummy code added as query parameter."""
    return RedirectResponse(url=redirect_uri + "?code=123456")


@mock_orcid.post("/revoke", status_code=status.HTTP_204_NO_CONTENT)
def mock_orcid_revoke():
    """Does nothing."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@mock_orcid.post("/token", response_model=OrcidBearerToken)
def mock_orcid_token():
    """Returns dummy token."""
    return OrcidBearerToken(
        token_type="bearer",
        scope="/authenticate",
        access_token="my-access-token",
        refresh_token="my-refresh-token",
        expires_in=10000,
        name="Doctor Who",
        orcid="0123-4567-8910-1337",
    )


def orcid_server_pref(sandbox: bool, fake_pref: Optional[str] = None) -> str:
    """
    Returns the oauth API entry point with or without sandbox, depending on config.

    When fake_pref is set to a the base site prefix (it must be something starting with
    http(s)://...), it returns the site with the appended minimal mock prefix.
    (Add mock_orcid to your FastAPI routes for it to work!)
    """

    if fake_pref:  # if given, we want to use our own fake-server for testing
        return fake_pref + MOCK_ORCID_ENDPOINT

    # use one of the two real servers
    sbx = "sandbox." if sandbox else ""
    return f"https://{sbx}orcid.org/oauth"


def load_allowlist(filename: Optional[str]) -> Optional[List[OrcidStr]]:
    """
    Load list of ORCIDs that should be allowed to sign in.

    Assumes that the provided path to the allowlist file exists
    (should be checked before).
    """

    if filename is None or filename == "":
        return None

    stripped = list(map(str.strip, open(filename, "r").readlines()))
    nonempty = list(filter(lambda x: x != "", stripped))
    noncommented = list(filter(lambda x: x[0] != "#", nonempty))
    invalid = list(filter(lambda oid: not re.match(ORCID_PAT, oid), noncommented))
    if len(invalid) > 0:
        log.critical(ValueError(f"Invalid ORCIDs in allow list: {invalid}"))
        sys.exit(1)
    return noncommented


def set_paranoid_cookie(res: Response, key: str, value: str, **kwargs) -> None:
    """Set a very restrictive cookie, preventing many kinds of attacks."""

    res.set_cookie(
        key=key, value=value, httponly=True, secure=True, samesite="strict", **kwargs
    )


def kill_cookie(res: Response, key: str) -> None:
    """Remove cookie by overwriting it and make it expire in a moment."""

    set_paranoid_cookie(res, key, "", max_age=2)


class Auth:
    PERSIST_FILE: Final[str] = "active_sessions.json"

    # route prefix for all auth-related things
    AUTH_PREF: Final[str] = "/oauth"

    # endpoint for auth redirection (both from app and ORCID service)
    ORCID_ENDPOINT: Final[str] = "/orcid"

    # global in-memory session storage
    sessions: Dict[SessionID, Session] = {}

    # routes to be added to the app
    routes: APIRouter = APIRouter(prefix=AUTH_PREF)

    # List of permitted ORCIDs.
    # If None, every ORCID is allowed. If empty list, all ORCIDs are forbidden.
    allow_list: Optional[List[str]] = None

    # provided orcid-specific config
    orcid_conf: OrcidConf
    # from main app config. we need that actually only for the mock server
    site_prefix: str
    # also from main app config. will persist/restore persistence file there
    persist_dir: Optional[str] = None

    # functions handling actual ORCID business

    def get_orcid_redir(self) -> str:
        """
        Returns a path that is supposed te be registered
        as a valid redirect for use with the ORCID API client credentials.
        """

        return self.site_prefix + self.AUTH_PREF + self.ORCID_ENDPOINT

    def orcid_server_pref(self) -> str:
        """
        Convenience wrapper. Calls the actual prefix function with params.
        """

        sandbox = self.orcid_conf.sandbox
        use_fake = self.orcid_conf.use_fake
        return orcid_server_pref(sandbox, self.site_prefix if use_fake else None)

    def userauth_url(self) -> str:
        """
        Construct an URL for login via ORCID for the user to click on.
        For this to work, you must first register your Metadir instance in
        the developer tools in the ORCID account.
        Input: -
        Output: URL for frontend use.
        """

        auth_url = self.orcid_server_pref() + "/authorize"
        auth_url += "?response_type=code&scope=/authenticate"

        orcid_cid = self.orcid_conf.client_id
        orcid_redir = self.get_orcid_redir()

        return f"{auth_url}&client_id={orcid_cid}&redirect_uri={orcid_redir}"

    def redeem_code(self, code: str) -> OrcidBearerToken:
        """
        Input: the 6-digit code from ORCID
        Output: Bearer token from ORCID certifying that the user logged into ORCID.
        """

        hdrs = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        dat = {
            "client_id": self.orcid_conf.client_id,
            "client_secret": self.orcid_conf.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.get_orcid_redir(),
        }

        r = httpx.post(
            self.orcid_server_pref() + "/token",
            headers=hdrs,
            data=dat,
        )
        return OrcidBearerToken.parse_obj(r.json())

    def revoke_token(self, tok: OrcidBearerToken) -> bool:
        """Invalidate an access token. Return success value."""

        hdrs = {"Accept": "application/json"}
        dat = {
            "client_id": self.orcid_conf.client_id,
            "client_secret": self.orcid_conf.client_secret,
            "token": tok.access_token,
        }
        r = httpx.post(
            self.orcid_server_pref() + "/revoke",
            headers=hdrs,
            data=dat,
        )
        if r.status_code != 200:
            log.warning("ORCID token revoke failed! Strange, but not a problem.")
            return False
        return True

    # create, dump and load session store

    def new_session(self, tok: OrcidBearerToken) -> SessionID:
        """
        From ORCID token, generate a new session with timestamp.

        Store it, return the SessionID.
        """

        session_id = SessionID(secrets.token_urlsafe(32))
        while session_id in self.sessions:  # just to be really sure...
            session_id = SessionID(secrets.token_urlsafe(32))

        self.sessions[session_id] = Session(
            created=datetime.today(), orcid=tok.orcid, user_name=tok.name
        )
        return session_id

    # helpers for FastAPI to be used as Depends(...)

    def maybe_session(
        self, session_id: Optional[SessionID] = Cookie(None)
    ) -> Optional[Session]:
        """
        Given a session id cookie, return session if it is still valid.

        Otherwise, the session is removed from list (expired, not allowed, etc.).
        """

        if session_id is None or session_id == "":  # no session id passed
            return None

        sess_id = SessionID(session_id)

        if sess_id not in self.sessions:  # session id not in list
            log.debug(f"Ignoring invalid session {sess_id}.")
            return None

        session = self.sessions[sess_id]

        age = (datetime.today() - session.created).total_seconds() / 60
        if age > self.orcid_conf.auth_expire_after:  # too old
            log.debug(f"Removing expired session {sess_id}.")
            del self.sessions[sess_id]
            return None

        # also check the allow list, it might have changed
        if self.allow_list is not None and session.orcid not in self.allow_list:
            log.debug(f"Removing session {sess_id} by not allowed user.")
            del self.sessions[sess_id]
            return None

        return session

    def get_session(
        self, session_id: Optional[SessionID] = Cookie(None)
    ) -> Optional[Session]:
        """Like maybe_session, but returns 403 automatically if not valid and
        authentication is enabled."""

        session = self.maybe_session(session_id)
        if self.orcid_conf.enabled and session is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please sign in to access this page.",
            )
        return session

    def persist_file(self) -> Optional[str]:
        if self.persist_dir is None:
            return None
        return os.path.join(self.persist_dir, self.PERSIST_FILE)

    def load_sessions(self) -> None:
        """If persistence directory specified, try to load sessions."""
        fname = self.persist_file()
        if not fname:
            log.debug("Session serialization is not enabled.")
            return

        if not os.path.isfile(fname):
            log.debug("No serialized session file.")
            return

        log.info(f"Restoring serialized sessions from {fname}")
        self.sessions = Sessions.parse_file(fname).__root__

    def dump_sessions(self) -> None:
        """
        If persistence directory specified, dump current sessions to file.

        This should be called on shutdown of the app.
        """

        fname = self.persist_file()
        if not fname:
            return

        log.info(f"Serializing sessions to {fname}")
        serialized = Sessions(__root__=self.sessions).json()
        with open(fname, "w") as file:
            file.write(serialized)
            file.flush()

    @validate_arguments
    def __init__(
        self, site: str, conf: OrcidConf, persist_dir: Optional[DirectoryPath] = None
    ):
        """
        Initialize authorization routes.

        Takes the site (from main config) the Orcid specific conf
        and the directory where the session is presisted on restarts.
        """

        self.site_prefix = site
        self.orcid_conf = conf

        if conf.allowlist_file:
            self.allow_list = load_allowlist(str(conf.allowlist_file))

        if persist_dir:
            self.persist_dir = str(persist_dir)
            self.load_sessions()

        @self.routes.get("/status", response_model=AuthStatus)
        async def get_auth_info(session: Session = Depends(self.maybe_session)):
            """Return current authentication info to the client."""

            return {"orcid_enabled": self.orcid_conf.enabled, "session": session}

        @self.routes.get(
            "/signout",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            response_class=RedirectResponse,
        )
        async def sign_out(session_id: Optional[SessionID] = Cookie(None)):
            """
            Remove session as requested by user, overwriting session cookie.

            Then, redirect to homepage.
            """

            if session_id is not None and session_id in self.sessions:
                log.debug(f"Removing session {session_id} by user request.")
                del self.sessions[session_id]

            res = RedirectResponse(url="/")
            kill_cookie(res, "session_id")
            return res

        @self.routes.get(
            self.ORCID_ENDPOINT,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            response_class=RedirectResponse,
        )
        def orcid_auth(code: Optional[str] = None):
            """
            Main endpoint for ORCID authentication.

            If no code is given, redirect to configured ORCID server.

            If code given, swap code to get authenticated ORCID of user,
            revoke the token and give out a classical Session ID in cookie instead.

            Then, redirect to homepage.
            """
            # no code -> redirect to orcid, which redirects back with code
            if code is None or code == "":
                return RedirectResponse(url=self.userauth_url())

            # this should give us a valid token, that we revoke immediately (we don't need it)
            orcidbearer = self.redeem_code(code)
            self.revoke_token(orcidbearer)

            allow_list = self.allow_list
            if allow_list is not None and orcidbearer.orcid not in allow_list:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"ORCID {orcidbearer.orcid} is not allowed to use this service. "
                    "Please ask the administrator to give you access.",
                )

            session_id = self.new_session(orcidbearer)
            log.debug(f"New session: {session_id} -> {self.sessions[session_id]}")

            res = RedirectResponse(url="/")
            maxage = self.orcid_conf.auth_expire_after * 60
            set_paranoid_cookie(res, "session_id", str(session_id), max_age=maxage)
            return res
