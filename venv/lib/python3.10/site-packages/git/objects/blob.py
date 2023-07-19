# blob.py
# Copyright (C) 2008, 2009 Michael Trier (mtrier@gmail.com) and contributors
#
# This module is part of GitPython and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php
from mimetypes import guess_type
from . import base

from git.types import Literal

__all__ = ("Blob",)


class Blob(base.IndexObject):

    """A Blob encapsulates a git blob object"""

    DEFAULT_MIME_TYPE = "text/plain"
    type: Literal["blob"] = "blob"

    # valid blob modes
    executable_mode = 0o100755
    file_mode = 0o100644
    link_mode = 0o120000

    __slots__ = ()

    @property
    def mime_type(self) -> str:
        """
        :return: String describing the mime type of this file (based on the filename)
        :note: Defaults to 'text/plain' in case the actual file type is unknown."""
        guesses = None
        if self.path:
            guesses = guess_type(str(self.path))
        return guesses and guesses[0] or self.DEFAULT_MIME_TYPE
