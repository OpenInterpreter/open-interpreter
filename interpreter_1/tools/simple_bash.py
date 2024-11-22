import asyncio
import os
from typing import ClassVar, Literal

from anthropic.types.beta import BetaToolBash20241022Param

from .base import BaseAnthropicTool, CLIResult, ToolError, ToolResult

print("Using simple bash tool")


class BashTool(BaseAnthropicTool):
    """A tool that executes bash commands and returns their output."""

    name: ClassVar[Literal["bash"]] = "bash"
    api_type: ClassVar[Literal["bash_20241022"]] = "bash_20241022"

    async def __call__(
        self, command: str | None = None, restart: bool = False, **kwargs
    ):
        if not command:
            raise ToolError("no command provided")

        try:
            # Create process with shell=True to handle all bash features properly
            process = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=300
                )

                # Decode and combine output
                output = stdout.decode() + stderr.decode()

                # Print output
                print(output, end="", flush=True)

                # Return combined output
                return CLIResult(output=output if output else "<No output>")

            except asyncio.TimeoutError:
                process.kill()
                msg = "Command timed out after 5 minutes"
                print(msg)
                return ToolResult(error=msg)

        except Exception as e:
            msg = f"Failed to run command: {str(e)}"
            print(msg)
            return ToolResult(error=msg)

    def to_params(self) -> BetaToolBash20241022Param:
        return {
            "type": self.api_type,
            "name": self.name,
        }
