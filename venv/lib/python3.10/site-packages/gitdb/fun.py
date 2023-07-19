# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
"""Contains basic c-functions which usually contain performance critical code
Keeping this code separate from the beginning makes it easier to out-source
it into c later, if required"""

import zlib
from gitdb.util import byte_ord
decompressobj = zlib.decompressobj

import mmap
from itertools import islice
from functools import reduce

from gitdb.const import NULL_BYTE, BYTE_SPACE
from gitdb.utils.encoding import force_text
from gitdb.typ import (
    str_blob_type,
    str_commit_type,
    str_tree_type,
    str_tag_type,
)

from io import StringIO

# INVARIANTS
OFS_DELTA = 6
REF_DELTA = 7
delta_types = (OFS_DELTA, REF_DELTA)

type_id_to_type_map = {
    0: b'',             # EXT 1
    1: str_commit_type,
    2: str_tree_type,
    3: str_blob_type,
    4: str_tag_type,
    5: b'',             # EXT 2
    OFS_DELTA: "OFS_DELTA",    # OFFSET DELTA
    REF_DELTA: "REF_DELTA"     # REFERENCE DELTA
}

type_to_type_id_map = {
    str_commit_type: 1,
    str_tree_type: 2,
    str_blob_type: 3,
    str_tag_type: 4,
    "OFS_DELTA": OFS_DELTA,
    "REF_DELTA": REF_DELTA,
}

# used when dealing with larger streams
chunk_size = 1000 * mmap.PAGESIZE

__all__ = ('is_loose_object', 'loose_object_header_info', 'msb_size', 'pack_object_header_info',
           'write_object', 'loose_object_header', 'stream_copy', 'apply_delta_data',
           'is_equal_canonical_sha', 'connect_deltas', 'DeltaChunkList', 'create_pack_object_header')


#{ Structures

def _set_delta_rbound(d, size):
    """Truncate the given delta to the given size
    :param size: size relative to our target offset, may not be 0, must be smaller or equal
        to our size
    :return: d"""
    d.ts = size

    # NOTE: data is truncated automatically when applying the delta
    # MUST NOT DO THIS HERE
    return d


def _move_delta_lbound(d, bytes):
    """Move the delta by the given amount of bytes, reducing its size so that its
    right bound stays static
    :param bytes: amount of bytes to move, must be smaller than delta size
    :return: d"""
    if bytes == 0:
        return

    d.to += bytes
    d.so += bytes
    d.ts -= bytes
    if d.data is not None:
        d.data = d.data[bytes:]
    # END handle data

    return d


def delta_duplicate(src):
    return DeltaChunk(src.to, src.ts, src.so, src.data)


def delta_chunk_apply(dc, bbuf, write):
    """Apply own data to the target buffer
    :param bbuf: buffer providing source bytes for copy operations
    :param write: write method to call with data to write"""
    if dc.data is None:
        # COPY DATA FROM SOURCE
        write(bbuf[dc.so:dc.so + dc.ts])
    else:
        # APPEND DATA
        # what's faster: if + 4 function calls or just a write with a slice ?
        # Considering data can be larger than 127 bytes now, it should be worth it
        if dc.ts < len(dc.data):
            write(dc.data[:dc.ts])
        else:
            write(dc.data)
        # END handle truncation
    # END handle chunk mode


class DeltaChunk:

    """Represents a piece of a delta, it can either add new data, or copy existing
    one from a source buffer"""
    __slots__ = (
        'to',       # start offset in the target buffer in bytes
                    'ts',       # size of this chunk in the target buffer in bytes
                    'so',       # start offset in the source buffer in bytes or None
                    'data',     # chunk of bytes to be added to the target buffer,
                                # DeltaChunkList to use as base, or None
    )

    def __init__(self, to, ts, so, data):
        self.to = to
        self.ts = ts
        self.so = so
        self.data = data

    def __repr__(self):
        return "DeltaChunk(%i, %i, %s, %s)" % (self.to, self.ts, self.so, self.data or "")

    #{ Interface

    def rbound(self):
        return self.to + self.ts

    def has_data(self):
        """:return: True if the instance has data to add to the target stream"""
        return self.data is not None

    #} END interface


def _closest_index(dcl, absofs):
    """:return: index at which the given absofs should be inserted. The index points
    to the DeltaChunk with a target buffer absofs that equals or is greater than
    absofs.
    **Note:** global method for performance only, it belongs to DeltaChunkList"""
    lo = 0
    hi = len(dcl)
    while lo < hi:
        mid = (lo + hi) / 2
        dc = dcl[mid]
        if dc.to > absofs:
            hi = mid
        elif dc.rbound() > absofs or dc.to == absofs:
            return mid
        else:
            lo = mid + 1
        # END handle bound
    # END for each delta absofs
    return len(dcl) - 1


def delta_list_apply(dcl, bbuf, write):
    """Apply the chain's changes and write the final result using the passed
    write function.
    :param bbuf: base buffer containing the base of all deltas contained in this
        list. It will only be used if the chunk in question does not have a base
        chain.
    :param write: function taking a string of bytes to write to the output"""
    for dc in dcl:
        delta_chunk_apply(dc, bbuf, write)
    # END for each dc


def delta_list_slice(dcl, absofs, size, ndcl):
    """:return: Subsection of this  list at the given absolute  offset, with the given
        size in bytes.
    :return: None"""
    cdi = _closest_index(dcl, absofs)   # delta start index
    cd = dcl[cdi]
    slen = len(dcl)
    lappend = ndcl.append

    if cd.to != absofs:
        tcd = DeltaChunk(cd.to, cd.ts, cd.so, cd.data)
        _move_delta_lbound(tcd, absofs - cd.to)
        tcd.ts = min(tcd.ts, size)
        lappend(tcd)
        size -= tcd.ts
        cdi += 1
    # END lbound overlap handling

    while cdi < slen and size:
        # are we larger than the current block
        cd = dcl[cdi]
        if cd.ts <= size:
            lappend(DeltaChunk(cd.to, cd.ts, cd.so, cd.data))
            size -= cd.ts
        else:
            tcd = DeltaChunk(cd.to, cd.ts, cd.so, cd.data)
            tcd.ts = size
            lappend(tcd)
            size -= tcd.ts
            break
        # END hadle size
        cdi += 1
    # END for each chunk


class DeltaChunkList(list):

    """List with special functionality to deal with DeltaChunks.
    There are two types of lists we represent. The one was created bottom-up, working
    towards the latest delta, the other kind was created top-down, working from the
    latest delta down to the earliest ancestor. This attribute is queryable
    after all processing with is_reversed."""

    __slots__ = tuple()

    def rbound(self):
        """:return: rightmost extend in bytes, absolute"""
        if len(self) == 0:
            return 0
        return self[-1].rbound()

    def lbound(self):
        """:return: leftmost byte at which this chunklist starts"""
        if len(self) == 0:
            return 0
        return self[0].to

    def size(self):
        """:return: size of bytes as measured by our delta chunks"""
        return self.rbound() - self.lbound()

    def apply(self, bbuf, write):
        """Only used by public clients, internally we only use the global routines
        for performance"""
        return delta_list_apply(self, bbuf, write)

    def compress(self):
        """Alter the list to reduce the amount of nodes. Currently we concatenate
        add-chunks
        :return: self"""
        slen = len(self)
        if slen < 2:
            return self
        i = 0

        first_data_index = None
        while i < slen:
            dc = self[i]
            i += 1
            if dc.data is None:
                if first_data_index is not None and i - 2 - first_data_index > 1:
                    # if first_data_index is not None:
                    nd = StringIO()                     # new data
                    so = self[first_data_index].to      # start offset in target buffer
                    for x in range(first_data_index, i - 1):
                        xdc = self[x]
                        nd.write(xdc.data[:xdc.ts])
                    # END collect data

                    del(self[first_data_index:i - 1])
                    buf = nd.getvalue()
                    self.insert(first_data_index, DeltaChunk(so, len(buf), 0, buf))

                    slen = len(self)
                    i = first_data_index + 1

                # END concatenate data
                first_data_index = None
                continue
            # END skip non-data chunks

            if first_data_index is None:
                first_data_index = i - 1
        # END iterate list

        # if slen_orig != len(self):
        #   print "INFO: Reduced delta list len to %f %% of former size" % ((float(len(self)) / slen_orig) * 100)
        return self

    def check_integrity(self, target_size=-1):
        """Verify the list has non-overlapping chunks only, and the total size matches
        target_size
        :param target_size: if not -1, the total size of the chain must be target_size
        :raise AssertionError: if the size doesn't match"""
        if target_size > -1:
            assert self[-1].rbound() == target_size
            assert reduce(lambda x, y: x + y, (d.ts for d in self), 0) == target_size
        # END target size verification

        if len(self) < 2:
            return

        # check data
        for dc in self:
            assert dc.ts > 0
            if dc.has_data():
                assert len(dc.data) >= dc.ts
        # END for each dc

        left = islice(self, 0, len(self) - 1)
        right = iter(self)
        right.next()
        # this is very pythonic - we might have just use index based access here,
        # but this could actually be faster
        for lft, rgt in zip(left, right):
            assert lft.rbound() == rgt.to
            assert lft.to + lft.ts == rgt.to
        # END for each pair


class TopdownDeltaChunkList(DeltaChunkList):

    """Represents a list which is generated by feeding its ancestor streams one by
    one"""
    __slots__ = tuple()

    def connect_with_next_base(self, bdcl):
        """Connect this chain with the next level of our base delta chunklist.
        The goal in this game is to mark as many of our chunks rigid, hence they
        cannot be changed by any of the upcoming bases anymore. Once all our
        chunks are marked like that, we can stop all processing
        :param bdcl: data chunk list being one of our bases. They must be fed in
            consecutively and in order, towards the earliest ancestor delta
        :return: True if processing was done. Use it to abort processing of
            remaining streams if False is returned"""
        nfc = 0                             # number of frozen chunks
        dci = 0                             # delta chunk index
        slen = len(self)                    # len of self
        ccl = list()                        # temporary list
        while dci < slen:
            dc = self[dci]
            dci += 1

            # all add-chunks which are already topmost don't need additional processing
            if dc.data is not None:
                nfc += 1
                continue
            # END skip add chunks

            # copy chunks
            # integrate the portion of the base list into ourselves. Lists
            # dont support efficient insertion ( just one at a time ), but for now
            # we live with it. Internally, its all just a 32/64bit pointer, and
            # the portions of moved memory should be smallish. Maybe we just rebuild
            # ourselves in order to reduce the amount of insertions ...
            del(ccl[:])
            delta_list_slice(bdcl, dc.so, dc.ts, ccl)

            # move the target bounds into place to match with our chunk
            ofs = dc.to - dc.so
            for cdc in ccl:
                cdc.to += ofs
            # END update target bounds

            if len(ccl) == 1:
                self[dci - 1] = ccl[0]
            else:
                # maybe try to compute the expenses here, and pick the right algorithm
                # It would normally be faster than copying everything physically though
                # TODO: Use a deque here, and decide by the index whether to extend
                # or extend left !
                post_dci = self[dci:]
                del(self[dci - 1:])           # include deletion of dc
                self.extend(ccl)
                self.extend(post_dci)

                slen = len(self)
                dci += len(ccl) - 1           # deleted dc, added rest

            # END handle chunk replacement
        # END for each chunk

        if nfc == slen:
            return False
        # END handle completeness
        return True


#} END structures

#{ Routines

def is_loose_object(m):
    """
    :return: True the file contained in memory map m appears to be a loose object.
        Only the first two bytes are needed"""
    b0, b1 = map(ord, m[:2])
    word = (b0 << 8) + b1
    return b0 == 0x78 and (word % 31) == 0


def loose_object_header_info(m):
    """
    :return: tuple(type_string, uncompressed_size_in_bytes) the type string of the
        object as well as its uncompressed size in bytes.
    :param m: memory map from which to read the compressed object data"""
    decompress_size = 8192      # is used in cgit as well
    hdr = decompressobj().decompress(m, decompress_size)
    type_name, size = hdr[:hdr.find(NULL_BYTE)].split(BYTE_SPACE)

    return type_name, int(size)


def pack_object_header_info(data):
    """
    :return: tuple(type_id, uncompressed_size_in_bytes, byte_offset)
        The type_id should be interpreted according to the ``type_id_to_type_map`` map
        The byte-offset specifies the start of the actual zlib compressed datastream
    :param m: random-access memory, like a string or memory map"""
    c = byte_ord(data[0])           # first byte
    i = 1                           # next char to read
    type_id = (c >> 4) & 7          # numeric type
    size = c & 15                   # starting size
    s = 4                           # starting bit-shift size
    while c & 0x80:
        c = byte_ord(data[i])
        i += 1
        size += (c & 0x7f) << s
        s += 7
    # END character loop
    # end performance at expense of maintenance ...
    return (type_id, size, i)


def create_pack_object_header(obj_type, obj_size):
    """
    :return: string defining the pack header comprised of the object type
        and its incompressed size in bytes

    :param obj_type: pack type_id of the object
    :param obj_size: uncompressed size in bytes of the following object stream"""
    c = 0       # 1 byte
    hdr = bytearray()  # output string

    c = (obj_type << 4) | (obj_size & 0xf)
    obj_size >>= 4
    while obj_size:
        hdr.append(c | 0x80)
        c = obj_size & 0x7f
        obj_size >>= 7
    # END until size is consumed
    hdr.append(c)
    # end handle interpreter
    return hdr


def msb_size(data, offset=0):
    """
    :return: tuple(read_bytes, size) read the msb size from the given random
        access data starting at the given byte offset"""
    size = 0
    i = 0
    l = len(data)
    hit_msb = False
    while i < l:
        c = data[i + offset]
        size |= (c & 0x7f) << i * 7
        i += 1
        if not c & 0x80:
            hit_msb = True
            break
        # END check msb bit
    # END while in range
    # end performance ...
    if not hit_msb:
        raise AssertionError("Could not find terminating MSB byte in data stream")
    return i + offset, size


def loose_object_header(type, size):
    """
    :return: bytes representing the loose object header, which is immediately
        followed by the content stream of size 'size'"""
    return ('%s %i\0' % (force_text(type), size)).encode('ascii')


def write_object(type, size, read, write, chunk_size=chunk_size):
    """
    Write the object as identified by type, size and source_stream into the
    target_stream

    :param type: type string of the object
    :param size: amount of bytes to write from source_stream
    :param read: read method of a stream providing the content data
    :param write: write method of the output stream
    :param close_target_stream: if True, the target stream will be closed when
        the routine exits, even if an error is thrown
    :return: The actual amount of bytes written to stream, which includes the header and a trailing newline"""
    tbw = 0                                             # total num bytes written

    # WRITE HEADER: type SP size NULL
    tbw += write(loose_object_header(type, size))
    tbw += stream_copy(read, write, size, chunk_size)

    return tbw


def stream_copy(read, write, size, chunk_size):
    """
    Copy a stream up to size bytes using the provided read and write methods,
    in chunks of chunk_size

    **Note:** its much like stream_copy utility, but operates just using methods"""
    dbw = 0                                             # num data bytes written

    # WRITE ALL DATA UP TO SIZE
    while True:
        cs = min(chunk_size, size - dbw)
        # NOTE: not all write methods return the amount of written bytes, like
        # mmap.write. Its bad, but we just deal with it ... perhaps its not
        # even less efficient
        # data_len = write(read(cs))
        # dbw += data_len
        data = read(cs)
        data_len = len(data)
        dbw += data_len
        write(data)
        if data_len < cs or dbw == size:
            break
        # END check for stream end
    # END duplicate data
    return dbw


def connect_deltas(dstreams):
    """
    Read the condensed delta chunk information from dstream and merge its information
        into a list of existing delta chunks

    :param dstreams: iterable of delta stream objects, the delta to be applied last
        comes first, then all its ancestors in order
    :return: DeltaChunkList, containing all operations to apply"""
    tdcl = None                         # topmost dcl

    dcl = tdcl = TopdownDeltaChunkList()
    for dsi, ds in enumerate(dstreams):
        # print "Stream", dsi
        db = ds.read()
        delta_buf_size = ds.size

        # read header
        i, base_size = msb_size(db)
        i, target_size = msb_size(db, i)

        # interpret opcodes
        tbw = 0                     # amount of target bytes written
        while i < delta_buf_size:
            c = ord(db[i])
            i += 1
            if c & 0x80:
                cp_off, cp_size = 0, 0
                if (c & 0x01):
                    cp_off = ord(db[i])
                    i += 1
                if (c & 0x02):
                    cp_off |= (ord(db[i]) << 8)
                    i += 1
                if (c & 0x04):
                    cp_off |= (ord(db[i]) << 16)
                    i += 1
                if (c & 0x08):
                    cp_off |= (ord(db[i]) << 24)
                    i += 1
                if (c & 0x10):
                    cp_size = ord(db[i])
                    i += 1
                if (c & 0x20):
                    cp_size |= (ord(db[i]) << 8)
                    i += 1
                if (c & 0x40):
                    cp_size |= (ord(db[i]) << 16)
                    i += 1

                if not cp_size:
                    cp_size = 0x10000

                rbound = cp_off + cp_size
                if (rbound < cp_size or
                        rbound > base_size):
                    break

                dcl.append(DeltaChunk(tbw, cp_size, cp_off, None))
                tbw += cp_size
            elif c:
                # NOTE: in C, the data chunks should probably be concatenated here.
                # In python, we do it as a post-process
                dcl.append(DeltaChunk(tbw, c, 0, db[i:i + c]))
                i += c
                tbw += c
            else:
                raise ValueError("unexpected delta opcode 0")
            # END handle command byte
        # END while processing delta data

        dcl.compress()

        # merge the lists !
        if dsi > 0:
            if not tdcl.connect_with_next_base(dcl):
                break
        # END handle merge

        # prepare next base
        dcl = DeltaChunkList()
    # END for each delta stream

    return tdcl


def apply_delta_data(src_buf, src_buf_size, delta_buf, delta_buf_size, write):
    """
    Apply data from a delta buffer using a source buffer to the target file

    :param src_buf: random access data from which the delta was created
    :param src_buf_size: size of the source buffer in bytes
    :param delta_buf_size: size for the delta buffer in bytes
    :param delta_buf: random access delta data
    :param write: write method taking a chunk of bytes

    **Note:** transcribed to python from the similar routine in patch-delta.c"""
    i = 0
    db = delta_buf
    while i < delta_buf_size:
        c = db[i]
        i += 1
        if c & 0x80:
            cp_off, cp_size = 0, 0
            if (c & 0x01):
                cp_off = db[i]
                i += 1
            if (c & 0x02):
                cp_off |= (db[i] << 8)
                i += 1
            if (c & 0x04):
                cp_off |= (db[i] << 16)
                i += 1
            if (c & 0x08):
                cp_off |= (db[i] << 24)
                i += 1
            if (c & 0x10):
                cp_size = db[i]
                i += 1
            if (c & 0x20):
                cp_size |= (db[i] << 8)
                i += 1
            if (c & 0x40):
                cp_size |= (db[i] << 16)
                i += 1

            if not cp_size:
                cp_size = 0x10000

            rbound = cp_off + cp_size
            if (rbound < cp_size or
                    rbound > src_buf_size):
                break
            write(src_buf[cp_off:cp_off + cp_size])
        elif c:
            write(db[i:i + c])
            i += c
        else:
            raise ValueError("unexpected delta opcode 0")
        # END handle command byte
    # END while processing delta data

    # yes, lets use the exact same error message that git uses :)
    assert i == delta_buf_size, "delta replay has gone wild"


def is_equal_canonical_sha(canonical_length, match, sha1):
    """
    :return: True if the given lhs and rhs 20 byte binary shas
        The comparison will take the canonical_length of the match sha into account,
        hence the comparison will only use the last 4 bytes for uneven canonical representations
    :param match: less than 20 byte sha
    :param sha1: 20 byte sha"""
    binary_length = canonical_length // 2
    if match[:binary_length] != sha1[:binary_length]:
        return False

    if canonical_length - binary_length and \
            (byte_ord(match[-1]) ^ byte_ord(sha1[len(match) - 1])) & 0xf0:
        return False
    # END handle uneven canonnical length
    return True

#} END routines


try:
    from gitdb_speedups._perf import connect_deltas
except ImportError:
    pass
