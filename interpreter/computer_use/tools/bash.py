import asyncio
import os
import pty
import sys
from typing import ClassVar, Literal

import pyte
from anthropic.types.beta import BetaToolBash20241022Param

from .base import BaseAnthropicTool, CLIResult, ToolError, ToolResult


class _BashSession:
    """A session of a bash shell."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "/bin/bash"
    _output_delay: float = 0.2  # seconds
    _timeout: float = 120.0  # seconds
    _sentinel: str = "<<exit>>"

    def __init__(self):
        self._started = False
        self._timed_out = False
        # Create a terminal screen and stream
        self._screen = pyte.Screen(80, 24)  # Standard terminal size
        self._stream = pyte.Stream(self._screen)

    async def start(self):
        if self._started:
            return

        try:
            # Try to create process with PTY
            master, slave = pty.openpty()
            self._process = await asyncio.create_subprocess_shell(
                self.command,
                preexec_fn=os.setsid,
                shell=True,
                bufsize=0,
                stdin=asyncio.subprocess.PIPE,
                stdout=slave,
                stderr=slave,
            )
            # Store master fd for reading
            self._master_fd = master
            self._using_pty = True
            print("using pty")
        except (ImportError, OSError):
            print("using pipes")
            # Fall back to regular pipes if PTY is not available
            self._process = await asyncio.create_subprocess_shell(
                self.command,
                preexec_fn=os.setsid,
                shell=True,
                bufsize=0,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._using_pty = False

        self._started = True

    def stop(self):
        """Terminate the bash shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return
        self._process.terminate()
        if hasattr(self, "_master_fd"):
            os.close(self._master_fd)

    async def run(self, command: str):
        """Execute a command in the bash shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return ToolResult(
                system="tool must be restarted",
                error=f"bash has exited with returncode {self._process.returncode}",
            )
        if self._timed_out:
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            )

        # we know these are not None because we created the process with PIPEs
        assert self._process.stdin

        # send command to the process
        self._process.stdin.write(
            command.encode() + f"; echo '{self._sentinel}'\n".encode()
        )
        await self._process.stdin.drain()

        try:
            async with asyncio.timeout(self._timeout):
                if self._using_pty:
                    # Reset screen state
                    self._screen.reset()
                    output = ""
                    while True:
                        try:
                            raw_chunk = os.read(self._master_fd, 1024)
                            chunk_str = raw_chunk.decode()

                            # Update output before checking sentinel
                            output += chunk_str

                            # Check for sentinel
                            if self._sentinel in chunk_str:
                                # Clean the output for display
                                clean_chunk = chunk_str[
                                    : chunk_str.index(self._sentinel)
                                ].encode()
                                if clean_chunk:
                                    os.write(sys.stdout.fileno(), clean_chunk)
                                # Clean the stored output
                                if self._sentinel in output:
                                    output = output[: output.index(self._sentinel)]
                                break

                            os.write(sys.stdout.fileno(), raw_chunk)
                        except OSError:
                            break
                        await asyncio.sleep(0.01)
                    error = ""
                else:
                    # Real-time output for pipe-based reading
                    output = ""
                    while True:
                        chunk = await self._process.stdout.read(1024)
                        if not chunk:
                            break
                        chunk_str = chunk.decode()
                        output += chunk_str

                        # Check for sentinel
                        if self._sentinel in chunk_str:
                            # Clean the chunk for display
                            clean_chunk = chunk_str[
                                : chunk_str.index(self._sentinel)
                            ].encode()
                            if clean_chunk:
                                os.write(sys.stdout.fileno(), clean_chunk)
                            # Clean the stored output
                            if self._sentinel in output:
                                output = output[: output.index(self._sentinel)]
                            break

                        os.write(sys.stdout.fileno(), chunk)
                        await asyncio.sleep(0.01)
        except asyncio.TimeoutError:
            self._timed_out = True
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            ) from None

        if output.endswith("\n"):
            output = output[:-1]
        if not self._using_pty and error.endswith("\n"):
            error = error[:-1]

        # Clear buffers only when using pipes
        if not self._using_pty:
            self._process.stdout._buffer.clear()
            self._process.stderr._buffer.clear()

        return CLIResult(output=output, error=error)

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Remove ANSI escape sequences from text."""
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)


class BashTool(BaseAnthropicTool):
    """
    A tool that allows the agent to run bash commands.
    The tool parameters are defined by Anthropic and are not editable.
    """

    _session: _BashSession | None
    name: ClassVar[Literal["bash"]] = "bash"
    api_type: ClassVar[Literal["bash_20241022"]] = "bash_20241022"

    def __init__(self):
        self._session = None
        super().__init__()

    async def __call__(
        self, command: str | None = None, restart: bool = False, **kwargs
    ):
        if restart:
            if self._session:
                self._session.stop()
            self._session = _BashSession()
            await self._session.start()

            return ToolResult(system="tool has been restarted.")

        if self._session is None:
            self._session = _BashSession()
            await self._session.start()

        if command is not None:
            return await self._session.run(command)

        raise ToolError("no command provided.")

    def to_params(self) -> BetaToolBash20241022Param:
        return {
            "type": self.api_type,
            "name": self.name,
        }
