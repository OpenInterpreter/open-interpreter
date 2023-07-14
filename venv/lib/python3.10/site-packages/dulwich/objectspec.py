# objectspec.py -- Object specification
# Copyright (C) 2014 Jelmer Vernooij <jelmer@jelmer.uk>
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

"""Object specification."""

from typing import TYPE_CHECKING, Iterator, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from .objects import Commit, ShaFile, Tree
    from .refs import Ref, RefsContainer
    from .repo import Repo


def to_bytes(text: Union[str, bytes]) -> bytes:
    if getattr(text, "encode", None) is not None:
        text = text.encode("ascii")  # type: ignore
    return text  # type: ignore


def parse_object(repo: "Repo", objectish: Union[bytes, str]) -> "ShaFile":
    """Parse a string referring to an object.

    Args:
      repo: A `Repo` object
      objectish: A string referring to an object
    Returns: A git object
    Raises:
      KeyError: If the object can not be found
    """
    objectish = to_bytes(objectish)
    return repo[objectish]


def parse_tree(repo: "Repo", treeish: Union[bytes, str]) -> "Tree":
    """Parse a string referring to a tree.

    Args:
      repo: A `Repo` object
      treeish: A string referring to a tree
    Returns: A git object
    Raises:
      KeyError: If the object can not be found
    """
    treeish = to_bytes(treeish)
    try:
        treeish = parse_ref(repo, treeish)
    except KeyError:  # treeish is commit sha
        pass
    o = repo[treeish]
    if o.type_name == b"commit":
        return repo[o.tree]
    return o


def parse_ref(container: Union["Repo", "RefsContainer"], refspec: Union[str, bytes]) -> "Ref":
    """Parse a string referring to a reference.

    Args:
      container: A RefsContainer object
      refspec: A string referring to a ref
    Returns: A ref
    Raises:
      KeyError: If the ref can not be found
    """
    refspec = to_bytes(refspec)
    possible_refs = [
        refspec,
        b"refs/" + refspec,
        b"refs/tags/" + refspec,
        b"refs/heads/" + refspec,
        b"refs/remotes/" + refspec,
        b"refs/remotes/" + refspec + b"/HEAD",
    ]
    for ref in possible_refs:
        if ref in container:
            return ref
    raise KeyError(refspec)


def parse_reftuple(
        lh_container: Union["Repo", "RefsContainer"],
        rh_container: Union["Repo", "RefsContainer"], refspec: Union[str, bytes],
        force: bool = False) -> Tuple[Optional["Ref"], Optional["Ref"], bool]:
    """Parse a reftuple spec.

    Args:
      lh_container: A RefsContainer object
      rh_container: A RefsContainer object
      refspec: A string
    Returns: A tuple with left and right ref
    Raises:
      KeyError: If one of the refs can not be found
    """
    refspec = to_bytes(refspec)
    if refspec.startswith(b"+"):
        force = True
        refspec = refspec[1:]
    lh: Optional[bytes]
    rh: Optional[bytes]
    if b":" in refspec:
        (lh, rh) = refspec.split(b":")
    else:
        lh = rh = refspec
    if lh == b"":
        lh = None
    else:
        lh = parse_ref(lh_container, lh)
    if rh == b"":
        rh = None
    else:
        try:
            rh = parse_ref(rh_container, rh)
        except KeyError:
            # TODO: check force?
            if b"/" not in rh:
                rh = b"refs/heads/" + rh
    return (lh, rh, force)


def parse_reftuples(
        lh_container: Union["Repo", "RefsContainer"],
        rh_container: Union["Repo", "RefsContainer"],
        refspecs: Union[bytes, List[bytes]],
        force: bool = False):
    """Parse a list of reftuple specs to a list of reftuples.

    Args:
      lh_container: A RefsContainer object
      rh_container: A RefsContainer object
      refspecs: A list of refspecs or a string
      force: Force overwriting for all reftuples
    Returns: A list of refs
    Raises:
      KeyError: If one of the refs can not be found
    """
    if not isinstance(refspecs, list):
        refspecs = [refspecs]
    ret = []
    # TODO: Support * in refspecs
    for refspec in refspecs:
        ret.append(parse_reftuple(lh_container, rh_container, refspec, force=force))
    return ret


def parse_refs(container, refspecs):
    """Parse a list of refspecs to a list of refs.

    Args:
      container: A RefsContainer object
      refspecs: A list of refspecs or a string
    Returns: A list of refs
    Raises:
      KeyError: If one of the refs can not be found
    """
    # TODO: Support * in refspecs
    if not isinstance(refspecs, list):
        refspecs = [refspecs]
    ret = []
    for refspec in refspecs:
        ret.append(parse_ref(container, refspec))
    return ret


def parse_commit_range(repo: "Repo", committishs: Union[str, bytes]) -> Iterator["Commit"]:
    """Parse a string referring to a range of commits.

    Args:
      repo: A `Repo` object
      committishs: A string referring to a range of commits.
    Returns: An iterator over `Commit` objects
    Raises:
      KeyError: When the reference commits can not be found
      ValueError: If the range can not be parsed
    """
    committishs = to_bytes(committishs)
    # TODO(jelmer): Support more than a single commit..
    return iter([parse_commit(repo, committishs)])


class AmbiguousShortId(Exception):
    """The short id is ambiguous."""

    def __init__(self, prefix, options):
        self.prefix = prefix
        self.options = options


def scan_for_short_id(object_store, prefix):
    """Scan an object store for a short id."""
    # TODO(jelmer): This could short-circuit looking for objects
    # starting with a certain prefix.
    ret = []
    for object_id in object_store:
        if object_id.startswith(prefix):
            ret.append(object_store[object_id])
    if not ret:
        raise KeyError(prefix)
    if len(ret) == 1:
        return ret[0]
    raise AmbiguousShortId(prefix, ret)


def parse_commit(repo: "Repo", committish: Union[str, bytes]) -> "Commit":
    """Parse a string referring to a single commit.

    Args:
      repo: A` Repo` object
      committish: A string referring to a single commit.
    Returns: A Commit object
    Raises:
      KeyError: When the reference commits can not be found
      ValueError: If the range can not be parsed
    """
    committish = to_bytes(committish)
    try:
        return repo[committish]
    except KeyError:
        pass
    try:
        return repo[parse_ref(repo, committish)]
    except KeyError:
        pass
    if len(committish) >= 4 and len(committish) < 40:
        try:
            int(committish, 16)
        except ValueError:
            pass
        else:
            try:
                return scan_for_short_id(repo.object_store, committish)
            except KeyError:
                pass
    raise KeyError(committish)


# TODO: parse_path_in_tree(), which handles e.g. v1.0:Documentation
