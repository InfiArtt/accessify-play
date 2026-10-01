# Accessify Play
[![Build & Release Addon](https://github.com/InfiArtt/accessify-play/actions/workflows/build_addon.yml/badge.svg)](https://github.com/InfiArtt/accessify-play/actions/workflows/build_addon.yml)
[![Latest Release](https://img.shields.io/github/v/release/InfiArtt/accessify-play)](https://github.com/InfiArtt/accessify-play/releases/latest)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://www.gnu.org/licenses/gpl-2.0.html)

<p align="center"><strong>Your Spotify Universe, Commanded by NVDA.</strong></p>

---

Go beyond simple playback. Accessify Play transforms NVDA into a powerful command center for your entire Spotify experience. Control what's playing on *any* of your devices—your PC, phone, smart speaker, or console—directly from your keyboard, without ever touching the Spotify app.

With effortless, zero-configuration setup, you'll be jamming to your favorite tracks, exploring deep cuts, and discovering Spotify's official moods in seconds. No API keys, no developer dashboards, no hassle. Why wouldn't you want Accessify Play running your daily soundtrack?

> **⚠️ Important: Spotify Premium Required!**
>
> Due to Spotify API limitations, this addon requires an active **Spotify Premium** subscription for playback control features. Free accounts have restricted API access and will not work correctly with this addon.

## Prerequisites

*   An active **Spotify Premium** subscription.
*   NVDA version **2025.1** or later.

## Installation

Install Accessify Play from NVDA's **Add-on Store** (NVDA menu → Tools → Add-on Store), or download the `.nvda-addon` file from [GitHub Releases](https://github.com/InfiArtt/accessify-play/releases/latest) and open it.

## 🚀 First Setup (One-Click Login)

Accessify Play connects through a Spotify client with an extended quota, so you don't need to create your own Spotify Developer app or deal with Client IDs.

1. Open the NVDA menu (`NVDA+N`), go to **Preferences**, then **Settings**.
2. In the categories list, select **Accessify Play**.
3. Press the **"Validate Credentials"** button.
4. Your web browser will open and ask you to grant Spotify permissions to the add-on. Click "Agree".
5. If successful, you will see a "Validation successful!" message.
6. Click "OK" to save and close the settings. The addon is now ready to use!

## 🚀 Feature Universe

### Playback & Information

*   **Universal Control:** Play, pause, skip, seek, shuffle, repeat and adjust volume on any Spotify Connect device, and move playback between devices.
*   **Instant Info:** Announce the current track, the playback time, or what's next in the queue, and open the full queue.
*   **Automatic Announcements:** Optionally, have NVDA announce each new song as it starts.
*   **Share with Ease:** Copy the Spotify link of the current track, or a Song.link link that opens in any music service.
*   **Play from Link:** Play anything from a Spotify link: tracks, albums, artists, playlists, podcasts, episodes, audiobooks and chapters. Profile links let you follow the person.
*   **Sleep Timer:** Pause the music after a set time, even across NVDA restarts.

### 🎤 Lyrics

Powered by [lrclib.net](https://lrclib.net), a free, community-driven lyrics database whose lyrics are released under **Creative Commons Zero (CC0)**, so they are in the public domain.

*   **Lyrics Window:** Read the current song's lyrics line by line, jump the song to any line, and copy them.
*   **Auto Lyric Reading:** NVDA speaks each line as it is sung, in time with the music.
*   **Lyrics for any song:** Read the lyrics of any song in a list without playing it.

### Library Management

*   **Playlists:** Create, edit, delete or unfollow playlists; reorder tracks, remove a single copy of a track, remove duplicates, or clear a playlist.
*   **Everything you save:** Liked Songs, albums, podcasts, individual episodes and audiobooks, each in its own Library tab, with one command to save or unsave.
*   **Follow:** Artists, playlists, and the people who make the playlists you like.
*   **Your stats:** Top tracks and artists from the last 4 weeks, 6 months or all time, and recently played.

### Discovery

*   **Advanced Search:** Find songs, albums, artists, playlists, podcasts and audiobooks.
*   **Browse Categories & Featured Playlists:** Explore Spotify's moods and genres (Sleep, Focus, Workout, Pop, and more).
*   **Deep Dives:** Explore an artist's info, top tracks, every track and full discography.

## 🎛️ Keyboard Command Center

Accessify Play has one default shortcut, **`NVDA+Alt+G`**, which opens the command layer. Press one more key to run a command, for example `NVDA+Alt+G` then `P` to play or pause. `F1` in the layer lists every key, and `Escape` closes it.

Every key can be changed in the layer's editor (`F2`), and every command can also be given its own shortcut in NVDA's **Input Gestures** dialog, under "Accessify Play".

| Key | Action | Key | Action |
| :-- | :----- | :-- | :----- |
| `P` | Play / Pause | `I` | Announce current track |
| `N` | Next track | `T` | Announce playback time |
| `B` | Previous track | `E` | Announce next in queue |
| `=` / `-` | Volume up / down | `Q` | Open the queue |
| `V` | Set volume | `L` | Like / unlike track |
| `]` / `[` | Seek forward / backward | `F` | Follow / unfollow artist |
| `J` | Seek to a time | `A` | Add track to a playlist |
| `H` | Shuffle on / off | `M` | Open the Library |
| `R` | Cycle repeat | `S` | Search |
| `G` | Play my top tracks | `U` | Play from link |
| `O` | Play recently played | `C` | Copy track link |
| `D` | Choose device | `X` | Copy Song.link link |
| `W` | Lyrics window | `Z` | Sleep timer |
| `Y` | Auto lyric reading | `F4` | Settings |
| `F1` | List all keys | `F2` | Edit the keys |

The full user guide is included with the add-on: select Accessify Play in NVDA's Add-on Store or Add-ons Manager and choose **Help**. You can also read it in [addon/doc/en](addon/doc/en/readme.md).

---

## 🔄 Updates

Accessify Play is updated through NVDA's Add-on Store (NVDA menu → Tools → Add-on Store), which tells you when a new version is available. Every release is also published on [GitHub Releases](https://github.com/InfiArtt/accessify-play/releases) if you prefer to install it yourself.

Versions before 1.12.0 had their own built-in update checker. It was removed in 1.12.0, now that the Add-on Store takes care of updates.

---

## 🙏 Acknowledgements

This project wouldn't be where it is today without the incredible support and dedication of our community. A heartfelt thank you to all the testers who provided invaluable ideas, helped tirelessly with debugging, and offered supportive encouragement throughout the development process.

A special shoutout to the open-source [ncspot](https://github.com/hrkfdn/ncspot) project! Their client integration is what allows this accessibility add-on to completely bypass API quotas and provide a seamless, zero-configuration login experience for our users.

Your contributions have been instrumental in shaping Accessify Play into what it is. Thank you for making this project a success!

---

## 📄 License

This addon is licensed under the [GNU General Public License v2.0](https://www.gnu.org/licenses/gpl-2.0.html).

## 💖 Support the Developer

If you find this addon useful, please consider supporting its development. Every little bit helps!

* [**Donate via PayPal**](https://www.paypal.com/paypalme/rafli23115)
* For alternative donation methods, please contact: [rafli08523717409@gmail.com](mailto:rafli08523717409@gmail.com)
