from .lib import TestBase, FileCreator

from smmap.mman import (
    WindowCursor,
    SlidingWindowMapManager,
    StaticWindowMapManager
)
from smmap.util import align_to_mmap

from random import randint
from time import time
import os
import sys
from copy import copy


class TestMMan(TestBase):

    def test_cursor(self):
        with FileCreator(self.k_window_test_size, "cursor_test") as fc:
            man = SlidingWindowMapManager()
            ci = WindowCursor(man)  # invalid cursor
            assert not ci.is_valid()
            assert not ci.is_associated()
            assert ci.size() == 0       # this is cached, so we can query it in invalid state

            cv = man.make_cursor(fc.path)
            assert not cv.is_valid()    # no region mapped yet
            assert cv.is_associated()  # but it know where to map it from
            assert cv.file_size() == fc.size
            assert cv.path() == fc.path

        # copy module
        cio = copy(cv)
        assert not cio.is_valid() and cio.is_associated()

        # assign method
        assert not ci.is_associated()
        ci.assign(cv)
        assert not ci.is_valid() and ci.is_associated()

        # unuse non-existing region is fine
        cv.unuse_region()
        cv.unuse_region()

        # destruction is fine (even multiple times)
        cv._destroy()
        WindowCursor(man)._destroy()

    def test_memory_manager(self):
        slide_man = SlidingWindowMapManager()
        static_man = StaticWindowMapManager()

        for man in (static_man, slide_man):
            assert man.num_file_handles() == 0
            assert man.num_open_files() == 0
            winsize_cmp_val = 0
            if isinstance(man, StaticWindowMapManager):
                winsize_cmp_val = -1
            # END handle window size
            assert man.window_size() > winsize_cmp_val
            assert man.mapped_memory_size() == 0
            assert man.max_mapped_memory_size() > 0

            # collection doesn't raise in 'any' mode
            man._collect_lru_region(0)
            # doesn't raise if we are within the limit
            man._collect_lru_region(10)

            # doesn't fail if we over-allocate
            assert man._collect_lru_region(sys.maxsize) == 0

            # use a region, verify most basic functionality
            with FileCreator(self.k_window_test_size, "manager_test") as fc:
                fd = os.open(fc.path, os.O_RDONLY)
                try:
                    for item in (fc.path, fd):
                        c = man.make_cursor(item)
                        assert c.path_or_fd() is item
                        assert c.use_region(10, 10).is_valid()
                        assert c.ofs_begin() == 10
                        assert c.size() == 10
                        with open(fc.path, 'rb') as fp:
                            assert c.buffer()[:] == fp.read(20)[10:]

                    if isinstance(item, int):
                        self.assertRaises(ValueError, c.path)
                    else:
                        self.assertRaises(ValueError, c.fd)
                    # END handle value error
                # END for each input
                finally:
                    os.close(fd)
        # END for each manasger type

    def test_memman_operation(self):
        # test more access, force it to actually unmap regions
        with FileCreator(self.k_window_test_size, "manager_operation_test") as fc:
            with open(fc.path, 'rb') as fp:
                data = fp.read()
            fd = os.open(fc.path, os.O_RDONLY)
            try:
                max_num_handles = 15
                # small_size =
                for mtype, args in ((StaticWindowMapManager, (0, fc.size // 3, max_num_handles)),
                                    (SlidingWindowMapManager, (fc.size // 100, fc.size // 3, max_num_handles)),):
                    for item in (fc.path, fd):
                        assert len(data) == fc.size

                        # small windows, a reasonable max memory. Not too many regions at once
                        man = mtype(window_size=args[0], max_memory_size=args[1], max_open_handles=args[2])
                        c = man.make_cursor(item)

                        # still empty (more about that is tested in test_memory_manager()
                        assert man.num_open_files() == 0
                        assert man.mapped_memory_size() == 0

                        base_offset = 5000
                        # window size is 0 for static managers, hence size will be 0. We take that into consideration
                        size = man.window_size() // 2
                        assert c.use_region(base_offset, size).is_valid()
                        rr = c.region()
                        assert rr.client_count() == 2  # the manager and the cursor and us

                        assert man.num_open_files() == 1
                        assert man.num_file_handles() == 1
                        assert man.mapped_memory_size() == rr.size()

                        # assert c.size() == size        # the cursor may overallocate in its static version
                        assert c.ofs_begin() == base_offset
                        assert rr.ofs_begin() == 0        # it was aligned and expanded
                        if man.window_size():
                            # but isn't larger than the max window (aligned)
                            assert rr.size() == align_to_mmap(man.window_size(), True)
                        else:
                            assert rr.size() == fc.size
                        # END ignore static managers which dont use windows and are aligned to file boundaries

                        assert c.buffer()[:] == data[base_offset:base_offset + (size or c.size())]

                        # obtain second window, which spans the first part of the file - it is a still the same window
                        nsize = (size or fc.size) - 10
                        assert c.use_region(0, nsize).is_valid()
                        assert c.region() == rr
                        assert man.num_file_handles() == 1
                        assert c.size() == nsize
                        assert c.ofs_begin() == 0
                        assert c.buffer()[:] == data[:nsize]

                        # map some part at the end, our requested size cannot be kept
                        overshoot = 4000
                        base_offset = fc.size - (size or c.size()) + overshoot
                        assert c.use_region(base_offset, size).is_valid()
                        if man.window_size():
                            assert man.num_file_handles() == 2
                            assert c.size() < size
                            assert c.region() is not rr  # old region is still available, but has not curser ref anymore
                            assert rr.client_count() == 1  # only held by manager
                        else:
                            assert c.size() < fc.size
                        # END ignore static managers which only have one handle per file
                        rr = c.region()
                        assert rr.client_count() == 2  # manager + cursor
                        assert rr.ofs_begin() < c.ofs_begin()  # it should have extended itself to the left
                        assert rr.ofs_end() <= fc.size  # it cannot be larger than the file
                        assert c.buffer()[:] == data[base_offset:base_offset + (size or c.size())]

                        # unising a region makes the cursor invalid
                        c.unuse_region()
                        assert not c.is_valid()
                        if man.window_size():
                            # but doesn't change anything regarding the handle count - we cache it and only
                            # remove mapped regions if we have to
                            assert man.num_file_handles() == 2
                        # END ignore this for static managers

                        # iterate through the windows, verify data contents
                        # this will trigger map collection after a while
                        max_random_accesses = 5000
                        num_random_accesses = max_random_accesses
                        memory_read = 0
                        st = time()

                        # cache everything to get some more performance
                        includes_ofs = c.includes_ofs
                        max_mapped_memory_size = man.max_mapped_memory_size()
                        max_file_handles = man.max_file_handles()
                        mapped_memory_size = man.mapped_memory_size
                        num_file_handles = man.num_file_handles
                        while num_random_accesses:
                            num_random_accesses -= 1
                            base_offset = randint(0, fc.size - 1)

                            # precondition
                            if man.window_size():
                                assert max_mapped_memory_size >= mapped_memory_size()
                            # END statics will overshoot, which is fine
                            assert max_file_handles >= num_file_handles()
                            assert c.use_region(base_offset, (size or c.size())).is_valid()
                            csize = c.size()
                            assert c.buffer()[:] == data[base_offset:base_offset + csize]
                            memory_read += csize

                            assert includes_ofs(base_offset)
                            assert includes_ofs(base_offset + csize - 1)
                            assert not includes_ofs(base_offset + csize)
                        # END while we should do an access
                        elapsed = max(time() - st, 0.001)  # prevent zero divison errors on windows
                        mb = float(1000 * 1000)
                        print("%s: Read %i mb of memory with %i random on cursor initialized with %s accesses in %fs (%f mb/s)\n"
                              % (mtype, memory_read / mb, max_random_accesses, type(item), elapsed, (memory_read / mb) / elapsed),
                              file=sys.stderr)

                        # an offset as large as the size doesn't work !
                        assert not c.use_region(fc.size, size).is_valid()

                        # collection - it should be able to collect all
                        assert man.num_file_handles()
                        assert man.collect()
                        assert man.num_file_handles() == 0
                    # END for each item
                # END for each manager type
            finally:
                os.close(fd)
