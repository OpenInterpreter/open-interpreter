# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
"""Contains implementations of database retrieveing objects"""
from gitdb.util import (
    join,
    LazyMixin,
    hex_to_bin
)

from gitdb.utils.encoding import force_text
from gitdb.exc import (
    BadObject,
    AmbiguousObjectName
)

from itertools import chain
from functools import reduce


__all__ = ('ObjectDBR', 'ObjectDBW', 'FileDBBase', 'CompoundDB', 'CachingDB')


class ObjectDBR:

    """Defines an interface for object database lookup.
    Objects are identified either by their 20 byte bin sha"""

    def __contains__(self, sha):
        return self.has_obj

    #{ Query Interface
    def has_object(self, sha):
        """
        Whether the object identified by the given 20 bytes
            binary sha is contained in the database

        :return: True if the object identified by the given 20 bytes
            binary sha is contained in the database"""
        raise NotImplementedError("To be implemented in subclass")

    def info(self, sha):
        """ :return: OInfo instance
        :param sha: bytes binary sha
        :raise BadObject:"""
        raise NotImplementedError("To be implemented in subclass")

    def stream(self, sha):
        """:return: OStream instance
        :param sha: 20 bytes binary sha
        :raise BadObject:"""
        raise NotImplementedError("To be implemented in subclass")

    def size(self):
        """:return: amount of objects in this database"""
        raise NotImplementedError()

    def sha_iter(self):
        """Return iterator yielding 20 byte shas for all objects in this data base"""
        raise NotImplementedError()

    #} END query interface


class ObjectDBW:

    """Defines an interface to create objects in the database"""

    def __init__(self, *args, **kwargs):
        self._ostream = None

    #{ Edit Interface
    def set_ostream(self, stream):
        """
        Adjusts the stream to which all data should be sent when storing new objects

        :param stream: if not None, the stream to use, if None the default stream
            will be used.
        :return: previously installed stream, or None if there was no override
        :raise TypeError: if the stream doesn't have the supported functionality"""
        cstream = self._ostream
        self._ostream = stream
        return cstream

    def ostream(self):
        """
        Return the output stream

        :return: overridden output stream this instance will write to, or None
            if it will write to the default stream"""
        return self._ostream

    def store(self, istream):
        """
        Create a new object in the database
        :return: the input istream object with its sha set to its corresponding value

        :param istream: IStream compatible instance. If its sha is already set
            to a value, the object will just be stored in the our database format,
            in which case the input stream is expected to be in object format ( header + contents ).
        :raise IOError: if data could not be written"""
        raise NotImplementedError("To be implemented in subclass")

    #} END edit interface


class FileDBBase:

    """Provides basic facilities to retrieve files of interest, including
    caching facilities to help mapping hexsha's to objects"""

    def __init__(self, root_path):
        """Initialize this instance to look for its files at the given root path
        All subsequent operations will be relative to this path
        :raise InvalidDBRoot:
        **Note:** The base will not perform any accessablity checking as the base
            might not yet be accessible, but become accessible before the first
            access."""
        super().__init__()
        self._root_path = root_path

    #{ Interface
    def root_path(self):
        """:return: path at which this db operates"""
        return self._root_path

    def db_path(self, rela_path):
        """
        :return: the given relative path relative to our database root, allowing
            to pontentially access datafiles"""
        return join(self._root_path, force_text(rela_path))
    #} END interface


class CachingDB:

    """A database which uses caches to speed-up access"""

    #{ Interface
    def update_cache(self, force=False):
        """
        Call this method if the underlying data changed to trigger an update
        of the internal caching structures.

        :param force: if True, the update must be performed. Otherwise the implementation
            may decide not to perform an update if it thinks nothing has changed.
        :return: True if an update was performed as something change indeed"""

    # END interface


def _databases_recursive(database, output):
    """Fill output list with database from db, in order. Deals with Loose, Packed
    and compound databases."""
    if isinstance(database, CompoundDB):
        dbs = database.databases()
        output.extend(db for db in dbs if not isinstance(db, CompoundDB))
        for cdb in (db for db in dbs if isinstance(db, CompoundDB)):
            _databases_recursive(cdb, output)
    else:
        output.append(database)
    # END handle database type


class CompoundDB(ObjectDBR, LazyMixin, CachingDB):

    """A database which delegates calls to sub-databases.

    Databases are stored in the lazy-loaded _dbs attribute.
    Define _set_cache_ to update it with your databases"""

    def _set_cache_(self, attr):
        if attr == '_dbs':
            self._dbs = list()
        elif attr == '_db_cache':
            self._db_cache = dict()
        else:
            super()._set_cache_(attr)

    def _db_query(self, sha):
        """:return: database containing the given 20 byte sha
        :raise BadObject:"""
        # most databases use binary representations, prevent converting
        # it every time a database is being queried
        try:
            return self._db_cache[sha]
        except KeyError:
            pass
        # END first level cache

        for db in self._dbs:
            if db.has_object(sha):
                self._db_cache[sha] = db
                return db
        # END for each database
        raise BadObject(sha)

    #{ ObjectDBR interface

    def has_object(self, sha):
        try:
            self._db_query(sha)
            return True
        except BadObject:
            return False
        # END handle exceptions

    def info(self, sha):
        return self._db_query(sha).info(sha)

    def stream(self, sha):
        return self._db_query(sha).stream(sha)

    def size(self):
        """:return: total size of all contained databases"""
        return reduce(lambda x, y: x + y, (db.size() for db in self._dbs), 0)

    def sha_iter(self):
        return chain(*(db.sha_iter() for db in self._dbs))

    #} END object DBR Interface

    #{ Interface

    def databases(self):
        """:return: tuple of database instances we use for lookups"""
        return tuple(self._dbs)

    def update_cache(self, force=False):
        # something might have changed, clear everything
        self._db_cache.clear()
        stat = False
        for db in self._dbs:
            if isinstance(db, CachingDB):
                stat |= db.update_cache(force)
            # END if is caching db
        # END for each database to update
        return stat

    def partial_to_complete_sha_hex(self, partial_hexsha):
        """
        :return: 20 byte binary sha1 from the given less-than-40 byte hexsha (bytes or str)
        :param partial_hexsha: hexsha with less than 40 byte
        :raise AmbiguousObjectName: """
        databases = list()
        _databases_recursive(self, databases)
        partial_hexsha = force_text(partial_hexsha)
        len_partial_hexsha = len(partial_hexsha)
        if len_partial_hexsha % 2 != 0:
            partial_binsha = hex_to_bin(partial_hexsha + "0")
        else:
            partial_binsha = hex_to_bin(partial_hexsha)
        # END assure successful binary conversion

        candidate = None
        for db in databases:
            full_bin_sha = None
            try:
                if hasattr(db, 'partial_to_complete_sha_hex'):
                    full_bin_sha = db.partial_to_complete_sha_hex(partial_hexsha)
                else:
                    full_bin_sha = db.partial_to_complete_sha(partial_binsha, len_partial_hexsha)
                # END handle database type
            except BadObject:
                continue
            # END ignore bad objects
            if full_bin_sha:
                if candidate and candidate != full_bin_sha:
                    raise AmbiguousObjectName(partial_hexsha)
                candidate = full_bin_sha
            # END handle candidate
        # END for each db
        if not candidate:
            raise BadObject(partial_binsha)
        return candidate

    #} END interface
