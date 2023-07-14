# hooks.py -- for dealing with git hooks
# Copyright (C) 2012-2013 Jelmer Vernooij and others.
#
# Dulwich is dual-licensed under the Apache License, Version 2.0 and the GNU
# General Public License as public by the Free Software Foundation; version 2.0
# or (at your option) any later version. You can redistribute it and/or
# modify it under the terms of either of these two licenses.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# You should have received a copy of the licenses; if not, see
# <http://www.gnu.org/licenses/> for a copy of the GNU General Public License
# and <http://www.apache.org/licenses/LICENSE-2.0> for a copy of the Apache
# License, Version 2.0.
#

"""Access to hooks."""

import os
import subprocess

from .errors import HookError


class Hook:
    """Generic hook object."""

    def execute(self, *args):
        """Execute the hook with the given args

        Args:
          args: argument list to hook
        Raises:
          HookError: hook execution failure
        Returns:
          a hook may return a useful value
        """
        raise NotImplementedError(self.execute)


class ShellHook(Hook):
    """Hook by executable file

    Implements standard githooks(5) [0]:

    [0] http://www.kernel.org/pub/software/scm/git/docs/githooks.html
    """

    def __init__(
        self,
        name,
        path,
        numparam,
        pre_exec_callback=None,
        post_exec_callback=None,
        cwd=None,
    ):
        """Setup shell hook definition

        Args:
          name: name of hook for error messages
          path: absolute path to executable file
          numparam: number of requirements parameters
          pre_exec_callback: closure for setup before execution
            Defaults to None. Takes in the variable argument list from the
            execute functions and returns a modified argument list for the
            shell hook.
          post_exec_callback: closure for cleanup after execution
            Defaults to None. Takes in a boolean for hook success and the
            modified argument list and returns the final hook return value
            if applicable
          cwd: working directory to switch to when executing the hook
        """
        self.name = name
        self.filepath = path
        self.numparam = numparam

        self.pre_exec_callback = pre_exec_callback
        self.post_exec_callback = post_exec_callback

        self.cwd = cwd

    def execute(self, *args):
        """Execute the hook with given args"""

        if len(args) != self.numparam:
            raise HookError(
                "Hook %s executed with wrong number of args. \
                            Expected %d. Saw %d. args: %s"
                % (self.name, self.numparam, len(args), args)
            )

        if self.pre_exec_callback is not None:
            args = self.pre_exec_callback(*args)

        try:
            ret = subprocess.call(
                [os.path.relpath(self.filepath, self.cwd)] + list(args),
                cwd=self.cwd)
            if ret != 0:
                if self.post_exec_callback is not None:
                    self.post_exec_callback(0, *args)
                raise HookError(
                    "Hook %s exited with non-zero status %d" % (self.name, ret)
                )
            if self.post_exec_callback is not None:
                return self.post_exec_callback(1, *args)
        except OSError:  # no file. silent failure.
            if self.post_exec_callback is not None:
                self.post_exec_callback(0, *args)


class PreCommitShellHook(ShellHook):
    """pre-commit shell hook"""

    def __init__(self, cwd, controldir):
        filepath = os.path.join(controldir, "hooks", "pre-commit")

        ShellHook.__init__(self, "pre-commit", filepath, 0, cwd=cwd)


class PostCommitShellHook(ShellHook):
    """post-commit shell hook"""

    def __init__(self, controldir):
        filepath = os.path.join(controldir, "hooks", "post-commit")

        ShellHook.__init__(self, "post-commit", filepath, 0, cwd=controldir)


class CommitMsgShellHook(ShellHook):
    """commit-msg shell hook
    """

    def __init__(self, controldir):
        filepath = os.path.join(controldir, "hooks", "commit-msg")

        def prepare_msg(*args):
            import tempfile

            (fd, path) = tempfile.mkstemp()

            with os.fdopen(fd, "wb") as f:
                f.write(args[0])

            return (path,)

        def clean_msg(success, *args):
            if success:
                with open(args[0], "rb") as f:
                    new_msg = f.read()
                os.unlink(args[0])
                return new_msg
            os.unlink(args[0])

        ShellHook.__init__(
            self, "commit-msg", filepath, 1, prepare_msg, clean_msg, controldir
        )


class PostReceiveShellHook(ShellHook):
    """post-receive shell hook"""

    def __init__(self, controldir):
        self.controldir = controldir
        filepath = os.path.join(controldir, "hooks", "post-receive")
        ShellHook.__init__(self, "post-receive", path=filepath, numparam=0)

    def execute(self, client_refs):
        # do nothing if the script doesn't exist
        if not os.path.exists(self.filepath):
            return None

        try:
            env = os.environ.copy()
            env["GIT_DIR"] = self.controldir

            p = subprocess.Popen(
                self.filepath,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            # client_refs is a list of (oldsha, newsha, ref)
            in_data = b"\n".join([b" ".join(ref) for ref in client_refs])

            out_data, err_data = p.communicate(in_data)

            if (p.returncode != 0) or err_data:
                err_fmt = b"post-receive exit code: %d\n" + b"stdout:\n%s\nstderr:\n%s"
                err_msg = err_fmt % (p.returncode, out_data, err_data)
                raise HookError(err_msg.decode('utf-8', 'backslashreplace'))
            return out_data
        except OSError as err:
            raise HookError(repr(err)) from err
