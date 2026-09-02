# Accessify Play
[![Code Quality Linting](https://github.com/InfiArtt/accessify-play/actions/workflows/lint.yml/badge.svg)](https://github.com/InfiArtt/accessify-play/actions/workflows/lint.yml)
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
*   NVDA version **2024.4** or later.

## 🎤 Lyrics Support

Accessify Play now includes **lyrics support** powered by [lrclib.net](https://lrclib.net) — a free, open, and community-driven lyrics database. All lyrics served by lrclib.net are released under the **Creative Commons Zero (CC0)** license, meaning they are in the public domain and can be used freely without any copyright concern. This is the key distinction that makes this feature legal, distributable, and fully compliant — unlike scraping from unlicensed sources.

Two lyrics modes are available inside the **Command Layer** (`NVDA+Alt+g`):

- **`W` — Lyrics Window**: Opens a popup showing the full, plain-text lyrics for the current song. Navigate line by line with arrow keys — NVDA reads each line as you go.
- **`Y` — Auto Lyric Reading**: NVDA automatically speaks each lyric line in real time, perfectly synchronized with the music as it plays. Press `Y` again to stop.

## License

This addon is licensed under the [GNU General Public License v2.0](https://www.gnu.org/licenses/gpl-2.0.html).

## 🚀 Feature Universe

Accessify Play is packed with features, organized for your convenience:

### Playback & Information

*   **Universal Control:** Play, pause, skip, seek, and adjust volume on any active Spotify Connect device.
*   **Set Specific Volume:** Set the volume to a precise percentage (0-100) via a dialog.
*   **Instant Info:** Announce the currently playing track, artist, and album at any time.
*   **Queue Insights:** Announce the next track in your queue or open a full, interactive list of what's coming up.
*   **Automatic Announcements:** Optionally, have NVDA announce the new song automatically every time the track changes.
*   **Share with Ease:** Copy the Spotify URL of the current track to your clipboard.
*   **Play from Link:** Open a dialog to play any track directly from a Spotify URL.
*   **Lyrics Window (`W`):** Open a popup showing the full plain-text lyrics for the current track, navigable line by line with arrow keys.
*   **Auto Lyric Reading (`Y`):** Toggle NVDA automatically speaking each lyric line in real time, synchronized to the music.

### Library Management & Interaction

*   **Quick Save:** Instantly save the current track to your "Liked Songs" with a single command.
*   **Add to Playlist:** Quickly add the current track to any of your playlists.
*   **Full Management Suite:** Open a powerful multi-tabbed dialog to manage every aspect of your library:
    *   **Playlists:** Create new playlists, update details, delete them, and manage the tracks within.
    *   **Saved Library:** View and remove tracks from your "Liked Songs".
    *   **Followed Artists:** See all the artists you follow, with options to unfollow or explore their music.

### Discovery

*   **Advanced Search:** A powerful search dialog to find songs, albums, artists, playlists, and podcasts.
*   **Browse Categories:** Explore Spotify's official moods and genres (Sleep, Focus, Workout, Pop, etc.) right from the Search dialog.
*   **Your Top Hits:** See your personal top-played tracks and artists from the last month, 6 months, or all time.
*   **New Releases:** Browse the latest album and single releases curated for you by Spotify.
*   **Deep Dives:** From an artist search result, dive into their full discography, or discover related artists.
*   **Podcast Explorer:** View and play any episode from a podcast you've found.

## 🎛️ Keyboard Command Center

| Command                      | Shortcut                             |
| :--------------------------- | :----------------------------------- |
| Play/Pause                   | `NVDA+Shift+Alt+Space`               |
| Next Track                   | `NVDA+Shift+Alt+RightArrow`          |
| Previous Track               | `NVDA+Shift+Alt+LeftArrow`           |
| Volume Up                    | `NVDA+Shift+Alt+UpArrow`             |
| Volume Down                  | `NVDA+Shift+Alt+DownArrow`           |
| Set Specific Volume          | `NVDA+Shift+Alt+V`                   |
| Seek Forward (configurable)  | `Control+Alt+NVDA+RightArrow`        |
| Seek Backward (configurable) | `Control+Alt+NVDA+LeftArrow`         |
| Announce Current Track       | `NVDA+Shift+Alt+I`                   |
| Announce Playback Time       | `NVDA+Alt+Shift+T`                   |
| Copy Track URL               | `NVDA+Shift+Alt+C`                   |
| Open Search Dialog           | `NVDA+Shift+Alt+S`                   |
| Play from Link Dialog        | `NVDA+Shift+Alt+P`                   |
| Open Queue List              | `NVDA+Shift+Alt+Q`                   |
| Announce Next in Queue       | `NVDA+Shift+Alt+N`                   |
| Save Track to Library        | `NVDA+Alt+Shift+L`                   |
| Add Track to Playlist        | `NVDA+Alt+Shift+A`                   |
| Open Management Dialog       | `NVDA+Alt+Shift+M`                   |

### Command Layer (`NVDA+Alt+g`) Quick Reference

> Press `NVDA+Alt+g` first to enter the command layer, then press the single key listed below.

| Key | Action |
| :-- | :----- |
| `P` | Play / Pause |
| `N` | Next Track |
| `B` | Previous Track |
| `G` | Play My Top Tracks |
| `O` | Play Recently Played |
| `S` | Search |
| `V` | Set Volume |
| `I` | Announce current track |
| `T` | Announce Playback Time |
| `C` | Copy Track URL |
| `U` | Play from Link |
| `Q` | Open Queue List |
| `X` | Announce Next in Queue |
| `L` | Save Track to Library |
| `A` | Add Track to Playlist |
| `M` | Open Management Dialog |
| `D` | Select Device |
| `W` | Toggle Lyrics Window |
| `Y` | Toggle Auto Lyric Reading |
| `R` | Repeat Toggle |
| `H` | Shuffle Toggle |

---

## 🚀 First Setup (One-Click Login)

Thanks to a massive backend update in version 1.9.0, Accessify Play now completely bypasses the restrictive Spotify Developer API limits. You no longer need to create your own Spotify Developer app or mess with Client IDs!

1. Open the NVDA menu (`NVDA+N`), go to **Preferences**, then **Settings**.
2. In the categories list, select **Accessify Play**.
3. Press the **"Validate Credentials"** button. 
4. Your web browser will open and ask you to grant Spotify permissions to the add-on. Click "Agree".
5. If successful, you will see a "Validation successful!" message.
6. Click "OK" to save and close the settings. The addon is now ready to use!

---

## 🔄 Update System

Accessify Play includes a built-in update system to keep your add-on up-to-date with the latest features and bug fixes. Updates are sourced directly from [GitHub Releases](https://github.com/InfiArtt/accessify-play/releases).

### Automatic Updates

If "Check for updates automatically" is enabled in the settings, Accessify Play will perform a silent check for new versions every time NVDA starts. If an update is available for your selected channel (Stable or Beta), a pop-up window will appear, showing the new version and its changelog. You can then choose to download and install the update or postpone it.

If no update is available, or if an error occurs during the background check (e.g., no internet connection), the add-on will remain silent and not display any messages.

### Manual Updates

You can manually check for updates at any time by navigating to the Accessify Play settings panel (NVDA menu -> Preferences -> Settings -> Accessify Play) and clicking the **"Check for Updates"** button. The process is similar to automatic updates: if a new version is found, a pop-up will appear; otherwise, a message will confirm that you are running the latest version.

### Update Channels

You can choose between two update channels in the settings:

*   **Stable:** This is the recommended channel for most users. You will receive only stable, thoroughly tested releases. These updates correspond to releases published from the add-on's `main` branch on GitHub.
*   **Beta:** This channel provides access to pre-release versions, offering the latest features and bug fixes before they are officially released. Beta versions correspond to releases from the `dev` branch on GitHub. While they offer early access, they might be less stable than official releases.

---

## 🙏 Acknowledgements

This project wouldn't be where it is today without the incredible support and dedication of our community. A heartfelt thank you to all the testers who provided invaluable ideas, helped tirelessly with debugging, and offered supportive encouragement throughout the development process. 

A special shoutout to the open-source [ncspot](https://github.com/hrkfdn/ncspot) project! Their client integration is what allows this accessibility add-on to completely bypass API quotas and provide a seamless, zero-configuration login experience for our users.

Your contributions have been instrumental in shaping Accessify Play into what it is. Thank you for making this project a success!

---

## 💖 Support the Developer

If you find this addon useful, please consider supporting its development. Every little bit helps!

* [**Donate via PayPal**](https://www.paypal.com/paypalme/rafli23115)
* For alternative donation methods, please contact: [rafli08523717409@gmail.com](mailto:rafli08523717409@gmail.com)