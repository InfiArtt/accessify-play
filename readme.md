# Accessify Play

<p align="center"><strong>Your Spotify Universe, Commanded by NVDA.</strong></p>

---

Go beyond simple playback. Accessify Play transforms NVDA into a powerful command center for your entire Spotify experience. Control what's playing on *any* of your devices—your PC, phone, smart speaker, or console—directly from your keyboard, without ever touching the Spotify app.

Search, discover, manage playlists, and control your music with unparalleled freedom. This is how Spotify was meant to be experienced with a screen reader.

> **⚠️ Important: Spotify Premium Required!**
>
> Due to Spotify API limitations, this addon requires an active **Spotify Premium** subscription for playback control features. Free accounts have restricted API access and will not work correctly with this addon.

## Prerequisites

*   An active **Spotify Premium** subscription.
*   NVDA version **2024.4** or later.

## A Note on Lyrics

This addon does not, and will not, include a feature to display song lyrics. Most methods for obtaining lyrics, such as scraping websites, are done without a proper license from the copyright holders. This is an illegal practice that violates the terms of service of lyrics providers and may infringe on copyright law, potentially leading to legal consequences under regulations like the DMCA (Digital Millennium Copyright Act) in the United States and similar laws worldwide. To ensure this addon remains legal, distributable, and respectful of copyright, this feature is intentionally omitted.

## License

This addon is licensed under the [GNU General Public License v2.0](https://www.gnu.org/licenses/gpl-2.0.html).

## ✨ Feature Universe

Accessify Play is packed with features, organized for your convenience:

### Playback & Information

*   **Universal Control:** Play, pause, skip, seek, and adjust volume on any active Spotify Connect device.
*   **Set Specific Volume:** Set the volume to a precise percentage (0-100) via a dialog.
*   **Instant Info:** Announce the currently playing track, artist, and album at any time.
*   **Queue Insights:** Announce the next track in your queue or open a full, interactive list of what's coming up.
*   **Automatic Announcements:** Optionally, have NVDA announce the new song automatically every time the track changes.
*   **Share with Ease:** Copy the Spotify URL of the current track to your clipboard.
*   **Play from Link:** Open a dialog to play any track directly from a Spotify URL.

### Library Management & Interaction

*   **Quick Save:** Instantly save the current track to your "Liked Songs" with a single command.
*   **Add to Playlist:** Quickly add the current track to any of your playlists.
*   **Full Management Suite:** Open a powerful multi-tabbed dialog to manage every aspect of your library:
    *   **Playlists:** Create new playlists, update details, delete them, and manage the tracks within.
    *   **Saved Library:** View and remove tracks from your "Liked Songs".
    *   **Followed Artists:** See all the artists you follow, with options to unfollow or explore their music.

### Discovery

*   **Advanced Search:** A powerful search dialog to find songs, albums, artists, playlists, and podcasts.
*   **Your Top Hits:** See your personal top-played tracks and artists from the last month, 6 months, or all time.
*   **New Releases:** Browse the latest album and single releases curated for you by Spotify.
*   **Deep Dives:** From an artist search result, dive into their full discography, or discover related artists.
*   **Podcast Explorer:** View and play any episode from a podcast you've found.

## ⌨️ Keyboard Command Center

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
| Copy Track URL               | `NVDA+Shift+Alt+C`                   |
| Open Search Dialog           | `NVDA+Shift+Alt+S`                   |
| Play from Link Dialog        | `NVDA+Shift+Alt+P`                   |
| Open Queue List              | `NVDA+Shift+Alt+Q`                   |
| Announce Next in Queue       | `NVDA+Shift+Alt+N`                   |
| Save Track to Library        | `NVDA+Alt+Shift+L`                   |
| Add Track to Playlist        | `NVDA+Alt+Shift+A`                   |
| Open Management Dialog       | `NVDA+Alt+Shift+M`                   |

---

## ⚙️ Configuration Guide

To use this addon, you need to get a **Client ID** and **Client Secret** from the Spotify Developer Dashboard. Follow these steps carefully.

### Step 1: Create a Spotify App

1.  Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2.  Click the "Create app" button.
3.  Fill out the form:
    *   **App name:** Give it a name (e.g., "NVDA Controller").
    *   **App description:** A short description is fine.
    *   **Redirect URI:** **This is the most important step.** The addon listens on your local machine for the authentication callback. You must enter this URI exactly: `http://127.0.0.1:8888/callback`
4.  Agree to the terms and click "Save".

### Step 2: Get Your Credentials

1.  On your new app's dashboard, click "Settings".
2.  You will see your **Client ID**. You may need to click "View client secret" to see the **Client Secret**.
3.  Copy both of these long strings of text.

### Step 3: Configure the Addon in NVDA

1.  Open the NVDA menu (`NVDA+N`), go to Preferences, then Settings.
2.  In the categories list, select "Accessify Play".
3.  Paste your **Client ID** and **Client Secret** into the fields.
4.  Review the other settings:
    *   **Callback Port:** Only change this if you have a port conflict and you have also changed it in the Spotify Dashboard.
    *   **Announce track changes automatically:** Check this box if you want NVDA to announce every new song as it begins playing.
5.  Press the **"Validate Credentials"** button. Your web browser will open and ask you to grant permissions. Click "Agree".
6.  If successful, you will see a "Validation successful!" message. If not, carefully re-check all steps, especially the Redirect URI.
7.  Click "OK" to save and close the settings. The addon is now ready to use!

---

## 🙏 Acknowledgements

This project wouldn't be where it is today without the incredible support and dedication of our community. A heartfelt thank you to all the testers who provided invaluable ideas, helped tirelessly with debugging, and offered supportive encouragement throughout the development process. Your contributions have been instrumental in shaping Accessify Play into what it is. Thank you for making this project a success!

---

## ❤️ Support the Developer

If you find this addon useful, please consider supporting its development. Every little bit helps!

*   [**Donate via PayPal**](https://www.paypal.com/paypalme/rafli23115)
*   For alternative donation methods, please contact: [rafli08523717409@gmail.com](mailto:rafli08523717409@gmail.com)