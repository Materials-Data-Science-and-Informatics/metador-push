from typing import Optional

from fastapi import Cookie, HTTPException, status

from .auth import Auth, Session, SessionID

_auth = None
"""Var for singleton instance of Auth."""


def init_auth(*args, **kwargs) -> None:
    """Initialize Auth singleton."""

    global _auth
    _auth = Auth(*args, **kwargs)


def get_auth() -> Auth:
    """Return singleton Auth instance."""

    global _auth
    if _auth is None:
        raise RuntimeError("Auth singleton not initialized!")

    return _auth


####
# helpers for FastAPI to be used as Depends(...)


def get_session(session_id: Optional[SessionID] = Cookie(None)) -> Optional[Session]:
    """
    Checks out session (if available) and returns it, if cookie is set.

    Returns 403 automatically if no valid session + authentication is enabled.
    """

    auth = get_auth()
    session = auth.lookup_session(session_id)
    if auth.orcid_conf.enabled and session is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please sign in to access this page.",
        )
    return session
