# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
from gitdb.db.base import (
    FileDBBase,
    ObjectDBR,
    ObjectDBW
)


from gitdb.exc import (
    BadObject,
    AmbiguousObjectName
)

from gitdb.stream import (
    DecompressMemMapReader,
    FDCompressedSha1Writer,
    FDStream,
    Sha1Writer
)

from gitdb.base import (
    OStream,
    OInfo
)

from gitdb.util import (
    file_contents_ro_filepath,
    ENOENT,
    hex_to_bin,
    bin_to_hex,
    exists,
    chmod,
    isdir,
    isfile,
    remove,
    mkdir,
    rename,
    dirname,
    basename,
    join
)

from gitdb.fun import (
    chunk_size,
    loose_object_header_info,
    write_object,
    stream_copy
)

from gitdb.utils.encoding import force_bytes

import tempfile
import os
import sys


__all__ = ('LooseObjectDB', )


class LooseObjectDB(FileDBBase, ObjectDBR, ObjectDBW):

    """A database which operates on loose object files"""

    # CONFIGURATION
    # chunks in which data will be copied between streams
    stream_chunk_size = chunk_size

    # On windows we need to keep it writable, otherwise it cannot be removed
    # either
    new_objects_mode = int("444", 8)
    if os.name == 'nt':
        new_objects_mode = int("644", 8)

    def __init__(self, root_path):
        super().__init__(root_path)
        self._hexsha_to_file = dict()
        # Additional Flags - might be set to 0 after the first failure
        # Depending on the root, this might work for some mounts, for others not, which
        # is why it is per instance
        self._fd_open_flags = getattr(os, 'O_NOATIME', 0)

    #{ Interface
    def object_path(self, hexsha):
        """
        :return: path at which the object with the given hexsha would be stored,
            relative to the database root"""
        return join(hexsha[:2], hexsha[2:])

    def readable_db_object_path(self, hexsha):
        """
        :return: readable object path to the object identified by hexsha
        :raise BadObject: If the object file does not exist"""
        try:
            return self._hexsha_to_file[hexsha]
        except KeyError:
            pass
        # END ignore cache misses

        # try filesystem
        path = self.db_path(self.object_path(hexsha))
        if exists(path):
            self._hexsha_to_file[hexsha] = path
            return path
        # END handle cache
        raise BadObject(hexsha)

    def partial_to_complete_sha_hex(self, partial_hexsha):
        """:return: 20 byte binary sha1 string which matches the given name uniquely
        :param name: hexadecimal partial name (bytes or ascii string)
        :raise AmbiguousObjectName:
        :raise BadObject: """
        candidate = None
        for binsha in self.sha_iter():
            if bin_to_hex(binsha).startswith(force_bytes(partial_hexsha)):
                # it can't ever find the same object twice
                if candidate is not None:
                    raise AmbiguousObjectName(partial_hexsha)
                candidate = binsha
        # END for each object
        if candidate is None:
            raise BadObject(partial_hexsha)
        return candidate

    #} END interface

    def _map_loose_object(self, sha):
        """
        :return: memory map of that file to allow random read access
        :raise BadObject: if object could not be located"""
        db_path = self.db_path(self.object_path(bin_to_hex(sha)))
        try:
            return file_contents_ro_filepath(db_path, flags=self._fd_open_flags)
        except OSError as e:
            if e.errno != ENOENT:
                # try again without noatime
                try:
                    return file_contents_ro_filepath(db_path)
                except OSError as new_e:
                    raise BadObject(sha) from new_e
                # didn't work because of our flag, don't try it again
                self._fd_open_flags = 0
            else:
                raise BadObject(sha) from e
            # END handle error
        # END exception handling

    def set_ostream(self, stream):
        """:raise TypeError: if the stream does not support the Sha1Writer interface"""
        if stream is not None and not isinstance(stream, Sha1Writer):
            raise TypeError("Output stream musst support the %s interface" % Sha1Writer.__name__)
        return super().set_ostream(stream)

    def info(self, sha):
        m = self._map_loose_object(sha)
        try:
            typ, size = loose_object_header_info(m)
            return OInfo(sha, typ, size)
        finally:
            if hasattr(m, 'close'):
                m.close()
        # END assure release of system resources

    def stream(self, sha):
        m = self._map_loose_object(sha)
        type, size, stream = DecompressMemMapReader.new(m, close_on_deletion=True)
        return OStream(sha, type, size, stream)

    def has_object(self, sha):
        try:
            self.readable_db_object_path(bin_to_hex(sha))
            return True
        except BadObject:
            return False
        # END check existence

    def store(self, istream):
        """note: The sha we produce will be hex by nature"""
        tmp_path = None
        writer = self.ostream()
        if writer is None:
            # open a tmp file to write the data to
            fd, tmp_path = tempfile.mkstemp(prefix='obj', dir=self._root_path)

            if istream.binsha is None:
                writer = FDCompressedSha1Writer(fd)
            else:
                writer = FDStream(fd)
            # END handle direct stream copies
        # END handle custom writer

        try:
            try:
                if istream.binsha is not None:
                    # copy as much as possible, the actual uncompressed item size might
                    # be smaller than the compressed version
                    stream_copy(istream.read, writer.write, sys.maxsize, self.stream_chunk_size)
                else:
                    # write object with header, we have to make a new one
                    write_object(istream.type, istream.size, istream.read, writer.write,
                                 chunk_size=self.stream_chunk_size)
                # END handle direct stream copies
            finally:
                if tmp_path:
                    writer.close()
            # END assure target stream is closed
        except:
            if tmp_path:
                os.remove(tmp_path)
            raise
        # END assure tmpfile removal on error

        hexsha = None
        if istream.binsha:
            hexsha = istream.hexsha
        else:
            hexsha = writer.sha(as_hex=True)
        # END handle sha

        if tmp_path:
            obj_path = self.db_path(self.object_path(hexsha))
            obj_dir = dirname(obj_path)
            if not isdir(obj_dir):
                mkdir(obj_dir)
            # END handle destination directory
            # rename onto existing doesn't work on NTFS
            if isfile(obj_path):
                remove(tmp_path)
            else:
                rename(tmp_path, obj_path)
            # end rename only if needed

            # make sure its readable for all ! It started out as rw-- tmp file
            # but needs to be rwrr
            chmod(obj_path, self.new_objects_mode)
        # END handle dry_run

        istream.binsha = hex_to_bin(hexsha)
        return istream

    def sha_iter(self):
        # find all files which look like an object, extract sha from there
        for root, dirs, files in os.walk(self.root_path()):
            root_base = basename(root)
            if len(root_base) != 2:
                continue

            for f in files:
                if len(f) != 38:
                    continue
                yield hex_to_bin(root_base + f)
            # END for each file
        # END for each walk iteration

    def size(self):
        return len(tuple(self.sha_iter()))
