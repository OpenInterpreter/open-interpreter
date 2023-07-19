"""Module containing a memory memory manager which provides a sliding window on a number of memory mapped files"""
import os
import sys

from mmap import mmap, ACCESS_READ
from mmap import ALLOCATIONGRANULARITY

__all__ = ["align_to_mmap", "is_64_bit",
           "MapWindow", "MapRegion", "MapRegionList", "ALLOCATIONGRANULARITY"]

#{ Utilities


def align_to_mmap(num, round_up):
    """
    Align the given integer number to the closest page offset, which usually is 4096 bytes.

    :param round_up: if True, the next higher multiple of page size is used, otherwise
        the lower page_size will be used (i.e. if True, 1 becomes 4096, otherwise it becomes 0)
    :return: num rounded to closest page"""
    res = (num // ALLOCATIONGRANULARITY) * ALLOCATIONGRANULARITY
    if round_up and (res != num):
        res += ALLOCATIONGRANULARITY
    # END handle size
    return res


def is_64_bit():
    """:return: True if the system is 64 bit. Otherwise it can be assumed to be 32 bit"""
    return sys.maxsize > (1 << 32) - 1

#}END utilities


#{ Utility Classes

class MapWindow:

    """Utility type which is used to snap windows towards each other, and to adjust their size"""
    __slots__ = (
        'ofs',      # offset into the file in bytes
        'size'              # size of the window in bytes
    )

    def __init__(self, offset, size):
        self.ofs = offset
        self.size = size

    def __repr__(self):
        return "MapWindow(%i, %i)" % (self.ofs, self.size)

    @classmethod
    def from_region(cls, region):
        """:return: new window from a region"""
        return cls(region._b, region.size())

    def ofs_end(self):
        return self.ofs + self.size

    def align(self):
        """Assures the previous window area is contained in the new one"""
        nofs = align_to_mmap(self.ofs, 0)
        self.size += self.ofs - nofs    # keep size constant
        self.ofs = nofs
        self.size = align_to_mmap(self.size, 1)

    def extend_left_to(self, window, max_size):
        """Adjust the offset to start where the given window on our left ends if possible,
        but don't make yourself larger than max_size.
        The resize will assure that the new window still contains the old window area"""
        rofs = self.ofs - window.ofs_end()
        nsize = rofs + self.size
        rofs -= nsize - min(nsize, max_size)
        self.ofs = self.ofs - rofs
        self.size += rofs

    def extend_right_to(self, window, max_size):
        """Adjust the size to make our window end where the right window begins, but don't
        get larger than max_size"""
        self.size = min(self.size + (window.ofs - self.ofs_end()), max_size)


class MapRegion:

    """Defines a mapped region of memory, aligned to pagesizes

    **Note:** deallocates used region automatically on destruction"""
    __slots__ = [
        '_b',   # beginning of mapping
        '_mf',  # mapped memory chunk (as returned by mmap)
        '_uc',  # total amount of usages
        '_size',  # cached size of our memory map
        '__weakref__'
    ]

    #{ Configuration
    #} END configuration

    def __init__(self, path_or_fd, ofs, size, flags=0):
        """Initialize a region, allocate the memory map
        :param path_or_fd: path to the file to map, or the opened file descriptor
        :param ofs: **aligned** offset into the file to be mapped
        :param size: if size is larger then the file on disk, the whole file will be
            allocated the the size automatically adjusted
        :param flags: additional flags to be given when opening the file.
        :raise Exception: if no memory can be allocated"""
        self._b = ofs
        self._size = 0
        self._uc = 0

        if isinstance(path_or_fd, int):
            fd = path_or_fd
        else:
            fd = os.open(path_or_fd, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | flags)
        # END handle fd

        try:
            kwargs = dict(access=ACCESS_READ, offset=ofs)
            corrected_size = size
            sizeofs = ofs

            # have to correct size, otherwise (instead of the c version) it will
            # bark that the size is too large ... many extra file accesses because
            # if this ... argh !
            actual_size = min(os.fstat(fd).st_size - sizeofs, corrected_size)
            self._mf = mmap(fd, actual_size, **kwargs)
            # END handle memory mode

            self._size = len(self._mf)
        finally:
            if isinstance(path_or_fd, str):
                os.close(fd)
            # END only close it if we opened it
        # END close file handle
        # We assume the first one to use us keeps us around
        self.increment_client_count()

    def __repr__(self):
        return "MapRegion<%i, %i>" % (self._b, self.size())

    #{ Interface

    def buffer(self):
        """:return: a buffer containing the memory"""
        return self._mf

    def map(self):
        """:return: a memory map containing the memory"""
        return self._mf

    def ofs_begin(self):
        """:return: absolute byte offset to the first byte of the mapping"""
        return self._b

    def size(self):
        """:return: total size of the mapped region in bytes"""
        return self._size

    def ofs_end(self):
        """:return: Absolute offset to one byte beyond the mapping into the file"""
        return self._b + self._size

    def includes_ofs(self, ofs):
        """:return: True if the given offset can be read in our mapped region"""
        return self._b <= ofs < self._b + self._size

    def client_count(self):
        """:return: number of clients currently using this region"""
        return self._uc

    def increment_client_count(self, ofs = 1):
        """Adjust the usage count by the given positive or negative offset.
        If usage count equals 0, we will auto-release our resources
        :return: True if we released resources, False otherwise. In the latter case, we can still be used"""
        self._uc += ofs
        assert self._uc > -1, "Increments must match decrements, usage counter negative: %i" % self._uc

        if self.client_count() == 0:
            self.release()
            return True
        else:
            return False
        # end handle release

    def release(self):
        """Release all resources this instance might hold. Must only be called if there usage_count() is zero"""
        self._mf.close()

    #} END interface


class MapRegionList(list):

    """List of MapRegion instances associating a path with a list of regions."""
    __slots__ = (
        '_path_or_fd',  # path or file descriptor which is mapped by all our regions
        '_file_size'    # total size of the file we map
    )

    def __new__(cls, path):
        return super().__new__(cls)

    def __init__(self, path_or_fd):
        self._path_or_fd = path_or_fd
        self._file_size = None

    def path_or_fd(self):
        """:return: path or file descriptor we are attached to"""
        return self._path_or_fd

    def file_size(self):
        """:return: size of file we manager"""
        if self._file_size is None:
            if isinstance(self._path_or_fd, str):
                self._file_size = os.stat(self._path_or_fd).st_size
            else:
                self._file_size = os.fstat(self._path_or_fd).st_size
            # END handle path type
        # END update file size
        return self._file_size

#} END utility classes
