Accessify Play
==============

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
*   NVDA version **2025.1** or later.

## A Note on Lyrics

This addon does not, and will not, include a feature to display song lyrics. Most methods for obtaining lyrics, such as scraping websites, are done without a proper license from the copyright holders. This is an illegal practice that violates the terms of service of lyrics providers and may infringe on copyright law, potentially leading to legal consequences under regulations like the DMCA (Digital Millennium Copyright Act) in the United States and similar laws worldwide. To ensure this addon remains legal, distributable, and respectful of copyright, this feature is intentionally omitted.

## License

This addon is licensed under the [GNU General Public License v2.0](https://www.gnu.org/licenses/gpl-2.0.html).

## ✨ Feature Universe

Accessify Play is packed with features for playback, library management, and discovery.

[Read more about features in features.html](features.html)

## ⌨️ Keyboard Commands

Accessify Play uses a powerful **Command Layer** system. Press `NVDA+G` to enter this layer, then press single keys to perform actions.

See the full list of commands in [keybindings.html](keybindings.html)

## ⚙️ Configuration Guide

To use this addon, you need to get a **Client ID** and **Client Secret** from the Spotify Developer Dashboard.

[Read the full configuration guide in configuration.html](configuration.html)

## 🔒 Authentication & Migration (Version 1.3.0)

Since version 1.3.0, Accessify Play uses the more secure PKCE authentication.

[Read about authentication and migration in authentication.html](authentication.html)

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

## 🙏 Acknowledgements

This project wouldn't be where it is today without the incredible support and dedication of our community. A heartfelt thank you to all the testers who provided invaluable ideas, helped tirelessly with debugging, and offered supportive encouragement throughout the development process. Your contributions have been instrumental in shaping Accessify Play into what it is. Thank you for making this project a success!

---

## ❤️ Support the Developer

If you find this addon useful, please consider supporting its development. Every little bit helps!

* [**Donate via PayPal**](https://www.paypal.com/paypalme/rafli23115)
* For alternative donation methods, please contact: [rafli08523717409@gmail.com](mailto:rafli08523717409@gmail.com)
