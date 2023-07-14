from .exceptions import (
    DecryptError,
    EncryptError,
    NotSupportedError,
    PysetoError,
    SignError,
    VerifyError,
)
from .key import Key
from .key_interface import KeyInterface
from .paseto import Paseto
from .pyseto import decode, encode
from .token import Token

__version__ = "1.7.0"
__title__ = "PySETO"
__description__ = "A Python implementation of PASETO/PASERK."
__url__ = "https://pyseto.readthedocs.io"
__uri__ = __url__
__doc__ = __description__ + " <" + __uri__ + ">"
__author__ = "AJITOMI Daisuke"
__email__ = "ajitomi@gmail.com"
__license__ = "MIT"
__copyright__ = "Copyright 2021-2022 Ajitomi Daisuke"
__all__ = [
    "encode",
    "decode",
    "Key",
    "KeyInterface",
    "Paseto",
    "PysetoError",
    "Token",
    "DecryptError",
    "EncryptError",
    "NotSupportedError",
    "SignError",
    "VerifyError",
]
