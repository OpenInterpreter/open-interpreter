import asyncio
import os
import pty
import select
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
        accumulated_output = []  # Store all output here

        async def watch_for_ctrl_c():
            try:
                while True:
                    await asyncio.sleep(0.1)
            except KeyboardInterrupt:
                ctrl_c_event.set()

        watcher = asyncio.create_task(watch_for_ctrl_c())

        try:
            wrapped_command = f'{command}; echo "{self._sentinel}"'
            self._process.stdin.write(f"{wrapped_command}\n".encode())
            await self._process.stdin.drain()

            if self._using_pty:
                while True:
                    r, _, _ = select.select([self._master_fd], [], [], 0.001)

                    if ctrl_c_event.is_set():
                        return CLIResult(
                            output="".join(accumulated_output)
                            + "\n\nCommand cancelled by user.",
                        )

                    if r:
                        try:
                            chunk = os.read(self._master_fd, 1024)
                            if not chunk:
                                break
                            try:
                                chunk_str = chunk.decode("utf-8")
                            except UnicodeDecodeError:
                                chunk_str = chunk.decode("utf-8", errors="replace")
                            accumulated_output.append(chunk_str)

                            # Check if sentinel is in the output
                            full_output = "".join(accumulated_output)
                            if self._sentinel in full_output:
                                # Remove sentinel and everything after it
                                clean_output = full_output.split(self._sentinel)[0]
                                # If output is empty or only whitespace, return a message
                                if not clean_output.strip():
                                    return CLIResult(output="<No output>")
                                return CLIResult(output=clean_output)
                            else:
                                print(chunk_str, end="", flush=True)

                        except (OSError, IOError):
                            break

                    await asyncio.sleep(0)

            else:
                output, error = await self._process.communicate()
                output_str = output.decode()
                error_str = error.decode()
                combined_output = output_str + "\n" + error_str
                if not combined_output.strip():
                    return CLIResult(output="<No output>")
                return CLIResult(output=combined_output)

        except (KeyboardInterrupt, asyncio.CancelledError):
            self.stop()
            print("\n\nExecution stopped.")
            return CLIResult(
                output="".join(accumulated_output) + "\n\nCommand cancelled by user."
            )
        finally:
            watcher.cancel()

        # If we somehow get here, return whatever we've accumulated
        return CLIResult(output="".join(accumulated_output))


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
