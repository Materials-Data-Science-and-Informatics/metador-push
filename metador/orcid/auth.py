"""
Module for ORCID authentication, implemented based on the official integration guide.

The guide can be found here:
https://info.orcid.org/documentation/api-tutorials/api-tutorial-get-and-authenticated-orcid-id/

This module performs the 3-legged auth and then exchanges the authenticated ORCID for a
plain old user session. Common wisdom says that JWT should not be used for sessions.
Furthermore, the crypto makes everything more complicated. Sessions via cookies are fine.

This module supports the official production+sandbox servers and the mock server.

This module does not directly rely on Metador-specifics to simplify reuse.
"""

import re
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Dict, Final, List, Literal, NewType, Optional

import httpx
from pydantic import (
    BaseModel,
    DirectoryPath,
    Extra,
    Field,
    FilePath,
    validate_arguments,
)

from ..log import log
from .util import orcid_redir, orcid_server_pref

#: Regex matching an ORCID
ORCID_PAT: str = r"\d{4}-\d{4}-\d{4}-\d{4}"

#: Type alias for Pydantic checks
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
    expires: datetime
    orcid: OrcidStr
    user_name: str


class Sessions(BaseModel):
    """Wrapper class purely existing for serialization."""

    __root__: Dict[SessionID, Session]


class OrcidConf(BaseModel):
    """Configuration of ORCID authentication."""

    class Config:
        #: complain about unknown fields (likely a mistake!)
        extra = Extra.forbid

    #: is authentication enabled?
    enabled: bool = False

    #: use sandbox ORCID servers? use production server if False
    sandbox: bool = False

    #: use fake mock servers? (overrides sandbox setting)
    use_fake: bool = False

    #: ORCID API credentials: registered ID
    client_id: str = ""
    #: ORCID API credentials: the corresponding secret
    client_secret: str = ""

    #: minutes after which the session expires
    auth_expire_after: int = 180

    #: Filename of ORCID whitelist (one ORCID per line).
    #  If not provided, every authentic ORCID is accepted.
    allowlist_file: Optional[FilePath] = None


def load_allowlist(filename: Optional[str]) -> Optional[List[OrcidStr]]:
    """
    Load list of ORCIDs that should be allowed to sign in.

    Assumes that the provided path to the allowlist file exists
    (should be checked before).
    """

    if filename is None or filename == "":
        return None

    lines: List[str] = []
    with open(filename, "r") as file:
        lines = file.readlines()

    stripped = list(map(str.strip, lines))
    nonempty = list(filter(lambda x: x != "", stripped))
    noncommented = list(filter(lambda x: x[0] != "#", nonempty))
    invalid = list(filter(lambda oid: not re.match(ORCID_PAT, oid), noncommented))
    if len(invalid) > 0:
        log.critical(ValueError(f"Invalid ORCIDs in allow list: {invalid}"))
        sys.exit(1)
    return noncommented


class Auth:

    PERSIST_FILE: Final[str] = "active_sessions.json"

    @validate_arguments
    def __init__(
        self, site: str, conf: OrcidConf, persist_dir: Optional[DirectoryPath] = None
    ):
        """
        Initialize authorization management.

        Takes the site prefix (passed from main config, needed for correct back-redirect),
        the Orcid specific conf (which servers to use, expiry times, etc),
        and the directory where the session is presisted on server restarts.
        """

        #: global in-memory session storage. Only access through lookup_session!
        self.sessions: Dict[SessionID, Session] = {}

        #: From main app config. We need that actually only for the mock server.
        self.site_prefix: str = site

        #: Provided orcid-specific config.
        self.orcid_conf: OrcidConf = conf

        #: Directory where the sessions are persisted between server restarts.
        self.persist_dir: Optional[Path] = None
        if persist_dir:
            self.persist_dir = persist_dir
            self.load_sessions()

        #: List of permitted ORCIDs.
        #  If None, every ORCID is allowed. If empty list, all ORCIDs are forbidden.
        self.allow_list: Optional[List[str]] = None

        if conf.allowlist_file:
            self.allow_list = load_allowlist(str(conf.allowlist_file))

    # functions handling actual ORCID business

    def orcid_server_pref(self) -> str:
        """
        Convenience wrapper. Calls the actual prefix function with params.
        """

        sandbox = self.orcid_conf.sandbox
        use_fake = self.orcid_conf.use_fake
        return orcid_server_pref(sandbox, self.site_prefix if use_fake else None)

    def userauth_url(self, state: Optional[str] = None) -> str:
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
        redir = orcid_redir(self.site_prefix)
        opt_state = f"&state={state}" if state else ""

        return f"{auth_url}{opt_state}&client_id={orcid_cid}&redirect_uri={redir}"

    async def redeem_code(self, code: str) -> OrcidBearerToken:
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
            "redirect_uri": orcid_redir(self.site_prefix),
        }

        async with httpx.AsyncClient() as client:
            r = await client.post(
                self.orcid_server_pref() + "/token",
                headers=hdrs,
                data=dat,
            )
        return OrcidBearerToken.parse_obj(r.json())

    async def revoke_token(self, tok: OrcidBearerToken) -> bool:
        """Invalidate an access token. Return success value."""

        hdrs = {"Accept": "application/json"}
        dat = {
            "client_id": self.orcid_conf.client_id,
            "client_secret": self.orcid_conf.client_secret,
            "token": tok.access_token,
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self.orcid_server_pref() + "/revoke",
                headers=hdrs,
                data=dat,
            )
        if 200 <= r.status_code < 300:
            return True
        return False

    ####

    def new_session(self, tok: OrcidBearerToken) -> SessionID:
        """
        From ORCID token, generate a new session with timestamp.

        Store it, return the SessionID.
        """

        session_id = SessionID(secrets.token_urlsafe(32))
        while session_id in self.sessions:  # just to be really sure...
            session_id = SessionID(secrets.token_urlsafe(32))

        now = datetime.today()
        self.sessions[session_id] = Session(
            created=now,
            expires=now + timedelta(minutes=self.orcid_conf.auth_expire_after),
            orcid=tok.orcid,
            user_name=tok.name,
        )
        return session_id

    ####

    def persist_file_path(self) -> Optional[Path]:
        if self.persist_dir is None:
            return None
        return self.persist_dir / self.PERSIST_FILE

    def load_sessions(self) -> None:
        """If persistence directory specified, try to load sessions."""
        fname = self.persist_file_path()
        if not fname:
            log.debug("Session serialization is not enabled.")
            return

        if not fname.is_file():
            log.debug("No serialized session file.")
            return

        log.info(f"Restoring serialized sessions from {fname}")
        self.sessions = Sessions.parse_file(fname).__root__

    def dump_sessions(self) -> None:
        """
        If persistence directory specified, dump current sessions to file.

        This should be called on shutdown of the app.
        """

        fname = self.persist_file_path()
        if not fname:
            log.info("No persistence directory given, nothing to do.")
            return

        log.info(f"Serializing sessions to {fname}")
        serialized = Sessions(__root__=self.sessions).json()
        with open(fname, "w") as file:
            file.write(serialized)
            file.flush()

    def lookup_session(self, session_id: Optional[SessionID]) -> Optional[Session]:
        """
        Given a session id, return session if it is still valid.

        Otherwise, the session is removed from list (expired, not allowed, etc.).
        """

        if session_id is None or session_id == "":  # no session id passed
            return None

        sess_id = SessionID(session_id)

        if sess_id not in self.sessions:  # session id not in list
            log.debug(f"Ignoring invalid session {sess_id}.")
            return None

        session = self.sessions[sess_id]

        age = (session.expires - datetime.today()).total_seconds() <= 0
        if age > self.orcid_conf.auth_expire_after:  # too old
            log.debug(f"Removing expired session {sess_id}.")
            del self.sessions[sess_id]
            return None

        # also check the allow list, it might have changed (e.g. server restart)
        if self.allow_list is not None and session.orcid not in self.allow_list:
            log.debug(f"Removing session {sess_id} by not allowed user.")
            del self.sessions[sess_id]
            return None

        return session
