# refs.py -- For dealing with git refs
# Copyright (C) 2008-2013 Jelmer Vernooij <jelmer@jelmer.uk>
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


"""Ref handling.

"""
import os
import warnings
from contextlib import suppress
from typing import Dict, Optional

from .errors import PackedRefsException, RefFormatError
from .file import GitFile, ensure_dir_exists
from .objects import ZERO_SHA, ObjectID, Tag, git_line, valid_hexsha
from .pack import ObjectContainer

Ref = bytes

HEADREF = b"HEAD"
SYMREF = b"ref: "
LOCAL_BRANCH_PREFIX = b"refs/heads/"
LOCAL_TAG_PREFIX = b"refs/tags/"
LOCAL_REMOTE_PREFIX = b"refs/remotes/"
BAD_REF_CHARS = set(b"\177 ~^:?*[")
PEELED_TAG_SUFFIX = b"^{}"

# For backwards compatibility
ANNOTATED_TAG_SUFFIX = PEELED_TAG_SUFFIX


class SymrefLoop(Exception):
    """There is a loop between one or more symrefs."""

    def __init__(self, ref, depth):
        self.ref = ref
        self.depth = depth


def parse_symref_value(contents):
    """Parse a symref value.

    Args:
      contents: Contents to parse
    Returns: Destination
    """
    if contents.startswith(SYMREF):
        return contents[len(SYMREF) :].rstrip(b"\r\n")
    raise ValueError(contents)


def check_ref_format(refname: Ref):
    """Check if a refname is correctly formatted.

    Implements all the same rules as git-check-ref-format[1].

    [1]
    http://www.kernel.org/pub/software/scm/git/docs/git-check-ref-format.html

    Args:
      refname: The refname to check
    Returns: True if refname is valid, False otherwise
    """
    # These could be combined into one big expression, but are listed
    # separately to parallel [1].
    if b"/." in refname or refname.startswith(b"."):
        return False
    if b"/" not in refname:
        return False
    if b".." in refname:
        return False
    for i, c in enumerate(refname):
        if ord(refname[i : i + 1]) < 0o40 or c in BAD_REF_CHARS:
            return False
    if refname[-1] in b"/.":
        return False
    if refname.endswith(b".lock"):
        return False
    if b"@{" in refname:
        return False
    if b"\\" in refname:
        return False
    return True


class RefsContainer:
    """A container for refs."""

    def __init__(self, logger=None):
        self._logger = logger

    def _log(
        self,
        ref,
        old_sha,
        new_sha,
        committer=None,
        timestamp=None,
        timezone=None,
        message=None,
    ):
        if self._logger is None:
            return
        if message is None:
            return
        self._logger(ref, old_sha, new_sha, committer, timestamp, timezone, message)

    def set_symbolic_ref(
        self,
        name,
        other,
        committer=None,
        timestamp=None,
        timezone=None,
        message=None,
    ):
        """Make a ref point at another ref.

        Args:
          name: Name of the ref to set
          other: Name of the ref to point at
          message: Optional message
        """
        raise NotImplementedError(self.set_symbolic_ref)

    def get_packed_refs(self):
        """Get contents of the packed-refs file.

        Returns: Dictionary mapping ref names to SHA1s

        Note: Will return an empty dictionary when no packed-refs file is
            present.
        """
        raise NotImplementedError(self.get_packed_refs)

    def add_packed_refs(self, new_refs: Dict[Ref, Optional[ObjectID]]):
        """Add the given refs as packed refs.

        Args:
          new_refs: A mapping of ref names to targets; if a target is None that
            means remove the ref
        """
        raise NotImplementedError(self.add_packed_refs)

    def get_peeled(self, name):
        """Return the cached peeled value of a ref, if available.

        Args:
          name: Name of the ref to peel
        Returns: The peeled value of the ref. If the ref is known not point to
            a tag, this will be the SHA the ref refers to. If the ref may point
            to a tag, but no cached information is available, None is returned.
        """
        return None

    def import_refs(
        self,
        base: Ref,
        other: Dict[Ref, ObjectID],
        committer: Optional[bytes] = None,
        timestamp: Optional[bytes] = None,
        timezone: Optional[bytes] = None,
        message: Optional[bytes] = None,
        prune: bool = False,
    ):
        if prune:
            to_delete = set(self.subkeys(base))
        else:
            to_delete = set()
        for name, value in other.items():
            if value is None:
                to_delete.add(name)
            else:
                self.set_if_equals(
                    b"/".join((base, name)), None, value, message=message
                )
            if to_delete:
                try:
                    to_delete.remove(name)
                except KeyError:
                    pass
        for ref in to_delete:
            self.remove_if_equals(b"/".join((base, ref)), None, message=message)

    def allkeys(self):
        """All refs present in this container."""
        raise NotImplementedError(self.allkeys)

    def __iter__(self):
        return iter(self.allkeys())

    def keys(self, base=None):
        """Refs present in this container.

        Args:
          base: An optional base to return refs under.
        Returns: An unsorted set of valid refs in this container, including
            packed refs.
        """
        if base is not None:
            return self.subkeys(base)
        else:
            return self.allkeys()

    def subkeys(self, base):
        """Refs present in this container under a base.

        Args:
          base: The base to return refs under.
        Returns: A set of valid refs in this container under the base; the base
            prefix is stripped from the ref names returned.
        """
        keys = set()
        base_len = len(base) + 1
        for refname in self.allkeys():
            if refname.startswith(base):
                keys.add(refname[base_len:])
        return keys

    def as_dict(self, base=None):
        """Return the contents of this container as a dictionary."""
        ret = {}
        keys = self.keys(base)
        if base is None:
            base = b""
        else:
            base = base.rstrip(b"/")
        for key in keys:
            try:
                ret[key] = self[(base + b"/" + key).strip(b"/")]
            except (SymrefLoop, KeyError):
                continue  # Unable to resolve

        return ret

    def _check_refname(self, name):
        """Ensure a refname is valid and lives in refs or is HEAD.

        HEAD is not a valid refname according to git-check-ref-format, but this
        class needs to be able to touch HEAD. Also, check_ref_format expects
        refnames without the leading 'refs/', but this class requires that
        so it cannot touch anything outside the refs dir (or HEAD).

        Args:
          name: The name of the reference.
        Raises:
          KeyError: if a refname is not HEAD or is otherwise not valid.
        """
        if name in (HEADREF, b"refs/stash"):
            return
        if not name.startswith(b"refs/") or not check_ref_format(name[5:]):
            raise RefFormatError(name)

    def read_ref(self, refname):
        """Read a reference without following any references.

        Args:
          refname: The name of the reference
        Returns: The contents of the ref file, or None if it does
            not exist.
        """
        contents = self.read_loose_ref(refname)
        if not contents:
            contents = self.get_packed_refs().get(refname, None)
        return contents

    def read_loose_ref(self, name):
        """Read a loose reference and return its contents.

        Args:
          name: the refname to read
        Returns: The contents of the ref file, or None if it does
            not exist.
        """
        raise NotImplementedError(self.read_loose_ref)

    def follow(self, name):
        """Follow a reference name.

        Returns: a tuple of (refnames, sha), wheres refnames are the names of
            references in the chain
        """
        contents = SYMREF + name
        depth = 0
        refnames = []
        while contents.startswith(SYMREF):
            refname = contents[len(SYMREF) :]
            refnames.append(refname)
            contents = self.read_ref(refname)
            if not contents:
                break
            depth += 1
            if depth > 5:
                raise SymrefLoop(name, depth)
        return refnames, contents

    def __contains__(self, refname):
        if self.read_ref(refname):
            return True
        return False

    def __getitem__(self, name):
        """Get the SHA1 for a reference name.

        This method follows all symbolic references.
        """
        _, sha = self.follow(name)
        if sha is None:
            raise KeyError(name)
        return sha

    def set_if_equals(
        self,
        name,
        old_ref,
        new_ref,
        committer=None,
        timestamp=None,
        timezone=None,
        message=None,
    ):
        """Set a refname to new_ref only if it currently equals old_ref.

        This method follows all symbolic references if applicable for the
        subclass, and can be used to perform an atomic compare-and-swap
        operation.

        Args:
          name: The refname to set.
          old_ref: The old sha the refname must refer to, or None to set
            unconditionally.
          new_ref: The new sha the refname will refer to.
          message: Message for reflog
        Returns: True if the set was successful, False otherwise.
        """
        raise NotImplementedError(self.set_if_equals)

    def add_if_new(self, name, ref, committer=None, timestamp=None,
                   timezone=None, message=None):
        """Add a new reference only if it does not already exist.

        Args:
          name: Ref name
          ref: Ref value
        """
        raise NotImplementedError(self.add_if_new)

    def __setitem__(self, name, ref):
        """Set a reference name to point to the given SHA1.

        This method follows all symbolic references if applicable for the
        subclass.

        Note: This method unconditionally overwrites the contents of a
            reference. To update atomically only if the reference has not
            changed, use set_if_equals().

        Args:
          name: The refname to set.
          ref: The new sha the refname will refer to.
        """
        self.set_if_equals(name, None, ref)

    def remove_if_equals(
        self,
        name,
        old_ref,
        committer=None,
        timestamp=None,
        timezone=None,
        message=None,
    ):
        """Remove a refname only if it currently equals old_ref.

        This method does not follow symbolic references, even if applicable for
        the subclass. It can be used to perform an atomic compare-and-delete
        operation.

        Args:
          name: The refname to delete.
          old_ref: The old sha the refname must refer to, or None to
            delete unconditionally.
          message: Message for reflog
        Returns: True if the delete was successful, False otherwise.
        """
        raise NotImplementedError(self.remove_if_equals)

    def __delitem__(self, name):
        """Remove a refname.

        This method does not follow symbolic references, even if applicable for
        the subclass.

        Note: This method unconditionally deletes the contents of a reference.
            To delete atomically only if the reference has not changed, use
            remove_if_equals().

        Args:
          name: The refname to delete.
        """
        self.remove_if_equals(name, None)

    def get_symrefs(self):
        """Get a dict with all symrefs in this container.

        Returns: Dictionary mapping source ref to target ref
        """
        ret = {}
        for src in self.allkeys():
            try:
                dst = parse_symref_value(self.read_ref(src))
            except ValueError:
                pass
            else:
                ret[src] = dst
        return ret


class DictRefsContainer(RefsContainer):
    """RefsContainer backed by a simple dict.

    This container does not support symbolic or packed references and is not
    threadsafe.
    """

    def __init__(self, refs, logger=None):
        super().__init__(logger=logger)
        self._refs = refs
        self._peeled = {}
        self._watchers = set()

    def allkeys(self):
        return self._refs.keys()

    def read_loose_ref(self, name):
        return self._refs.get(name, None)

    def get_packed_refs(self):
        return {}

    def _notify(self, ref, newsha):
        for watcher in self._watchers:
            watcher._notify((ref, newsha))

    def set_symbolic_ref(
        self,
        name: Ref,
        other: Ref,
        committer=None,
        timestamp=None,
        timezone=None,
        message=None,
    ):
        old = self.follow(name)[-1]
        new = SYMREF + other
        self._refs[name] = new
        self._notify(name, new)
        self._log(
            name,
            old,
            new,
            committer=committer,
            timestamp=timestamp,
            timezone=timezone,
            message=message,
        )

    def set_if_equals(
        self,
        name,
        old_ref,
        new_ref,
        committer=None,
        timestamp=None,
        timezone=None,
        message=None,
    ):
        if old_ref is not None and self._refs.get(name, ZERO_SHA) != old_ref:
            return False
        realnames, _ = self.follow(name)
        for realname in realnames:
            self._check_refname(realname)
            old = self._refs.get(realname)
            self._refs[realname] = new_ref
            self._notify(realname, new_ref)
            self._log(
                realname,
                old,
                new_ref,
                committer=committer,
                timestamp=timestamp,
                timezone=timezone,
                message=message,
            )
        return True

    def add_if_new(
        self,
        name: Ref,
        ref: ObjectID,
        committer=None,
        timestamp=None,
        timezone=None,
        message: Optional[bytes] = None,
    ):
        if name in self._refs:
            return False
        self._refs[name] = ref
        self._notify(name, ref)
        self._log(
            name,
            None,
            ref,
            committer=committer,
            timestamp=timestamp,
            timezone=timezone,
            message=message,
        )
        return True

    def remove_if_equals(
        self,
        name,
        old_ref,
        committer=None,
        timestamp=None,
        timezone=None,
        message=None,
    ):
        if old_ref is not None and self._refs.get(name, ZERO_SHA) != old_ref:
            return False
        try:
            old = self._refs.pop(name)
        except KeyError:
            pass
        else:
            self._notify(name, None)
            self._log(
                name,
                old,
                None,
                committer=committer,
                timestamp=timestamp,
                timezone=timezone,
                message=message,
            )
        return True

    def get_peeled(self, name):
        return self._peeled.get(name)

    def _update(self, refs):
        """Update multiple refs; intended only for testing."""
        # TODO(dborowitz): replace this with a public function that uses
        # set_if_equal.
        for ref, sha in refs.items():
            self.set_if_equals(ref, None, sha)

    def _update_peeled(self, peeled):
        """Update cached peeled refs; intended only for testing."""
        self._peeled.update(peeled)


class InfoRefsContainer(RefsContainer):
    """Refs container that reads refs from a info/refs file."""

    def __init__(self, f):
        self._refs = {}
        self._peeled = {}
        for line in f.readlines():
            sha, name = line.rstrip(b"\n").split(b"\t")
            if name.endswith(PEELED_TAG_SUFFIX):
                name = name[:-3]
                if not check_ref_format(name):
                    raise ValueError("invalid ref name %r" % name)
                self._peeled[name] = sha
            else:
                if not check_ref_format(name):
                    raise ValueError("invalid ref name %r" % name)
                self._refs[name] = sha

    def allkeys(self):
        return self._refs.keys()

    def read_loose_ref(self, name):
        return self._refs.get(name, None)

    def get_packed_refs(self):
        return {}

    def get_peeled(self, name):
        try:
            return self._peeled[name]
        except KeyError:
            return self._refs[name]


class DiskRefsContainer(RefsContainer):
    """Refs container that reads refs from disk."""

    def __init__(self, path, worktree_path=None, logger=None):
        super().__init__(logger=logger)
        if getattr(path, "encode", None) is not None:
            path = os.fsencode(path)
        self.path = path
        if worktree_path is None:
            worktree_path = path
        if getattr(worktree_path, "encode", None) is not None:
            worktree_path = os.fsencode(worktree_path)
        self.worktree_path = worktree_path
        self._packed_refs = None
        self._peeled_refs = None

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self.path)

    def subkeys(self, base):
        subkeys = set()
        path = self.refpath(base)
        for root, unused_dirs, files in os.walk(path):
            dir = root[len(path) :]
            if os.path.sep != "/":
                dir = dir.replace(os.fsencode(os.path.sep), b"/")
            dir = dir.strip(b"/")
            for filename in files:
                refname = b"/".join(([dir] if dir else []) + [filename])
                # check_ref_format requires at least one /, so we prepend the
                # base before calling it.
                if check_ref_format(base + b"/" + refname):
                    subkeys.add(refname)
        for key in self.get_packed_refs():
            if key.startswith(base):
                subkeys.add(key[len(base) :].strip(b"/"))
        return subkeys

    def allkeys(self):
        allkeys = set()
        if os.path.exists(self.refpath(HEADREF)):
            allkeys.add(HEADREF)
        path = self.refpath(b"")
        refspath = self.refpath(b"refs")
        for root, unused_dirs, files in os.walk(refspath):
            dir = root[len(path) :]
            if os.path.sep != "/":
                dir = dir.replace(os.fsencode(os.path.sep), b"/")
            for filename in files:
                refname = b"/".join([dir, filename])
                if check_ref_format(refname):
                    allkeys.add(refname)
        allkeys.update(self.get_packed_refs())
        return allkeys

    def refpath(self, name):
        """Return the disk path of a ref."""
        if os.path.sep != "/":
            name = name.replace(b"/", os.fsencode(os.path.sep))
        # TODO: as the 'HEAD' reference is working tree specific, it
        # should actually not be a part of RefsContainer
        if name == HEADREF:
            return os.path.join(self.worktree_path, name)
        else:
            return os.path.join(self.path, name)

    def get_packed_refs(self):
        """Get contents of the packed-refs file.

        Returns: Dictionary mapping ref names to SHA1s

        Note: Will return an empty dictionary when no packed-refs file is
            present.
        """
        # TODO: invalidate the cache on repacking
        if self._packed_refs is None:
            # set both to empty because we want _peeled_refs to be
            # None if and only if _packed_refs is also None.
            self._packed_refs = {}
            self._peeled_refs = {}
            path = os.path.join(self.path, b"packed-refs")
            try:
                f = GitFile(path, "rb")
            except FileNotFoundError:
                return {}
            with f:
                first_line = next(iter(f)).rstrip()
                if first_line.startswith(b"# pack-refs") and b" peeled" in first_line:
                    for sha, name, peeled in read_packed_refs_with_peeled(f):
                        self._packed_refs[name] = sha
                        if peeled:
                            self._peeled_refs[name] = peeled
                else:
                    f.seek(0)
                    for sha, name in read_packed_refs(f):
                        self._packed_refs[name] = sha
        return self._packed_refs

    def add_packed_refs(self, new_refs: Dict[Ref, Optional[ObjectID]]):
        """Add the given refs as packed refs.

        Args:
          new_refs: A mapping of ref names to targets; if a target is None that
            means remove the ref
        """
        if not new_refs:
            return

        path = os.path.join(self.path, b"packed-refs")

        with GitFile(path, "wb") as f:
            # reread cached refs from disk, while holding the lock
            packed_refs = self.get_packed_refs().copy()

            for ref, target in new_refs.items():
                # sanity check
                if ref == HEADREF:
                    raise ValueError("cannot pack HEAD")

                # remove any loose refs pointing to this one -- please
                # note that this bypasses remove_if_equals as we don't
                # want to affect packed refs in here
                with suppress(OSError):
                    os.remove(self.refpath(ref))

                if target is not None:
                    packed_refs[ref] = target
                else:
                    packed_refs.pop(ref, None)

            write_packed_refs(f, packed_refs, self._peeled_refs)

            self._packed_refs = packed_refs

    def get_peeled(self, name):
        """Return the cached peeled value of a ref, if available.

        Args:
          name: Name of the ref to peel
        Returns: The peeled value of the ref. If the ref is known not point to
            a tag, this will be the SHA the ref refers to. If the ref may point
            to a tag, but no cached information is available, None is returned.
        """
        self.get_packed_refs()
        if self._peeled_refs is None or name not in self._packed_refs:
            # No cache: no peeled refs were read, or this ref is loose
            return None
        if name in self._peeled_refs:
            return self._peeled_refs[name]
        else:
            # Known not peelable
            return self[name]

    def read_loose_ref(self, name):
        """Read a reference file and return its contents.

        If the reference file a symbolic reference, only read the first line of
        the file. Otherwise, only read the first 40 bytes.

        Args:
          name: the refname to read, relative to refpath
        Returns: The contents of the ref file, or None if the file does not
            exist.
        Raises:
          IOError: if any other error occurs
        """
        filename = self.refpath(name)
        try:
            with GitFile(filename, "rb") as f:
                header = f.read(len(SYMREF))
                if header == SYMREF:
                    # Read only the first line
                    return header + next(iter(f)).rstrip(b"\r\n")
                else:
                    # Read only the first 40 bytes
                    return header + f.read(40 - len(SYMREF))
        except (OSError, UnicodeError):
            # don't assume anything specific about the error; in
            # particular, invalid or forbidden paths can raise weird
            # errors depending on the specific operating system
            return None

    def _remove_packed_ref(self, name):
        if self._packed_refs is None:
            return
        filename = os.path.join(self.path, b"packed-refs")
        # reread cached refs from disk, while holding the lock
        f = GitFile(filename, "wb")
        try:
            self._packed_refs = None
            self.get_packed_refs()

            if name not in self._packed_refs:
                return

            del self._packed_refs[name]
            with suppress(KeyError):
                del self._peeled_refs[name]
            write_packed_refs(f, self._packed_refs, self._peeled_refs)
            f.close()
        finally:
            f.abort()

    def set_symbolic_ref(
        self,
        name,
        other,
        committer=None,
        timestamp=None,
        timezone=None,
        message=None,
    ):
        """Make a ref point at another ref.

        Args:
          name: Name of the ref to set
          other: Name of the ref to point at
          message: Optional message to describe the change
        """
        self._check_refname(name)
        self._check_refname(other)
        filename = self.refpath(name)
        f = GitFile(filename, "wb")
        try:
            f.write(SYMREF + other + b"\n")
            sha = self.follow(name)[-1]
            self._log(
                name,
                sha,
                sha,
                committer=committer,
                timestamp=timestamp,
                timezone=timezone,
                message=message,
            )
        except BaseException:
            f.abort()
            raise
        else:
            f.close()

    def set_if_equals(
        self,
        name,
        old_ref,
        new_ref,
        committer=None,
        timestamp=None,
        timezone=None,
        message=None,
    ):
        """Set a refname to new_ref only if it currently equals old_ref.

        This method follows all symbolic references, and can be used to perform
        an atomic compare-and-swap operation.

        Args:
          name: The refname to set.
          old_ref: The old sha the refname must refer to, or None to set
            unconditionally.
          new_ref: The new sha the refname will refer to.
          message: Set message for reflog
        Returns: True if the set was successful, False otherwise.
        """
        self._check_refname(name)
        try:
            realnames, _ = self.follow(name)
            realname = realnames[-1]
        except (KeyError, IndexError, SymrefLoop):
            realname = name
        filename = self.refpath(realname)

        # make sure none of the ancestor folders is in packed refs
        probe_ref = os.path.dirname(realname)
        packed_refs = self.get_packed_refs()
        while probe_ref:
            if packed_refs.get(probe_ref, None) is not None:
                raise NotADirectoryError(filename)
            probe_ref = os.path.dirname(probe_ref)

        ensure_dir_exists(os.path.dirname(filename))
        with GitFile(filename, "wb") as f:
            if old_ref is not None:
                try:
                    # read again while holding the lock
                    orig_ref = self.read_loose_ref(realname)
                    if orig_ref is None:
                        orig_ref = self.get_packed_refs().get(realname, ZERO_SHA)
                    if orig_ref != old_ref:
                        f.abort()
                        return False
                except OSError:
                    f.abort()
                    raise
            try:
                f.write(new_ref + b"\n")
            except OSError:
                f.abort()
                raise
            self._log(
                realname,
                old_ref,
                new_ref,
                committer=committer,
                timestamp=timestamp,
                timezone=timezone,
                message=message,
            )
        return True

    def add_if_new(
        self,
        name: bytes,
        ref: bytes,
        committer=None,
        timestamp=None,
        timezone=None,
        message: Optional[bytes] = None,
    ):
        """Add a new reference only if it does not already exist.

        This method follows symrefs, and only ensures that the last ref in the
        chain does not exist.

        Args:
          name: The refname to set.
          ref: The new sha the refname will refer to.
          message: Optional message for reflog
        Returns: True if the add was successful, False otherwise.
        """
        try:
            realnames, contents = self.follow(name)
            if contents is not None:
                return False
            realname = realnames[-1]
        except (KeyError, IndexError):
            realname = name
        self._check_refname(realname)
        filename = self.refpath(realname)
        ensure_dir_exists(os.path.dirname(filename))
        with GitFile(filename, "wb") as f:
            if os.path.exists(filename) or name in self.get_packed_refs():
                f.abort()
                return False
            try:
                f.write(ref + b"\n")
            except OSError:
                f.abort()
                raise
            else:
                self._log(
                    name,
                    None,
                    ref,
                    committer=committer,
                    timestamp=timestamp,
                    timezone=timezone,
                    message=message,
                )
        return True

    def remove_if_equals(
        self,
        name,
        old_ref,
        committer=None,
        timestamp=None,
        timezone=None,
        message=None,
    ):
        """Remove a refname only if it currently equals old_ref.

        This method does not follow symbolic references. It can be used to
        perform an atomic compare-and-delete operation.

        Args:
          name: The refname to delete.
          old_ref: The old sha the refname must refer to, or None to
            delete unconditionally.
          message: Optional message
        Returns: True if the delete was successful, False otherwise.
        """
        self._check_refname(name)
        filename = self.refpath(name)
        ensure_dir_exists(os.path.dirname(filename))
        f = GitFile(filename, "wb")
        try:
            if old_ref is not None:
                orig_ref = self.read_loose_ref(name)
                if orig_ref is None:
                    orig_ref = self.get_packed_refs().get(name, ZERO_SHA)
                if orig_ref != old_ref:
                    return False

            # remove the reference file itself
            try:
                found = os.path.lexists(filename)
            except OSError:
                # may only be packed, or otherwise unstorable
                found = False

            if found:
                os.remove(filename)

            self._remove_packed_ref(name)
            self._log(
                name,
                old_ref,
                None,
                committer=committer,
                timestamp=timestamp,
                timezone=timezone,
                message=message,
            )
        finally:
            # never write, we just wanted the lock
            f.abort()

        # outside of the lock, clean-up any parent directory that might now
        # be empty. this ensures that re-creating a reference of the same
        # name of what was previously a directory works as expected
        parent = name
        while True:
            try:
                parent, _ = parent.rsplit(b"/", 1)
            except ValueError:
                break

            if parent == b'refs':
                break
            parent_filename = self.refpath(parent)
            try:
                os.rmdir(parent_filename)
            except OSError:
                # this can be caused by the parent directory being
                # removed by another process, being not empty, etc.
                # in any case, this is non fatal because we already
                # removed the reference, just ignore it
                break

        return True


def _split_ref_line(line):
    """Split a single ref line into a tuple of SHA1 and name."""
    fields = line.rstrip(b"\n\r").split(b" ")
    if len(fields) != 2:
        raise PackedRefsException("invalid ref line %r" % line)
    sha, name = fields
    if not valid_hexsha(sha):
        raise PackedRefsException("Invalid hex sha %r" % sha)
    if not check_ref_format(name):
        raise PackedRefsException("invalid ref name %r" % name)
    return (sha, name)


def read_packed_refs(f):
    """Read a packed refs file.

    Args:
      f: file-like object to read from
    Returns: Iterator over tuples with SHA1s and ref names.
    """
    for line in f:
        if line.startswith(b"#"):
            # Comment
            continue
        if line.startswith(b"^"):
            raise PackedRefsException("found peeled ref in packed-refs without peeled")
        yield _split_ref_line(line)


def read_packed_refs_with_peeled(f):
    """Read a packed refs file including peeled refs.

    Assumes the "# pack-refs with: peeled" line was already read. Yields tuples
    with ref names, SHA1s, and peeled SHA1s (or None).

    Args:
      f: file-like object to read from, seek'ed to the second line
    """
    last = None
    for line in f:
        if line[0] == b"#":
            continue
        line = line.rstrip(b"\r\n")
        if line.startswith(b"^"):
            if not last:
                raise PackedRefsException("unexpected peeled ref line")
            if not valid_hexsha(line[1:]):
                raise PackedRefsException("Invalid hex sha %r" % line[1:])
            sha, name = _split_ref_line(last)
            last = None
            yield (sha, name, line[1:])
        else:
            if last:
                sha, name = _split_ref_line(last)
                yield (sha, name, None)
            last = line
    if last:
        sha, name = _split_ref_line(last)
        yield (sha, name, None)


def write_packed_refs(f, packed_refs, peeled_refs=None):
    """Write a packed refs file.

    Args:
      f: empty file-like object to write to
      packed_refs: dict of refname to sha of packed refs to write
      peeled_refs: dict of refname to peeled value of sha
    """
    if peeled_refs is None:
        peeled_refs = {}
    else:
        f.write(b"# pack-refs with: peeled\n")
    for refname in sorted(packed_refs.keys()):
        f.write(git_line(packed_refs[refname], refname))
        if refname in peeled_refs:
            f.write(b"^" + peeled_refs[refname] + b"\n")


def read_info_refs(f):
    ret = {}
    for line in f.readlines():
        (sha, name) = line.rstrip(b"\r\n").split(b"\t", 1)
        ret[name] = sha
    return ret


def write_info_refs(refs, store: ObjectContainer):
    """Generate info refs."""
    # TODO: Avoid recursive import :(
    from .object_store import peel_sha
    for name, sha in sorted(refs.items()):
        # get_refs() includes HEAD as a special case, but we don't want to
        # advertise it
        if name == HEADREF:
            continue
        try:
            o = store[sha]
        except KeyError:
            continue
        unpeeled, peeled = peel_sha(store, sha)
        yield o.id + b"\t" + name + b"\n"
        if o.id != peeled.id:
            yield peeled.id + b"\t" + name + PEELED_TAG_SUFFIX + b"\n"


def is_local_branch(x):
    return x.startswith(LOCAL_BRANCH_PREFIX)


def strip_peeled_refs(refs):
    """Remove all peeled refs"""
    return {
        ref: sha
        for (ref, sha) in refs.items()
        if not ref.endswith(PEELED_TAG_SUFFIX)
    }


def _set_origin_head(refs, origin, origin_head):
    # set refs/remotes/origin/HEAD
    origin_base = b"refs/remotes/" + origin + b"/"
    if origin_head and origin_head.startswith(LOCAL_BRANCH_PREFIX):
        origin_ref = origin_base + HEADREF
        target_ref = origin_base + origin_head[len(LOCAL_BRANCH_PREFIX) :]
        if target_ref in refs:
            refs.set_symbolic_ref(origin_ref, target_ref)


def _set_default_branch(
        refs: RefsContainer, origin: bytes, origin_head: bytes, branch: bytes,
        ref_message: Optional[bytes]) -> bytes:
    """Set the default branch.
    """
    origin_base = b"refs/remotes/" + origin + b"/"
    if branch:
        origin_ref = origin_base + branch
        if origin_ref in refs:
            local_ref = LOCAL_BRANCH_PREFIX + branch
            refs.add_if_new(
                local_ref, refs[origin_ref], ref_message
            )
            head_ref = local_ref
        elif LOCAL_TAG_PREFIX + branch in refs:
            head_ref = LOCAL_TAG_PREFIX + branch
        else:
            raise ValueError(
                "%r is not a valid branch or tag" % os.fsencode(branch)
            )
    elif origin_head:
        head_ref = origin_head
        if origin_head.startswith(LOCAL_BRANCH_PREFIX):
            origin_ref = origin_base + origin_head[len(LOCAL_BRANCH_PREFIX) :]
        else:
            origin_ref = origin_head
        try:
            refs.add_if_new(
                head_ref, refs[origin_ref], ref_message
            )
        except KeyError:
            pass
    else:
        raise ValueError('neither origin_head nor branch are provided')
    return head_ref


def _set_head(refs, head_ref, ref_message):
    if head_ref.startswith(LOCAL_TAG_PREFIX):
        # detach HEAD at specified tag
        head = refs[head_ref]
        if isinstance(head, Tag):
            _cls, obj = head.object
            head = obj.get_object(obj).id
        del refs[HEADREF]
        refs.set_if_equals(
            HEADREF, None, head, message=ref_message
        )
    else:
        # set HEAD to specific branch
        try:
            head = refs[head_ref]
            refs.set_symbolic_ref(HEADREF, head_ref)
            refs.set_if_equals(HEADREF, None, head, message=ref_message)
        except KeyError:
            head = None
    return head


def _import_remote_refs(
    refs_container: RefsContainer,
    remote_name: str,
    refs: Dict[str, str],
    message: Optional[bytes] = None,
    prune: bool = False,
    prune_tags: bool = False,
):
    stripped_refs = strip_peeled_refs(refs)
    branches = {
        n[len(LOCAL_BRANCH_PREFIX) :]: v
        for (n, v) in stripped_refs.items()
        if n.startswith(LOCAL_BRANCH_PREFIX)
    }
    refs_container.import_refs(
        b"refs/remotes/" + remote_name.encode(),
        branches,
        message=message,
        prune=prune,
    )
    tags = {
        n[len(LOCAL_TAG_PREFIX) :]: v
        for (n, v) in stripped_refs.items()
        if n.startswith(LOCAL_TAG_PREFIX) and not n.endswith(PEELED_TAG_SUFFIX)
    }
    refs_container.import_refs(LOCAL_TAG_PREFIX, tags, message=message, prune=prune_tags)


def serialize_refs(store, refs):
    # TODO: Avoid recursive import :(
    from .object_store import peel_sha
    ret = {}
    for ref, sha in refs.items():
        try:
            unpeeled, peeled = peel_sha(store, sha)
        except KeyError:
            warnings.warn(
                "ref %s points at non-present sha %s"
                % (ref.decode("utf-8", "replace"), sha.decode("ascii")),
                UserWarning,
            )
            continue
        else:
            if isinstance(unpeeled, Tag):
                ret[ref + PEELED_TAG_SUFFIX] = peeled.id
            ret[ref] = unpeeled.id
    return ret
