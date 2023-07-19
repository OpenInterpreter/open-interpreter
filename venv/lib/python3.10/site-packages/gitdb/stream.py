# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from io import BytesIO

import mmap
import os
import sys
import zlib

from gitdb.fun import (
    msb_size,
    stream_copy,
    apply_delta_data,
    connect_deltas,
    delta_types
)

from gitdb.util import (
    allocate_memory,
    LazyMixin,
    make_sha,
    write,
    close,
)

from gitdb.const import NULL_BYTE, BYTE_SPACE
from gitdb.utils.encoding import force_bytes

has_perf_mod = False
try:
    from gitdb_speedups._perf import apply_delta as c_apply_delta
    has_perf_mod = True
except ImportError:
    pass

__all__ = ('DecompressMemMapReader', 'FDCompressedSha1Writer', 'DeltaApplyReader',
           'Sha1Writer', 'FlexibleSha1Writer', 'ZippedStoreShaWriter', 'FDCompressedSha1Writer',
           'FDStream', 'NullStream')


#{ RO Streams

class DecompressMemMapReader(LazyMixin):

    """Reads data in chunks from a memory map and decompresses it. The client sees
    only the uncompressed data, respective file-like read calls are handling on-demand
    buffered decompression accordingly

    A constraint on the total size of bytes is activated, simulating
    a logical file within a possibly larger physical memory area

    To read efficiently, you clearly don't want to read individual bytes, instead,
    read a few kilobytes at least.

    **Note:** The chunk-size should be carefully selected as it will involve quite a bit
        of string copying due to the way the zlib is implemented. Its very wasteful,
        hence we try to find a good tradeoff between allocation time and number of
        times we actually allocate. An own zlib implementation would be good here
        to better support streamed reading - it would only need to keep the mmap
        and decompress it into chunks, that's all ... """
    __slots__ = ('_m', '_zip', '_buf', '_buflen', '_br', '_cws', '_cwe', '_s', '_close',
                 '_cbr', '_phi')

    max_read_size = 512 * 1024        # currently unused

    def __init__(self, m, close_on_deletion, size=None):
        """Initialize with mmap for stream reading
        :param m: must be content data - use new if you have object data and no size"""
        self._m = m
        self._zip = zlib.decompressobj()
        self._buf = None                        # buffer of decompressed bytes
        self._buflen = 0                        # length of bytes in buffer
        if size is not None:
            self._s = size                      # size of uncompressed data to read in total
        self._br = 0                            # num uncompressed bytes read
        self._cws = 0                           # start byte of compression window
        self._cwe = 0                           # end byte of compression window
        self._cbr = 0                           # number of compressed bytes read
        self._phi = False                       # is True if we parsed the header info
        self._close = close_on_deletion         # close the memmap on deletion ?

    def _set_cache_(self, attr):
        assert attr == '_s'
        # only happens for size, which is a marker to indicate we still
        # have to parse the header from the stream
        self._parse_header_info()

    def __del__(self):
        self.close()

    def _parse_header_info(self):
        """If this stream contains object data, parse the header info and skip the
        stream to a point where each read will yield object content

        :return: parsed type_string, size"""
        # read header
        # should really be enough, cgit uses 8192 I believe
        # And for good reason !! This needs to be that high for the header to be read correctly in all cases
        maxb = 8192
        self._s = maxb
        hdr = self.read(maxb)
        hdrend = hdr.find(NULL_BYTE)
        typ, size = hdr[:hdrend].split(BYTE_SPACE)
        size = int(size)
        self._s = size

        # adjust internal state to match actual header length that we ignore
        # The buffer will be depleted first on future reads
        self._br = 0
        hdrend += 1
        self._buf = BytesIO(hdr[hdrend:])
        self._buflen = len(hdr) - hdrend

        self._phi = True

        return typ, size

    #{ Interface

    @classmethod
    def new(self, m, close_on_deletion=False):
        """Create a new DecompressMemMapReader instance for acting as a read-only stream
        This method parses the object header from m and returns the parsed
        type and size, as well as the created stream instance.

        :param m: memory map on which to operate. It must be object data ( header + contents )
        :param close_on_deletion: if True, the memory map will be closed once we are
            being deleted"""
        inst = DecompressMemMapReader(m, close_on_deletion, 0)
        typ, size = inst._parse_header_info()
        return typ, size, inst

    def data(self):
        """:return: random access compatible data we are working on"""
        return self._m

    def close(self):
        """Close our underlying stream of compressed bytes if this was allowed during initialization
        :return: True if we closed the underlying stream
        :note: can be called safely 
        """
        if self._close:
            if hasattr(self._m, 'close'):
                self._m.close()
            self._close = False
        # END handle resource freeing

    def compressed_bytes_read(self):
        """
        :return: number of compressed bytes read. This includes the bytes it
            took to decompress the header ( if there was one )"""
        # ABSTRACT: When decompressing a byte stream, it can be that the first
        # x bytes which were requested match the first x bytes in the loosely
        # compressed datastream. This is the worst-case assumption that the reader
        # does, it assumes that it will get at least X bytes from X compressed bytes
        # in call cases.
        # The caveat is that the object, according to our known uncompressed size,
        # is already complete, but there are still some bytes left in the compressed
        # stream that contribute to the amount of compressed bytes.
        # How can we know that we are truly done, and have read all bytes we need
        # to read ?
        # Without help, we cannot know, as we need to obtain the status of the
        # decompression. If it is not finished, we need to decompress more data
        # until it is finished, to yield the actual number of compressed bytes
        # belonging to the decompressed object
        # We are using a custom zlib module for this, if its not present,
        # we try to put in additional bytes up for decompression if feasible
        # and check for the unused_data.

        # Only scrub the stream forward if we are officially done with the
        # bytes we were to have.
        if self._br == self._s and not self._zip.unused_data:
            # manipulate the bytes-read to allow our own read method to continue
            # but keep the window at its current position
            self._br = 0
            if hasattr(self._zip, 'status'):
                while self._zip.status == zlib.Z_OK:
                    self.read(mmap.PAGESIZE)
                # END scrub-loop custom zlib
            else:
                # pass in additional pages, until we have unused data
                while not self._zip.unused_data and self._cbr != len(self._m):
                    self.read(mmap.PAGESIZE)
                # END scrub-loop default zlib
            # END handle stream scrubbing

            # reset bytes read, just to be sure
            self._br = self._s
        # END handle stream scrubbing

        # unused data ends up in the unconsumed tail, which was removed
        # from the count already
        return self._cbr

    #} END interface

    def seek(self, offset, whence=getattr(os, 'SEEK_SET', 0)):
        """Allows to reset the stream to restart reading
        :raise ValueError: If offset and whence are not 0"""
        if offset != 0 or whence != getattr(os, 'SEEK_SET', 0):
            raise ValueError("Can only seek to position 0")
        # END handle offset

        self._zip = zlib.decompressobj()
        self._br = self._cws = self._cwe = self._cbr = 0
        if self._phi:
            self._phi = False
            del(self._s)        # trigger header parsing on first access
        # END skip header

    def read(self, size=-1):
        if size < 1:
            size = self._s - self._br
        else:
            size = min(size, self._s - self._br)
        # END clamp size

        if size == 0:
            return b''
        # END handle depletion

        # deplete the buffer, then just continue using the decompress object
        # which has an own buffer. We just need this to transparently parse the
        # header from the zlib stream
        dat = b''
        if self._buf:
            if self._buflen >= size:
                # have enough data
                dat = self._buf.read(size)
                self._buflen -= size
                self._br += size
                return dat
            else:
                dat = self._buf.read()      # ouch, duplicates data
                size -= self._buflen
                self._br += self._buflen

                self._buflen = 0
                self._buf = None
            # END handle buffer len
        # END handle buffer

        # decompress some data
        # Abstract: zlib needs to operate on chunks of our memory map ( which may
        # be large ), as it will otherwise and always fill in the 'unconsumed_tail'
        # attribute which possible reads our whole map to the end, forcing
        # everything to be read from disk even though just a portion was requested.
        # As this would be a nogo, we workaround it by passing only chunks of data,
        # moving the window into the memory map along as we decompress, which keeps
        # the tail smaller than our chunk-size. This causes 'only' the chunk to be
        # copied once, and another copy of a part of it when it creates the unconsumed
        # tail. We have to use it to hand in the appropriate amount of bytes during
        # the next read.
        tail = self._zip.unconsumed_tail
        if tail:
            # move the window, make it as large as size demands. For code-clarity,
            # we just take the chunk from our map again instead of reusing the unconsumed
            # tail. The latter one would safe some memory copying, but we could end up
            # with not getting enough data uncompressed, so we had to sort that out as well.
            # Now we just assume the worst case, hence the data is uncompressed and the window
            # needs to be as large as the uncompressed bytes we want to read.
            self._cws = self._cwe - len(tail)
            self._cwe = self._cws + size
        else:
            cws = self._cws
            self._cws = self._cwe
            self._cwe = cws + size
        # END handle tail

        # if window is too small, make it larger so zip can decompress something
        if self._cwe - self._cws < 8:
            self._cwe = self._cws + 8
        # END adjust winsize

        # takes a slice, but doesn't copy the data, it says ...
        indata = self._m[self._cws:self._cwe]

        # get the actual window end to be sure we don't use it for computations
        self._cwe = self._cws + len(indata)
        dcompdat = self._zip.decompress(indata, size)
        # update the amount of compressed bytes read
        # We feed possibly overlapping chunks, which is why the unconsumed tail
        # has to be taken into consideration, as well as the unused data
        # if we hit the end of the stream
        # NOTE: Behavior changed in PY2.7 onward, which requires special handling to make the tests work properly.
        # They are thorough, and I assume it is truly working.
        # Why is this logic as convoluted as it is ? Please look at the table in 
        # https://github.com/gitpython-developers/gitdb/issues/19 to learn about the test-results.
        # Basically, on py2.6, you want to use branch 1, whereas on all other python version, the second branch
        # will be the one that works. 
        # However, the zlib VERSIONs as well as the platform check is used to further match the entries in the 
        # table in the github issue. This is it ... it was the only way I could make this work everywhere.
        # IT's CERTAINLY GOING TO BITE US IN THE FUTURE ... .
        if zlib.ZLIB_VERSION in ('1.2.7', '1.2.5') and not sys.platform == 'darwin':
            unused_datalen = len(self._zip.unconsumed_tail)
        else:
            unused_datalen = len(self._zip.unconsumed_tail) + len(self._zip.unused_data)
        # # end handle very special case ...

        self._cbr += len(indata) - unused_datalen
        self._br += len(dcompdat)

        if dat:
            dcompdat = dat + dcompdat
        # END prepend our cached data

        # it can happen, depending on the compression, that we get less bytes
        # than ordered as it needs the final portion of the data as well.
        # Recursively resolve that.
        # Note: dcompdat can be empty even though we still appear to have bytes
        # to read, if we are called by compressed_bytes_read - it manipulates
        # us to empty the stream
        if dcompdat and (len(dcompdat) - len(dat)) < size and self._br < self._s:
            dcompdat += self.read(size - len(dcompdat))
        # END handle special case
        return dcompdat


class DeltaApplyReader(LazyMixin):

    """A reader which dynamically applies pack deltas to a base object, keeping the
    memory demands to a minimum.

    The size of the final object is only obtainable once all deltas have been
    applied, unless it is retrieved from a pack index.

    The uncompressed Delta has the following layout (MSB being a most significant
    bit encoded dynamic size):

    * MSB Source Size - the size of the base against which the delta was created
    * MSB Target Size - the size of the resulting data after the delta was applied
    * A list of one byte commands (cmd) which are followed by a specific protocol:

     * cmd & 0x80 - copy delta_data[offset:offset+size]

      * Followed by an encoded offset into the delta data
      * Followed by an encoded size of the chunk to copy

     *  cmd & 0x7f - insert

      * insert cmd bytes from the delta buffer into the output stream

     * cmd == 0 - invalid operation ( or error in delta stream )
    """
    __slots__ = (
        "_bstream",             # base stream to which to apply the deltas
        "_dstreams",            # tuple of delta stream readers
        "_mm_target",           # memory map of the delta-applied data
        "_size",                # actual number of bytes in _mm_target
        "_br"                   # number of bytes read
    )

    #{ Configuration
    k_max_memory_move = 250 * 1000 * 1000
    #} END configuration

    def __init__(self, stream_list):
        """Initialize this instance with a list of streams, the first stream being
        the delta to apply on top of all following deltas, the last stream being the
        base object onto which to apply the deltas"""
        assert len(stream_list) > 1, "Need at least one delta and one base stream"

        self._bstream = stream_list[-1]
        self._dstreams = tuple(stream_list[:-1])
        self._br = 0

    def _set_cache_too_slow_without_c(self, attr):
        # the direct algorithm is fastest and most direct if there is only one
        # delta. Also, the extra overhead might not be worth it for items smaller
        # than X - definitely the case in python, every function call costs
        # huge amounts of time
        # if len(self._dstreams) * self._bstream.size < self.k_max_memory_move:
        if len(self._dstreams) == 1:
            return self._set_cache_brute_(attr)

        # Aggregate all deltas into one delta in reverse order. Hence we take
        # the last delta, and reverse-merge its ancestor delta, until we receive
        # the final delta data stream.
        dcl = connect_deltas(self._dstreams)

        # call len directly, as the (optional) c version doesn't implement the sequence
        # protocol
        if dcl.rbound() == 0:
            self._size = 0
            self._mm_target = allocate_memory(0)
            return
        # END handle empty list

        self._size = dcl.rbound()
        self._mm_target = allocate_memory(self._size)

        bbuf = allocate_memory(self._bstream.size)
        stream_copy(self._bstream.read, bbuf.write, self._bstream.size, 256 * mmap.PAGESIZE)

        # APPLY CHUNKS
        write = self._mm_target.write
        dcl.apply(bbuf, write)

        self._mm_target.seek(0)

    def _set_cache_brute_(self, attr):
        """If we are here, we apply the actual deltas"""
        # TODO: There should be a special case if there is only one stream
        # Then the default-git algorithm should perform a tad faster, as the
        # delta is not peaked into, causing less overhead.
        buffer_info_list = list()
        max_target_size = 0
        for dstream in self._dstreams:
            buf = dstream.read(512)         # read the header information + X
            offset, src_size = msb_size(buf)
            offset, target_size = msb_size(buf, offset)
            buffer_info_list.append((buf[offset:], offset, src_size, target_size))
            max_target_size = max(max_target_size, target_size)
        # END for each delta stream

        # sanity check - the first delta to apply should have the same source
        # size as our actual base stream
        base_size = self._bstream.size
        target_size = max_target_size

        # if we have more than 1 delta to apply, we will swap buffers, hence we must
        # assure that all buffers we use are large enough to hold all the results
        if len(self._dstreams) > 1:
            base_size = target_size = max(base_size, max_target_size)
        # END adjust buffer sizes

        # Allocate private memory map big enough to hold the first base buffer
        # We need random access to it
        bbuf = allocate_memory(base_size)
        stream_copy(self._bstream.read, bbuf.write, base_size, 256 * mmap.PAGESIZE)

        # allocate memory map large enough for the largest (intermediate) target
        # We will use it as scratch space for all delta ops. If the final
        # target buffer is smaller than our allocated space, we just use parts
        # of it upon return.
        tbuf = allocate_memory(target_size)

        # for each delta to apply, memory map the decompressed delta and
        # work on the op-codes to reconstruct everything.
        # For the actual copying, we use a seek and write pattern of buffer
        # slices.
        final_target_size = None
        for (dbuf, offset, src_size, target_size), dstream in zip(reversed(buffer_info_list), reversed(self._dstreams)):
            # allocate a buffer to hold all delta data - fill in the data for
            # fast access. We do this as we know that reading individual bytes
            # from our stream would be slower than necessary ( although possible )
            # The dbuf buffer contains commands after the first two MSB sizes, the
            # offset specifies the amount of bytes read to get the sizes.
            ddata = allocate_memory(dstream.size - offset)
            ddata.write(dbuf)
            # read the rest from the stream. The size we give is larger than necessary
            stream_copy(dstream.read, ddata.write, dstream.size, 256 * mmap.PAGESIZE)

            #######################################################################
            if 'c_apply_delta' in globals():
                c_apply_delta(bbuf, ddata, tbuf)
            else:
                apply_delta_data(bbuf, src_size, ddata, len(ddata), tbuf.write)
            #######################################################################

            # finally, swap out source and target buffers. The target is now the
            # base for the next delta to apply
            bbuf, tbuf = tbuf, bbuf
            bbuf.seek(0)
            tbuf.seek(0)
            final_target_size = target_size
        # END for each delta to apply

        # its already seeked to 0, constrain it to the actual size
        # NOTE: in the end of the loop, it swaps buffers, hence our target buffer
        # is not tbuf, but bbuf !
        self._mm_target = bbuf
        self._size = final_target_size

    #{ Configuration
    if not has_perf_mod:
        _set_cache_ = _set_cache_brute_
    else:
        _set_cache_ = _set_cache_too_slow_without_c

    #} END configuration

    def read(self, count=0):
        bl = self._size - self._br      # bytes left
        if count < 1 or count > bl:
            count = bl
        # NOTE: we could check for certain size limits, and possibly
        # return buffers instead of strings to prevent byte copying
        data = self._mm_target.read(count)
        self._br += len(data)
        return data

    def seek(self, offset, whence=getattr(os, 'SEEK_SET', 0)):
        """Allows to reset the stream to restart reading

        :raise ValueError: If offset and whence are not 0"""
        if offset != 0 or whence != getattr(os, 'SEEK_SET', 0):
            raise ValueError("Can only seek to position 0")
        # END handle offset
        self._br = 0
        self._mm_target.seek(0)

    #{ Interface

    @classmethod
    def new(cls, stream_list):
        """
        Convert the given list of streams into a stream which resolves deltas
        when reading from it.

        :param stream_list: two or more stream objects, first stream is a Delta
            to the object that you want to resolve, followed by N additional delta
            streams. The list's last stream must be a non-delta stream.

        :return: Non-Delta OPackStream object whose stream can be used to obtain
            the decompressed resolved data
        :raise ValueError: if the stream list cannot be handled"""
        if len(stream_list) < 2:
            raise ValueError("Need at least two streams")
        # END single object special handling

        if stream_list[-1].type_id in delta_types:
            raise ValueError(
                "Cannot resolve deltas if there is no base object stream, last one was type: %s" % stream_list[-1].type)
        # END check stream
        return cls(stream_list)

    #} END interface

    #{ OInfo like Interface

    @property
    def type(self):
        return self._bstream.type

    @property
    def type_id(self):
        return self._bstream.type_id

    @property
    def size(self):
        """:return: number of uncompressed bytes in the stream"""
        return self._size

    #} END oinfo like interface


#} END RO streams


#{ W Streams

class Sha1Writer:

    """Simple stream writer which produces a sha whenever you like as it degests
    everything it is supposed to write"""
    __slots__ = "sha1"

    def __init__(self):
        self.sha1 = make_sha()

    #{ Stream Interface

    def write(self, data):
        """:raise IOError: If not all bytes could be written
        :param data: byte object
        :return: length of incoming data"""

        self.sha1.update(data)

        return len(data)

    # END stream interface

    #{ Interface

    def sha(self, as_hex=False):
        """:return: sha so far
        :param as_hex: if True, sha will be hex-encoded, binary otherwise"""
        if as_hex:
            return self.sha1.hexdigest()
        return self.sha1.digest()

    #} END interface


class FlexibleSha1Writer(Sha1Writer):

    """Writer producing a sha1 while passing on the written bytes to the given
    write function"""
    __slots__ = 'writer'

    def __init__(self, writer):
        Sha1Writer.__init__(self)
        self.writer = writer

    def write(self, data):
        Sha1Writer.write(self, data)
        self.writer(data)


class ZippedStoreShaWriter(Sha1Writer):

    """Remembers everything someone writes to it and generates a sha"""
    __slots__ = ('buf', 'zip')

    def __init__(self):
        Sha1Writer.__init__(self)
        self.buf = BytesIO()
        self.zip = zlib.compressobj(zlib.Z_BEST_SPEED)

    def __getattr__(self, attr):
        return getattr(self.buf, attr)

    def write(self, data):
        alen = Sha1Writer.write(self, data)
        self.buf.write(self.zip.compress(data))

        return alen

    def close(self):
        self.buf.write(self.zip.flush())

    def seek(self, offset, whence=getattr(os, 'SEEK_SET', 0)):
        """Seeking currently only supports to rewind written data
        Multiple writes are not supported"""
        if offset != 0 or whence != getattr(os, 'SEEK_SET', 0):
            raise ValueError("Can only seek to position 0")
        # END handle offset
        self.buf.seek(0)

    def getvalue(self):
        """:return: string value from the current stream position to the end"""
        return self.buf.getvalue()


class FDCompressedSha1Writer(Sha1Writer):

    """Digests data written to it, making the sha available, then compress the
    data and write it to the file descriptor

    **Note:** operates on raw file descriptors
    **Note:** for this to work, you have to use the close-method of this instance"""
    __slots__ = ("fd", "sha1", "zip")

    # default exception
    exc = IOError("Failed to write all bytes to filedescriptor")

    def __init__(self, fd):
        super().__init__()
        self.fd = fd
        self.zip = zlib.compressobj(zlib.Z_BEST_SPEED)

    #{ Stream Interface

    def write(self, data):
        """:raise IOError: If not all bytes could be written
        :return: length of incoming data"""
        self.sha1.update(data)
        cdata = self.zip.compress(data)
        bytes_written = write(self.fd, cdata)

        if bytes_written != len(cdata):
            raise self.exc

        return len(data)

    def close(self):
        remainder = self.zip.flush()
        if write(self.fd, remainder) != len(remainder):
            raise self.exc
        return close(self.fd)

    #} END stream interface


class FDStream:

    """A simple wrapper providing the most basic functions on a file descriptor
    with the fileobject interface. Cannot use os.fdopen as the resulting stream
    takes ownership"""
    __slots__ = ("_fd", '_pos')

    def __init__(self, fd):
        self._fd = fd
        self._pos = 0

    def write(self, data):
        self._pos += len(data)
        os.write(self._fd, data)

    def read(self, count=0):
        if count == 0:
            count = os.path.getsize(self._filepath)
        # END handle read everything

        bytes = os.read(self._fd, count)
        self._pos += len(bytes)
        return bytes

    def fileno(self):
        return self._fd

    def tell(self):
        return self._pos

    def close(self):
        close(self._fd)


class NullStream:

    """A stream that does nothing but providing a stream interface.
    Use it like /dev/null"""
    __slots__ = tuple()

    def read(self, size=0):
        return ''

    def close(self):
        pass

    def write(self, data):
        return len(data)


#} END W streams
