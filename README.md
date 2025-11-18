# Accessify Play
[![Code Quality Linting](https://github.com/InfiArtt/accessify-play/actions/workflows/lint.yml/badge.svg)](https://github.com/InfiArtt/accessify-play/actions/workflows/lint.yml)
[![Latest Release](https://img.shields.io/github/v/release/InfiArtt/accessify-play)](https://github.com/InfiArtt/accessify-play/releases/latest)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://www.gnu.org/licenses/gpl-2.0.html)

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
| Announce Playback Time       | `NVDA+Alt+Shift+T`                   |
| Copy Track URL               | `NVDA+Shift+Alt+C`                   |
| Open Search Dialog           | `NVDA+Shift+Alt+S`                   |
| Play from Link Dialog        | `NVDA+Shift+Alt+P`                   |
| Open Queue List              | `NVDA+Shift+Alt+Q`                   |
| Announce Next in Queue       | `NVDA+Shift+Alt+N`                   |
| Save Track to Library        | `NVDA+Alt+Shift+L`                   |
| Add Track to Playlist        | `NVDA+Alt+Shift+A`                   |
| Open Management Dialog       | `NVDA+Alt+Shift+M`                   |

---

### A Note on the Spotify Queue Feature: Understanding Its Behavior

You may have noticed that the queue list in Accessify Play (`NVDA+Shift+Alt+Q`) can be both incredibly accurate and, at other times, seem completely out of sync with what's playing next. This behavior is not a bug but a direct consequence of the data provided by the Spotify API.

Here is the precise breakdown of when the addon's queue list is reliable and when it is not:

#### When the Queue List is ACCURATE

The queue list displayed by the addon is a correct representation of what Spotify will play next in two key scenarios:

1.  **Playing a Finite Context Sequentially:** When you are playing a playlist or an album with **Shuffle Mode turned OFF**, the addon's queue list will reliably match the "Next Up" list in the Spotify app.
2.  **Manually Added Tracks:** Any song you manually add using "Add to Queue" will always appear correctly at the top of the list.

#### Where the Discrepancy Occurs

The predictability breaks down completely in two very common situations, causing a mismatch between the addon and the Spotify app:

1.  **When Shuffle Mode is ON:** This is the most significant limitation. While the Spotify app knows the special randomized order it has created, the public API used by this addon **does not have access to this shuffled order**. The API will *always* report the playlist's original, saved sequence, completely ignoring the fact that shuffle is active.
2.  **When Autoplay Takes Over:** After your album or playlist finishes, Spotify's "Autoplay" feature begins playing similar tracks. This is an algorithmic radio stream, and the API **provides no information about what songs are coming up** in this stream.

#### The Addon's Design and the API's Definition

To provide a consistent experience, Accessify Play is designed to show exactly what the Spotify API provides. The addon uses the official `/me/player/queue` endpoint. According to the Spotify Developer documentation, this endpoint is designed to:

> Get the list of objects that make up the user's queue.

This means the API's definition of a "queue" is primarily the list of manually added tracks. While the API response also includes the next track from the current context (album/playlist), it cannot provide the full, upcoming sequence for shuffled or algorithmically generated content.

#### Conclusion: How to Use the Queue Feature Effectively

Therefore, the Accessify Play queue feature is your reliable tool for two main purposes:

1.  Viewing the upcoming tracks when you are listening to an **album or playlist with Shuffle turned OFF**.
2.  Viewing and managing the songs you have **manually added to the queue**, regardless of what is playing.

It should not be used as a reference when **Shuffle Mode is ON** or when **Autoplay** has started, as the API does not provide the necessary data for those scenarios.

---

## ⚙️ Configuration Guide

To use this addon, you need to get a **Client ID** and **Client Secret** from the Spotify Developer Dashboard. Follow these steps carefully.

### Step 1: Create a Spotify App

1.  Open the Accessify Play settings in NVDA (NVDA menu -> Preferences -> Settings -> Accessify Play).
2.  Click the **"Go to Developer Dashboard"** button. This will open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) in your web browser. Log in if prompted.
3.  Click the "Create app" button.
4.  Fill out the form:
    * **App name:** Give it a name (e.g., "NVDA Controller").
    * **App description:** A short description is fine.
    * **Redirect URI:** **This is the most important step.** The addon listens on your local machine for the authentication callback. You must enter this URI exactly: `http://127.0.0.1:8888/callback`
        > **Note on Port 8888:** Based on private reports, some users experience validation failures. This can happen if another application on your computer (often a local development server) is already using port `8888`.
        >
        > **Future Update:** To prevent this conflict, the default port for the addon **will be changed to `8539` in a future version.**
5.  You may be asked which API to use. **Please select "Web API"**.
6.  Agree to the terms and click "Save".

### Step 2: Get Your Credentials

1.  On your new app's dashboard, click "Settings".
2.  You will see your **Client ID**.
3.  Copy this long string of text.

### Step 3: Configure the Addon in NVDA

1.  Open the NVDA menu (`NVDA+N`), go to Preferences, then Settings.
2.  In the categories list, select "Accessify Play".
3.  Locate the **"Add Client ID"** (or "Display/Edit Client ID") button. Click it to open a dialog where you can paste your **Client ID**.
4.  Review the other settings:
    * **Callback Port:** Only change this if you have a port conflict and you have also changed it in the Spotify Dashboard. *(See note in Step 1)*.
    * **Announce track changes automatically:** Check this box if you want NVDA to announce every new song as it begins playing.
    * **Language:** Choose the display language for the add-on. This setting allows Accessify Play to use a different language than NVDA's main interface. You can select "Follow NVDA language (default)" or force a specific language like "Bahasa Indonesia".
    * **Update Channel:** Select your preferred update channel.
        * **Stable:** Receive only stable, well-tested updates. These correspond to releases from the `main` branch on GitHub.
        * **Beta:** Receive pre-release versions with the latest features and bug fixes, but potentially less stability. These correspond to releases from the `dev` branch on GitHub.
    * **Check for updates automatically:** If checked, the add-on will silently check for new versions every time NVDA starts. If an update is available, a pop-up window will appear. If unchecked, you will only receive updates when you manually check.
5.  Press the **"Validate Credentials"** button. Your web browser will open and ask you to grant permissions. Click "Agree".
6.  If successful, you will see a "Validation successful!" message. If not, carefully re-check all steps, especially the Redirect URI and your Client ID.
7.  Click "OK" to save and close the settings. The addon is now ready to use!

---

## ✨ Update System

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

## 🔒 Authentication & Migration Update (Version 1.3.0)

With version 1.3.0, Accessify Play has undergone a significant update to its authentication system to enhance security and improve user experience, especially for portable NVDA installations.

*   **Enhanced Security with PKCE:** The addon now utilizes the Proof Key for Code Exchange (PKCE) authentication flow. This modern and more secure method eliminates the need for a `Client Secret`, making your Spotify integration safer.
*   **Portable Client ID Storage:** Your Spotify Client ID is no longer stored within NVDA's configuration files. Instead, it is now saved in a dedicated, portable file located at `%userprofile%/.spotify_client_id.json`. This ensures your Client ID remains intact even if you move or reinstall NVDA, and it's easier to manage.
*   **Simplified Settings:** The 'Client Secret' field has been removed from the Accessify Play settings panel, streamlining the setup process. The 'Client ID' input is now managed via a dynamic button that allows you to easily add, view, or edit your Client ID.
*   **Seamless Migration:** If you are upgrading from an older version of Accessify Play and have your Client ID (or Client Secret) still stored in NVDA's configuration, a new **"Migrate Old Credentials"** button will appear in the Accessify Play settings panel. Clicking this button will automatically:
    1.  Move your existing Client ID to the new portable `%userprofile%/.spotify_client_id.json` file.
    2.  Remove both the old Client ID and the obsolete Client Secret from NVDA's configuration.
    This ensures a smooth transition to the new, more secure system.

---

## 🤔 Why This Authentication Method? (Instead of a Simple Login Button)

You might be wondering why Accessify Play requires you to create your own Spotify application and input a Client ID, instead of offering a simple "Login to Spotify" button like many other apps (e.g., Alexa, Google Home, etc.). The answer lies in Spotify's API policies and the challenges faced by independent developers.

To provide a seamless "Login to Spotify" experience without requiring users to become "mini-developers," an application needs to apply for and be granted an **Extended Quota** from Spotify. The requirements for obtaining such an extended quota are quite extraordinary and often include:

*   **Significant User Base:** Demonstrating a large and active user base.
*   **Business Model:** A clear and sustainable business model.
*   **Legal & Security Reviews:** Extensive legal and security reviews by Spotify.
*   **Brand Alignment:** Strong alignment with Spotify's brand and strategic goals.

For a small, independent, and open-source accessibility addon like Accessify Play, meeting these stringent requirements is **almost impossible**. The resources, legal overhead, and user base needed are far beyond what this project can realistically achieve.

Therefore, the current method, while requiring a few extra steps from the user, is a necessary workaround. It allows Accessify Play to function and provide its valuable accessibility features by leveraging Spotify's standard developer access, without needing to meet the prohibitive criteria for extended quotas. This approach empowers you, the user, to directly control your Spotify API access, ensuring the addon remains functional and accessible.


## 🙏 Acknowledgements

This project wouldn't be where it is today without the incredible support and dedication of our community. A heartfelt thank you to all the testers who provided invaluable ideas, helped tirelessly with debugging, and offered supportive encouragement throughout the development process. Your contributions have been instrumental in shaping Accessify Play into what it is. Thank you for making this project a success!

---

## ❤️ Support the Developer

If you find this addon useful, please consider supporting its development. Every little bit helps!

* [**Donate via PayPal**](https://www.paypal.com/paypalme/rafli23115)
* For alternative donation methods, please contact: [rafli08523717409@gmail.com](mailto:rafli08523717409@gmail.com)