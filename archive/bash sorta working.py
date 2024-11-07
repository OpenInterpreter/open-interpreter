import asyncio
import os
import pty
import signal
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
        self._screen = pyte.Screen(80, 24)
        self._stream = pyte.Stream(self._screen)
        self._pgid = None
        self._cancelled = False

    async def start(self):
        if self._started:
            return

        try:
            master, slave = pty.openpty()

            # Set up bash to immediately exit on Ctrl+C
            self._process = await asyncio.create_subprocess_shell(
                f"exec {self.command}",  # exec ensures signals go to bash
                preexec_fn=os.setsid,
                shell=True,
                bufsize=0,
                stdin=asyncio.subprocess.PIPE,
                stdout=slave,
                stderr=slave,
            )

            self._pgid = os.getpgid(self._process.pid)
            self._master_fd = master
            self._using_pty = True

        except (ImportError, OSError):
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
        """Terminate the bash shell and all child processes."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return

        try:
            # Kill the entire process group
            if self._pgid:
                try:
                    os.killpg(self._pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        finally:
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

        # Create an event to signal when Ctrl+C is pressed
        ctrl_c_event = asyncio.Event()

        async def watch_for_ctrl_c():
            try:
                while True:
                    await asyncio.sleep(0.1)  # Small sleep to prevent CPU hogging
            except KeyboardInterrupt:
                ctrl_c_event.set()

        # Start the watcher task
        watcher = asyncio.create_task(watch_for_ctrl_c())

        try:
            self._process.stdin.write(f"{command}\n".encode())
            await self._process.stdin.drain()

            if self._using_pty:
                while True:
                    if ctrl_c_event.is_set():
                        self.stop()
                        return ToolResult(system="Command cancelled by user")

                    try:
                        chunk = os.read(self._master_fd, 1024)
                        if not chunk:
                            break
                        print(chunk.decode(), end="", flush=True)
                    except (OSError, IOError):
                        break
                    # Check for Ctrl+C every iteration
                    await asyncio.sleep(0)

            else:
                output, error = await self._process.communicate()
                print(output.decode(), end="", flush=True)
                return CLIResult(output=output.decode(), error=error.decode())

        except (KeyboardInterrupt, asyncio.CancelledError):
            self.stop()
            return ToolResult(system="Command cancelled by user")
        finally:
            watcher.cancel()  # Clean up the watcher task

        return CLIResult(output="Command completed", error="")


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
