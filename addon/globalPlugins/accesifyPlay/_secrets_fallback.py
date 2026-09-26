# Accessify Play: fallback for the standard library `secrets` module.
#
# NVDA 2025's bundled Python leaves `secrets` out, and spotipy needs it to log
# in (PKCE code verifier). The code between the markers below is an unmodified
# copy of CPython 3.13's Lib/secrets.py, so any add-on importing `secrets` gets
# exactly the real API. Its only dependencies -- base64, hmac and random -- are
# all part of NVDA's Python.
#
# Copyright (c) 2001 Python Software Foundation; All Rights Reserved.
# Licensed under the PSF License Agreement, which is GPL-compatible:
# https://docs.python.org/3/license.html
#
# ---- begin copy of CPython 3.13 Lib/secrets.py ----
"""Generate cryptographically strong pseudo-random numbers suitable for
managing secrets such as account authentication, tokens, and similar.

See PEP 506 for more information.
https://peps.python.org/pep-0506/

"""

__all__ = ['choice', 'randbelow', 'randbits', 'SystemRandom',
           'token_bytes', 'token_hex', 'token_urlsafe',
           'compare_digest',
           ]


import base64

from hmac import compare_digest
from random import SystemRandom

_sysrand = SystemRandom()

randbits = _sysrand.getrandbits
choice = _sysrand.choice

def randbelow(exclusive_upper_bound):
    """Return a random int in the range [0, n)."""
    if exclusive_upper_bound <= 0:
        raise ValueError("Upper bound must be positive.")
    return _sysrand._randbelow(exclusive_upper_bound)

DEFAULT_ENTROPY = 32  # number of bytes to return by default

def token_bytes(nbytes=None):
    """Return a random byte string containing *nbytes* bytes.

    If *nbytes* is ``None`` or not supplied, a reasonable
    default is used.

    >>> token_bytes(16)  #doctest:+SKIP
    b'\\xebr\\x17D*t\\xae\\xd4\\xe3S\\xb6\\xe2\\xebP1\\x8b'

    """
    if nbytes is None:
        nbytes = DEFAULT_ENTROPY
    return _sysrand.randbytes(nbytes)

def token_hex(nbytes=None):
    """Return a random text string, in hexadecimal.

    The string has *nbytes* random bytes, each byte converted to two
    hex digits.  If *nbytes* is ``None`` or not supplied, a reasonable
    default is used.

    >>> token_hex(16)  #doctest:+SKIP
    'f9bf78b9a18ce6d46a0cd2b0b86df9da'

    """
    return token_bytes(nbytes).hex()

def token_urlsafe(nbytes=None):
    """Return a random URL-safe text string, in Base64 encoding.

    The string has *nbytes* random bytes.  If *nbytes* is ``None``
    or not supplied, a reasonable default is used.

    >>> token_urlsafe(16)  #doctest:+SKIP
    'Drmhze6EPcv0fN_81Bj-nA'

    """
    tok = token_bytes(nbytes)
    return base64.urlsafe_b64encode(tok).rstrip(b'=').decode('ascii')

# ---- end copy of CPython 3.13 Lib/secrets.py ----


def install_if_missing():
    """Register a `secrets` module, but only if the real one is missing.

    Returns True if it was installed. When Python already has `secrets` it is
    left untouched, so this can never shadow it -- the previous
    lib/secrets.py, a two-function stub first on sys.path, could.

    The module registered is a new one named `secrets` holding exactly the
    standard API, rather than this file itself: it does not depend on how this
    file was imported, and it does not expose install_if_missing.
    """
    import sys
    import types

    try:
        import secrets  # noqa: F401
    except ImportError:
        module = types.ModuleType("secrets", globals()["__doc__"])
        for name in __all__ + ["DEFAULT_ENTROPY"]:
            setattr(module, name, globals()[name])
        module.__all__ = list(__all__)
        sys.modules["secrets"] = module
        return True
    return False
