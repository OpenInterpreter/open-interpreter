# base.py
# Copyright (C) 2008, 2009 Michael Trier (mtrier@gmail.com) and contributors
#
# This module is part of GitPython and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

from git.exc import WorkTreeRepositoryUnsupported
from git.util import LazyMixin, join_path_native, stream_copy, bin_to_hex

import gitdb.typ as dbtyp
import os.path as osp

from .util import get_object_type_by_name


# typing ------------------------------------------------------------------

from typing import Any, TYPE_CHECKING, Union

from git.types import PathLike, Commit_ish, Lit_commit_ish

if TYPE_CHECKING:
    from git.repo import Repo
    from gitdb.base import OStream
    from .tree import Tree
    from .blob import Blob
    from .submodule.base import Submodule
    from git.refs.reference import Reference

IndexObjUnion = Union["Tree", "Blob", "Submodule"]

# --------------------------------------------------------------------------


_assertion_msg_format = "Created object %r whose python type %r disagrees with the actual git object type %r"

__all__ = ("Object", "IndexObject")


class Object(LazyMixin):

    """Implements an Object which may be Blobs, Trees, Commits and Tags"""

    NULL_HEX_SHA = "0" * 40
    NULL_BIN_SHA = b"\0" * 20

    TYPES = (
        dbtyp.str_blob_type,
        dbtyp.str_tree_type,
        dbtyp.str_commit_type,
        dbtyp.str_tag_type,
    )
    __slots__ = ("repo", "binsha", "size")
    type: Union[Lit_commit_ish, None] = None

    def __init__(self, repo: "Repo", binsha: bytes):
        """Initialize an object by identifying it by its binary sha.
        All keyword arguments will be set on demand if None.

        :param repo: repository this object is located in

        :param binsha: 20 byte SHA1"""
        super(Object, self).__init__()
        self.repo = repo
        self.binsha = binsha
        assert len(binsha) == 20, "Require 20 byte binary sha, got %r, len = %i" % (
            binsha,
            len(binsha),
        )

    @classmethod
    def new(cls, repo: "Repo", id: Union[str, "Reference"]) -> Commit_ish:
        """
        :return: New Object instance of a type appropriate to the object type behind
            id. The id of the newly created object will be a binsha even though
            the input id may have been a Reference or Rev-Spec

        :param id: reference, rev-spec, or hexsha

        :note: This cannot be a __new__ method as it would always call __init__
            with the input id which is not necessarily a binsha."""
        return repo.rev_parse(str(id))

    @classmethod
    def new_from_sha(cls, repo: "Repo", sha1: bytes) -> Commit_ish:
        """
        :return: new object instance of a type appropriate to represent the given
            binary sha1
        :param sha1: 20 byte binary sha1"""
        if sha1 == cls.NULL_BIN_SHA:
            # the NULL binsha is always the root commit
            return get_object_type_by_name(b"commit")(repo, sha1)
        # END handle special case
        oinfo = repo.odb.info(sha1)
        inst = get_object_type_by_name(oinfo.type)(repo, oinfo.binsha)
        inst.size = oinfo.size
        return inst

    def _set_cache_(self, attr: str) -> None:
        """Retrieve object information"""
        if attr == "size":
            oinfo = self.repo.odb.info(self.binsha)
            self.size = oinfo.size  # type:  int
            # assert oinfo.type == self.type, _assertion_msg_format % (self.binsha, oinfo.type, self.type)
        else:
            super(Object, self)._set_cache_(attr)

    def __eq__(self, other: Any) -> bool:
        """:return: True if the objects have the same SHA1"""
        if not hasattr(other, "binsha"):
            return False
        return self.binsha == other.binsha

    def __ne__(self, other: Any) -> bool:
        """:return: True if the objects do not have the same SHA1"""
        if not hasattr(other, "binsha"):
            return True
        return self.binsha != other.binsha

    def __hash__(self) -> int:
        """:return: Hash of our id allowing objects to be used in dicts and sets"""
        return hash(self.binsha)

    def __str__(self) -> str:
        """:return: string of our SHA1 as understood by all git commands"""
        return self.hexsha

    def __repr__(self) -> str:
        """:return: string with pythonic representation of our object"""
        return '<git.%s "%s">' % (self.__class__.__name__, self.hexsha)

    @property
    def hexsha(self) -> str:
        """:return: 40 byte hex version of our 20 byte binary sha"""
        # b2a_hex produces bytes
        return bin_to_hex(self.binsha).decode("ascii")

    @property
    def data_stream(self) -> "OStream":
        """:return:  File Object compatible stream to the uncompressed raw data of the object
        :note: returned streams must be read in order"""
        return self.repo.odb.stream(self.binsha)

    def stream_data(self, ostream: "OStream") -> "Object":
        """Writes our data directly to the given output stream

        :param ostream: File object compatible stream object.
        :return: self"""
        istream = self.repo.odb.stream(self.binsha)
        stream_copy(istream, ostream)
        return self


class IndexObject(Object):

    """Base for all objects that can be part of the index file , namely Tree, Blob and
    SubModule objects"""

    __slots__ = ("path", "mode")

    # for compatibility with iterable lists
    _id_attribute_ = "path"

    def __init__(
        self,
        repo: "Repo",
        binsha: bytes,
        mode: Union[None, int] = None,
        path: Union[None, PathLike] = None,
    ) -> None:
        """Initialize a newly instanced IndexObject

        :param repo: is the Repo we are located in
        :param binsha: 20 byte sha1
        :param mode:
            is the stat compatible file mode as int, use the stat module
            to evaluate the information
        :param path:
            is the path to the file in the file system, relative to the git repository root, i.e.
            file.ext or folder/other.ext
        :note:
            Path may not be set of the index object has been created directly as it cannot
            be retrieved without knowing the parent tree."""
        super(IndexObject, self).__init__(repo, binsha)
        if mode is not None:
            self.mode = mode
        if path is not None:
            self.path = path

    def __hash__(self) -> int:
        """
        :return:
            Hash of our path as index items are uniquely identifiable by path, not
            by their data !"""
        return hash(self.path)

    def _set_cache_(self, attr: str) -> None:
        if attr in IndexObject.__slots__:
            # they cannot be retrieved lateron ( not without searching for them )
            raise AttributeError(
                "Attribute '%s' unset: path and mode attributes must have been set during %s object creation"
                % (attr, type(self).__name__)
            )
        else:
            super(IndexObject, self)._set_cache_(attr)
        # END handle slot attribute

    @property
    def name(self) -> str:
        """:return: Name portion of the path, effectively being the basename"""
        return osp.basename(self.path)

    @property
    def abspath(self) -> PathLike:
        """
        :return:
            Absolute path to this index object in the file system ( as opposed to the
            .path field which is a path relative to the git repository ).

            The returned path will be native to the system and contains '\' on windows."""
        if self.repo.working_tree_dir is not None:
            return join_path_native(self.repo.working_tree_dir, self.path)
        else:
            raise WorkTreeRepositoryUnsupported("Working_tree_dir was None or empty")
