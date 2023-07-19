from .lib import TestBase


class TestTutorial(TestBase):

    def test_example(self):
        # Memory Managers
        ##################
        import smmap
        # This instance should be globally available in your application
        # It is configured to be well suitable for 32-bit or 64 bit applications.
        mman = smmap.SlidingWindowMapManager()

        # the manager provides much useful information about its current state
        # like the amount of open file handles or the amount of mapped memory
        assert mman.num_file_handles() == 0
        assert mman.mapped_memory_size() == 0
        # and many more ...

        # Cursors
        ##########
        import smmap.test.lib
        with smmap.test.lib.FileCreator(1024 * 1024 * 8, "test_file") as fc:
            # obtain a cursor to access some file.
            c = mman.make_cursor(fc.path)

            # the cursor is now associated with the file, but not yet usable
            assert c.is_associated()
            assert not c.is_valid()

            # before you can use the cursor, you have to specify a window you want to
            # access. The following just says you want as much data as possible starting
            # from offset 0.
            # To be sure your region could be mapped, query for validity
            assert c.use_region().is_valid()        # use_region returns self

            # once a region was mapped, you must query its dimension regularly
            # to assure you don't try to access its buffer out of its bounds
            assert c.size()
            c.buffer()[0]           # first byte
            c.buffer()[1:10]            # first 9 bytes
            c.buffer()[c.size() - 1]  # last byte

            # you can query absolute offsets, and check whether an offset is included
            # in the cursor's data.
            assert c.ofs_begin() < c.ofs_end()
            assert c.includes_ofs(100)

            # If you are over out of bounds with one of your region requests, the
            # cursor will be come invalid. It cannot be used in that state
            assert not c.use_region(fc.size, 100).is_valid()
            # map as much as possible after skipping the first 100 bytes
            assert c.use_region(100).is_valid()

            # You can explicitly free cursor resources by unusing the cursor's region
            c.unuse_region()
            assert not c.is_valid()

            # Buffers
            #########
            # Create a default buffer which can operate on the whole file
            buf = smmap.SlidingWindowMapBuffer(mman.make_cursor(fc.path))

            # you can use it right away
            assert buf.cursor().is_valid()

            buf[0]  # access the first byte
            buf[-1]  # access the last ten bytes on the file
            buf[-10:]  # access the last ten bytes

            # If you want to keep the instance between different accesses, use the
            # dedicated methods
            buf.end_access()
            assert not buf.cursor().is_valid()  # you cannot use the buffer anymore
            assert buf.begin_access(offset=10)  # start using the buffer at an offset
