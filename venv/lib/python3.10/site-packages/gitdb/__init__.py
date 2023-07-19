# Copyright (C) 2010, 2011 Sebastian Thiel (byronimo@gmail.com) and contributors
#
# This module is part of GitDB and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php
"""Initialize the object database module"""

import sys
import os

#{ Initialization


def _init_externals():
    """Initialize external projects by putting them into the path"""
    if 'PYOXIDIZER' not in os.environ:
        where = os.path.join(os.path.dirname(__file__), 'ext', 'smmap')
        if os.path.exists(where):
            sys.path.append(where)

    import smmap
    del smmap
    # END handle imports

#} END initialization

_init_externals()

__author__ = "Sebastian Thiel"
__contact__ = "byronimo@gmail.com"
__homepage__ = "https://github.com/gitpython-developers/gitdb"
version_info = (4, 0, 10)
__version__ = '.'.join(str(i) for i in version_info)


# default imports
from gitdb.base import *
from gitdb.db import *
from gitdb.stream import *
