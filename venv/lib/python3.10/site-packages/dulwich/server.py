# server.py -- Implementation of the server side git protocols
# Copyright (C) 2008 John Carr <john.carr@unrouted.co.uk>
# Copyright(C) 2011-2012 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Git smart network protocol server implementation.

For more detailed implementation on the network protocol, see the
Documentation/technical directory in the cgit distribution, and in particular:

* Documentation/technical/protocol-capabilities.txt
* Documentation/technical/pack-protocol.txt

Currently supported capabilities:

 * include-tag
 * thin-pack
 * multi_ack_detailed
 * multi_ack
 * side-band-64k
 * ofs-delta
 * no-progress
 * report-status
 * delete-refs
 * shallow
 * symref
"""

import collections
import os
import socket
import sys
import time
from functools import partial
from typing import Dict, Iterable, List, Optional, Set, Tuple

try:
    from typing import Protocol as TypingProtocol
except ImportError:  # python < 3.8
    from typing_extensions import Protocol as TypingProtocol  # type: ignore

import socketserver
import zlib

from dulwich import log_utils

from .archive import tar_stream
from .errors import (ApplyDeltaError, ChecksumMismatch, GitProtocolError,
                     HookError, NotGitRepository, ObjectFormatException,
                     UnexpectedCommandError)
from .object_store import peel_sha
from .objects import Commit, ObjectID, valid_hexsha
from .pack import (ObjectContainer, PackedObjectContainer,
                   write_pack_from_container)
from .protocol import (CAPABILITIES_REF, CAPABILITY_AGENT,
                       CAPABILITY_DELETE_REFS, CAPABILITY_INCLUDE_TAG,
                       CAPABILITY_MULTI_ACK, CAPABILITY_MULTI_ACK_DETAILED,
                       CAPABILITY_NO_DONE, CAPABILITY_NO_PROGRESS,
                       CAPABILITY_OFS_DELTA, CAPABILITY_QUIET,
                       CAPABILITY_REPORT_STATUS, CAPABILITY_SHALLOW,
                       CAPABILITY_SIDE_BAND_64K, CAPABILITY_THIN_PACK,
                       COMMAND_DEEPEN, COMMAND_DONE, COMMAND_HAVE,
                       COMMAND_SHALLOW, COMMAND_UNSHALLOW, COMMAND_WANT,
                       MULTI_ACK, MULTI_ACK_DETAILED, NAK_LINE,
                       SIDE_BAND_CHANNEL_DATA, SIDE_BAND_CHANNEL_FATAL,
                       SIDE_BAND_CHANNEL_PROGRESS, SINGLE_ACK, TCP_GIT_PORT,
                       ZERO_SHA, BufferedPktLineWriter, Protocol,
                       ReceivableProtocol, ack_type, capability_agent,
                       extract_capabilities, extract_want_line_capabilities,
                       format_ack_line, format_ref_line, format_shallow_line,
                       format_unshallow_line, symref_capabilities)
from .refs import PEELED_TAG_SUFFIX, RefsContainer, write_info_refs
from .repo import BaseRepo, Repo

logger = log_utils.getLogger(__name__)


class Backend:
    """A backend for the Git smart server implementation."""

    def open_repository(self, path):
        """Open the repository at a path.

        Args:
          path: Path to the repository
        Raises:
          NotGitRepository: no git repository was found at path
        Returns: Instance of BackendRepo
        """
        raise NotImplementedError(self.open_repository)


class BackendRepo(TypingProtocol):
    """Repository abstraction used by the Git server.

    The methods required here are a subset of those provided by
    dulwich.repo.Repo.
    """

    object_store: PackedObjectContainer
    refs: RefsContainer

    def get_refs(self) -> Dict[bytes, bytes]:
        """
        Get all the refs in the repository

        Returns: dict of name -> sha
        """
        raise NotImplementedError

    def get_peeled(self, name: bytes) -> Optional[bytes]:
        """Return the cached peeled value of a ref, if available.

        Args:
          name: Name of the ref to peel
        Returns: The peeled value of the ref. If the ref is known not point to
            a tag, this will be the SHA the ref refers to. If no cached
            information about a tag is available, this method may return None,
            but it should attempt to peel the tag if possible.
        """
        return None

    def find_missing_objects(self, determine_wants, graph_walker, progress, get_tagged=None):
        """
        Yield the objects required for a list of commits.

        Args:
          progress: is a callback to send progress messages to the client
          get_tagged: Function that returns a dict of pointed-to sha ->
            tag sha for including tags.
        """
        raise NotImplementedError


class DictBackend(Backend):
    """Trivial backend that looks up Git repositories in a dictionary."""

    def __init__(self, repos):
        self.repos = repos

    def open_repository(self, path: str) -> BaseRepo:
        logger.debug("Opening repository at %s", path)
        try:
            return self.repos[path]
        except KeyError as exc:
            raise NotGitRepository(
                "No git repository was found at %(path)s" % dict(path=path)
            ) from exc


class FileSystemBackend(Backend):
    """Simple backend looking up Git repositories in the local file system."""

    def __init__(self, root=os.sep):
        super().__init__()
        self.root = (os.path.abspath(root) + os.sep).replace(os.sep * 2, os.sep)

    def open_repository(self, path):
        logger.debug("opening repository at %s", path)
        abspath = os.path.abspath(os.path.join(self.root, path)) + os.sep
        normcase_abspath = os.path.normcase(abspath)
        normcase_root = os.path.normcase(self.root)
        if not normcase_abspath.startswith(normcase_root):
            raise NotGitRepository("Path {!r} not inside root {!r}".format(path, self.root))
        return Repo(abspath)


class Handler:
    """Smart protocol command handler base class."""

    def __init__(self, backend, proto, stateless_rpc=False):
        self.backend = backend
        self.proto = proto
        self.stateless_rpc = stateless_rpc

    def handle(self):
        raise NotImplementedError(self.handle)


class PackHandler(Handler):
    """Protocol handler for packs."""

    def __init__(self, backend, proto, stateless_rpc=False):
        super().__init__(backend, proto, stateless_rpc)
        self._client_capabilities = None
        # Flags needed for the no-done capability
        self._done_received = False

    @classmethod
    def capabilities(cls) -> Iterable[bytes]:
        raise NotImplementedError(cls.capabilities)

    @classmethod
    def innocuous_capabilities(cls) -> Iterable[bytes]:
        return [
            CAPABILITY_INCLUDE_TAG,
            CAPABILITY_THIN_PACK,
            CAPABILITY_NO_PROGRESS,
            CAPABILITY_OFS_DELTA,
            capability_agent(),
        ]

    @classmethod
    def required_capabilities(cls) -> Iterable[bytes]:
        """Return a list of capabilities that we require the client to have."""
        return []

    def set_client_capabilities(self, caps: Iterable[bytes]) -> None:
        allowable_caps = set(self.innocuous_capabilities())
        allowable_caps.update(self.capabilities())
        for cap in caps:
            if cap.startswith(CAPABILITY_AGENT + b"="):
                continue
            if cap not in allowable_caps:
                raise GitProtocolError(
                    "Client asked for capability %r that " "was not advertised." % cap
                )
        for cap in self.required_capabilities():
            if cap not in caps:
                raise GitProtocolError(
                    "Client does not support required " "capability %r." % cap
                )
        self._client_capabilities = set(caps)
        logger.info("Client capabilities: %s", caps)

    def has_capability(self, cap: bytes) -> bool:
        if self._client_capabilities is None:
            raise GitProtocolError(
                "Server attempted to access capability %r " "before asking client" % cap
            )
        return cap in self._client_capabilities

    def notify_done(self) -> None:
        self._done_received = True


class UploadPackHandler(PackHandler):
    """Protocol handler for uploading a pack to the client."""

    def __init__(self, backend, args, proto, stateless_rpc=False, advertise_refs=False):
        super().__init__(
            backend, proto, stateless_rpc=stateless_rpc
        )
        self.repo = backend.open_repository(args[0])
        self._graph_walker = None
        self.advertise_refs = advertise_refs
        # A state variable for denoting that the have list is still
        # being processed, and the client is not accepting any other
        # data (such as side-band, see the progress method here).
        self._processing_have_lines = False

    @classmethod
    def capabilities(cls):
        return [
            CAPABILITY_MULTI_ACK_DETAILED,
            CAPABILITY_MULTI_ACK,
            CAPABILITY_SIDE_BAND_64K,
            CAPABILITY_THIN_PACK,
            CAPABILITY_OFS_DELTA,
            CAPABILITY_NO_PROGRESS,
            CAPABILITY_INCLUDE_TAG,
            CAPABILITY_SHALLOW,
            CAPABILITY_NO_DONE,
        ]

    @classmethod
    def required_capabilities(cls):
        return (
            CAPABILITY_SIDE_BAND_64K,
            CAPABILITY_THIN_PACK,
            CAPABILITY_OFS_DELTA,
        )

    def progress(self, message: bytes):
        pass

    def _start_pack_send_phase(self):
        if self.has_capability(CAPABILITY_SIDE_BAND_64K):
            # The provided haves are processed, and it is safe to send side-
            # band data now.
            if not self.has_capability(CAPABILITY_NO_PROGRESS):
                self.progress = partial(self.proto.write_sideband, SIDE_BAND_CHANNEL_PROGRESS)

            self.write_pack_data = partial(self.proto.write_sideband, SIDE_BAND_CHANNEL_DATA)
        else:
            self.write_pack_data = self.proto.write

    def get_tagged(self, refs=None, repo=None) -> Dict[ObjectID, ObjectID]:
        """Get a dict of peeled values of tags to their original tag shas.

        Args:
          refs: dict of refname -> sha of possible tags; defaults to all
            of the backend's refs.
          repo: optional Repo instance for getting peeled refs; defaults
            to the backend's repo, if available
        Returns: dict of peeled_sha -> tag_sha, where tag_sha is the sha of a
            tag whose peeled value is peeled_sha.
        """
        if not self.has_capability(CAPABILITY_INCLUDE_TAG):
            return {}
        if refs is None:
            refs = self.repo.get_refs()
        if repo is None:
            repo = getattr(self.repo, "repo", None)
            if repo is None:
                # Bail if we don't have a Repo available; this is ok since
                # clients must be able to handle if the server doesn't include
                # all relevant tags.
                # TODO: fix behavior when missing
                return {}
        # TODO(jelmer): Integrate this with the refs logic in
        # Repo.find_missing_objects
        tagged = {}
        for name, sha in refs.items():
            peeled_sha = repo.get_peeled(name)
            if peeled_sha != sha:
                tagged[peeled_sha] = sha
        return tagged

    def handle(self):
        # Note the fact that client is only processing responses related
        # to the have lines it sent, and any other data (including side-
        # band) will be be considered a fatal error.
        self._processing_have_lines = True

        graph_walker = _ProtocolGraphWalker(
            self,
            self.repo.object_store,
            self.repo.get_peeled,
            self.repo.refs.get_symrefs,
        )
        wants = []

        def wants_wrapper(refs, **kwargs):
            wants.extend(graph_walker.determine_wants(refs, **kwargs))
            return wants

        missing_objects = self.repo.find_missing_objects(
            wants_wrapper,
            graph_walker,
            self.progress,
            get_tagged=self.get_tagged,
        )

        object_ids = list(missing_objects)

        # Did the process short-circuit (e.g. in a stateless RPC call)? Note
        # that the client still expects a 0-object pack in most cases.
        # Also, if it also happens that the object_iter is instantiated
        # with a graph walker with an implementation that talks over the
        # wire (which is this instance of this class) this will actually
        # iterate through everything and write things out to the wire.
        if len(wants) == 0:
            return

        if not graph_walker.handle_done(
            not self.has_capability(CAPABILITY_NO_DONE), self._done_received
        ):
            return

        self._start_pack_send_phase()
        self.progress(
            ("counting objects: %d, done.\n" % len(object_ids)).encode("ascii")
        )

        write_pack_from_container(self.write_pack_data, self.repo.object_store, object_ids)
        # we are done
        self.proto.write_pkt_line(None)


def _split_proto_line(line, allowed):
    """Split a line read from the wire.

    Args:
      line: The line read from the wire.
      allowed: An iterable of command names that should be allowed.
        Command names not listed below as possible return values will be
        ignored.  If None, any commands from the possible return values are
        allowed.
    Returns: a tuple having one of the following forms:
        ('want', obj_id)
        ('have', obj_id)
        ('done', None)
        (None, None)  (for a flush-pkt)

    Raises:
      UnexpectedCommandError: if the line cannot be parsed into one of the
        allowed return values.
    """
    if not line:
        fields = [None]
    else:
        fields = line.rstrip(b"\n").split(b" ", 1)
    command = fields[0]
    if allowed is not None and command not in allowed:
        raise UnexpectedCommandError(command)
    if len(fields) == 1 and command in (COMMAND_DONE, None):
        return (command, None)
    elif len(fields) == 2:
        if command in (
            COMMAND_WANT,
            COMMAND_HAVE,
            COMMAND_SHALLOW,
            COMMAND_UNSHALLOW,
        ):
            if not valid_hexsha(fields[1]):
                raise GitProtocolError("Invalid sha")
            return tuple(fields)
        elif command == COMMAND_DEEPEN:
            return command, int(fields[1])
    raise GitProtocolError("Received invalid line from client: %r" % line)


def _find_shallow(store: ObjectContainer, heads, depth):
    """Find shallow commits according to a given depth.

    Args:
      store: An ObjectStore for looking up objects.
      heads: Iterable of head SHAs to start walking from.
      depth: The depth of ancestors to include. A depth of one includes
        only the heads themselves.
    Returns: A tuple of (shallow, not_shallow), sets of SHAs that should be
        considered shallow and unshallow according to the arguments. Note that
        these sets may overlap if a commit is reachable along multiple paths.
    """
    parents: Dict[bytes, List[bytes]] = {}

    def get_parents(sha):
        result = parents.get(sha, None)
        if not result:
            result = store[sha].parents
            parents[sha] = result
        return result

    todo = []  # stack of (sha, depth)
    for head_sha in heads:
        _unpeeled, peeled = peel_sha(store, head_sha)
        if isinstance(peeled, Commit):
            todo.append((peeled.id, 1))

    not_shallow = set()
    shallow = set()
    while todo:
        sha, cur_depth = todo.pop()
        if cur_depth < depth:
            not_shallow.add(sha)
            new_depth = cur_depth + 1
            todo.extend((p, new_depth) for p in get_parents(sha))
        else:
            shallow.add(sha)

    return shallow, not_shallow


def _want_satisfied(store: ObjectContainer, haves, want, earliest):
    o = store[want]
    pending = collections.deque([o])
    known = {want}
    while pending:
        commit = pending.popleft()
        if commit.id in haves:
            return True
        if not isinstance(commit, Commit):
            # non-commit wants are assumed to be satisfied
            continue
        for parent in commit.parents:
            if parent in known:
                continue
            known.add(parent)
            parent_obj = store[parent]
            assert isinstance(parent_obj, Commit)
            # TODO: handle parents with later commit times than children
            if parent_obj.commit_time >= earliest:
                pending.append(parent_obj)
    return False


def _all_wants_satisfied(store: ObjectContainer, haves, wants):
    """Check whether all the current wants are satisfied by a set of haves.

    Args:
      store: Object store to retrieve objects from
      haves: A set of commits we know the client has.
      wants: A set of commits the client wants
    Note: Wants are specified with set_wants rather than passed in since
        in the current interface they are determined outside this class.
    """
    haves = set(haves)
    if haves:
        have_objs = [store[h] for h in haves]
        earliest = min([h.commit_time for h in have_objs if isinstance(h, Commit)])
    else:
        earliest = 0
    for want in wants:
        if not _want_satisfied(store, haves, want, earliest):
            return False

    return True


class _ProtocolGraphWalker:
    """A graph walker that knows the git protocol.

    As a graph walker, this class implements ack(), next(), and reset(). It
    also contains some base methods for interacting with the wire and walking
    the commit tree.

    The work of determining which acks to send is passed on to the
    implementation instance stored in _impl. The reason for this is that we do
    not know at object creation time what ack level the protocol requires. A
    call to set_ack_type() is required to set up the implementation, before
    any calls to next() or ack() are made.
    """

    def __init__(self, handler, object_store: ObjectContainer, get_peeled, get_symrefs):
        self.handler = handler
        self.store: ObjectContainer = object_store
        self.get_peeled = get_peeled
        self.get_symrefs = get_symrefs
        self.proto = handler.proto
        self.stateless_rpc = handler.stateless_rpc
        self.advertise_refs = handler.advertise_refs
        self._wants: List[bytes] = []
        self.shallow: Set[bytes] = set()
        self.client_shallow: Set[bytes] = set()
        self.unshallow: Set[bytes] = set()
        self._cached = False
        self._cache: List[bytes] = []
        self._cache_index = 0
        self._impl = None

    def determine_wants(self, heads, depth=None):
        """Determine the wants for a set of heads.

        The given heads are advertised to the client, who then specifies which
        refs they want using 'want' lines. This portion of the protocol is the
        same regardless of ack type, and in fact is used to set the ack type of
        the ProtocolGraphWalker.

        If the client has the 'shallow' capability, this method also reads and
        responds to the 'shallow' and 'deepen' lines from the client. These are
        not part of the wants per se, but they set up necessary state for
        walking the graph. Additionally, later code depends on this method
        consuming everything up to the first 'have' line.

        Args:
          heads: a dict of refname->SHA1 to advertise
        Returns: a list of SHA1s requested by the client
        """
        symrefs = self.get_symrefs()
        values = set(heads.values())
        if self.advertise_refs or not self.stateless_rpc:
            for i, (ref, sha) in enumerate(sorted(heads.items())):
                try:
                    peeled_sha = self.get_peeled(ref)
                except KeyError:
                    # Skip refs that are inaccessible
                    # TODO(jelmer): Integrate with Repo.find_missing_objects refs
                    # logic.
                    continue
                if i == 0:
                    logger.info(
                        "Sending capabilities: %s", self.handler.capabilities())
                    line = format_ref_line(
                        ref, sha,
                        self.handler.capabilities()
                        + symref_capabilities(symrefs.items()))
                else:
                    line = format_ref_line(ref, sha)
                self.proto.write_pkt_line(line)
                if peeled_sha != sha:
                    self.proto.write_pkt_line(
                        format_ref_line(ref + PEELED_TAG_SUFFIX, peeled_sha))

            # i'm done..
            self.proto.write_pkt_line(None)

            if self.advertise_refs:
                return []

        # Now client will sending want want want commands
        want = self.proto.read_pkt_line()
        if not want:
            return []
        line, caps = extract_want_line_capabilities(want)
        self.handler.set_client_capabilities(caps)
        self.set_ack_type(ack_type(caps))
        allowed = (COMMAND_WANT, COMMAND_SHALLOW, COMMAND_DEEPEN, None)
        command, sha = _split_proto_line(line, allowed)

        want_revs = []
        while command == COMMAND_WANT:
            if sha not in values:
                raise GitProtocolError("Client wants invalid object %s" % sha)
            want_revs.append(sha)
            command, sha = self.read_proto_line(allowed)

        self.set_wants(want_revs)
        if command in (COMMAND_SHALLOW, COMMAND_DEEPEN):
            self.unread_proto_line(command, sha)
            self._handle_shallow_request(want_revs)

        if self.stateless_rpc and self.proto.eof():
            # The client may close the socket at this point, expecting a
            # flush-pkt from the server. We might be ready to send a packfile
            # at this point, so we need to explicitly short-circuit in this
            # case.
            return []

        return want_revs

    def unread_proto_line(self, command, value):
        if isinstance(value, int):
            value = str(value).encode("ascii")
        self.proto.unread_pkt_line(command + b" " + value)

    def nak(self):
        pass

    def ack(self, have_ref):
        if len(have_ref) != 40:
            raise ValueError("invalid sha %r" % have_ref)
        return self._impl.ack(have_ref)

    def reset(self):
        self._cached = True
        self._cache_index = 0

    def next(self):
        if not self._cached:
            if not self._impl and self.stateless_rpc:
                return None
            return next(self._impl)
        self._cache_index += 1
        if self._cache_index > len(self._cache):
            return None
        return self._cache[self._cache_index]

    __next__ = next

    def read_proto_line(self, allowed):
        """Read a line from the wire.

        Args:
          allowed: An iterable of command names that should be allowed.
        Returns: A tuple of (command, value); see _split_proto_line.
        Raises:
          UnexpectedCommandError: If an error occurred reading the line.
        """
        return _split_proto_line(self.proto.read_pkt_line(), allowed)

    def _handle_shallow_request(self, wants):
        while True:
            command, val = self.read_proto_line((COMMAND_DEEPEN, COMMAND_SHALLOW))
            if command == COMMAND_DEEPEN:
                depth = val
                break
            self.client_shallow.add(val)
        self.read_proto_line((None,))  # consume client's flush-pkt

        shallow, not_shallow = _find_shallow(self.store, wants, depth)

        # Update self.shallow instead of reassigning it since we passed a
        # reference to it before this method was called.
        self.shallow.update(shallow - not_shallow)
        new_shallow = self.shallow - self.client_shallow
        unshallow = self.unshallow = not_shallow & self.client_shallow

        for sha in sorted(new_shallow):
            self.proto.write_pkt_line(format_shallow_line(sha))
        for sha in sorted(unshallow):
            self.proto.write_pkt_line(format_unshallow_line(sha))

        self.proto.write_pkt_line(None)

    def notify_done(self):
        # relay the message down to the handler.
        self.handler.notify_done()

    def send_ack(self, sha, ack_type=b""):
        self.proto.write_pkt_line(format_ack_line(sha, ack_type))

    def send_nak(self):
        self.proto.write_pkt_line(NAK_LINE)

    def handle_done(self, done_required, done_received):
        # Delegate this to the implementation.
        return self._impl.handle_done(done_required, done_received)

    def set_wants(self, wants):
        self._wants = wants

    def all_wants_satisfied(self, haves):
        """Check whether all the current wants are satisfied by a set of haves.

        Args:
          haves: A set of commits we know the client has.
        Note: Wants are specified with set_wants rather than passed in since
            in the current interface they are determined outside this class.
        """
        return _all_wants_satisfied(self.store, haves, self._wants)

    def set_ack_type(self, ack_type):
        impl_classes = {
            MULTI_ACK: MultiAckGraphWalkerImpl,
            MULTI_ACK_DETAILED: MultiAckDetailedGraphWalkerImpl,
            SINGLE_ACK: SingleAckGraphWalkerImpl,
        }
        self._impl = impl_classes[ack_type](self)


_GRAPH_WALKER_COMMANDS = (COMMAND_HAVE, COMMAND_DONE, None)


class SingleAckGraphWalkerImpl:
    """Graph walker implementation that speaks the single-ack protocol."""

    def __init__(self, walker):
        self.walker = walker
        self._common = []

    def ack(self, have_ref):
        if not self._common:
            self.walker.send_ack(have_ref)
            self._common.append(have_ref)

    def next(self):
        command, sha = self.walker.read_proto_line(_GRAPH_WALKER_COMMANDS)
        if command in (None, COMMAND_DONE):
            # defer the handling of done
            self.walker.notify_done()
            return None
        elif command == COMMAND_HAVE:
            return sha

    __next__ = next

    def handle_done(self, done_required, done_received):
        if not self._common:
            self.walker.send_nak()

        if done_required and not done_received:
            # we are not done, especially when done is required; skip
            # the pack for this request and especially do not handle
            # the done.
            return False

        if not done_received and not self._common:
            # Okay we are not actually done then since the walker picked
            # up no haves.  This is usually triggered when client attempts
            # to pull from a source that has no common base_commit.
            # See: test_server.MultiAckDetailedGraphWalkerImplTestCase.\
            #          test_multi_ack_stateless_nodone
            return False

        return True


class MultiAckGraphWalkerImpl:
    """Graph walker implementation that speaks the multi-ack protocol."""

    def __init__(self, walker):
        self.walker = walker
        self._found_base = False
        self._common = []

    def ack(self, have_ref):
        self._common.append(have_ref)
        if not self._found_base:
            self.walker.send_ack(have_ref, b"continue")
            if self.walker.all_wants_satisfied(self._common):
                self._found_base = True
        # else we blind ack within next

    def next(self):
        while True:
            command, sha = self.walker.read_proto_line(_GRAPH_WALKER_COMMANDS)
            if command is None:
                self.walker.send_nak()
                # in multi-ack mode, a flush-pkt indicates the client wants to
                # flush but more have lines are still coming
                continue
            elif command == COMMAND_DONE:
                self.walker.notify_done()
                return None
            elif command == COMMAND_HAVE:
                if self._found_base:
                    # blind ack
                    self.walker.send_ack(sha, b"continue")
                return sha

    __next__ = next

    def handle_done(self, done_required, done_received):
        if done_required and not done_received:
            # we are not done, especially when done is required; skip
            # the pack for this request and especially do not handle
            # the done.
            return False

        if not done_received and not self._common:
            # Okay we are not actually done then since the walker picked
            # up no haves.  This is usually triggered when client attempts
            # to pull from a source that has no common base_commit.
            # See: test_server.MultiAckDetailedGraphWalkerImplTestCase.\
            #          test_multi_ack_stateless_nodone
            return False

        # don't nak unless no common commits were found, even if not
        # everything is satisfied
        if self._common:
            self.walker.send_ack(self._common[-1])
        else:
            self.walker.send_nak()
        return True


class MultiAckDetailedGraphWalkerImpl:
    """Graph walker implementation speaking the multi-ack-detailed protocol."""

    def __init__(self, walker):
        self.walker = walker
        self._common = []

    def ack(self, have_ref):
        # Should only be called iff have_ref is common
        self._common.append(have_ref)
        self.walker.send_ack(have_ref, b"common")

    def next(self):
        while True:
            command, sha = self.walker.read_proto_line(_GRAPH_WALKER_COMMANDS)
            if command is None:
                if self.walker.all_wants_satisfied(self._common):
                    self.walker.send_ack(self._common[-1], b"ready")
                self.walker.send_nak()
                if self.walker.stateless_rpc:
                    # The HTTP version of this request a flush-pkt always
                    # signifies an end of request, so we also return
                    # nothing here as if we are done (but not really, as
                    # it depends on whether no-done capability was
                    # specified and that's handled in handle_done which
                    # may or may not call post_nodone_check depending on
                    # that).
                    return None
            elif command == COMMAND_DONE:
                # Let the walker know that we got a done.
                self.walker.notify_done()
                break
            elif command == COMMAND_HAVE:
                # return the sha and let the caller ACK it with the
                # above ack method.
                return sha
        # don't nak unless no common commits were found, even if not
        # everything is satisfied

    __next__ = next

    def handle_done(self, done_required, done_received):
        if done_required and not done_received:
            # we are not done, especially when done is required; skip
            # the pack for this request and especially do not handle
            # the done.
            return False

        if not done_received and not self._common:
            # Okay we are not actually done then since the walker picked
            # up no haves.  This is usually triggered when client attempts
            # to pull from a source that has no common base_commit.
            # See: test_server.MultiAckDetailedGraphWalkerImplTestCase.\
            #          test_multi_ack_stateless_nodone
            return False

        # don't nak unless no common commits were found, even if not
        # everything is satisfied
        if self._common:
            self.walker.send_ack(self._common[-1])
        else:
            self.walker.send_nak()
        return True


class ReceivePackHandler(PackHandler):
    """Protocol handler for downloading a pack from the client."""

    def __init__(self, backend, args, proto, stateless_rpc=False, advertise_refs=False):
        super().__init__(
            backend, proto, stateless_rpc=stateless_rpc
        )
        self.repo = backend.open_repository(args[0])
        self.advertise_refs = advertise_refs

    @classmethod
    def capabilities(cls) -> Iterable[bytes]:
        return [
            CAPABILITY_REPORT_STATUS,
            CAPABILITY_DELETE_REFS,
            CAPABILITY_QUIET,
            CAPABILITY_OFS_DELTA,
            CAPABILITY_SIDE_BAND_64K,
            CAPABILITY_NO_DONE,
        ]

    def _apply_pack(
        self, refs: List[Tuple[bytes, bytes, bytes]]
    ) -> List[Tuple[bytes, bytes]]:
        all_exceptions = (
            IOError,
            OSError,
            ChecksumMismatch,
            ApplyDeltaError,
            AssertionError,
            socket.error,
            zlib.error,
            ObjectFormatException,
        )
        status = []
        will_send_pack = False

        for command in refs:
            if command[1] != ZERO_SHA:
                will_send_pack = True

        if will_send_pack:
            # TODO: more informative error messages than just the exception
            # string
            try:
                recv = getattr(self.proto, "recv", None)
                self.repo.object_store.add_thin_pack(self.proto.read, recv)
                status.append((b"unpack", b"ok"))
            except all_exceptions as e:
                status.append((b"unpack", str(e).replace("\n", "").encode("utf-8")))
                # The pack may still have been moved in, but it may contain
                # broken objects. We trust a later GC to clean it up.
        else:
            # The git protocol want to find a status entry related to unpack
            # process even if no pack data has been sent.
            status.append((b"unpack", b"ok"))

        for oldsha, sha, ref in refs:
            ref_status = b"ok"
            try:
                if sha == ZERO_SHA:
                    if CAPABILITY_DELETE_REFS not in self.capabilities():
                        raise GitProtocolError(
                            "Attempted to delete refs without delete-refs "
                            "capability."
                        )
                    try:
                        self.repo.refs.remove_if_equals(ref, oldsha)
                    except all_exceptions:
                        ref_status = b"failed to delete"
                else:
                    try:
                        self.repo.refs.set_if_equals(ref, oldsha, sha)
                    except all_exceptions:
                        ref_status = b"failed to write"
            except KeyError:
                ref_status = b"bad ref"
            status.append((ref, ref_status))

        return status

    def _report_status(self, status: List[Tuple[bytes, bytes]]) -> None:
        if self.has_capability(CAPABILITY_SIDE_BAND_64K):
            writer = BufferedPktLineWriter(
                lambda d: self.proto.write_sideband(SIDE_BAND_CHANNEL_DATA, d)
            )
            write = writer.write

            def flush():
                writer.flush()
                self.proto.write_pkt_line(None)

        else:
            write = self.proto.write_pkt_line

            def flush():
                pass

        for name, msg in status:
            if name == b"unpack":
                write(b"unpack " + msg + b"\n")
            elif msg == b"ok":
                write(b"ok " + name + b"\n")
            else:
                write(b"ng " + name + b" " + msg + b"\n")
        write(None)
        flush()

    def _on_post_receive(self, client_refs):
        hook = self.repo.hooks.get("post-receive", None)
        if not hook:
            return
        try:
            output = hook.execute(client_refs)
            if output:
                self.proto.write_sideband(SIDE_BAND_CHANNEL_PROGRESS, output)
        except HookError as err:
            self.proto.write_sideband(SIDE_BAND_CHANNEL_FATAL, str(err).encode('utf-8'))

    def handle(self) -> None:
        if self.advertise_refs or not self.stateless_rpc:
            refs = sorted(self.repo.get_refs().items())
            symrefs = sorted(self.repo.refs.get_symrefs().items())

            if not refs:
                refs = [(CAPABILITIES_REF, ZERO_SHA)]
            logger.info(
                "Sending capabilities: %s", self.capabilities())
            self.proto.write_pkt_line(
                format_ref_line(
                    refs[0][0], refs[0][1],
                    self.capabilities() + symref_capabilities(symrefs)))
            for i in range(1, len(refs)):
                ref = refs[i]
                self.proto.write_pkt_line(format_ref_line(ref[0], ref[1]))

            self.proto.write_pkt_line(None)
            if self.advertise_refs:
                return

        client_refs = []
        ref = self.proto.read_pkt_line()

        # if ref is none then client doesn't want to send us anything..
        if ref is None:
            return

        ref, caps = extract_capabilities(ref)
        self.set_client_capabilities(caps)

        # client will now send us a list of (oldsha, newsha, ref)
        while ref:
            client_refs.append(ref.split())
            ref = self.proto.read_pkt_line()

        # backend can now deal with this refs and read a pack using self.read
        status = self._apply_pack(client_refs)

        self._on_post_receive(client_refs)

        # when we have read all the pack from the client, send a status report
        # if the client asked for it
        if self.has_capability(CAPABILITY_REPORT_STATUS):
            self._report_status(status)


class UploadArchiveHandler(Handler):
    def __init__(self, backend, args, proto, stateless_rpc=False):
        super().__init__(backend, proto, stateless_rpc)
        self.repo = backend.open_repository(args[0])

    def handle(self):
        def write(x):
            return self.proto.write_sideband(SIDE_BAND_CHANNEL_DATA, x)

        arguments = []
        for pkt in self.proto.read_pkt_seq():
            (key, value) = pkt.split(b" ", 1)
            if key != b"argument":
                raise GitProtocolError("unknown command %s" % key)
            arguments.append(value.rstrip(b"\n"))
        prefix = b""
        format = "tar"
        i = 0
        store: ObjectContainer = self.repo.object_store
        while i < len(arguments):
            argument = arguments[i]
            if argument == b"--prefix":
                i += 1
                prefix = arguments[i]
            elif argument == b"--format":
                i += 1
                format = arguments[i].decode("ascii")
            else:
                commit_sha = self.repo.refs[argument]
                tree = store[store[commit_sha].tree]
            i += 1
        self.proto.write_pkt_line(b"ACK")
        self.proto.write_pkt_line(None)
        for chunk in tar_stream(
            store, tree, mtime=time.time(), prefix=prefix, format=format
        ):
            write(chunk)
        self.proto.write_pkt_line(None)


# Default handler classes for git services.
DEFAULT_HANDLERS = {
    b"git-upload-pack": UploadPackHandler,
    b"git-receive-pack": ReceivePackHandler,
    b"git-upload-archive": UploadArchiveHandler,
}


class TCPGitRequestHandler(socketserver.StreamRequestHandler):
    def __init__(self, handlers, *args, **kwargs):
        self.handlers = handlers
        socketserver.StreamRequestHandler.__init__(self, *args, **kwargs)

    def handle(self):
        proto = ReceivableProtocol(self.connection.recv, self.wfile.write)
        command, args = proto.read_cmd()
        logger.info("Handling %s request, args=%s", command, args)

        cls = self.handlers.get(command, None)
        if not callable(cls):
            raise GitProtocolError("Invalid service %s" % command)
        h = cls(self.server.backend, args, proto)
        h.handle()


class TCPGitServer(socketserver.TCPServer):

    allow_reuse_address = True
    serve = socketserver.TCPServer.serve_forever

    def _make_handler(self, *args, **kwargs):
        return TCPGitRequestHandler(self.handlers, *args, **kwargs)

    def __init__(self, backend, listen_addr, port=TCP_GIT_PORT, handlers=None):
        self.handlers = dict(DEFAULT_HANDLERS)
        if handlers is not None:
            self.handlers.update(handlers)
        self.backend = backend
        logger.info("Listening for TCP connections on %s:%d", listen_addr, port)
        socketserver.TCPServer.__init__(self, (listen_addr, port), self._make_handler)

    def verify_request(self, request, client_address):
        logger.info("Handling request from %s", client_address)
        return True

    def handle_error(self, request, client_address):
        logger.exception(
            "Exception happened during processing of request " "from %s",
            client_address,
        )


def main(argv=sys.argv):
    """Entry point for starting a TCP git server."""
    import optparse

    parser = optparse.OptionParser()
    parser.add_option(
        "-l",
        "--listen_address",
        dest="listen_address",
        default="localhost",
        help="Binding IP address.",
    )
    parser.add_option(
        "-p",
        "--port",
        dest="port",
        type=int,
        default=TCP_GIT_PORT,
        help="Binding TCP port.",
    )
    options, args = parser.parse_args(argv)

    log_utils.default_logging_config()
    if len(args) > 1:
        gitdir = args[1]
    else:
        gitdir = "."
    # TODO(jelmer): Support git-daemon-export-ok and --export-all.
    backend = FileSystemBackend(gitdir)
    server = TCPGitServer(backend, options.listen_address, options.port)
    server.serve_forever()


def serve_command(
    handler_cls, argv=sys.argv, backend=None, inf=sys.stdin, outf=sys.stdout
):
    """Serve a single command.

    This is mostly useful for the implementation of commands used by e.g.
    git+ssh.

    Args:
      handler_cls: `Handler` class to use for the request
      argv: execv-style command-line arguments. Defaults to sys.argv.
      backend: `Backend` to use
      inf: File-like object to read from, defaults to standard input.
      outf: File-like object to write to, defaults to standard output.
    Returns: Exit code for use with sys.exit. 0 on success, 1 on failure.
    """
    if backend is None:
        backend = FileSystemBackend()

    def send_fn(data):
        outf.write(data)
        outf.flush()

    proto = Protocol(inf.read, send_fn)
    handler = handler_cls(backend, argv[1:], proto)
    # FIXME: Catch exceptions and write a single-line summary to outf.
    handler.handle()
    return 0


def generate_info_refs(repo):
    """Generate an info refs file."""
    refs = repo.get_refs()
    return write_info_refs(refs, repo.object_store)


def generate_objects_info_packs(repo):
    """Generate an index for for packs."""
    for pack in repo.object_store.packs:
        yield (b"P " + os.fsencode(pack.data.filename) + b"\n")


def update_server_info(repo):
    """Generate server info for dumb file access.

    This generates info/refs and objects/info/packs,
    similar to "git update-server-info".
    """
    repo._put_named_file(
        os.path.join("info", "refs"), b"".join(generate_info_refs(repo))
    )

    repo._put_named_file(
        os.path.join("objects", "info", "packs"),
        b"".join(generate_objects_info_packs(repo)),
    )


if __name__ == "__main__":
    main()
