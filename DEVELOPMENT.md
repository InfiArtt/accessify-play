# Developing Accessify Play

How the code is organised, how to check it, and the conventions it follows. Read this before changing anything.

Accessify Play is an NVDA add-on: Python that runs inside NVDA (NVDA 2025.1 and later, Python 3.11 and later; NVDA 2026 runs Python 3.13). It talks to Spotify's Web API through spotipy and shows its windows with wxPython, which NVDA provides.

## Getting started

```
pip install -r requirements.txt -r tests/requirements.txt
pip install pre-commit ruff==0.16.9 pyright==1.1.414
pre-commit install
```

The checks CI runs, in the same order:

```
pre-commit run --all-files            # ruff check and ruff format, plus a few file checks
pyright                               # type checking of the add-on's code
python -m pytest --cov                # the test suite; fails below 99% coverage
scons && scons pot                    # build the .nvda-addon and the translation template
```

`ruff check --fix .` and `ruff format .` fix most lint findings themselves. On Windows, install the built `.nvda-addon` by opening it, or copy `addon/` into NVDA's `addons` folder for a quick try.

## Layout

Everything lives in `addon/globalPlugins/accesifyPlay/`:

* `__init__.py`: the `GlobalPlugin`. It registers the settings spec, and has every script (command), the track poller that announces new songs and keeps the lyrics in time, and opening the windows.
* `settings_spec.py`: every setting in one table (`SETTINGS`): its default, its range or choices, and whether it is hidden. The config spec NVDA validates against (`CONFSPEC`), the defaults `conf_get` falls back on, and the ranges and labels of the settings panel are all made from it. It translates nothing, so `__init__` can import it before registering the spec.
* `commands.py`: every command of the command layer in one table (`COMMANDS`): default key, whether the layer stays open, its name in the layer editor and its description, which is also the script's description in Input Gestures.
* `rows.py`: how each kind of item reads as a row ("Song - Artist (3:21)", "Album - Artist (2020)", ...), the same in every list; `item_row` picks by the item's type.
* `labels.py`: what the choices of a setting (periods, search types) and the window shortcuts are called on screen, shared by the settings panel and the windows.
* `shortcuts.py`: the shortcuts inside the windows. It reads their keys from the shortcut settings (`keyPlay`, ...), written like NVDA's gestures, checks them, and gives them to windows and menus. `dialogs/window_shortcuts.py` changes them, from the settings panel.
* `spotify_client.py`: everything the add-on asks Spotify. Spotify's own limits (page sizes, batch sizes) are named at its top; they are facts of the Web API, not settings. `SpotifyClient` is shared (`get_client()`). Its methods return Spotify's answer, or a message string to speak when something went wrong; callers check `isinstance(result, str)`. `run_request` sends a request and turns errors into those messages; `run_on_device` adds the active device. Sign-in, the token cache, rate limits and retired endpoints are handled here.
* `command_layers.py`, `layer_config.py`, `dialogs/layer_editor.py`: the command layer (`NVDA+Alt+G`, then one key). `layer_config.py` loads and saves the user's own keys (`layerConfig.json` keeps only keys and "keep open"; everything else comes from `commands.py`), which the editor (`F2` in the layer) changes. New keys work as soon as the editor closes.
* `lyrics.py`: lyrics from lrclib.net (`lyrics_for_track`), LRC parsing, and the auto-reader that speaks each line in time.
* `ui/base_dialog.py`: `AccessifyDialog`, the base of every window. It destroys the window on close and has the shared actions: play (saying why when Spotify refuses), queue (`_queue_item`), save and follow toggles, opening an item in its window (`_open`), what Enter does (`_activate`), the context menu of any item (`_show_item_menu`), the user's own playlists for Add to Playlist, the lyrics preview, the tab keys of windows with tabs, and the window's shortcuts (`_bind_shortcuts`).
* `ui/paged_list.py`: `PagedList`, a list box filled a page at a time, with the Loading, Load More, empty and failed rows. A reload drops a page still on its way; Load More moves to the first new row. Used by every long list: Search, the Library's tabs, playlists, episodes, chapters, the artist's All Tracks, and Browse Categories and Featured Playlists. A list Spotify does not page by offset (followed artists, recently played, top items) is handed over as one page.
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
* **Settings** live in `config.conf["spotify"]`, described by the table in `settings_spec.py`; read them with `conf_get(key)`, which never raises and falls back on the table's default. A value that could reasonably differ between users or setups (an interval, a timeout, a limit, a default choice) belongs in that table rather than in the code: in the settings panel when users will want to change it, otherwise as a hidden setting (`hidden=True`), changeable in `nvda.ini` and listed in `configuration.md`. Read settings when they are needed, not once at import. The page size of every paged list is the `searchLimit` setting.
* **Shortcuts.** The command layer is configurable (`layer_config.py`). Inside windows, every shortcut is a setting of its own (the `shortcut` field in `settings_spec.py`): a window calls `self._bind_shortcuts({"keyPlay": handler, ...}, buttons={"keyPlay": [self.play_button]})`, where `buttons` names the buttons that do the same as a shortcut (any other button whose letter a shortcut has loses the letter; change a label later with `_set_button_label`), and its menu items share the action's id through `self._append_action(menu, label, "keyPlay")`, which shows the keys. Keys that only work in one list (moving tracks in the Library) are checked with `shortcuts.matches(setting, event)`. A new shortcut needs a row in the table, a name in `labels.shortcut_labels()`, and a line in `customizing_commands.md` (a test checks both languages). The underlined letters of buttons stay in the translations.
* **Lists behave the same in every window.** Rows come from `rows.py`. Enter calls `self._activate(item, play)`: it opens what holds other items and an artist, and plays the rest. The context menu is `self._show_item_menu(item)`, which offers only what works for the item, in a fixed order; a window adds `remove=` (the Library's tabs, in place of Save/Unsave), `extras=` (its own entries, last) or `here=` (the artists the window is about). These go by the item's `type`, so a list whose items Spotify sends without one gives them theirs (see `_typed` in `management.py`).
* **Playing** from a window goes through `_play_uri`, `_play_in_context` or `_play_item` (a song from a list that is not its album, played within its album), which speak Spotify's reason when it refuses; don't submit `play_item` directly.

## Conventions

* **Tabs** for indentation, lines up to 110 characters, double quotes. `ruff format` takes care of it.
* **pyright** checks the types of the add-on's code (`[tool.pyright]` in `pyproject.toml`). NVDA's modules and wx come from the fakes in `tests/fakes`, so a fake's signature should match the real one; `__builtins__.pyi` declares the `_` NVDA installs. Spotify's answers are `Item` (`dict[str, Any]`), so `.get()` gives `Any | None`: pass it on to parameters that accept `None`, or index (`item["id"]`) where the value is certain.
* **Every ruff rule is on** (`select = ["ALL"]` in `pyproject.toml`). The few exceptions are listed there with the reason for each; NVDA's own names (`script_*`, `event_*`, `makeSettings`, ...) are allowed. Fix a finding rather than silencing it; a `# noqa` needs a reason after it.
* **Every module starts** with the licence header and `from __future__ import annotations` (ruff adds the import).
* **Annotations and docstrings** on everything public. Docstrings say what a thing is for, in plain words.
* **Translations.** User-facing text goes through `_()`, with a `# Translators:` comment where the meaning isn't obvious. Never put `_()` inside an f-string: use `_("... {name}").format(name=...)`. Changing an English text drops its Indonesian translation until it is translated again, so change texts only on purpose.
* **Keep it small.** Shared behaviour goes in `ui/` or `utils.py` instead of being copied into a second window. Prefer deleting code to adding options nobody asked for.
* **Changelog.** Every user-visible change gets a line in `CHANGELOG.md`, under a `## Unreleased` heading until it is released, in the existing style. Bug fixes are listed separately and say what went wrong, so users recognise them.
* **Docs.** When a feature changes, update its page in `addon/doc/en` and the same page in `addon/doc/id`. Both languages must have the same pages, and `keybindings.md` must list exactly the command layer's keys (a test checks both).

## Tests

`tests/unit` is the test suite, run with pytest. It needs neither NVDA nor Windows nor a network:

* `tests/fakes/` stands in for NVDA's modules (`ui`, `config`, `api`, `gui`, `logHandler`, `scriptHandler`, `tones`, ...) and for wxPython. The fake widgets keep their state (items, selection, value, focus, enabled, shown) so a test can look at a window the way a user would; destroying a window destroys its children, as in wx. `wx.CallAfter` and `wx.CallLater` run at once.
* `tests/unit/conftest.py` puts the fakes first on `sys.path` and resets them before every test. Background tasks run at once (the `nvda` fixture). Useful fixtures and helpers:
  * `spoken`: everything the add-on said, in order.
  * `server` and `client`: a real `SpotifyClient` and spotipy, whose HTTP calls go to `SpotifyServer` instead of Spotify. Set `server.routes["GET", "me/playlists"] = {...}` (an answer, an exception from `spotify_error(status)`, or a function of params and payload); `server.requests` records what was asked.
  * `choose(window, menu, label)` picks a context menu item; `last_menu()` is the menu that popped up; `accelerate(window, wx.ACCEL_ALT, "P")` presses a shortcut; `record_windows(monkeypatch, module, "AlbumTracksDialog", ...)` replaces windows a dialog opens with recorders.
  * Fake widgets have test-only helpers: `button.press()`, `control.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))`, `combobox.select(row, wx.EVT_COMBOBOX)`, `listctrl.activate(row)`.
* Test behaviour through the window, as a user would: press keys and buttons, open menus, and check what is spoken, shown and sent to Spotify. Coverage must stay at 99% or more (`fail_under` in `pyproject.toml`); every line and branch is covered now. `# pragma: no cover` needs a reason after it, like `# noqa`.
* Some tests check the project rather than the code. `test_project.py`: the Indonesian and English catalogues against the code's strings, the user guides (pages, links, the key tables against `commands.py`), the import order, that every setting in `settings_spec.py` is used, and the bundled libraries' notices. `test_settings_spec.py`: the config spec, the settings panel and `configuration.md` against the table of settings. `test_isolated.py` runs the scripts in `tests/isolated` with `python -I -S`, so the bundled libraries and the secrets fallback are tried with the standard library alone, as inside NVDA.
* Changing or adding a user-facing text means updating `addon/locale/id/LC_MESSAGES/nvda.po` (translated) and `addon/locale/en/LC_MESSAGES/nvda.po` (untranslated) in the same change; `test_project.py` fails until both match the code.

## Releases

The version is `addon_version` in `buildVars.py`. This fork numbers releases by date (`2026.11.0`: year, month, number), so they never collide with the original add-on's 1.x versions. To release:

1. Set the new version in `buildVars.py`, and the short store changelog (`addon_changelog`) next to it.
2. Rename `## Unreleased` in `CHANGELOG.md` to `## Version <version>`.
3. Push to `main`. CI builds the add-on and, for a version that has no release yet, publishes a GitHub release with that changelog section as its notes. A push without a new version builds but publishes nothing. If the push started no workflow (some tokens don't), run "Build & Release Addon" by hand on `main` from the Actions tab; it releases the same way.

## Ideas and known gaps

* The Library's playlist tracks and the artist's albums still load whole: moving and removing tracks works by position in the whole playlist, and All Tracks walks the albums.
