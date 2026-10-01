# Accessify Play

Accessify Play lets you control Spotify from NVDA: playback, search, your library, playlists, podcasts, audiobooks and lyrics, on whichever Spotify Connect device is playing (this computer, your phone, a smart speaker or a console), without switching to the Spotify app.

> **Spotify Premium is required.** Spotify only lets Premium accounts control playback through its API, so most commands will not work with a free account.

## Requirements

* NVDA 2025.1 or later.
* A Spotify Premium account.
* The Spotify app (or another Spotify Connect device) open and signed in, so there is something to control.

## Getting started

1. Open the NVDA menu (`NVDA+N`), then Preferences, Settings, and choose the **Accessify Play** category.
2. Press **Validate Credentials**. Your web browser opens a Spotify page asking you to allow Accessify Play to use your account. Agree to it.
3. When you hear "Validation successful!", press OK. That's all: there is no Spotify developer app, Client ID or port to set up.

Details: [Sign-in and settings](configuration.html).

## How you use it: the command layer

Accessify Play has a single default shortcut: **`NVDA+Alt+G`**. It opens the *command layer*. Press one more key and the matching command runs. For example, `NVDA+Alt+G` then `P` plays or pauses, and `NVDA+Alt+G` then `S` opens Search. Inside the layer, `F1` lists every key and `Escape` closes the layer.

You can change the keys in the layer, and you can also give any command a shortcut of its own in NVDA's Input Gestures dialog, under "Accessify Play".

* [Command keys](keybindings.html): every key in the layer.
* [Customizing the command layer](customizing_commands.html).

## Guides

* [Search](search_guide.html): songs, albums, artists, playlists, podcasts and audiobooks; Browse Categories and Featured Playlists.
* [Library](library_management.html): your playlists, saved music, podcasts and audiobooks, followed artists, top items and recently played.
* [Lyrics](lyrics_guide.html): the lyrics window, automatic lyric reading, and lyrics for any song.
* [Queue](queue_guide.html): what plays next.
* [Play from Link](play_from_url.html): play or follow anything from a Spotify link.
* [Devices](devices_guide.html): move playback to another device.
* [More tools](misc_features.html): shuffle, repeat, seeking, volume, sharing links, the sleep timer and track announcements.

## Updates

Accessify Play is updated through NVDA's Add-on Store (NVDA menu, Tools, Add-on Store), which tells you when a new version is available. Every release is also published on [GitHub Releases](https://github.com/InfiArtt/accessify-play/releases).

## Support and license

Report problems and ideas on [GitHub](https://github.com/InfiArtt/accessify-play/issues). If you find the add-on useful, you can support its development with the **Donate** button in the Accessify Play settings.

Lyrics come from [lrclib.net](https://lrclib.net), a free, community-run lyrics database whose lyrics are in the public domain (CC0).

Accessify Play is licensed under the [GNU General Public License v2.0](https://www.gnu.org/licenses/gpl-2.0.html).
