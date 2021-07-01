import asyncio
import socket
from typing import List, Optional

import uvicorn


# https://gist.github.com/gabrielfalcao/20e567e188f588b65ba2
def get_free_tcp_port() -> int:
    """Get a free port to bind to (this has a race condition, but it does not matter)."""

    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    tcp.bind(("", 0))
    port = tcp.getsockname()
    tcp.close()
    return port[1]


# As the auth flow needs an ORCID server that responds to our backend,
# we need to actually run a server for that ORCID mock routes.
#
# from https://stackoverflow.com/questions
#      /57412825/how-to-start-a-uvicorn-fastapi-in-background-when-testing-with-pytest
class UvicornTestServer(uvicorn.Server):
    """Uvicorn test server

    Usage:
        @pytest.fixture
        server = UvicornTestServer()
        await server.up()
        yield
        await server.down()
    """

    def __init__(self, app, host="127.0.0.1", port=8000):
        """Create a Uvicorn test server

        Args:
            app (FastAPI, optional): the FastAPI app. Defaults to main.app.
            host (str, optional): the host ip. Defaults to '127.0.0.1'.
            port (int, optional): the port. Defaults to PORT.
        """
        self._startup_done = asyncio.Event()
        super().__init__(config=uvicorn.Config(app, host=host, port=port))

    async def startup(self, sockets: Optional[List] = None) -> None:
        """Override uvicorn startup"""
        await super().startup(sockets=sockets)
        self.config.setup_event_loop()
        self._startup_done.set()

    async def up(self) -> None:
        """Start up server asynchronously"""
        self._serve_task = asyncio.create_task(self.serve())
        await self._startup_done.wait()

    async def down(self) -> None:
        """Shut down server asynchronously"""
        self.should_exit = True
        await self._serve_task
