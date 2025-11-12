# Changelog

## Version 1.3.1

This is a major release focusing on security, usability, and new features, representing the most significant update to the addon yet.

#### ✨ New Features

- **Automatic & Manual Updater**: The addon can now check for updates directly from GitHub. Enable automatic checks on NVDA startup or trigger them manually from the settings panel, with support for `Stable` and `Beta` release channels.
- **Announce Playback Time**: A new command (`NVDA+Alt+Shift+T`) announces the current track's progress and total duration (e.g., "1min 23sec out of 3min 45sec").
- **Advanced Queue Management**: The Queue dialog now features a context menu with `Play`, `Copy Link`, and `Remove` actions. Removing an item rebuilds Spotify's playback queue, giving you direct control over upcoming tracks.
- **Flexible Language Options**: You can now have the addon follow NVDA's language or override it with a specific language (e.g., keep the addon in English even if NVDA is set to another locale).
- **Seamless Credential Migration**: A "Migrate Old Credentials" button now appears in settings if legacy `Client ID` or `Client Secret` data is found, allowing for a one-click migration to the new, more secure storage system.
- **Quick Developer Access**: A "Go to Developer Dashboard" button has been added to the settings panel for easy access to manage your Spotify Client ID.

#### 🔐 Security Enhancements

- **Modernized PKCE Authentication**: The addon now uses Spotify's more secure **Proof Key for Code Exchange (PKCE)** authentication flow. This significantly enhances security and **removes the need for a `Client Secret`**, simplifying the setup process.

#### 🚀 Improvements

- **Enhanced User Interface & Experience**:
  - **Context Menus Everywhere**: All lists (Search Results, Saved Tracks, Queue, etc.) now feature context menus for quick access to actions like `Play`, `Add to Queue`, `Copy Link`, and more, creating a cleaner and more powerful UI.
  - **Smarter Focus Handling**: When using "Load More" in the Search dialog, focus is now intelligently moved to the first new result, enabling a seamless browsing experience without losing your place.
  - **Responsive Data Loading**: Dialogs that rely on Spotify data (like Management and Queue) now preload content *before* appearing, providing a faster and more fluid user experience.
- **Reliable Playback Commands**: All playback-related shortcuts (Play/Pause, Next/Previous, Volume, etc.) are now more stable. The addon prevents overlapping commands; if a shortcut is pressed while another is processing, a "Please wait..." message is announced, ensuring each action completes successfully.
- **Full Internationalization Support**: The translation system has been standardized, ensuring that all text is translatable and that non-English locales (including Bahasa Indonesia) load correctly.

#### 🛠️ Fixes

- **Podcast & Show Information Now Works**: Fixed a critical issue where information for currently playing podcasts or shows could not be retrieved. The addon can now correctly identify and announce details for both music tracks and podcast episodes.
- **Search Dialog Stability**: Resolved a crash that could occur if Spotify's search results contained invalid or empty data.
- **Dialog Management**: Ensured all dialogs are properly destroyed when closed, so reopening them always presents fresh data.

## Version 1.2.0

- New Feature: Set Specific Volume: Added a dialog to set the Spotify volume to a precise percentage (0-100) using the shortcut NVDA+Shift+Alt+V.
- New Feature: Comprehensive Library Management: Introduced a new multi-tabbed "Management" dialog (NVDA+Alt+Shift+M) for full control over your Spotify library.
    - Manage Playlists: View tracks within your playlists, update playlist details, delete playlists, and remove tracks from a playlist.
    - Create Playlist: A new tab to create new public or private playlists with a description.
    - Saved Tracks: View all your "Liked Songs" and remove them directly from the list.
    - Followed Artists: View all followed artists with options to play, unfollow, or view their discography.
    - Top Items: Discover your top-played tracks and artists over different time periods (4 weeks, 6 months, all time).
    - Saved Shows: View your saved podcasts and browse their episodes.
    - New Releases: Browse the latest album and single releases on Spotify.
- New Feature: Quick Save to Library: Added a command to quickly save the currently playing track to your "Liked Songs" (NVDA+Alt+Shift+L).
- New Feature: Quick Add to Playlist: Added a command to add the currently playing track to one of your playlists via a selection dialog (NVDA+Alt+Shift+A).
- New Feature: Automatic Track Announcements: Added an optional setting to have NVDA automatically announce the new track whenever the song changes.
- New Feature: Artist and Podcast Discovery:
    - Added an Artist Discography dialog to view top tracks and albums.
    - Added a Podcast Episodes dialog to browse all episodes of a show.
- New Feature: Language Selection: Added an option in the settings to change the add-on's language (English or Bahasa Indonesia, though it is not working right now).
- Fix: Corrected a critical indentation error in spotify_client.py that prevented several API calls (like getting artist albums and related artists) from working.
- Fix (Accessibility): Ensured labels for checkboxes in the Settings and Create Playlist panels are integrated directly into the control, making them readable by NVDA.

## Version 1.0.1

- New Feature: Added a command to announce the next track in the Spotify queue (NVDA+Shift+Alt+N).
- New Feature: Implemented a dialog to show the full Spotify queue, allowing users to view and play selected items (NVDA+Shift+Alt+Q).
- New Feature: Added commands to seek forward (Control+Alt+NVDA+RightArrow) and backward (Control+Alt+NVDA+LeftArrow) in the current track.
- Improvement: The seek forward/backward duration is now configurable via the Accessify Play settings (default 15 seconds).
- New Feature: Added a "Clear Credentials" button in the Accessify Play settings panel, allowing users to clear their Spotify API credentials and delete the token cache with a confirmation prompt.
- Improvement: Changed the storage location of spotify_token_cache.json to %USERPROFILE%\.spotify_cache.json for enhanced portability and security, separating it from NVDA's configuration.
- Fix: Resolved sys.sys.path typo in __init__.py that prevented the addon from loading correctly.
- Fix: Corrected AttributeError: 'Spotify' object has no attribute 'current_user_queue' by using the proper spotipy.client.queue method.
- Fix: Addressed SyntaxError in spotify_client.py caused by a corrupted replace operation during development.

## Version 1.0.0

- New Feature: Added a dialog to play a track from a shared Spotify URL (NVDA+Shift+Alt+P).
- New Feature: Added a command to copy the current track's Spotify URL to the clipboard (NVDA+Shift+Alt+C).
- New Feature: Added an enhanced search dialog (NVDA+Shift+Alt+S) with filtering by type (song, album, etc.) and a "Load More" option for results.
- New Feature: Added a command to announce the currently playing song, artist, and album (NVDA+Shift+Alt+I).
- Improvement: Added settings to configure the callback port and the search result limit.
- Improvement: The search dialog now displays the owner's name for playlist results.
- Improvement: The addon now automatically re-authenticates when NVDA restarts if it has been validated once, removing the need to re-validate every session.
- Improvement: Added a "Validate Credentials" button in the settings panel for immediate feedback on the configuration.
- Fix: Corrected addon structure to prevent load errors and ensure third-party libraries are imported correctly.
- Fix: Improved error messages to better guide users when their Spotify Developer App is misconfigured.
