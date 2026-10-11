# Third-party components

Accessify Play is licensed under the GNU General Public License, version 2 or later. It bundles the third-party code listed below, all under licenses compatible with that. The libraries are in `addon/lib/`, and each library's full license text is included in its `addon/lib/<name>.dist-info/licenses/` folder.

## Bundled libraries

| Component | Version | License | Source | Changes |
| :-- | :-- | :-- | :-- | :-- |
| spotipy | 2.26.0 | MIT | https://github.com/spotipy-dev/spotipy | One change, described below |
| requests | 2.34.2 | Apache-2.0 | https://github.com/psf/requests | None (its NOTICE file is included) |
| urllib3 | 2.7.0 | MIT | https://github.com/urllib3/urllib3 | None |
| idna | 3.15 | BSD-3-Clause | https://github.com/kjd/idna | None |
| charset-normalizer | 3.4.7 | MIT | https://github.com/jawah/charset_normalizer | None (the pure-Python release) |
| certifi | 2026.4.22 | MPL-2.0 | https://github.com/certifi/python-certifi | None |

spotipy is the Spotify Web API client; the others are its dependencies. Except for the change below, every file is identical to the corresponding release on PyPI.

### Change to spotipy

`addon/lib/spotipy/cache_handler.py` imports `RedisError` from the `redis` package unconditionally. Accessify Play only uses spotipy's `CacheFileHandler` and does not bundle redis, so the import is wrapped in `try`/`except ImportError` with a stand-in exception class. A comment in the file marks the change.

## Code copied from Python

| Component | License | Where |
| :-- | :-- | :-- |
| `secrets` module from CPython 3.13 (`Lib/secrets.py`) | Python Software Foundation License | `addon/globalPlugins/accesifyPlay/_secrets_fallback.py` |

NVDA 2025's Python does not include the standard `secrets` module, which spotipy needs to sign in. The file contains an unmodified copy of it, between marked lines, with its copyright notice, and is used only when NVDA does not provide the module itself.

## Online services

These services are used over the internet; none of their code is included.

- **Spotify Web API**, through spotipy, to control playback and the user's library.
- **lrclib.net**, a free, community-run lyrics database whose lyrics are released into the public domain (CC0), for lyrics.
- **song.link**, only to build the universal links that the Copy Universal Link command copies.
