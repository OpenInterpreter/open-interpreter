# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
"""Test for object db"""
import tempfile
import os

from gitdb.test.lib import TestBase
from gitdb.util import (
    to_hex_sha,
    to_bin_sha,
    NULL_HEX_SHA,
    LockedFD
)


class TestUtils(TestBase):

    def test_basics(self):
        assert to_hex_sha(NULL_HEX_SHA) == NULL_HEX_SHA
        assert len(to_bin_sha(NULL_HEX_SHA)) == 20
        assert to_hex_sha(to_bin_sha(NULL_HEX_SHA)) == NULL_HEX_SHA.encode("ascii")

    def _cmp_contents(self, file_path, data):
        # raise if data from file at file_path
        # does not match data string
        with open(file_path, "rb") as fp:
            assert fp.read() == data.encode("ascii")

    def test_lockedfd(self):
        my_file = tempfile.mktemp()
        orig_data = "hello"
        new_data = "world"
        with open(my_file, "wb") as my_file_fp:
            my_file_fp.write(orig_data.encode("ascii"))

        try:
            lfd = LockedFD(my_file)
            lockfilepath = lfd._lockfilepath()

            # cannot end before it was started
            self.assertRaises(AssertionError, lfd.rollback)
            self.assertRaises(AssertionError, lfd.commit)

            # open for writing
            assert not os.path.isfile(lockfilepath)
            wfd = lfd.open(write=True)
            assert lfd._fd is wfd
            assert os.path.isfile(lockfilepath)

            # write data and fail
            os.write(wfd, new_data.encode("ascii"))
            lfd.rollback()
            assert lfd._fd is None
            self._cmp_contents(my_file, orig_data)
            assert not os.path.isfile(lockfilepath)

            # additional call doesn't fail
            lfd.commit()
            lfd.rollback()

            # test reading
            lfd = LockedFD(my_file)
            rfd = lfd.open(write=False)
            assert os.read(rfd, len(orig_data)) == orig_data.encode("ascii")

            assert os.path.isfile(lockfilepath)
            # deletion rolls back
            del(lfd)
            assert not os.path.isfile(lockfilepath)

            # write data - concurrently
            lfd = LockedFD(my_file)
            olfd = LockedFD(my_file)
            assert not os.path.isfile(lockfilepath)
            wfdstream = lfd.open(write=True, stream=True)       # this time as stream
            assert os.path.isfile(lockfilepath)
            # another one fails
            self.assertRaises(IOError, olfd.open)

            wfdstream.write(new_data.encode("ascii"))
            lfd.commit()
            assert not os.path.isfile(lockfilepath)
            self._cmp_contents(my_file, new_data)

            # could test automatic _end_writing on destruction
        finally:
            os.remove(my_file)
        # END final cleanup

        # try non-existing file for reading
        lfd = LockedFD(tempfile.mktemp())
        try:
            lfd.open(write=False)
        except OSError:
            assert not os.path.exists(lfd._lockfilepath())
        else:
            self.fail("expected OSError")
        # END handle exceptions
