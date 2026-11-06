# Developing Accessify Play

How the code is organised, how to check it, and the conventions it follows. Read this before changing anything.

Accessify Play is an NVDA add-on: Python that runs inside NVDA (NVDA 2025.1 and later, Python 3.11 and later; NVDA 2026 runs Python 3.13). It talks to Spotify's Web API through spotipy and shows its windows with wxPython, which NVDA provides.

## Getting started

```
pip install -r requirements.txt -r tests/requirements.txt
pip install pre-commit ruff==0.16.9
pre-commit install
```

The checks CI runs, in the same order:

```
pre-commit run --all-files            # ruff check and ruff format, plus a few file checks
python tests/run_tests.py             # the older test scripts (see "Tests" below)
python -m pytest --cov                # the test suite; fails below 90% coverage
scons && scons pot                    # build the .nvda-addon and the translation template
```

`ruff check --fix .` and `ruff format .` fix most lint findings themselves. On Windows, install the built `.nvda-addon` by opening it, or copy `addon/` into NVDA's `addons` folder for a quick try.

## Layout

Everything lives in `addon/globalPlugins/accesifyPlay/`:

* `__init__.py`: the `GlobalPlugin`. The settings spec (`confspec`), every script (command), the track poller that announces new songs and keeps the lyrics in time, and opening the windows.
* `spotify_client.py`: everything the add-on asks Spotify. `SpotifyClient` is shared (`get_client()`). Its methods return Spotify's answer, or a message string to speak when something went wrong; callers check `isinstance(result, str)`. `run_request` sends a request and turns errors into those messages; `run_on_device` adds the active device. Sign-in, the token cache, rate limits and retired endpoints are handled here.
* `command_layers.py`, `layer_config.py`, `dialogs/layer_editor.py`: the command layer (`NVDA+Alt+G`, then one key). `layer_config.py` holds the default keys and loads and saves the user's own, which the editor (`F2` in the layer) changes.
* `lyrics.py`: lyrics from lrclib.net (`lyrics_for_track`), LRC parsing, and the auto-reader that speaks each line in time.
* `ui/base_dialog.py`: `AccessifyDialog`, the base of every window. It destroys the window on close and has the shared actions: play, queue, save and follow toggles, the Add to Playlist submenu, the Go to Album/Artist items, the lyrics preview.
* `ui/paged_list.py`: `PagedList`, a list box filled a page at a time, with the Loading, Load More, empty and failed rows. Used by playlists, episodes, chapters and the artist's All Tracks.
* `dialogs/`: one module per window. `play_in_order.py` is the base of the episode and chapter windows; `categories.py` has one `PlaylistBrowserDialog` for featured and category playlists; `management.py` is the Library (`M`).
* `utils.py`, `formatting.py`, `language.py`, `paths.py`: small helpers, number formatting, translations, data file locations.
* `spotify_types.py`: `Item` (a dict from Spotify), `Reply` and `TimedLines`, for annotations only.
* `core/thread_manager.py`: background threads NVDA can stop when it exits.
* `_secrets_fallback.py`: a verbatim copy of Python's `secrets`, installed only when NVDA's Python lacks it. Not linted, not measured.

Bundled libraries are in `addon/lib` (see `addon/thirdPartyNotices.md`). User guides are in `addon/doc/en` and `addon/doc/id`, translations in `addon/locale`.

## How the code works

* **Never block NVDA.** Anything that talks to Spotify or lrclib runs in the background through `thread_manager.submit_task(...)`, and comes back to the window with `wx.CallAfter(...)`. A window may have closed meanwhile, so callbacks start with `if not self: return`.
* **Say what happened.** Results are spoken with `ui.message`. When a client method returns a string, speak it; that is the reason it failed.
* **Windows put their data where the user looks.** A list that failed to load, or is empty, says so in its first row, so the screen reader finds it there.
* **Every list and field is named** by a `wx.StaticText` created right before it, which NVDA reads as its label.
* **Settings** live in `config.conf["spotify"]` (spec in `__init__.py`); read them with `conf_get(key, default)`. The page size of every paged list is the `searchLimit` setting.
* **Shortcuts.** The command layer is configurable (`layer_config.py`). Inside windows, shortcuts are accelerator tables written in each dialog: `Alt+P` play, `Alt+Q` queue, `Alt+L` copy link, `Alt+R` refresh, plus a few per window (`Alt+F`, `Alt+D`, `Alt+W` in Search; `Alt+S` for episodes; `Ctrl+1` to `Ctrl+6` and `Ctrl+Tab` for types or tabs in Search and the artist window). They are not configurable yet.

## Conventions

* **Tabs** for indentation, lines up to 110 characters, double quotes. `ruff format` takes care of it.
* **Every ruff rule is on** (`select = ["ALL"]` in `pyproject.toml`). The few exceptions are listed there with the reason for each; NVDA's own names (`script_*`, `event_*`, `makeSettings`, ...) are allowed. Fix a finding rather than silencing it; a `# noqa` needs a reason after it.
* **Every module starts** with the licence header and `from __future__ import annotations` (ruff adds the import).
* **Annotations and docstrings** on everything public. Docstrings say what a thing is for, in plain words.
* **Translations.** User-facing text goes through `_()`, with a `# Translators:` comment where the meaning isn't obvious. Never put `_()` inside an f-string: use `_("... {name}").format(name=...)`. Changing an English text drops its Indonesian translation until it is translated again, so change texts only on purpose.
* **Keep it small.** Shared behaviour goes in `ui/` or `utils.py` instead of being copied into a second window. Prefer deleting code to adding options nobody asked for.
* **Changelog.** Every user-visible change gets a line in `CHANGELOG.md`, under a `## Unreleased` heading until it is released, in the existing style. Bug fixes are listed separately and say what went wrong, so users recognise them.
* **Docs.** When a feature changes, update its page in `addon/doc/en` and the same page in `addon/doc/id`. Both languages must have the same pages, and `keybindings.md` must list exactly the command layer's keys (a test checks both).

## Tests

`tests/unit` is the test suite, run with pytest. It needs neither NVDA nor Windows nor a network:

* `tests/fakes/` stands in for NVDA's modules (`ui`, `config`, `api`, `gui`, `logHandler`, `scriptHandler`, `tones`, ...) and for wxPython. The fake widgets keep their state (items, selection, value, focus, enabled, shown) so a test can look at a window the way a user would. `wx.CallAfter` and `wx.CallLater` run at once.
* `tests/unit/conftest.py` puts the fakes first on `sys.path` and resets them before every test. Background tasks run at once (the `nvda` fixture). Useful fixtures and helpers:
  * `spoken`: everything the add-on said, in order.
  * `server` and `client`: a real `SpotifyClient` and spotipy, whose HTTP calls go to `SpotifyServer` instead of Spotify. Set `server.routes["GET", "me/playlists"] = {...}` (an answer, an exception from `spotify_error(status)`, or a function of params and payload); `server.requests` records what was asked.
  * `choose(window, menu, label)` picks a context menu item; `last_menu()` is the menu that popped up; `accelerate(window, wx.ACCEL_ALT, "P")` presses a shortcut; `record_windows(monkeypatch, module, "AlbumTracksDialog", ...)` replaces windows a dialog opens with recorders.
  * Fake widgets have test-only helpers: `button.press()`, `control.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))`, `listbox.select(row, wx.EVT_LISTBOX)`, `listctrl.activate(row)`.
* Test behaviour through the window, as a user would: press keys and buttons, open menus, and check what is spoken, shown and sent to Spotify. Coverage must stay at 90% or more (`fail_under` in `pyproject.toml`); it is about 98%.
* `tests/test_*.py` are older standalone scripts, run by `tests/run_tests.py`. They stay until their checks are in `tests/unit`; many already are. Some check the project rather than the code (the Indonesian catalog, the user guides, import order, a build without site-packages) and are worth porting as they are. When one is fully covered, delete it.

## Releases

The version is `addon_version` in `buildVars.py`. This fork numbers releases by date (`2026.11.0`: year, month, number), so they never collide with the original add-on's 1.x versions. To release:

1. Set the new version in `buildVars.py`, and the short store changelog (`addon_changelog`) next to it.
2. Rename `## Unreleased` in `CHANGELOG.md` to `## Version <version>`.
3. Push to `main`. CI builds the add-on and, for a version that has no release yet, publishes a GitHub release with that changelog section as its notes. A push without a new version builds but publishes nothing.

## Ideas and known gaps

* The shortcuts inside windows are hard-coded per dialog and repeated across them; the command layer shows how a configurable version could work.
* The two browse windows in `categories.py` load more as you reach the end of the list rather than with a Load More row, and share their loading code only partly; `PagedList` could serve them too.
* The lyrics window creates its timestamp buttons only if the first song shown has synced lyrics.
* The artist's All Tracks names the artist on every line, while Top Tracks names them only when someone else is on the song.
