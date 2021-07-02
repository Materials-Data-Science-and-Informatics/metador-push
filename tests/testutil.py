import asyncio
import socket
from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable, List, Optional

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


# Live stdout streaming subprocess, based on
# https://www.semicolonworld.com/question/42796/non-blocking-read-on-a-subprocess-pipe-in-python
#
# TODO: Maybe rewrite this to asyncio to have use just one concurrency mechanism.
# But replacing it naively with create_task instead of thread leads to problems :/


class NonblockingStream:
    """Helper to read output from running processes."""

    q: Queue
    """Queue to store lines from process."""

    def __init__(self, stream):
        self.q = Queue()
        self.stream = stream
        t = Thread(target=self._enqueue_output)
        t.daemon = True
        t.start()

    def _enqueue_output(self):
        """Helper. Read lines and put into queue, until stream ends."""
        for line in iter(self.stream.readline, ""):
            self.q.put(line)
        self.stream.close()

    def readlines_nonblock(self) -> List[str]:
        """Return lines currently in the queue until it is empty."""

        lines = []
        while not self.q.empty():
            try:
                lines.append(self.q.get_nowait())
            except Empty:
                break
        return lines

    def readlines_until(self, f, timeout) -> List[str]:
        """
        Read lines in the queue until a read is too long (timeout)
        or the predicate is satisfied.
        """

        lines = []
        while not self.q.empty():
            try:
                lines.append(self.q.get(timeout=timeout))
            except Empty:
                break
            if f(lines[-1]):  # predicate satisfied
                break
        return lines


async def wait_until(
    f: Callable[[], bool], num_retry: Optional[int] = 3, sleep_before_retry: float = 0.1
) -> bool:
    """Repeatedly check a predicate until it is satisfied or number of retries exceeded."""

    while num_retry is None or num_retry > 0:
        if f():
            return True
        else:
            await asyncio.sleep(sleep_before_retry)
            if num_retry is not None:
                num_retry -= 1
    return False


async def get_with_retries(
    q: Queue, num_retry: Optional[int] = 3, sleep_before_retry: float = 0.1
) -> Optional[Any]:
    """
    Try reading from a Queue, with possibility to retry a number of times.
    If num_retry is None, will retry until success, with sleep in between.
    """

    ret = None
    while num_retry is None or num_retry > 0:
        try:
            ret = q.get_nowait()
            return ret
        except Empty:
            await asyncio.sleep(sleep_before_retry)
            if num_retry is not None:
                num_retry -= 1
    return ret
