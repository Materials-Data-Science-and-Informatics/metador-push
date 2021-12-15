"""Helpers for the tests."""

import asyncio
import socket
from contextlib import closing
from typing import Any, Callable, List, Optional, TypeVar

import uvicorn


# https://gist.github.com/gabrielfalcao/20e567e188f588b65ba2
def get_free_tcp_port() -> int:
    """Get a free port to bind to (this has a race condition, but it does not matter)."""
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    tcp.bind(("127.0.0.1", 0))
    port = tcp.getsockname()
    tcp.close()
    return port[1]


# adapted from https://stackoverflow.com/a/35370008/432908
def can_connect(host, port):
    """Check that given host:port combination is listening for clients."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((host, port)) == 0


# As the auth flow needs an ORCID server that responds to our backend,
# we need to actually run a server for that ORCID mock routes.
#
# from https://stackoverflow.com/questions
#      /57412825/how-to-start-a-uvicorn-fastapi-in-background-when-testing-with-pytest
class UvicornTestServer(uvicorn.Server):
    """Uvicorn test server.

    Usage:
        @pytest.fixture
        server = UvicornTestServer()
        await server.up()
        yield
        await server.down()
    """

    def __init__(self, app, host="127.0.0.1", port=8000):
        """Create a Uvicorn test server.

        Args:
            app (FastAPI, optional): the FastAPI app. Defaults to main.app.
            host (str, optional): the host ip. Defaults to '127.0.0.1'.
            port (int, optional): the port. Defaults to PORT.
        """
        self._startup_done = asyncio.Event()
        super().__init__(config=uvicorn.Config(app, host=host, port=port))

    async def startup(self, sockets: Optional[List] = None) -> None:
        """Override uvicorn startup."""
        await super().startup(sockets=sockets)
        self.config.setup_event_loop()
        self._startup_done.set()

    async def up(self) -> None:
        """Start up server asynchronously."""
        self._serve_task = asyncio.create_task(self.serve())
        await self._startup_done.wait()

    async def down(self) -> None:
        """Shut down server asynchronously."""
        self.should_exit = True
        await self._serve_task


T = TypeVar("T")


async def with_retries(
    f: Callable[[], Optional[T]],
    num_retry: Optional[int] = 3,
    sleep_before_retry: float = 0.1,
) -> Optional[T]:
    """
    Try getting value from f, with possibility to retry a number of times.

    If num_retry is None, will retry until success, with sleep in between.
    """
    ret: Optional[T] = None
    while num_retry is None or num_retry > 0:
        ret = f()
        if ret is not None:
            return ret
        else:
            await asyncio.sleep(sleep_before_retry)
            if num_retry is not None:
                num_retry -= 1
    return ret


async def wait_until(pred: Callable[[], bool], *args) -> bool:
    """Repeatedly check a predicate until it is satisfied or number of retries exceeded."""
    ret = await with_retries(lambda: True if pred() else None, *args)
    return ret if ret else False


async def get_with_retries(q: asyncio.Queue, *args) -> Optional[Any]:
    """Repeatedly try reading from a Queue with retries and sleep in between."""

    def try_to_get() -> Optional[Any]:
        try:
            return q.get_nowait()
        except asyncio.QueueEmpty:
            return None

    return await with_retries(try_to_get, *args)


class AsyncLiveStream:
    """Helper to read output from running asyncio subprocesses."""

    q: asyncio.Queue
    """Queue to store lines from process."""

    t: asyncio.Task
    """Running task shoveling lines from process into queue."""

    def __init__(self, stream: asyncio.StreamReader):
        """Initialize a async task to pump lines from the stream."""
        self.q = asyncio.Queue()
        self.t = asyncio.create_task(self._enqueue_output())
        self.stream = stream

    async def _enqueue_output(self):
        """Read lines and put into queue."""
        while True:
            line = await self.stream.readline()
            await self.q.put(line.decode("utf-8"))

    async def readlines_nonblock(self) -> List[str]:
        """Return lines currently in the queue until it is empty."""
        lines: List[str] = []
        while not self.q.empty():
            try:
                line = await self.q.get()
                lines.append(line)
                self.q.task_done()
            except asyncio.QueueEmpty:
                break
        return lines

    async def readlines_until(
        self, predicate: Callable[[str], bool], timeout: int
    ) -> List[str]:
        """Read lines into queue until a timeout happens or predicate is satisfied."""
        lines: List[str] = []
        while not self.q.empty():
            try:
                line = await asyncio.wait_for(self.q.get(), timeout)
                lines.append(line)
                self.q.task_done()
            except asyncio.QueueEmpty:
                break
            if predicate(lines[-1]):  # predicate satisfied
                break
        return lines
