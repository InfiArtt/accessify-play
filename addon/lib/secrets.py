# Minimal fallback replacement for Python's secrets module
# This is intended for environments where the standard 'secrets' module is not available.

import base64
import os

def token_urlsafe(nbytes=32):
    """
    Generate a URL-safe text string in Base64, containing nbytes* of randomness.
    The result will contain about 1.3 times as many characters as nbytes.
    This implementation uses os.urandom for cryptographically strong randomness
    and base64.urlsafe_b64encode for the correct URL-safe character set.
    """
    random_bytes = os.urandom(nbytes)
    # Encode using the URL-safe alphabet and remove padding characters ('=').
    return base64.urlsafe_b64encode(random_bytes).rstrip(b'=').decode('ascii')

def token_hex(nbytes=32):
    """
    Return a random text string, in hexadecimal.
    The string has nbytes * 2 hexadecimal digits.
    """
    return os.urandom(nbytes).hex()