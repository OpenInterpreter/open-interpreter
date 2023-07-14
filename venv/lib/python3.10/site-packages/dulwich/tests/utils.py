# utils.py -- Test utilities for Dulwich.
# Copyright (C) 2010 Google, Inc.
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

"""Utility functions common to Dulwich tests."""


import datetime
import os
import shutil
import tempfile
import time
import types
import warnings

from dulwich.tests import SkipTest, skipIf  # noqa: F401

from ..index import commit_tree
from ..objects import Commit, FixedSha, Tag, object_class
from ..pack import (DELTA_TYPES, OFS_DELTA, REF_DELTA, SHA1Writer,
                    create_delta, obj_sha, write_pack_header,
                    write_pack_object)
from ..repo import Repo

# Plain files are very frequently used in tests, so let the mode be very short.
F = 0o100644  # Shorthand mode for Files.


def open_repo(name, temp_dir=None):
    """Open a copy of a repo in a temporary directory.

    Use this function for accessing repos in dulwich/tests/data/repos to avoid
    accidentally or intentionally modifying those repos in place. Use
    tear_down_repo to delete any temp files created.

    Args:
      name: The name of the repository, relative to
        dulwich/tests/data/repos
      temp_dir: temporary directory to initialize to. If not provided, a
        temporary directory will be created.
    Returns: An initialized Repo object that lives in a temporary directory.
    """
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()
    repo_dir = os.path.join(os.path.dirname(__file__), "..", "..", "testdata", "repos", name)
    temp_repo_dir = os.path.join(temp_dir, name)
    shutil.copytree(repo_dir, temp_repo_dir, symlinks=True)
    return Repo(temp_repo_dir)


def tear_down_repo(repo):
    """Tear down a test repository."""
    repo.close()
    temp_dir = os.path.dirname(repo.path.rstrip(os.sep))
    shutil.rmtree(temp_dir)


def make_object(cls, **attrs):
    """Make an object for testing and assign some members.

    This method creates a new subclass to allow arbitrary attribute
    reassignment, which is not otherwise possible with objects having
    __slots__.

    Args:
      attrs: dict of attributes to set on the new object.
    Returns: A newly initialized object of type cls.
    """

    class TestObject(cls):
        """Class that inherits from the given class, but without __slots__.

        Note that classes with __slots__ can't have arbitrary attributes
        monkey-patched in, so this is a class that is exactly the same only
        with a __dict__ instead of __slots__.
        """

        pass

    TestObject.__name__ = "TestObject_" + cls.__name__

    obj = TestObject()
    for name, value in attrs.items():
        if name == "id":
            # id property is read-only, so we overwrite sha instead.
            sha = FixedSha(value)
            obj.sha = lambda: sha
        else:
            setattr(obj, name, value)
    return obj


def make_commit(**attrs):
    """Make a Commit object with a default set of members.

    Args:
      attrs: dict of attributes to overwrite from the default values.
    Returns: A newly initialized Commit object.
    """
    default_time = 1262304000  # 2010-01-01 00:00:00
    all_attrs = {
        "author": b"Test Author <test@nodomain.com>",
        "author_time": default_time,
        "author_timezone": 0,
        "committer": b"Test Committer <test@nodomain.com>",
        "commit_time": default_time,
        "commit_timezone": 0,
        "message": b"Test message.",
        "parents": [],
        "tree": b"0" * 40,
    }
    all_attrs.update(attrs)
    return make_object(Commit, **all_attrs)


def make_tag(target, **attrs):
    """Make a Tag object with a default set of values.

    Args:
      target: object to be tagged (Commit, Blob, Tree, etc)
      attrs: dict of attributes to overwrite from the default values.
    Returns: A newly initialized Tag object.
    """
    target_id = target.id
    target_type = object_class(target.type_name)
    default_time = int(time.mktime(datetime.datetime(2010, 1, 1).timetuple()))
    all_attrs = {
        "tagger": b"Test Author <test@nodomain.com>",
        "tag_time": default_time,
        "tag_timezone": 0,
        "message": b"Test message.",
        "object": (target_type, target_id),
        "name": b"Test Tag",
    }
    all_attrs.update(attrs)
    return make_object(Tag, **all_attrs)


def functest_builder(method, func):
    """Generate a test method that tests the given function."""

    def do_test(self):
        method(self, func)

    return do_test


def ext_functest_builder(method, func):
    """Generate a test method that tests the given extension function.

    This is intended to generate test methods that test both a pure-Python
    version and an extension version using common test code. The extension test
    will raise SkipTest if the extension is not found.

    Sample usage:

    class MyTest(TestCase);
        def _do_some_test(self, func_impl):
            self.assertEqual('foo', func_impl())

        test_foo = functest_builder(_do_some_test, foo_py)
        test_foo_extension = ext_functest_builder(_do_some_test, _foo_c)

    Args:
      method: The method to run. It must must two parameters, self and the
        function implementation to test.
      func: The function implementation to pass to method.
    """

    def do_test(self):
        if not isinstance(func, types.BuiltinFunctionType):
            raise SkipTest("%s extension not found" % func)
        method(self, func)

    return do_test


def build_pack(f, objects_spec, store=None):
    """Write test pack data from a concise spec.

    Args:
      f: A file-like object to write the pack to.
      objects_spec: A list of (type_num, obj). For non-delta types, obj
        is the string of that object's data.
        For delta types, obj is a tuple of (base, data), where:

        * base can be either an index in objects_spec of the base for that
        * delta; or for a ref delta, a SHA, in which case the resulting pack
        * will be thin and the base will be an external ref.
        * data is a string of the full, non-deltified data for that object.

        Note that offsets/refs and deltas are computed within this function.
      store: An optional ObjectStore for looking up external refs.
    Returns: A list of tuples in the order specified by objects_spec:
        (offset, type num, data, sha, CRC32)
    """
    sf = SHA1Writer(f)
    num_objects = len(objects_spec)
    write_pack_header(sf.write, num_objects)

    full_objects = {}
    offsets = {}
    crc32s = {}

    while len(full_objects) < num_objects:
        for i, (type_num, data) in enumerate(objects_spec):
            if type_num not in DELTA_TYPES:
                full_objects[i] = (type_num, data, obj_sha(type_num, [data]))
                continue
            base, data = data
            if isinstance(base, int):
                if base not in full_objects:
                    continue
                base_type_num, _, _ = full_objects[base]
            else:
                base_type_num, _ = store.get_raw(base)
            full_objects[i] = (
                base_type_num,
                data,
                obj_sha(base_type_num, [data]),
            )

    for i, (type_num, obj) in enumerate(objects_spec):
        offset = f.tell()
        if type_num == OFS_DELTA:
            base_index, data = obj
            base = offset - offsets[base_index]
            _, base_data, _ = full_objects[base_index]
            obj = (base, list(create_delta(base_data, data)))
        elif type_num == REF_DELTA:
            base_ref, data = obj
            if isinstance(base_ref, int):
                _, base_data, base = full_objects[base_ref]
            else:
                base_type_num, base_data = store.get_raw(base_ref)
                base = obj_sha(base_type_num, base_data)
            obj = (base, list(create_delta(base_data, data)))

        crc32 = write_pack_object(sf.write, type_num, obj)
        offsets[i] = offset
        crc32s[i] = crc32

    expected = []
    for i in range(num_objects):
        type_num, data, sha = full_objects[i]
        assert len(sha) == 20
        expected.append((offsets[i], type_num, data, sha, crc32s[i]))

    sf.write_sha()
    f.seek(0)
    return expected


def build_commit_graph(object_store, commit_spec, trees=None, attrs=None):
    """Build a commit graph from a concise specification.

    Sample usage:
    >>> c1, c2, c3 = build_commit_graph(store, [[1], [2, 1], [3, 1, 2]])
    >>> store[store[c3].parents[0]] == c1
    True
    >>> store[store[c3].parents[1]] == c2
    True

    If not otherwise specified, commits will refer to the empty tree and have
    commit times increasing in the same order as the commit spec.

    Args:
      object_store: An ObjectStore to commit objects to.
      commit_spec: An iterable of iterables of ints defining the commit
        graph. Each entry defines one commit, and entries must be in
        topological order. The first element of each entry is a commit number,
        and the remaining elements are its parents. The commit numbers are only
        meaningful for the call to make_commits; since real commit objects are
        created, they will get created with real, opaque SHAs.
      trees: An optional dict of commit number -> tree spec for building
        trees for commits. The tree spec is an iterable of (path, blob, mode)
        or (path, blob) entries; if mode is omitted, it defaults to the normal
        file mode (0100644).
      attrs: A dict of commit number -> (dict of attribute -> value) for
        assigning additional values to the commits.
    Returns: The list of commit objects created.
    Raises:
      ValueError: If an undefined commit identifier is listed as a parent.
    """
    if trees is None:
        trees = {}
    if attrs is None:
        attrs = {}
    commit_time = 0
    nums = {}
    commits = []

    for commit in commit_spec:
        commit_num = commit[0]
        try:
            parent_ids = [nums[pn] for pn in commit[1:]]
        except KeyError as exc:
            (missing_parent,) = exc.args
            raise ValueError("Unknown parent %i" % missing_parent) from exc

        blobs = []
        for entry in trees.get(commit_num, []):
            if len(entry) == 2:
                path, blob = entry
                entry = (path, blob, F)
            path, blob, mode = entry
            blobs.append((path, blob.id, mode))
            object_store.add_object(blob)
        tree_id = commit_tree(object_store, blobs)

        commit_attrs = {
            "message": ("Commit %i" % commit_num).encode("ascii"),
            "parents": parent_ids,
            "tree": tree_id,
            "commit_time": commit_time,
        }
        commit_attrs.update(attrs.get(commit_num, {}))
        commit_obj = make_commit(**commit_attrs)

        # By default, increment the time by a lot. Out-of-order commits should
        # be closer together than this because their main cause is clock skew.
        commit_time = commit_attrs["commit_time"] + 100
        nums[commit_num] = commit_obj.id
        object_store.add_object(commit_obj)
        commits.append(commit_obj)

    return commits


def setup_warning_catcher():
    """Wrap warnings.showwarning with code that records warnings."""

    caught_warnings = []
    original_showwarning = warnings.showwarning

    def custom_showwarning(*args, **kwargs):
        caught_warnings.append(args[0])

    warnings.showwarning = custom_showwarning

    def restore_showwarning():
        warnings.showwarning = original_showwarning

    return caught_warnings, restore_showwarning
