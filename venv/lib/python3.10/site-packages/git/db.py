"""Module with our own gitdb implementation - it uses the git command"""
from git.util import bin_to_hex, hex_to_bin
from gitdb.base import OInfo, OStream
from gitdb.db import GitDB  # @UnusedImport
from gitdb.db import LooseObjectDB

from gitdb.exc import BadObject
from git.exc import GitCommandError

# typing-------------------------------------------------

from typing import TYPE_CHECKING
from git.types import PathLike

if TYPE_CHECKING:
    from git.cmd import Git


# --------------------------------------------------------

__all__ = ("GitCmdObjectDB", "GitDB")


class GitCmdObjectDB(LooseObjectDB):

    """A database representing the default git object store, which includes loose
    objects, pack files and an alternates file

    It will create objects only in the loose object database.
    :note: for now, we use the git command to do all the lookup, just until he
        have packs and the other implementations
    """

    def __init__(self, root_path: PathLike, git: "Git") -> None:
        """Initialize this instance with the root and a git command"""
        super(GitCmdObjectDB, self).__init__(root_path)
        self._git = git

    def info(self, binsha: bytes) -> OInfo:
        hexsha, typename, size = self._git.get_object_header(bin_to_hex(binsha))
        return OInfo(hex_to_bin(hexsha), typename, size)

    def stream(self, binsha: bytes) -> OStream:
        """For now, all lookup is done by git itself"""
        hexsha, typename, size, stream = self._git.stream_object_data(bin_to_hex(binsha))
        return OStream(hex_to_bin(hexsha), typename, size, stream)

    # { Interface

    def partial_to_complete_sha_hex(self, partial_hexsha: str) -> bytes:
        """:return: Full binary 20 byte sha from the given partial hexsha
        :raise AmbiguousObjectName:
        :raise BadObject:
        :note: currently we only raise BadObject as git does not communicate
            AmbiguousObjects separately"""
        try:
            hexsha, _typename, _size = self._git.get_object_header(partial_hexsha)
            return hex_to_bin(hexsha)
        except (GitCommandError, ValueError) as e:
            raise BadObject(partial_hexsha) from e
        # END handle exceptions

    # } END interface
