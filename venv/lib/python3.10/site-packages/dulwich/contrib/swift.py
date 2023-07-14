# swift.py -- Repo implementation atop OpenStack SWIFT
# Copyright (C) 2013 eNovance SAS <licensing@enovance.com>
#
# Author: Fabien Boucher <fabien.boucher@enovance.com>
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

"""Repo implementation atop OpenStack SWIFT."""

# TODO: Refactor to share more code with dulwich/repo.py.
# TODO(fbo): Second attempt to _send() must be notified via real log
# TODO(fbo): More logs for operations

import json
import os
import posixpath
import stat
import sys
import tempfile
import urllib.parse as urlparse
import zlib
from configparser import ConfigParser
from io import BytesIO

from geventhttpclient import HTTPClient

from ..greenthreads import GreenThreadsMissingObjectFinder
from ..lru_cache import LRUSizeCache
from ..object_store import INFODIR, PACKDIR, PackBasedObjectStore
from ..objects import S_ISGITLINK, Blob, Commit, Tag, Tree
from ..pack import (Pack, PackData, PackIndexer, PackStreamCopier,
                    _compute_object_size, compute_file_sha, iter_sha1,
                    load_pack_index_file, read_pack_header, unpack_object,
                    write_pack_header, write_pack_index_v2, write_pack_object)
from ..protocol import TCP_GIT_PORT
from ..refs import InfoRefsContainer, read_info_refs, write_info_refs
from ..repo import OBJECTDIR, BaseRepo
from ..server import Backend, TCPGitServer

"""
# Configuration file sample
[swift]
# Authentication URL (Keystone or Swift)
auth_url = http://127.0.0.1:5000/v2.0
# Authentication version to use
auth_ver = 2
# The tenant and username separated by a semicolon
username = admin;admin
# The user password
password = pass
# The Object storage region to use (auth v2) (Default RegionOne)
region_name = RegionOne
# The Object storage endpoint URL to use (auth v2) (Default internalURL)
endpoint_type = internalURL
# Concurrency to use for parallel tasks (Default 10)
concurrency = 10
# Size of the HTTP pool (Default 10)
http_pool_length = 10
# Timeout delay for HTTP connections (Default 20)
http_timeout = 20
# Chunk size to read from pack (Bytes) (Default 12228)
chunk_length = 12228
# Cache size (MBytes) (Default 20)
cache_length = 20
"""


class PackInfoMissingObjectFinder(GreenThreadsMissingObjectFinder):
    def next(self):
        while True:
            if not self.objects_to_send:
                return None
            (sha, name, leaf) = self.objects_to_send.pop()
            if sha not in self.sha_done:
                break
        if not leaf:
            info = self.object_store.pack_info_get(sha)
            if info[0] == Commit.type_num:
                self.add_todo([(info[2], "", False)])
            elif info[0] == Tree.type_num:
                self.add_todo([tuple(i) for i in info[1]])
            elif info[0] == Tag.type_num:
                self.add_todo([(info[1], None, False)])
            if sha in self._tagged:
                self.add_todo([(self._tagged[sha], None, True)])
        self.sha_done.add(sha)
        self.progress("counting objects: %d\r" % len(self.sha_done))
        return (sha, name)


def load_conf(path=None, file=None):
    """Load configuration in global var CONF

    Args:
      path: The path to the configuration file
      file: If provided read instead the file like object
    """
    conf = ConfigParser()
    if file:
        try:
            conf.read_file(file, path)
        except AttributeError:
            # read_file only exists in Python3
            conf.readfp(file)
        return conf
    confpath = None
    if not path:
        try:
            confpath = os.environ["DULWICH_SWIFT_CFG"]
        except KeyError as exc:
            raise Exception(
                "You need to specify a configuration file") from exc
    else:
        confpath = path
    if not os.path.isfile(confpath):
        raise Exception("Unable to read configuration file %s" % confpath)
    conf.read(confpath)
    return conf


def swift_load_pack_index(scon, filename):
    """Read a pack index file from Swift

    Args:
      scon: a `SwiftConnector` instance
      filename: Path to the index file objectise
    Returns: a `PackIndexer` instance
    """
    with scon.get_object(filename) as f:
        return load_pack_index_file(filename, f)


def pack_info_create(pack_data, pack_index):
    pack = Pack.from_objects(pack_data, pack_index)
    info = {}
    for obj in pack.iterobjects():
        # Commit
        if obj.type_num == Commit.type_num:
            info[obj.id] = (obj.type_num, obj.parents, obj.tree)
        # Tree
        elif obj.type_num == Tree.type_num:
            shas = [
                (s, n, not stat.S_ISDIR(m))
                for n, m, s in obj.items()
                if not S_ISGITLINK(m)
            ]
            info[obj.id] = (obj.type_num, shas)
        # Blob
        elif obj.type_num == Blob.type_num:
            info[obj.id] = None
        # Tag
        elif obj.type_num == Tag.type_num:
            info[obj.id] = (obj.type_num, obj.object[1])
    return zlib.compress(json.dumps(info))


def load_pack_info(filename, scon=None, file=None):
    if not file:
        f = scon.get_object(filename)
    else:
        f = file
    if not f:
        return None
    try:
        return json.loads(zlib.decompress(f.read()))
    finally:
        f.close()


class SwiftException(Exception):
    pass


class SwiftConnector:
    """A Connector to swift that manage authentication and errors catching"""

    def __init__(self, root, conf):
        """Initialize a SwiftConnector

        Args:
          root: The swift container that will act as Git bare repository
          conf: A ConfigParser Object
        """
        self.conf = conf
        self.auth_ver = self.conf.get("swift", "auth_ver")
        if self.auth_ver not in ["1", "2"]:
            raise NotImplementedError("Wrong authentication version use either 1 or 2")
        self.auth_url = self.conf.get("swift", "auth_url")
        self.user = self.conf.get("swift", "username")
        self.password = self.conf.get("swift", "password")
        self.concurrency = self.conf.getint("swift", "concurrency") or 10
        self.http_timeout = self.conf.getint("swift", "http_timeout") or 20
        self.http_pool_length = self.conf.getint("swift", "http_pool_length") or 10
        self.region_name = self.conf.get("swift", "region_name") or "RegionOne"
        self.endpoint_type = self.conf.get("swift", "endpoint_type") or "internalURL"
        self.cache_length = self.conf.getint("swift", "cache_length") or 20
        self.chunk_length = self.conf.getint("swift", "chunk_length") or 12228
        self.root = root
        block_size = 1024 * 12  # 12KB
        if self.auth_ver == "1":
            self.storage_url, self.token = self.swift_auth_v1()
        else:
            self.storage_url, self.token = self.swift_auth_v2()

        token_header = {"X-Auth-Token": str(self.token)}
        self.httpclient = HTTPClient.from_url(
            str(self.storage_url),
            concurrency=self.http_pool_length,
            block_size=block_size,
            connection_timeout=self.http_timeout,
            network_timeout=self.http_timeout,
            headers=token_header,
        )
        self.base_path = str(
            posixpath.join(urlparse.urlparse(self.storage_url).path, self.root)
        )

    def swift_auth_v1(self):
        self.user = self.user.replace(";", ":")
        auth_httpclient = HTTPClient.from_url(
            self.auth_url,
            connection_timeout=self.http_timeout,
            network_timeout=self.http_timeout,
        )
        headers = {"X-Auth-User": self.user, "X-Auth-Key": self.password}
        path = urlparse.urlparse(self.auth_url).path

        ret = auth_httpclient.request("GET", path, headers=headers)

        # Should do something with redirections (301 in my case)

        if ret.status_code < 200 or ret.status_code >= 300:
            raise SwiftException(
                "AUTH v1.0 request failed on "
                + "%s with error code %s (%s)"
                % (
                    str(auth_httpclient.get_base_url()) + path,
                    ret.status_code,
                    str(ret.items()),
                )
            )
        storage_url = ret["X-Storage-Url"]
        token = ret["X-Auth-Token"]
        return storage_url, token

    def swift_auth_v2(self):
        self.tenant, self.user = self.user.split(";")
        auth_dict = {}
        auth_dict["auth"] = {
            "passwordCredentials": {
                "username": self.user,
                "password": self.password,
            },
            "tenantName": self.tenant,
        }
        auth_json = json.dumps(auth_dict)
        headers = {"Content-Type": "application/json"}
        auth_httpclient = HTTPClient.from_url(
            self.auth_url,
            connection_timeout=self.http_timeout,
            network_timeout=self.http_timeout,
        )
        path = urlparse.urlparse(self.auth_url).path
        if not path.endswith("tokens"):
            path = posixpath.join(path, "tokens")
        ret = auth_httpclient.request("POST", path, body=auth_json, headers=headers)

        if ret.status_code < 200 or ret.status_code >= 300:
            raise SwiftException(
                "AUTH v2.0 request failed on "
                + "%s with error code %s (%s)"
                % (
                    str(auth_httpclient.get_base_url()) + path,
                    ret.status_code,
                    str(ret.items()),
                )
            )
        auth_ret_json = json.loads(ret.read())
        token = auth_ret_json["access"]["token"]["id"]
        catalogs = auth_ret_json["access"]["serviceCatalog"]
        object_store = [
            o_store for o_store in catalogs if o_store["type"] == "object-store"
        ][0]
        endpoints = object_store["endpoints"]
        endpoint = [endp for endp in endpoints if endp["region"] == self.region_name][0]
        return endpoint[self.endpoint_type], token

    def test_root_exists(self):
        """Check that Swift container exist

        Returns: True if exist or None it not
        """
        ret = self.httpclient.request("HEAD", self.base_path)
        if ret.status_code == 404:
            return None
        if ret.status_code < 200 or ret.status_code > 300:
            raise SwiftException(
                "HEAD request failed with error code %s" % ret.status_code
            )
        return True

    def create_root(self):
        """Create the Swift container

        Raises:
          SwiftException: if unable to create
        """
        if not self.test_root_exists():
            ret = self.httpclient.request("PUT", self.base_path)
            if ret.status_code < 200 or ret.status_code > 300:
                raise SwiftException(
                    "PUT request failed with error code %s" % ret.status_code
                )

    def get_container_objects(self):
        """Retrieve objects list in a container

        Returns: A list of dict that describe objects
                 or None if container does not exist
        """
        qs = "?format=json"
        path = self.base_path + qs
        ret = self.httpclient.request("GET", path)
        if ret.status_code == 404:
            return None
        if ret.status_code < 200 or ret.status_code > 300:
            raise SwiftException(
                "GET request failed with error code %s" % ret.status_code
            )
        content = ret.read()
        return json.loads(content)

    def get_object_stat(self, name):
        """Retrieve object stat

        Args:
          name: The object name
        Returns:
          A dict that describe the object or None if object does not exist
        """
        path = self.base_path + "/" + name
        ret = self.httpclient.request("HEAD", path)
        if ret.status_code == 404:
            return None
        if ret.status_code < 200 or ret.status_code > 300:
            raise SwiftException(
                "HEAD request failed with error code %s" % ret.status_code
            )
        resp_headers = {}
        for header, value in ret.items():
            resp_headers[header.lower()] = value
        return resp_headers

    def put_object(self, name, content):
        """Put an object

        Args:
          name: The object name
          content: A file object
        Raises:
          SwiftException: if unable to create
        """
        content.seek(0)
        data = content.read()
        path = self.base_path + "/" + name
        headers = {"Content-Length": str(len(data))}

        def _send():
            ret = self.httpclient.request("PUT", path, body=data, headers=headers)
            return ret

        try:
            # Sometime got Broken Pipe - Dirty workaround
            ret = _send()
        except Exception:
            # Second attempt work
            ret = _send()

        if ret.status_code < 200 or ret.status_code > 300:
            raise SwiftException(
                "PUT request failed with error code %s" % ret.status_code
            )

    def get_object(self, name, range=None):
        """Retrieve an object

        Args:
          name: The object name
          range: A string range like "0-10" to
                 retrieve specified bytes in object content
        Returns:
          A file like instance or bytestring if range is specified
        """
        headers = {}
        if range:
            headers["Range"] = "bytes=%s" % range
        path = self.base_path + "/" + name
        ret = self.httpclient.request("GET", path, headers=headers)
        if ret.status_code == 404:
            return None
        if ret.status_code < 200 or ret.status_code > 300:
            raise SwiftException(
                "GET request failed with error code %s" % ret.status_code
            )
        content = ret.read()

        if range:
            return content
        return BytesIO(content)

    def del_object(self, name):
        """Delete an object

        Args:
          name: The object name
        Raises:
          SwiftException: if unable to delete
        """
        path = self.base_path + "/" + name
        ret = self.httpclient.request("DELETE", path)
        if ret.status_code < 200 or ret.status_code > 300:
            raise SwiftException(
                "DELETE request failed with error code %s" % ret.status_code
            )

    def del_root(self):
        """Delete the root container by removing container content

        Raises:
          SwiftException: if unable to delete
        """
        for obj in self.get_container_objects():
            self.del_object(obj["name"])
        ret = self.httpclient.request("DELETE", self.base_path)
        if ret.status_code < 200 or ret.status_code > 300:
            raise SwiftException(
                "DELETE request failed with error code %s" % ret.status_code
            )


class SwiftPackReader:
    """A SwiftPackReader that mimic read and sync method

    The reader allows to read a specified amount of bytes from
    a given offset of a Swift object. A read offset is kept internally.
    The reader will read from Swift a specified amount of data to complete
    its internal buffer. chunk_length specify the amount of data
    to read from Swift.
    """

    def __init__(self, scon, filename, pack_length):
        """Initialize a SwiftPackReader

        Args:
          scon: a `SwiftConnector` instance
          filename: the pack filename
          pack_length: The size of the pack object
        """
        self.scon = scon
        self.filename = filename
        self.pack_length = pack_length
        self.offset = 0
        self.base_offset = 0
        self.buff = b""
        self.buff_length = self.scon.chunk_length

    def _read(self, more=False):
        if more:
            self.buff_length = self.buff_length * 2
        offset = self.base_offset
        r = min(self.base_offset + self.buff_length, self.pack_length)
        ret = self.scon.get_object(self.filename, range="{}-{}".format(offset, r))
        self.buff = ret

    def read(self, length):
        """Read a specified amount of Bytes form the pack object

        Args:
          length: amount of bytes to read
        Returns:
          a bytestring
        """
        end = self.offset + length
        if self.base_offset + end > self.pack_length:
            data = self.buff[self.offset :]
            self.offset = end
            return data
        if end > len(self.buff):
            # Need to read more from swift
            self._read(more=True)
            return self.read(length)
        data = self.buff[self.offset : end]
        self.offset = end
        return data

    def seek(self, offset):
        """Seek to a specified offset

        Args:
          offset: the offset to seek to
        """
        self.base_offset = offset
        self._read()
        self.offset = 0

    def read_checksum(self):
        """Read the checksum from the pack

        Returns: the checksum bytestring
        """
        return self.scon.get_object(self.filename, range="-20")


class SwiftPackData(PackData):
    """The data contained in a packfile.

    We use the SwiftPackReader to read bytes from packs stored in Swift
    using the Range header feature of Swift.
    """

    def __init__(self, scon, filename):
        """Initialize a SwiftPackReader

        Args:
          scon: a `SwiftConnector` instance
          filename: the pack filename
        """
        self.scon = scon
        self._filename = filename
        self._header_size = 12
        headers = self.scon.get_object_stat(self._filename)
        self.pack_length = int(headers["content-length"])
        pack_reader = SwiftPackReader(self.scon, self._filename, self.pack_length)
        (version, self._num_objects) = read_pack_header(pack_reader.read)
        self._offset_cache = LRUSizeCache(
            1024 * 1024 * self.scon.cache_length,
            compute_size=_compute_object_size,
        )
        self.pack = None

    def get_object_at(self, offset):
        if offset in self._offset_cache:
            return self._offset_cache[offset]
        assert offset >= self._header_size
        pack_reader = SwiftPackReader(self.scon, self._filename, self.pack_length)
        pack_reader.seek(offset)
        unpacked, _ = unpack_object(pack_reader.read)
        return (unpacked.pack_type_num, unpacked._obj())

    def get_stored_checksum(self):
        pack_reader = SwiftPackReader(self.scon, self._filename, self.pack_length)
        return pack_reader.read_checksum()

    def close(self):
        pass


class SwiftPack(Pack):
    """A Git pack object.

    Same implementation as pack.Pack except that _idx_load and
    _data_load are bounded to Swift version of load_pack_index and
    PackData.
    """

    def __init__(self, *args, **kwargs):
        self.scon = kwargs["scon"]
        del kwargs["scon"]
        super().__init__(*args, **kwargs)
        self._pack_info_path = self._basename + ".info"
        self._pack_info = None
        self._pack_info_load = lambda: load_pack_info(self._pack_info_path, self.scon)
        self._idx_load = lambda: swift_load_pack_index(self.scon, self._idx_path)
        self._data_load = lambda: SwiftPackData(self.scon, self._data_path)

    @property
    def pack_info(self):
        """The pack data object being used."""
        if self._pack_info is None:
            self._pack_info = self._pack_info_load()
        return self._pack_info


class SwiftObjectStore(PackBasedObjectStore):
    """A Swift Object Store

    Allow to manage a bare Git repository from Openstack Swift.
    This object store only supports pack files and not loose objects.
    """

    def __init__(self, scon):
        """Open a Swift object store.

        Args:
          scon: A `SwiftConnector` instance
        """
        super().__init__()
        self.scon = scon
        self.root = self.scon.root
        self.pack_dir = posixpath.join(OBJECTDIR, PACKDIR)
        self._alternates = None

    def _update_pack_cache(self):
        objects = self.scon.get_container_objects()
        pack_files = [
            o["name"].replace(".pack", "")
            for o in objects
            if o["name"].endswith(".pack")
        ]
        ret = []
        for basename in pack_files:
            pack = SwiftPack(basename, scon=self.scon)
            self._pack_cache[basename] = pack
            ret.append(pack)
        return ret

    def _iter_loose_objects(self):
        """Loose objects are not supported by this repository"""
        return []

    def pack_info_get(self, sha):
        for pack in self.packs:
            if sha in pack:
                return pack.pack_info[sha]

    def _collect_ancestors(self, heads, common=set()):
        def _find_parents(commit):
            for pack in self.packs:
                if commit in pack:
                    try:
                        parents = pack.pack_info[commit][1]
                    except KeyError:
                        # Seems to have no parents
                        return []
                    return parents

        bases = set()
        commits = set()
        queue = []
        queue.extend(heads)
        while queue:
            e = queue.pop(0)
            if e in common:
                bases.add(e)
            elif e not in commits:
                commits.add(e)
                parents = _find_parents(e)
                queue.extend(parents)
        return (commits, bases)

    def add_pack(self):
        """Add a new pack to this object store.

        Returns: Fileobject to write to and a commit function to
            call when the pack is finished.
        """
        f = BytesIO()

        def commit():
            f.seek(0)
            pack = PackData(file=f, filename="")
            entries = pack.sorted_entries()
            if entries:
                basename = posixpath.join(
                    self.pack_dir,
                    "pack-%s" % iter_sha1(entry[0] for entry in entries),
                )
                index = BytesIO()
                write_pack_index_v2(index, entries, pack.get_stored_checksum())
                self.scon.put_object(basename + ".pack", f)
                f.close()
                self.scon.put_object(basename + ".idx", index)
                index.close()
                final_pack = SwiftPack(basename, scon=self.scon)
                final_pack.check_length_and_checksum()
                self._add_cached_pack(basename, final_pack)
                return final_pack
            else:
                return None

        def abort():
            pass

        return f, commit, abort

    def add_object(self, obj):
        self.add_objects(
            [
                (obj, None),
            ]
        )

    def _pack_cache_stale(self):
        return False

    def _get_loose_object(self, sha):
        return None

    def add_thin_pack(self, read_all, read_some):
        """Read a thin pack

        Read it from a stream and complete it in a temporary file.
        Then the pack and the corresponding index file are uploaded to Swift.
        """
        fd, path = tempfile.mkstemp(prefix="tmp_pack_")
        f = os.fdopen(fd, "w+b")
        try:
            indexer = PackIndexer(f, resolve_ext_ref=self.get_raw)
            copier = PackStreamCopier(read_all, read_some, f, delta_iter=indexer)
            copier.verify()
            return self._complete_thin_pack(f, path, copier, indexer)
        finally:
            f.close()
            os.unlink(path)

    def _complete_thin_pack(self, f, path, copier, indexer):
        entries = list(indexer)

        # Update the header with the new number of objects.
        f.seek(0)
        write_pack_header(f, len(entries) + len(indexer.ext_refs()))

        # Must flush before reading (http://bugs.python.org/issue3207)
        f.flush()

        # Rescan the rest of the pack, computing the SHA with the new header.
        new_sha = compute_file_sha(f, end_ofs=-20)

        # Must reposition before writing (http://bugs.python.org/issue3207)
        f.seek(0, os.SEEK_CUR)

        # Complete the pack.
        for ext_sha in indexer.ext_refs():
            assert len(ext_sha) == 20
            type_num, data = self.get_raw(ext_sha)
            offset = f.tell()
            crc32 = write_pack_object(f, type_num, data, sha=new_sha)
            entries.append((ext_sha, offset, crc32))
        pack_sha = new_sha.digest()
        f.write(pack_sha)
        f.flush()

        # Move the pack in.
        entries.sort()
        pack_base_name = posixpath.join(
            self.pack_dir,
            "pack-" + os.fsdecode(iter_sha1(e[0] for e in entries)),
        )
        self.scon.put_object(pack_base_name + ".pack", f)

        # Write the index.
        filename = pack_base_name + ".idx"
        index_file = BytesIO()
        write_pack_index_v2(index_file, entries, pack_sha)
        self.scon.put_object(filename, index_file)

        # Write pack info.
        f.seek(0)
        pack_data = PackData(filename="", file=f)
        index_file.seek(0)
        pack_index = load_pack_index_file("", index_file)
        serialized_pack_info = pack_info_create(pack_data, pack_index)
        f.close()
        index_file.close()
        pack_info_file = BytesIO(serialized_pack_info)
        filename = pack_base_name + ".info"
        self.scon.put_object(filename, pack_info_file)
        pack_info_file.close()

        # Add the pack to the store and return it.
        final_pack = SwiftPack(pack_base_name, scon=self.scon)
        final_pack.check_length_and_checksum()
        self._add_cached_pack(pack_base_name, final_pack)
        return final_pack


class SwiftInfoRefsContainer(InfoRefsContainer):
    """Manage references in info/refs object."""

    def __init__(self, scon, store):
        self.scon = scon
        self.filename = "info/refs"
        self.store = store
        f = self.scon.get_object(self.filename)
        if not f:
            f = BytesIO(b"")
        super().__init__(f)

    def _load_check_ref(self, name, old_ref):
        self._check_refname(name)
        f = self.scon.get_object(self.filename)
        if not f:
            return {}
        refs = read_info_refs(f)
        if old_ref is not None:
            if refs[name] != old_ref:
                return False
        return refs

    def _write_refs(self, refs):
        f = BytesIO()
        f.writelines(write_info_refs(refs, self.store))
        self.scon.put_object(self.filename, f)

    def set_if_equals(self, name, old_ref, new_ref):
        """Set a refname to new_ref only if it currently equals old_ref."""
        if name == "HEAD":
            return True
        refs = self._load_check_ref(name, old_ref)
        if not isinstance(refs, dict):
            return False
        refs[name] = new_ref
        self._write_refs(refs)
        self._refs[name] = new_ref
        return True

    def remove_if_equals(self, name, old_ref):
        """Remove a refname only if it currently equals old_ref."""
        if name == "HEAD":
            return True
        refs = self._load_check_ref(name, old_ref)
        if not isinstance(refs, dict):
            return False
        del refs[name]
        self._write_refs(refs)
        del self._refs[name]
        return True

    def allkeys(self):
        try:
            self._refs["HEAD"] = self._refs["refs/heads/master"]
        except KeyError:
            pass
        return self._refs.keys()


class SwiftRepo(BaseRepo):
    def __init__(self, root, conf):
        """Init a Git bare Repository on top of a Swift container.

        References are managed in info/refs objects by
        `SwiftInfoRefsContainer`. The root attribute is the Swift
        container that contain the Git bare repository.

        Args:
          root: The container which contains the bare repo
          conf: A ConfigParser object
        """
        self.root = root.lstrip("/")
        self.conf = conf
        self.scon = SwiftConnector(self.root, self.conf)
        objects = self.scon.get_container_objects()
        if not objects:
            raise Exception("There is not any GIT repo here : %s" % self.root)
        objects = [o["name"].split("/")[0] for o in objects]
        if OBJECTDIR not in objects:
            raise Exception("This repository (%s) is not bare." % self.root)
        self.bare = True
        self._controldir = self.root
        object_store = SwiftObjectStore(self.scon)
        refs = SwiftInfoRefsContainer(self.scon, object_store)
        BaseRepo.__init__(self, object_store, refs)

    def _determine_file_mode(self):
        """Probe the file-system to determine whether permissions can be trusted.

        Returns: True if permissions can be trusted, False otherwise.
        """
        return False

    def _put_named_file(self, filename, contents):
        """Put an object in a Swift container

        Args:
          filename: the path to the object to put on Swift
          contents: the content as bytestring
        """
        with BytesIO() as f:
            f.write(contents)
            self.scon.put_object(filename, f)

    @classmethod
    def init_bare(cls, scon, conf):
        """Create a new bare repository.

        Args:
          scon: a `SwiftConnector` instance
          conf: a ConfigParser object
        Returns:
          a `SwiftRepo` instance
        """
        scon.create_root()
        for obj in [
            posixpath.join(OBJECTDIR, PACKDIR),
            posixpath.join(INFODIR, "refs"),
        ]:
            scon.put_object(obj, BytesIO(b""))
        ret = cls(scon.root, conf)
        ret._init_files(True)
        return ret


class SwiftSystemBackend(Backend):
    def __init__(self, logger, conf):
        self.conf = conf
        self.logger = logger

    def open_repository(self, path):
        self.logger.info("opening repository at %s", path)
        return SwiftRepo(path, self.conf)


def cmd_daemon(args):
    """Entry point for starting a TCP git server."""
    import optparse

    parser = optparse.OptionParser()
    parser.add_option(
        "-l",
        "--listen_address",
        dest="listen_address",
        default="127.0.0.1",
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
    parser.add_option(
        "-c",
        "--swift_config",
        dest="swift_config",
        default="",
        help="Path to the configuration file for Swift backend.",
    )
    options, args = parser.parse_args(args)

    try:
        import gevent
        import geventhttpclient  # noqa: F401
    except ImportError:
        print(
            "gevent and geventhttpclient libraries are mandatory "
            " for use the Swift backend."
        )
        sys.exit(1)
    import gevent.monkey

    gevent.monkey.patch_socket()
    from dulwich import log_utils

    logger = log_utils.getLogger(__name__)
    conf = load_conf(options.swift_config)
    backend = SwiftSystemBackend(logger, conf)

    log_utils.default_logging_config()
    server = TCPGitServer(backend, options.listen_address, port=options.port)
    server.serve_forever()


def cmd_init(args):
    import optparse

    parser = optparse.OptionParser()
    parser.add_option(
        "-c",
        "--swift_config",
        dest="swift_config",
        default="",
        help="Path to the configuration file for Swift backend.",
    )
    options, args = parser.parse_args(args)

    conf = load_conf(options.swift_config)
    if args == []:
        parser.error("missing repository name")
    repo = args[0]
    scon = SwiftConnector(repo, conf)
    SwiftRepo.init_bare(scon, conf)


def main(argv=sys.argv):
    commands = {
        "init": cmd_init,
        "daemon": cmd_daemon,
    }

    if len(sys.argv) < 2:
        print("Usage: {} <{}> [OPTIONS...]".format(sys.argv[0], "|".join(commands.keys())))
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd not in commands:
        print("No such subcommand: %s" % cmd)
        sys.exit(1)
    commands[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
