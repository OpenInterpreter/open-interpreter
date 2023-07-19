# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
"""Contains PackIndexFile and PackFile implementations"""
import zlib

from gitdb.exc import (
    BadObject,
    AmbiguousObjectName,
    UnsupportedOperation,
    ParseError
)

from gitdb.util import (
    mman,
    LazyMixin,
    unpack_from,
    bin_to_hex,
    byte_ord,
)

from gitdb.fun import (
    create_pack_object_header,
    pack_object_header_info,
    is_equal_canonical_sha,
    type_id_to_type_map,
    write_object,
    stream_copy,
    chunk_size,
    delta_types,
    OFS_DELTA,
    REF_DELTA,
    msb_size
)

try:
    from gitdb_speedups._perf import PackIndexFile_sha_to_index
except ImportError:
    pass
# END try c module

from gitdb.base import (      # Amazing !
    OInfo,
    OStream,
    OPackInfo,
    OPackStream,
    ODeltaStream,
    ODeltaPackInfo,
    ODeltaPackStream,
)

from gitdb.stream import (
    DecompressMemMapReader,
    DeltaApplyReader,
    Sha1Writer,
    NullStream,
    FlexibleSha1Writer
)

from struct import pack
from binascii import crc32

from gitdb.const import NULL_BYTE

import tempfile
import array
import os
import sys

__all__ = ('PackIndexFile', 'PackFile', 'PackEntity')


#{ Utilities

def pack_object_at(cursor, offset, as_stream):
    """
    :return: Tuple(abs_data_offset, PackInfo|PackStream)
        an object of the correct type according to the type_id  of the object.
        If as_stream is True, the object will contain a stream, allowing  the
        data to be read decompressed.
    :param data: random accessible data containing all required information
    :parma offset: offset in to the data at which the object information is located
    :param as_stream: if True, a stream object will be returned that can read
        the data, otherwise you receive an info object only"""
    data = cursor.use_region(offset).buffer()
    type_id, uncomp_size, data_rela_offset = pack_object_header_info(data)
    total_rela_offset = None                # set later, actual offset until data stream begins
    delta_info = None

    # OFFSET DELTA
    if type_id == OFS_DELTA:
        i = data_rela_offset
        c = byte_ord(data[i])
        i += 1
        delta_offset = c & 0x7f
        while c & 0x80:
            c = byte_ord(data[i])
            i += 1
            delta_offset += 1
            delta_offset = (delta_offset << 7) + (c & 0x7f)
        # END character loop
        delta_info = delta_offset
        total_rela_offset = i
    # REF DELTA
    elif type_id == REF_DELTA:
        total_rela_offset = data_rela_offset + 20
        delta_info = data[data_rela_offset:total_rela_offset]
    # BASE OBJECT
    else:
        # assume its a base object
        total_rela_offset = data_rela_offset
    # END handle type id
    abs_data_offset = offset + total_rela_offset
    if as_stream:
        stream = DecompressMemMapReader(data[total_rela_offset:], False, uncomp_size)
        if delta_info is None:
            return abs_data_offset, OPackStream(offset, type_id, uncomp_size, stream)
        else:
            return abs_data_offset, ODeltaPackStream(offset, type_id, uncomp_size, delta_info, stream)
    else:
        if delta_info is None:
            return abs_data_offset, OPackInfo(offset, type_id, uncomp_size)
        else:
            return abs_data_offset, ODeltaPackInfo(offset, type_id, uncomp_size, delta_info)
        # END handle info
    # END handle stream


def write_stream_to_pack(read, write, zstream, base_crc=None):
    """Copy a stream as read from read function, zip it, and write the result.
    Count the number of written bytes and return it
    :param base_crc: if not None, the crc will be the base for all compressed data
        we consecutively write and generate a crc32 from. If None, no crc will be generated
    :return: tuple(no bytes read, no bytes written, crc32) crc might be 0 if base_crc
        was false"""
    br = 0      # bytes read
    bw = 0      # bytes written
    want_crc = base_crc is not None
    crc = 0
    if want_crc:
        crc = base_crc
    # END initialize crc

    while True:
        chunk = read(chunk_size)
        br += len(chunk)
        compressed = zstream.compress(chunk)
        bw += len(compressed)
        write(compressed)           # cannot assume return value

        if want_crc:
            crc = crc32(compressed, crc)
        # END handle crc

        if len(chunk) != chunk_size:
            break
    # END copy loop

    compressed = zstream.flush()
    bw += len(compressed)
    write(compressed)
    if want_crc:
        crc = crc32(compressed, crc)
    # END handle crc

    return (br, bw, crc)


#} END utilities


class IndexWriter:

    """Utility to cache index information, allowing to write all information later
    in one go to the given stream
    **Note:** currently only writes v2 indices"""
    __slots__ = '_objs'

    def __init__(self):
        self._objs = list()

    def append(self, binsha, crc, offset):
        """Append one piece of object information"""
        self._objs.append((binsha, crc, offset))

    def write(self, pack_sha, write):
        """Write the index file using the given write method
        :param pack_sha: binary sha over the whole pack that we index
        :return: sha1 binary sha over all index file contents"""
        # sort for sha1 hash
        self._objs.sort(key=lambda o: o[0])

        sha_writer = FlexibleSha1Writer(write)
        sha_write = sha_writer.write
        sha_write(PackIndexFile.index_v2_signature)
        sha_write(pack(">L", PackIndexFile.index_version_default))

        # fanout
        tmplist = list((0,) * 256)                                # fanout or list with 64 bit offsets
        for t in self._objs:
            tmplist[byte_ord(t[0][0])] += 1
        # END prepare fanout
        for i in range(255):
            v = tmplist[i]
            sha_write(pack('>L', v))
            tmplist[i + 1] += v
        # END write each fanout entry
        sha_write(pack('>L', tmplist[255]))

        # sha1 ordered
        # save calls, that is push them into c
        sha_write(b''.join(t[0] for t in self._objs))

        # crc32
        for t in self._objs:
            sha_write(pack('>L', t[1] & 0xffffffff))
        # END for each crc

        tmplist = list()
        # offset 32
        for t in self._objs:
            ofs = t[2]
            if ofs > 0x7fffffff:
                tmplist.append(ofs)
                ofs = 0x80000000 + len(tmplist) - 1
            # END handle 64 bit offsets
            sha_write(pack('>L', ofs & 0xffffffff))
        # END for each offset

        # offset 64
        for ofs in tmplist:
            sha_write(pack(">Q", ofs))
        # END for each offset

        # trailer
        assert(len(pack_sha) == 20)
        sha_write(pack_sha)
        sha = sha_writer.sha(as_hex=False)
        write(sha)
        return sha


class PackIndexFile(LazyMixin):

    """A pack index provides offsets into the corresponding pack, allowing to find
    locations for offsets faster."""

    # Dont use slots as we dynamically bind functions for each version, need a dict for this
    # The slots you see here are just to keep track of our instance variables
    # __slots__ = ('_indexpath', '_fanout_table', '_cursor', '_version',
    #               '_sha_list_offset', '_crc_list_offset', '_pack_offset', '_pack_64_offset')

    # used in v2 indices
    _sha_list_offset = 8 + 1024
    index_v2_signature = b'\xfftOc'
    index_version_default = 2

    def __init__(self, indexpath):
        super().__init__()
        self._indexpath = indexpath

    def close(self):
        mman.force_map_handle_removal_win(self._indexpath)
        self._cursor = None
        
    def _set_cache_(self, attr):
        if attr == "_packfile_checksum":
            self._packfile_checksum = self._cursor.map()[-40:-20]
        elif attr == "_packfile_checksum":
            self._packfile_checksum = self._cursor.map()[-20:]
        elif attr == "_cursor":
            # Note: We don't lock the file when reading as we cannot be sure
            # that we can actually write to the location - it could be a read-only
            # alternate for instance
            self._cursor = mman.make_cursor(self._indexpath).use_region()
            # We will assume that the index will always fully fit into memory !
            if mman.window_size() > 0 and self._cursor.file_size() > mman.window_size():
                raise AssertionError("The index file at %s is too large to fit into a mapped window (%i > %i). This is a limitation of the implementation" % (
                    self._indexpath, self._cursor.file_size(), mman.window_size()))
            # END assert window size
        else:
            # now its time to initialize everything - if we are here, someone wants
            # to access the fanout table or related properties

            # CHECK VERSION
            mmap = self._cursor.map()
            self._version = (mmap[:4] == self.index_v2_signature and 2) or 1
            if self._version == 2:
                version_id = unpack_from(">L", mmap, 4)[0]
                assert version_id == self._version, "Unsupported index version: %i" % version_id
            # END assert version

            # SETUP FUNCTIONS
            # setup our functions according to the actual version
            for fname in ('entry', 'offset', 'sha', 'crc'):
                setattr(self, fname, getattr(self, "_%s_v%i" % (fname, self._version)))
            # END for each function to initialize

            # INITIALIZE DATA
            # byte offset is 8 if version is 2, 0 otherwise
            self._initialize()
        # END handle attributes

    #{ Access V1

    def _entry_v1(self, i):
        """:return: tuple(offset, binsha, 0)"""
        return unpack_from(">L20s", self._cursor.map(), 1024 + i * 24) + (0, )

    def _offset_v1(self, i):
        """see ``_offset_v2``"""
        return unpack_from(">L", self._cursor.map(), 1024 + i * 24)[0]

    def _sha_v1(self, i):
        """see ``_sha_v2``"""
        base = 1024 + (i * 24) + 4
        return self._cursor.map()[base:base + 20]

    def _crc_v1(self, i):
        """unsupported"""
        return 0

    #} END access V1

    #{ Access V2
    def _entry_v2(self, i):
        """:return: tuple(offset, binsha, crc)"""
        return (self._offset_v2(i), self._sha_v2(i), self._crc_v2(i))

    def _offset_v2(self, i):
        """:return: 32 or 64 byte offset into pack files. 64 byte offsets will only
            be returned if the pack is larger than 4 GiB, or 2^32"""
        offset = unpack_from(">L", self._cursor.map(), self._pack_offset + i * 4)[0]

        # if the high-bit is set, this indicates that we have to lookup the offset
        # in the 64 bit region of the file. The current offset ( lower 31 bits )
        # are the index into it
        if offset & 0x80000000:
            offset = unpack_from(">Q", self._cursor.map(), self._pack_64_offset + (offset & ~0x80000000) * 8)[0]
        # END handle 64 bit offset

        return offset

    def _sha_v2(self, i):
        """:return: sha at the given index of this file index instance"""
        base = self._sha_list_offset + i * 20
        return self._cursor.map()[base:base + 20]

    def _crc_v2(self, i):
        """:return: 4 bytes crc for the object at index i"""
        return unpack_from(">L", self._cursor.map(), self._crc_list_offset + i * 4)[0]

    #} END access V2

    #{ Initialization

    def _initialize(self):
        """initialize base data"""
        self._fanout_table = self._read_fanout((self._version == 2) * 8)

        if self._version == 2:
            self._crc_list_offset = self._sha_list_offset + self.size() * 20
            self._pack_offset = self._crc_list_offset + self.size() * 4
            self._pack_64_offset = self._pack_offset + self.size() * 4
        # END setup base

    def _read_fanout(self, byte_offset):
        """Generate a fanout table from our data"""
        d = self._cursor.map()
        out = list()
        append = out.append
        for i in range(256):
            append(unpack_from('>L', d, byte_offset + i * 4)[0])
        # END for each entry
        return out

    #} END initialization

    #{ Properties
    def version(self):
        return self._version

    def size(self):
        """:return: amount of objects referred to by this index"""
        return self._fanout_table[255]

    def path(self):
        """:return: path to the packindexfile"""
        return self._indexpath

    def packfile_checksum(self):
        """:return: 20 byte sha representing the sha1 hash of the pack file"""
        return self._cursor.map()[-40:-20]

    def indexfile_checksum(self):
        """:return: 20 byte sha representing the sha1 hash of this index file"""
        return self._cursor.map()[-20:]

    def offsets(self):
        """:return: sequence of all offsets in the order in which they were written

        **Note:** return value can be random accessed, but may be immmutable"""
        if self._version == 2:
            # read stream to array, convert to tuple
            a = array.array('I')    # 4 byte unsigned int, long are 8 byte on 64 bit it appears
            a.frombytes(self._cursor.map()[self._pack_offset:self._pack_64_offset])

            # networkbyteorder to something array likes more
            if sys.byteorder == 'little':
                a.byteswap()
            return a
        else:
            return tuple(self.offset(index) for index in range(self.size()))
        # END handle version

    def sha_to_index(self, sha):
        """
        :return: index usable with the ``offset`` or ``entry`` method, or None
            if the sha was not found in this pack index
        :param sha: 20 byte sha to lookup"""
        first_byte = byte_ord(sha[0])
        get_sha = self.sha
        lo = 0                  # lower index, the left bound of the bisection
        if first_byte != 0:
            lo = self._fanout_table[first_byte - 1]
        hi = self._fanout_table[first_byte]     # the upper, right bound of the bisection

        # bisect until we have the sha
        while lo < hi:
            mid = (lo + hi) // 2
            mid_sha = get_sha(mid)
            if sha < mid_sha:
                hi = mid
            elif sha == mid_sha:
                return mid
            else:
                lo = mid + 1
            # END handle midpoint
        # END bisect
        return None

    def partial_sha_to_index(self, partial_bin_sha, canonical_length):
        """
        :return: index as in `sha_to_index` or None if the sha was not found in this
            index file
        :param partial_bin_sha: an at least two bytes of a partial binary sha as bytes
        :param canonical_length: length of the original hexadecimal representation of the
            given partial binary sha
        :raise AmbiguousObjectName:"""
        if len(partial_bin_sha) < 2:
            raise ValueError("Require at least 2 bytes of partial sha")

        assert isinstance(partial_bin_sha, bytes), "partial_bin_sha must be bytes"
        first_byte = byte_ord(partial_bin_sha[0])

        get_sha = self.sha
        lo = 0                  # lower index, the left bound of the bisection
        if first_byte != 0:
            lo = self._fanout_table[first_byte - 1]
        hi = self._fanout_table[first_byte]     # the upper, right bound of the bisection

        # fill the partial to full 20 bytes
        filled_sha = partial_bin_sha + NULL_BYTE * (20 - len(partial_bin_sha))

        # find lowest
        while lo < hi:
            mid = (lo + hi) // 2
            mid_sha = get_sha(mid)
            if filled_sha < mid_sha:
                hi = mid
            elif filled_sha == mid_sha:
                # perfect match
                lo = mid
                break
            else:
                lo = mid + 1
            # END handle midpoint
        # END bisect

        if lo < self.size():
            cur_sha = get_sha(lo)
            if is_equal_canonical_sha(canonical_length, partial_bin_sha, cur_sha):
                next_sha = None
                if lo + 1 < self.size():
                    next_sha = get_sha(lo + 1)
                if next_sha and next_sha == cur_sha:
                    raise AmbiguousObjectName(partial_bin_sha)
                return lo
            # END if we have a match
        # END if we found something
        return None

    if 'PackIndexFile_sha_to_index' in globals():
        # NOTE: Its just about 25% faster, the major bottleneck might be the attr
        # accesses
        def sha_to_index(self, sha):
            return PackIndexFile_sha_to_index(self, sha)
    # END redefine heavy-hitter with c version

    #} END properties


class PackFile(LazyMixin):

    """A pack is a file written according to the Version 2 for git packs

    As we currently use memory maps, it could be assumed that the maximum size of
    packs therefore is 32 bit on 32 bit systems. On 64 bit systems, this should be
    fine though.

    **Note:** at some point, this might be implemented using streams as well, or
    streams are an alternate path in the case memory maps cannot be created
    for some reason - one clearly doesn't want to read 10GB at once in that
    case"""

    __slots__ = ('_packpath', '_cursor', '_size', '_version')
    pack_signature = 0x5041434b     # 'PACK'
    pack_version_default = 2

    # offset into our data at which the first object starts
    first_object_offset = 3 * 4       # header bytes
    footer_size = 20                # final sha

    def __init__(self, packpath):
        self._packpath = packpath

    def close(self):
        mman.force_map_handle_removal_win(self._packpath)
        self._cursor = None
        
    def _set_cache_(self, attr):
        # we fill the whole cache, whichever attribute gets queried first
        self._cursor = mman.make_cursor(self._packpath).use_region()

        # read the header information
        type_id, self._version, self._size = unpack_from(">LLL", self._cursor.map(), 0)

        # TODO: figure out whether we should better keep the lock, or maybe
        # add a .keep file instead ?
        if type_id != self.pack_signature:
            raise ParseError("Invalid pack signature: %i" % type_id)

    def _iter_objects(self, start_offset, as_stream=True):
        """Handle the actual iteration of objects within this pack"""
        c = self._cursor
        content_size = c.file_size() - self.footer_size
        cur_offset = start_offset or self.first_object_offset

        null = NullStream()
        while cur_offset < content_size:
            data_offset, ostream = pack_object_at(c, cur_offset, True)
            # scrub the stream to the end - this decompresses the object, but yields
            # the amount of compressed bytes we need to get to the next offset

            stream_copy(ostream.read, null.write, ostream.size, chunk_size)
            assert ostream.stream._br == ostream.size
            cur_offset += (data_offset - ostream.pack_offset) + ostream.stream.compressed_bytes_read()

            # if a stream is requested, reset it beforehand
            # Otherwise return the Stream object directly, its derived from the
            # info object
            if as_stream:
                ostream.stream.seek(0)
            yield ostream
        # END until we have read everything

    #{ Pack Information

    def size(self):
        """:return: The amount of objects stored in this pack"""
        return self._size

    def version(self):
        """:return: the version of this pack"""
        return self._version

    def data(self):
        """
        :return: read-only data of this pack. It provides random access and usually
            is a memory map.
        :note: This method is unsafe as it returns a window into a file which might be larger than than the actual window size"""
        # can use map as we are starting at offset 0. Otherwise we would have to use buffer()
        return self._cursor.use_region().map()

    def checksum(self):
        """:return: 20 byte sha1 hash on all object sha's contained in this file"""
        return self._cursor.use_region(self._cursor.file_size() - 20).buffer()[:]

    def path(self):
        """:return: path to the packfile"""
        return self._packpath
    #} END pack information

    #{ Pack Specific

    def collect_streams(self, offset):
        """
        :return: list of pack streams which are required to build the object
            at the given offset. The first entry of the list is the object at offset,
            the last one is either a full object, or a REF_Delta stream. The latter
            type needs its reference object to be locked up in an ODB to form a valid
            delta chain.
            If the object at offset is no delta, the size of the list is 1.
        :param offset: specifies the first byte of the object within this pack"""
        out = list()
        c = self._cursor
        while True:
            ostream = pack_object_at(c, offset, True)[1]
            out.append(ostream)
            if ostream.type_id == OFS_DELTA:
                offset = ostream.pack_offset - ostream.delta_info
            else:
                # the only thing we can lookup are OFFSET deltas. Everything
                # else is either an object, or a ref delta, in the latter
                # case someone else has to find it
                break
            # END handle type
        # END while chaining streams
        return out

    #} END pack specific

    #{ Read-Database like Interface

    def info(self, offset):
        """Retrieve information about the object at the given file-absolute offset

        :param offset: byte offset
        :return: OPackInfo instance, the actual type differs depending on the type_id attribute"""
        return pack_object_at(self._cursor, offset or self.first_object_offset, False)[1]

    def stream(self, offset):
        """Retrieve an object at the given file-relative offset as stream along with its information

        :param offset: byte offset
        :return: OPackStream instance, the actual type differs depending on the type_id attribute"""
        return pack_object_at(self._cursor, offset or self.first_object_offset, True)[1]

    def stream_iter(self, start_offset=0):
        """
        :return: iterator yielding OPackStream compatible instances, allowing
            to access the data in the pack directly.
        :param start_offset: offset to the first object to iterate. If 0, iteration
            starts at the very first object in the pack.

        **Note:** Iterating a pack directly is costly as the datastream has to be decompressed
        to determine the bounds between the objects"""
        return self._iter_objects(start_offset, as_stream=True)

    #} END Read-Database like Interface


class PackEntity(LazyMixin):

    """Combines the PackIndexFile and the PackFile into one, allowing the
    actual objects to be resolved and iterated"""

    __slots__ = ('_index',           # our index file
                 '_pack',            # our pack file
                 '_offset_map'       # on demand dict mapping one offset to the next consecutive one
                 )

    IndexFileCls = PackIndexFile
    PackFileCls = PackFile

    def __init__(self, pack_or_index_path):
        """Initialize ourselves with the path to the respective pack or index file"""
        basename, ext = os.path.splitext(pack_or_index_path)
        self._index = self.IndexFileCls("%s.idx" % basename)            # PackIndexFile instance
        self._pack = self.PackFileCls("%s.pack" % basename)         # corresponding PackFile instance

    def close(self):
        self._index.close()
        self._pack.close()

    def _set_cache_(self, attr):
        # currently this can only be _offset_map
        # TODO: make this a simple sorted offset array which can be bisected
        # to find the respective entry, from which we can take a +1 easily
        # This might be slower, but should also be much lighter in memory !
        offsets_sorted = sorted(self._index.offsets())
        last_offset = len(self._pack.data()) - self._pack.footer_size
        assert offsets_sorted, "Cannot handle empty indices"

        offset_map = None
        if len(offsets_sorted) == 1:
            offset_map = {offsets_sorted[0]: last_offset}
        else:
            iter_offsets = iter(offsets_sorted)
            iter_offsets_plus_one = iter(offsets_sorted)
            next(iter_offsets_plus_one)
            consecutive = zip(iter_offsets, iter_offsets_plus_one)

            offset_map = dict(consecutive)

            # the last offset is not yet set
            offset_map[offsets_sorted[-1]] = last_offset
        # END handle offset amount
        self._offset_map = offset_map

    def _sha_to_index(self, sha):
        """:return: index for the given sha, or raise"""
        index = self._index.sha_to_index(sha)
        if index is None:
            raise BadObject(sha)
        return index

    def _iter_objects(self, as_stream):
        """Iterate over all objects in our index and yield their OInfo or OStream instences"""
        _sha = self._index.sha
        _object = self._object
        for index in range(self._index.size()):
            yield _object(_sha(index), as_stream, index)
        # END for each index

    def _object(self, sha, as_stream, index=-1):
        """:return: OInfo or OStream object providing information about the given sha
        :param index: if not -1, its assumed to be the sha's index in the IndexFile"""
        # its a little bit redundant here, but it needs to be efficient
        if index < 0:
            index = self._sha_to_index(sha)
        if sha is None:
            sha = self._index.sha(index)
        # END assure sha is present ( in output )
        offset = self._index.offset(index)
        type_id, uncomp_size, data_rela_offset = pack_object_header_info(self._pack._cursor.use_region(offset).buffer())
        if as_stream:
            if type_id not in delta_types:
                packstream = self._pack.stream(offset)
                return OStream(sha, packstream.type, packstream.size, packstream.stream)
            # END handle non-deltas

            # produce a delta stream containing all info
            # To prevent it from applying the deltas when querying the size,
            # we extract it from the delta stream ourselves
            streams = self.collect_streams_at_offset(offset)
            dstream = DeltaApplyReader.new(streams)

            return ODeltaStream(sha, dstream.type, None, dstream)
        else:
            if type_id not in delta_types:
                return OInfo(sha, type_id_to_type_map[type_id], uncomp_size)
            # END handle non-deltas

            # deltas are a little tougher - unpack the first bytes to obtain
            # the actual target size, as opposed to the size of the delta data
            streams = self.collect_streams_at_offset(offset)
            buf = streams[0].read(512)
            offset, src_size = msb_size(buf)
            offset, target_size = msb_size(buf, offset)

            # collect the streams to obtain the actual object type
            if streams[-1].type_id in delta_types:
                raise BadObject(sha, "Could not resolve delta object")
            return OInfo(sha, streams[-1].type, target_size)
        # END handle stream

    #{ Read-Database like Interface

    def info(self, sha):
        """Retrieve information about the object identified by the given sha

        :param sha: 20 byte sha1
        :raise BadObject:
        :return: OInfo instance, with 20 byte sha"""
        return self._object(sha, False)

    def stream(self, sha):
        """Retrieve an object stream along with its information as identified by the given sha

        :param sha: 20 byte sha1
        :raise BadObject:
        :return: OStream instance, with 20 byte sha"""
        return self._object(sha, True)

    def info_at_index(self, index):
        """As ``info``, but uses a PackIndexFile compatible index to refer to the object"""
        return self._object(None, False, index)

    def stream_at_index(self, index):
        """As ``stream``, but uses a PackIndexFile compatible index to refer to the
        object"""
        return self._object(None, True, index)

    #} END Read-Database like Interface

    #{ Interface

    def pack(self):
        """:return: the underlying pack file instance"""
        return self._pack

    def index(self):
        """:return: the underlying pack index file instance"""
        return self._index

    def is_valid_stream(self, sha, use_crc=False):
        """
        Verify that the stream at the given sha is valid.

        :param use_crc: if True, the index' crc is run over the compressed stream of
            the object, which is much faster than checking the sha1. It is also
            more prone to unnoticed corruption or manipulation.
        :param sha: 20 byte sha1 of the object whose stream to verify
            whether the compressed stream of the object is valid. If it is
            a delta, this only verifies that the delta's data is valid, not the
            data of the actual undeltified object, as it depends on more than
            just this stream.
            If False, the object will be decompressed and the sha generated. It must
            match the given sha

        :return: True if the stream is valid
        :raise UnsupportedOperation: If the index is version 1 only
        :raise BadObject: sha was not found"""
        if use_crc:
            if self._index.version() < 2:
                raise UnsupportedOperation("Version 1 indices do not contain crc's, verify by sha instead")
            # END handle index version

            index = self._sha_to_index(sha)
            offset = self._index.offset(index)
            next_offset = self._offset_map[offset]
            crc_value = self._index.crc(index)

            # create the current crc value, on the compressed object data
            # Read it in chunks, without copying the data
            crc_update = zlib.crc32
            pack_data = self._pack.data()
            cur_pos = offset
            this_crc_value = 0
            while cur_pos < next_offset:
                rbound = min(cur_pos + chunk_size, next_offset)
                size = rbound - cur_pos
                this_crc_value = crc_update(pack_data[cur_pos:cur_pos + size], this_crc_value)
                cur_pos += size
            # END window size loop

            # crc returns signed 32 bit numbers, the AND op forces it into unsigned
            # mode ... wow, sneaky, from dulwich.
            return (this_crc_value & 0xffffffff) == crc_value
        else:
            shawriter = Sha1Writer()
            stream = self._object(sha, as_stream=True)
            # write a loose object, which is the basis for the sha
            write_object(stream.type, stream.size, stream.read, shawriter.write)

            assert shawriter.sha(as_hex=False) == sha
            return shawriter.sha(as_hex=False) == sha
        # END handle crc/sha verification
        return True

    def info_iter(self):
        """
        :return: Iterator over all objects in this pack. The iterator yields
            OInfo instances"""
        return self._iter_objects(as_stream=False)

    def stream_iter(self):
        """
        :return: iterator over all objects in this pack. The iterator yields
            OStream instances"""
        return self._iter_objects(as_stream=True)

    def collect_streams_at_offset(self, offset):
        """
        As the version in the PackFile, but can resolve REF deltas within this pack
        For more info, see ``collect_streams``

        :param offset: offset into the pack file at which the object can be found"""
        streams = self._pack.collect_streams(offset)

        # try to resolve the last one if needed. It is assumed to be either
        # a REF delta, or a base object, as OFFSET deltas are resolved by the pack
        if streams[-1].type_id == REF_DELTA:
            stream = streams[-1]
            while stream.type_id in delta_types:
                if stream.type_id == REF_DELTA:
                    # smmap can return memory view objects, which can't be compared as buffers/bytes can ...
                    if isinstance(stream.delta_info, memoryview):
                        sindex = self._index.sha_to_index(stream.delta_info.tobytes())
                    else:
                        sindex = self._index.sha_to_index(stream.delta_info)
                    if sindex is None:
                        break
                    stream = self._pack.stream(self._index.offset(sindex))
                    streams.append(stream)
                else:
                    # must be another OFS DELTA - this could happen if a REF
                    # delta we resolve previously points to an OFS delta. Who
                    # would do that ;) ? We can handle it though
                    stream = self._pack.stream(stream.delta_info)
                    streams.append(stream)
                # END handle ref delta
            # END resolve ref streams
        # END resolve streams

        return streams

    def collect_streams(self, sha):
        """
        As ``PackFile.collect_streams``, but takes a sha instead of an offset.
        Additionally, ref_delta streams will be resolved within this pack.
        If this is not possible, the stream will be left alone, hence it is adivsed
        to check for unresolved ref-deltas and resolve them before attempting to
        construct a delta stream.

        :param sha: 20 byte sha1 specifying the object whose related streams you want to collect
        :return: list of streams, first being the actual object delta, the last being
            a possibly unresolved base object.
        :raise BadObject:"""
        return self.collect_streams_at_offset(self._index.offset(self._sha_to_index(sha)))

    @classmethod
    def write_pack(cls, object_iter, pack_write, index_write=None,
                   object_count=None, zlib_compression=zlib.Z_BEST_SPEED):
        """
        Create a new pack by putting all objects obtained by the object_iterator
        into a pack which is written using the pack_write method.
        The respective index is produced as well if index_write is not Non.

        :param object_iter: iterator yielding odb output objects
        :param pack_write: function to receive strings to write into the pack stream
        :param indx_write: if not None, the function writes the index file corresponding
            to the pack.
        :param object_count: if you can provide the amount of objects in your iteration,
            this would be the place to put it. Otherwise we have to pre-iterate and store
            all items into a list to get the number, which uses more memory than necessary.
        :param zlib_compression: the zlib compression level to use
        :return: tuple(pack_sha, index_binsha) binary sha over all the contents of the pack
            and over all contents of the index. If index_write was None, index_binsha will be None

        **Note:** The destination of the write functions is up to the user. It could
        be a socket, or a file for instance

        **Note:** writes only undeltified objects"""
        objs = object_iter
        if not object_count:
            if not isinstance(object_iter, (tuple, list)):
                objs = list(object_iter)
            # END handle list type
            object_count = len(objs)
        # END handle object

        pack_writer = FlexibleSha1Writer(pack_write)
        pwrite = pack_writer.write
        ofs = 0                                         # current offset into the pack file
        index = None
        wants_index = index_write is not None

        # write header
        pwrite(pack('>LLL', PackFile.pack_signature, PackFile.pack_version_default, object_count))
        ofs += 12

        if wants_index:
            index = IndexWriter()
        # END handle index header

        actual_count = 0
        for obj in objs:
            actual_count += 1
            crc = 0

            # object header
            hdr = create_pack_object_header(obj.type_id, obj.size)
            if index_write:
                crc = crc32(hdr)
            else:
                crc = None
            # END handle crc
            pwrite(hdr)

            # data stream
            zstream = zlib.compressobj(zlib_compression)
            ostream = obj.stream
            br, bw, crc = write_stream_to_pack(ostream.read, pwrite, zstream, base_crc=crc)
            assert(br == obj.size)
            if wants_index:
                index.append(obj.binsha, crc, ofs)
            # END handle index

            ofs += len(hdr) + bw
            if actual_count == object_count:
                break
            # END abort once we are done
        # END for each object

        if actual_count != object_count:
            raise ValueError(
                "Expected to write %i objects into pack, but received only %i from iterators" % (object_count, actual_count))
        # END count assertion

        # write footer
        pack_sha = pack_writer.sha(as_hex=False)
        assert len(pack_sha) == 20
        pack_write(pack_sha)
        ofs += len(pack_sha)                            # just for completeness ;)

        index_sha = None
        if wants_index:
            index_sha = index.write(pack_sha, index_write)
        # END handle index

        return pack_sha, index_sha

    @classmethod
    def create(cls, object_iter, base_dir, object_count=None, zlib_compression=zlib.Z_BEST_SPEED):
        """Create a new on-disk entity comprised of a properly named pack file and a properly named
        and corresponding index file. The pack contains all OStream objects contained in object iter.
        :param base_dir: directory which is to contain the files
        :return: PackEntity instance initialized with the new pack

        **Note:** for more information on the other parameters see the write_pack method"""
        pack_fd, pack_path = tempfile.mkstemp('', 'pack', base_dir)
        index_fd, index_path = tempfile.mkstemp('', 'index', base_dir)
        pack_write = lambda d: os.write(pack_fd, d)
        index_write = lambda d: os.write(index_fd, d)

        pack_binsha, index_binsha = cls.write_pack(object_iter, pack_write, index_write, object_count, zlib_compression)
        os.close(pack_fd)
        os.close(index_fd)

        fmt = "pack-%s.%s"
        new_pack_path = os.path.join(base_dir, fmt % (bin_to_hex(pack_binsha), 'pack'))
        new_index_path = os.path.join(base_dir, fmt % (bin_to_hex(pack_binsha), 'idx'))
        os.rename(pack_path, new_pack_path)
        os.rename(index_path, new_index_path)

        return cls(new_pack_path)

    #} END interface
