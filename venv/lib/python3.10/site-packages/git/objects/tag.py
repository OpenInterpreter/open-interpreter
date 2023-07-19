# objects.py
# Copyright (C) 2008, 2009 Michael Trier (mtrier@gmail.com) and contributors
#
# This module is part of GitPython and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php
""" Module containing all object based types. """
from . import base
from .util import get_object_type_by_name, parse_actor_and_date
from ..util import hex_to_bin
from ..compat import defenc

from typing import List, TYPE_CHECKING, Union

from git.types import Literal

if TYPE_CHECKING:
    from git.repo import Repo
    from git.util import Actor
    from .commit import Commit
    from .blob import Blob
    from .tree import Tree

__all__ = ("TagObject",)


class TagObject(base.Object):

    """Non-Lightweight tag carrying additional information about an object we are pointing to."""

    type: Literal["tag"] = "tag"
    __slots__ = (
        "object",
        "tag",
        "tagger",
        "tagged_date",
        "tagger_tz_offset",
        "message",
    )

    def __init__(
        self,
        repo: "Repo",
        binsha: bytes,
        object: Union[None, base.Object] = None,
        tag: Union[None, str] = None,
        tagger: Union[None, "Actor"] = None,
        tagged_date: Union[int, None] = None,
        tagger_tz_offset: Union[int, None] = None,
        message: Union[str, None] = None,
    ) -> None:  # @ReservedAssignment
        """Initialize a tag object with additional data

        :param repo: repository this object is located in
        :param binsha: 20 byte SHA1
        :param object: Object instance of object we are pointing to
        :param tag: name of this tag
        :param tagger: Actor identifying the tagger
        :param tagged_date: int_seconds_since_epoch
            is the DateTime of the tag creation - use time.gmtime to convert
            it into a different format
        :param tagged_tz_offset: int_seconds_west_of_utc is the timezone that the
            authored_date is in, in a format similar to time.altzone"""
        super(TagObject, self).__init__(repo, binsha)
        if object is not None:
            self.object: Union["Commit", "Blob", "Tree", "TagObject"] = object
        if tag is not None:
            self.tag = tag
        if tagger is not None:
            self.tagger = tagger
        if tagged_date is not None:
            self.tagged_date = tagged_date
        if tagger_tz_offset is not None:
            self.tagger_tz_offset = tagger_tz_offset
        if message is not None:
            self.message = message

    def _set_cache_(self, attr: str) -> None:
        """Cache all our attributes at once"""
        if attr in TagObject.__slots__:
            ostream = self.repo.odb.stream(self.binsha)
            lines: List[str] = ostream.read().decode(defenc, "replace").splitlines()

            _obj, hexsha = lines[0].split(" ")
            _type_token, type_name = lines[1].split(" ")
            object_type = get_object_type_by_name(type_name.encode("ascii"))
            self.object = object_type(self.repo, hex_to_bin(hexsha))

            self.tag = lines[2][4:]  # tag <tag name>

            if len(lines) > 3:
                tagger_info = lines[3]  # tagger <actor> <date>
                (
                    self.tagger,
                    self.tagged_date,
                    self.tagger_tz_offset,
                ) = parse_actor_and_date(tagger_info)

            # line 4 empty - it could mark the beginning of the next header
            # in case there really is no message, it would not exist. Otherwise
            # a newline separates header from message
            if len(lines) > 5:
                self.message = "\n".join(lines[5:])
            else:
                self.message = ""
        # END check our attributes
        else:
            super(TagObject, self)._set_cache_(attr)
