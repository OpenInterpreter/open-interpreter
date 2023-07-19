# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
"""Test for object db"""

from gitdb.test.lib import (
    TestBase,
    DummyStream,
    make_bytes,
    make_object,
    fixture_path
)

from gitdb import (
    DecompressMemMapReader,
    FDCompressedSha1Writer,
    LooseObjectDB,
    Sha1Writer,
    MemoryDB,
    IStream,
)
from gitdb.util import hex_to_bin

import zlib
from gitdb.typ import (
    str_blob_type
)

import tempfile
import os
from io import BytesIO


class TestStream(TestBase):

    """Test stream classes"""

    data_sizes = (15, 10000, 1000 * 1024 + 512)

    def _assert_stream_reader(self, stream, cdata, rewind_stream=lambda s: None):
        """Make stream tests - the orig_stream is seekable, allowing it to be
        rewound and reused
        :param cdata: the data we expect to read from stream, the contents
        :param rewind_stream: function called to rewind the stream to make it ready
            for reuse"""
        ns = 10
        assert len(cdata) > ns - 1, "Data must be larger than %i, was %i" % (ns, len(cdata))

        # read in small steps
        ss = len(cdata) // ns
        for i in range(ns):
            data = stream.read(ss)
            chunk = cdata[i * ss:(i + 1) * ss]
            assert data == chunk
        # END for each step
        rest = stream.read()
        if rest:
            assert rest == cdata[-len(rest):]
        # END handle rest

        if isinstance(stream, DecompressMemMapReader):
            assert len(stream.data()) == stream.compressed_bytes_read()
        # END handle special type

        rewind_stream(stream)

        # read everything
        rdata = stream.read()
        assert rdata == cdata

        if isinstance(stream, DecompressMemMapReader):
            assert len(stream.data()) == stream.compressed_bytes_read()
        # END handle special type

    def test_decompress_reader(self):
        for close_on_deletion in range(2):
            for with_size in range(2):
                for ds in self.data_sizes:
                    cdata = make_bytes(ds, randomize=False)

                    # zdata = zipped actual data
                    # cdata = original content data

                    # create reader
                    if with_size:
                        # need object data
                        zdata = zlib.compress(make_object(str_blob_type, cdata))
                        typ, size, reader = DecompressMemMapReader.new(zdata, close_on_deletion)
                        assert size == len(cdata)
                        assert typ == str_blob_type

                        # even if we don't set the size, it will be set automatically on first read
                        test_reader = DecompressMemMapReader(zdata, close_on_deletion=False)
                        assert test_reader._s == len(cdata)
                    else:
                        # here we need content data
                        zdata = zlib.compress(cdata)
                        reader = DecompressMemMapReader(zdata, close_on_deletion, len(cdata))
                        assert reader._s == len(cdata)
                    # END get reader

                    self._assert_stream_reader(reader, cdata, lambda r: r.seek(0))

                    # put in a dummy stream for closing
                    dummy = DummyStream()
                    reader._m = dummy

                    assert not dummy.closed
                    del(reader)
                    assert dummy.closed == close_on_deletion
                # END for each datasize
            # END whether size should be used
        # END whether stream should be closed when deleted

    def test_sha_writer(self):
        writer = Sha1Writer()
        assert 2 == writer.write(b"hi")
        assert len(writer.sha(as_hex=1)) == 40
        assert len(writer.sha(as_hex=0)) == 20

        # make sure it does something ;)
        prev_sha = writer.sha()
        writer.write(b"hi again")
        assert writer.sha() != prev_sha

    def test_compressed_writer(self):
        for ds in self.data_sizes:
            fd, path = tempfile.mkstemp()
            ostream = FDCompressedSha1Writer(fd)
            data = make_bytes(ds, randomize=False)

            # for now, just a single write, code doesn't care about chunking
            assert len(data) == ostream.write(data)
            ostream.close()

            # its closed already
            self.assertRaises(OSError, os.close, fd)

            # read everything back, compare to data we zip
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0))
            written_data = os.read(fd, os.path.getsize(path))
            assert len(written_data) == os.path.getsize(path)
            os.close(fd)
            assert written_data == zlib.compress(data, 1)   # best speed

            os.remove(path)
        # END for each os

    def test_decompress_reader_special_case(self):
        odb = LooseObjectDB(fixture_path('objects'))
        mdb = MemoryDB()
        for sha in (b'888401851f15db0eed60eb1bc29dec5ddcace911',
                    b'7bb839852ed5e3a069966281bb08d50012fb309b',):
            ostream = odb.stream(hex_to_bin(sha))

            # if there is a bug, we will be missing one byte exactly !
            data = ostream.read()
            assert len(data) == ostream.size

            # Putting it back in should yield nothing new - after all, we have
            dump = mdb.store(IStream(ostream.type, ostream.size, BytesIO(data)))
            assert dump.hexsha == sha
        # end for each loose object sha to test
