# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
"""Contains the MemoryDatabase implementation"""
from gitdb.db.loose import LooseObjectDB
from gitdb.db.base import (
    ObjectDBR,
    ObjectDBW
)

from gitdb.base import (
    OStream,
    IStream,
)

from gitdb.exc import (
    BadObject,
    UnsupportedOperation
)

from gitdb.stream import (
    ZippedStoreShaWriter,
    DecompressMemMapReader,
)

from io import BytesIO

__all__ = ("MemoryDB", )


class MemoryDB(ObjectDBR, ObjectDBW):

    """A memory database stores everything to memory, providing fast IO and object
    retrieval. It should be used to buffer results and obtain SHAs before writing
    it to the actual physical storage, as it allows to query whether object already
    exists in the target storage before introducing actual IO"""

    def __init__(self):
        super().__init__()
        self._db = LooseObjectDB("path/doesnt/matter")

        # maps 20 byte shas to their OStream objects
        self._cache = dict()

    def set_ostream(self, stream):
        raise UnsupportedOperation("MemoryDB's always stream into memory")

    def store(self, istream):
        zstream = ZippedStoreShaWriter()
        self._db.set_ostream(zstream)

        istream = self._db.store(istream)
        zstream.close()     # close to flush
        zstream.seek(0)

        # don't provide a size, the stream is written in object format, hence the
        # header needs decompression
        decomp_stream = DecompressMemMapReader(zstream.getvalue(), close_on_deletion=False)
        self._cache[istream.binsha] = OStream(istream.binsha, istream.type, istream.size, decomp_stream)

        return istream

    def has_object(self, sha):
        return sha in self._cache

    def info(self, sha):
        # we always return streams, which are infos as well
        return self.stream(sha)

    def stream(self, sha):
        try:
            ostream = self._cache[sha]
            # rewind stream for the next one to read
            ostream.stream.seek(0)
            return ostream
        except KeyError as e:
            raise BadObject(sha) from e
        # END exception handling

    def size(self):
        return len(self._cache)

    def sha_iter(self):
        return self._cache.keys()

    #{ Interface
    def stream_copy(self, sha_iter, odb):
        """Copy the streams as identified by sha's yielded by sha_iter into the given odb
        The streams will be copied directly
        **Note:** the object will only be written if it did not exist in the target db

        :return: amount of streams actually copied into odb. If smaller than the amount
            of input shas, one or more objects did already exist in odb"""
        count = 0
        for sha in sha_iter:
            if odb.has_object(sha):
                continue
            # END check object existence

            ostream = self.stream(sha)
            # compressed data including header
            sio = BytesIO(ostream.stream.data())
            istream = IStream(ostream.type, ostream.size, sio, sha)

            odb.store(istream)
            count += 1
        # END for each sha
        return count
    #} END interface
