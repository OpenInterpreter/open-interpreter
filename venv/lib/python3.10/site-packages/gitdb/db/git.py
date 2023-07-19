# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
from gitdb.db.base import (
    CompoundDB,
    ObjectDBW,
    FileDBBase
)

from gitdb.db.loose import LooseObjectDB
from gitdb.db.pack import PackedDB
from gitdb.db.ref import ReferenceDB

from gitdb.exc import InvalidDBRoot

import os

__all__ = ('GitDB', )


class GitDB(FileDBBase, ObjectDBW, CompoundDB):

    """A git-style object database, which contains all objects in the 'objects'
    subdirectory

    ``IMPORTANT``: The usage of this implementation is highly discouraged as it fails to release file-handles.
    This can be a problem with long-running processes and/or big repositories.
    """
    # Configuration
    PackDBCls = PackedDB
    LooseDBCls = LooseObjectDB
    ReferenceDBCls = ReferenceDB

    # Directories
    packs_dir = 'pack'
    loose_dir = ''
    alternates_dir = os.path.join('info', 'alternates')

    def __init__(self, root_path):
        """Initialize ourselves on a git objects directory"""
        super().__init__(root_path)

    def _set_cache_(self, attr):
        if attr == '_dbs' or attr == '_loose_db':
            self._dbs = list()
            loose_db = None
            for subpath, dbcls in ((self.packs_dir, self.PackDBCls),
                                   (self.loose_dir, self.LooseDBCls),
                                   (self.alternates_dir, self.ReferenceDBCls)):
                path = self.db_path(subpath)
                if os.path.exists(path):
                    self._dbs.append(dbcls(path))
                    if dbcls is self.LooseDBCls:
                        loose_db = self._dbs[-1]
                    # END remember loose db
                # END check path exists
            # END for each db type

            # should have at least one subdb
            if not self._dbs:
                raise InvalidDBRoot(self.root_path())
            # END handle error

            # we the first one should have the store method
            assert loose_db is not None and hasattr(loose_db, 'store'), "First database needs store functionality"

            # finally set the value
            self._loose_db = loose_db
        else:
            super()._set_cache_(attr)
        # END handle attrs

    #{ ObjectDBW interface

    def store(self, istream):
        return self._loose_db.store(istream)

    def ostream(self):
        return self._loose_db.ostream()

    def set_ostream(self, ostream):
        return self._loose_db.set_ostream(ostream)

    #} END objectdbw interface
