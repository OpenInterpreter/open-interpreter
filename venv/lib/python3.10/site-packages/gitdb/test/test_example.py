# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
"""Module with examples from the tutorial section of the docs"""
import os
from gitdb.test.lib import TestBase
from gitdb import IStream
from gitdb.db import LooseObjectDB

from io import BytesIO


class TestExamples(TestBase):

    def test_base(self):
        ldb = LooseObjectDB(os.path.join(self.gitrepopath, 'objects'))

        for sha1 in ldb.sha_iter():
            oinfo = ldb.info(sha1)
            ostream = ldb.stream(sha1)
            assert oinfo[:3] == ostream[:3]

            assert len(ostream.read()) == ostream.size
            assert ldb.has_object(oinfo.binsha)
        # END for each sha in database
        # assure we close all files
        try:
            del(ostream)
            del(oinfo)
        except UnboundLocalError:
            pass
        # END ignore exception if there are no loose objects

        data = b"my data"
        istream = IStream("blob", len(data), BytesIO(data))

        # the object does not yet have a sha
        assert istream.binsha is None
        ldb.store(istream)
        # now the sha is set
        assert len(istream.binsha) == 20
        assert ldb.has_object(istream.binsha)
