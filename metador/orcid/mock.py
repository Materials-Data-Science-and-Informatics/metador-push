"""
A mock ORCID server implementation. It just plays along with signin process.
"""

from typing import Optional

from fastapi import APIRouter, status, Response
from fastapi.responses import RedirectResponse
from .auth import OrcidBearerToken
from .util import MOCK_ORCID_ENDPOINT

routes = APIRouter(prefix=MOCK_ORCID_ENDPOINT, tags=["orcid-server-mock"])


@routes.get(
    "/authorize",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
)
def mock_orcid_authorize(redirect_uri: str, state: Optional[str] = None):
    """Redirects back to given URI with a dummy code added as query parameter."""

    st_param = "" if not state else f"&state={state}"
    return RedirectResponse(url=redirect_uri + f"?code=123456{st_param}")


@routes.post("/revoke", status_code=status.HTTP_204_NO_CONTENT)
def mock_orcid_revoke():
    """Does nothing."""

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@routes.post("/token", response_model=OrcidBearerToken)
def mock_orcid_token():
    """Returns dummy token to sign in as a dummy user."""

    return OrcidBearerToken(
        token_type="bearer",
        scope="/authenticate",
        access_token="my-access-token",
        refresh_token="my-refresh-token",
        expires_in=10000,
        name="Doctor Who",
        orcid="0123-4567-8910-1337",
    )
